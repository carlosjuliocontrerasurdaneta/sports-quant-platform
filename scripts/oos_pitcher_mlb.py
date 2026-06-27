#!/usr/bin/env python
"""Out-of-sample test: does enabling the MLB starting-pitcher adjustment improve
realized ROI?

Background: production holds `pitcher_bound: 0.0` for MLB (the v1 RA starter
signal was rejected OOS, KI-006). A v2 per-start FIP signal exists in the
adapter but is inert at bound 0. This script freezes everything else at the
production MLB config and sweeps ONLY the pitcher signal/bound, scoring realized
ROI on a held-out test window (games on/after the cutoff; earlier games still
feed the walk-forward ratings).

It reports, per config: matched events, bets, graded, realized ROI overall and
by market. It also reports how many results carried a per-start FIP, so a flat
FIP result can be told apart from "no FIP data" (run scripts/backfill_starter_fip.py
first if the attach count is ~0).

  python scripts/oos_pitcher_mlb.py
  python scripts/oos_pitcher_mlb.py --test-frac 0.30
  python scripts/oos_pitcher_mlb.py --test-start 2026-05-01 --bounds 0.20 0.35

Single pre-game snapshot proxy for closing odds, limited coverage; a backtest,
never a profit guarantee. Realized ROI here is uncalibrated (the live run also
calibrates per (league, market)).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.backtesting.roi_engine import load_closing_odds, realized_roi_backtest
from sqp.config import ROOT, Settings
from sqp.logging_config import get_logger
from sqp.pipeline.daily import _league_meta
from sqp.storage.results_store import ResultsStore
from sqp.storage.starter_fip import StarterFIPStore
from sqp.storage.starters import StartersStore

log = get_logger("sqp.oos_pitcher")
LEAGUE = "mlb"


def _cutoff(results: list[dict], test_frac: float, test_start: str | None) -> str:
    if test_start:
        return test_start
    i = max(0, min(len(results) - 1, int(len(results) * (1.0 - test_frac))))
    return str(results[i].get("date", ""))[:10]


def _run(label: str, results, odds, base_params: dict, overrides: dict,
         settings: Settings, warmup: int, cutoff: str) -> dict:
    params = dict(base_params)
    params.update(overrides)
    res = realized_roi_backtest(results, odds, LEAGUE, "baseball", params,
                                risk=settings.risk, bankroll=settings.bankroll,
                                warmup=warmup, bet_from_date=cutoff)
    print(f"\n--- {label} | {overrides} ---")
    print(f"test events matched: {res['n_events_matched']} | bets: {res['n_bets']}")
    if res["n_bets"]:
        print(f"graded: {res['n_graded']} | staked: {res['staked']} | pnl: {res['pnl']} | "
              f"REALIZED ROI (test): {res['realized_roi']:.2%} | "
              f"mean est. edge: {res['mean_estimated_edge']:.4f}")
        print(res["by_market"].to_string(index=False))
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-frac", type=float, default=0.30,
                    help="Most-recent fraction of the timeline used as the test window")
    ap.add_argument("--test-start", default=None,
                    help="Explicit cutoff date YYYY-MM-DD (overrides --test-frac)")
    ap.add_argument("--warmup", type=int, default=60)
    ap.add_argument("--bounds", type=float, nargs="*", default=[0.20, 0.35],
                    help="pitcher_bound values to test for each signal")
    args = ap.parse_args()
    settings = Settings.load()

    results = ResultsStore(ROOT).load(LEAGUE)
    if not results:
        log.error("No MLB results stored; run scripts/backfill_results.py first.")
        return 1
    names_attached = StartersStore(ROOT).attach(LEAGUE, results)
    fip_attached = StarterFIPStore(ROOT).attach(LEAGUE, results)

    odds = load_closing_odds(ROOT, LEAGUE)
    if not odds:
        log.error("No captured MLB odds; run backfill_historical_odds.py first.")
        return 1

    cutoff = _cutoff(results, args.test_frac, args.test_start)
    train = [r for r in results if str(r.get("date", ""))[:10] < cutoff]
    base_params = dict(_league_meta(LEAGUE).get("league_params") or {})

    print("========== MLB pitcher-bound OOS test ==========")
    print(f"cutoff: {cutoff} | train games: {len(train)} | test games: "
          f"{len(results) - len(train)} | odds events: {len(odds)}")
    print(f"starter NAMES attached: {names_attached}/{len(results)} | "
          f"per-start FIP attached: {fip_attached}/{len(results)}")
    if fip_attached == 0:
        print("WARNING: 0 FIP rows attached -> the 'fip' configs below are inert "
              "(no v2 data). Run scripts/backfill_starter_fip.py to populate "
              "data/historical/starter_fip_mlb.csv, then re-run.")
    print(f"base MLB params (frozen, pitcher overridden below): {base_params}")

    # Baseline = production (pitcher off). Then RA (v1) and FIP (v2) at each bound.
    _run("baseline (pitcher OFF, production)", results, odds, base_params,
         {"pitcher_bound": 0.0}, settings, args.warmup, cutoff)
    for b in args.bounds:
        _run(f"ra  (v1) bound={b}", results, odds, base_params,
             {"pitcher_signal": "ra", "pitcher_bound": b}, settings, args.warmup, cutoff)
    for b in args.bounds:
        _run(f"fip (v2) bound={b}", results, odds, base_params,
             {"pitcher_signal": "fip", "pitcher_bound": b}, settings, args.warmup, cutoff)

    print("\nOut-of-sample realized ROI over a single pre-game snapshot proxy; "
          "limited coverage; a backtest, never a profit guarantee. Realized ROI "
          "is uncalibrated. Decide with edge-vs-realized, not edge alone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
