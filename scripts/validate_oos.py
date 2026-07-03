#!/usr/bin/env python
"""Out-of-sample validation of realized ROI with FROZEN parameters.

The plain realized-ROI backtest (scripts/backtest_roi.py) is optimistic about
PARAMETERS: tilt_scale / elo_home_adv / dc_rho in configs/leagues/ratings.yaml
were grid-searched over the SAME history it then scores, so the result is not
out-of-sample for the parameter selection.

This script splits the timeline at a cutoff date, SELECTS (freezes) parameters
on the TRAIN period only, and measures realized ROI exclusively on the later
TEST period (bet_from_date=cutoff) that the selection never saw. Ratings still
update walk-forward across the whole timeline (leak-free; they only ever see
past games). For contrast it scores the same TEST window under two more configs:

  - full_history : the ratings.yaml values (tuned on everything, incl. test).
  - family_default: no parameter tuning at all.

If frozen_train ROI is far below full_history, the full-history tuning was
optimistic; if frozen_train tracks family_default, the tuning adds little OOS.

  python scripts/validate_oos.py --leagues mlb --test-frac 0.30
  python scripts/validate_oos.py --leagues mlb --test-start 2026-05-01

Single pre-game snapshot proxy for closing odds, limited coverage. This is a
backtest and never a profit guarantee. pitcher_bound is held at 0.0 in every
config (the v1 starter feature was rejected; see KI-006), so only genuinely
tunable parameters are frozen here.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.backtesting.engine import walk_forward_backtest
from sqp.backtesting.roi_engine import (discover_leagues_with_odds,
                                        load_closing_odds, realized_roi_backtest)
from sqp.backtesting.tuning import tune_dc_rho, tune_home_advantage
from sqp.config import ROOT, Settings
from sqp.logging_config import get_logger
from sqp.pipeline.daily import _league_meta
from sqp.sports.registry import FAMILY_PARAMS
from sqp.storage.results_store import ResultsStore
from sqp.storage.starters import StartersStore

log = get_logger("sqp.oos")

TILT_GRID = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
HOME_ADV_GRID = (0.0, 15.0, 30.0, 45.0, 60.0)
TILT_FAMILIES = {"baseball", "hockey", "soccer"}


def _cutoff(results: list[dict], test_frac: float, test_start: str | None) -> str:
    if test_start:
        return test_start
    i = max(0, min(len(results) - 1, int(len(results) * (1.0 - test_frac))))
    return str(results[i].get("date", ""))[:10]


def _tune_tilt(train: list[dict], league: str, family: str, base: dict,
               warmup: int) -> tuple[float, list[tuple[float, float]]]:
    """Grid-search tilt_scale on TRAIN by binary log loss (lower is better)."""
    best_v, best_ll, rows = None, float("inf"), []
    for v in TILT_GRID:
        p = dict(base)
        p["tilt_scale"] = v
        ll = walk_forward_backtest(train, league, family, p, warmup=warmup)["log_loss"]
        rows.append((v, ll))
        if ll == ll and ll < best_ll:  # ll==ll guards against NaN
            best_ll, best_v = ll, v
    return (best_v if best_v is not None else base.get("tilt_scale", 0.5)), rows


def _freeze_on_train(train: list[dict], league: str, family: str, three_way: bool,
                     warmup: int, holdout_splits: int) -> dict:
    """Select parameters using ONLY the train period."""
    base: dict = {}
    if family == "baseball":
        base["pitcher_bound"] = 0.0  # v1 starter feature rejected (KI-006)
    if family in TILT_FAMILIES:
        tilt, _ = _tune_tilt(train, league, family, base, warmup)
        base["tilt_scale"] = tilt
    default_ha = float(FAMILY_PARAMS[family].get("elo_home_adv", 60.0))
    ha = tune_home_advantage(train, league, family, league_params=base,
                             grid=HOME_ADV_GRID, warmup=warmup,
                             default_home_adv=default_ha, n_splits=holdout_splits)
    base["elo_home_adv"] = ha["recommended_home_adv"]
    if three_way:
        rho = tune_dc_rho(train, league, family, league_params=base, warmup=warmup,
                          n_splits=holdout_splits)
        base["dc_rho"] = rho["recommended_dc_rho"]
    return base


def _run(label: str, results, odds, league, family, params, settings, warmup, cutoff):
    res = realized_roi_backtest(results, odds, league, family, params,
                                risk=settings.risk, bankroll=settings.bankroll,
                                warmup=warmup, bet_from_date=cutoff)
    print(f"\n--- {label} | params={params} ---")
    print(f"test events matched: {res['n_events_matched']} | bets: {res['n_bets']}")
    if res["n_bets"]:
        print(f"graded: {res['n_graded']} | staked: {res['staked']} | pnl: {res['pnl']} | "
              f"REALIZED ROI (test): {res['realized_roi']:.2%} | "
              f"mean est. edge: {res['mean_estimated_edge']:.4f}")
        print(res["by_market"].to_string(index=False))
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", nargs="*", default=None,
                    help="Leagues to validate; if omitted, auto-discover every "
                         "league that has captured odds (data/odds/).")
    ap.add_argument("--test-frac", type=float, default=0.30,
                    help="Fraction of the timeline (most recent) used as the test window")
    ap.add_argument("--test-start", default=None, help="Explicit cutoff date YYYY-MM-DD (overrides --test-frac)")
    ap.add_argument("--warmup", type=int, default=60)
    ap.add_argument("--holdout-splits", type=int, default=4)
    args = ap.parse_args()
    settings = Settings.load()
    leagues = args.leagues or discover_leagues_with_odds(ROOT)
    if not leagues:
        log.warning("No leagues with captured odds found in data/odds/; nothing to validate.")
        return 0
    log.info("OOS validation for: %s", ", ".join(leagues))
    failures = 0

    for league in leagues:
        odds = load_closing_odds(ROOT, league)
        if not odds:
            log.warning("[%s] no historical odds captured; run backfill_historical_odds.py.", league)
            failures += 1
            continue
        meta = _league_meta(league)
        family, three_way = meta["family"], meta.get("three_way", False)
        results = ResultsStore(ROOT).load(league)
        if family == "baseball":
            StartersStore(ROOT).attach(league, results)

        cutoff = _cutoff(results, args.test_frac, args.test_start)
        train = [r for r in results if str(r.get("date", ""))[:10] < cutoff]
        n_test = len(results) - len(train)
        print(f"\n========== {league.upper()} OOS validation ==========")
        print(f"cutoff: {cutoff} | train games: {len(train)} | test games: {n_test} | "
              f"odds events: {len(odds)}")
        if len(train) <= args.warmup + 50:
            log.warning("[%s] train period too small (%d games) for reliable tuning; "
                        "results indicative only.", league, len(train))

        frozen = _freeze_on_train(train, league, family, three_way, args.warmup, args.holdout_splits)
        print(f"FROZEN params (selected on train only): {frozen}")

        # Same TEST window under three parameter configs.
        base_default = {"pitcher_bound": 0.0} if family == "baseball" else None
        _run("frozen_train", results, odds, league, family, frozen, settings, args.warmup, cutoff)
        _run("full_history (ratings.yaml; optimistic)", results, odds, league, family,
             meta.get("league_params"), settings, args.warmup, cutoff)
        _run("family_default (no tuning)", results, odds, league, family,
             base_default, settings, args.warmup, cutoff)

    print("\nOut-of-sample realized ROI over a single pre-game snapshot proxy; "
          "limited coverage; a backtest, never a profit guarantee.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
