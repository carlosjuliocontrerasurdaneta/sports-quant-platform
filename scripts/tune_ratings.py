#!/usr/bin/env python
"""Tune per-league Elo home advantage by walk-forward grid search over the
stored history, and optionally persist it to configs/leagues/ratings.yaml.

Examples:
  python scripts/tune_ratings.py --leagues nba wnba ligamx
  python scripts/tune_ratings.py --leagues nba wnba ligamx --write
"""
import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.backtesting.tuning import (DEFAULT_DC_RHO_GRID, DEFAULT_HOLDOUT_SPLITS,
                                    DEFAULT_HOME_ADV_GRID, tune_dc_rho,
                                    tune_home_advantage)
from sqp.config import CONFIG_DIR, ROOT, load_yaml
from sqp.logging_config import get_logger
from sqp.pipeline.daily import _league_meta
from sqp.sports.registry import FAMILY_PARAMS
from sqp.storage.results_store import ResultsStore
from sqp.storage.starters import StartersStore

TUNABLE_KEYS = ("elo_home_adv", "dc_rho")  # keys this script manages on --write

log = get_logger("sqp.tune")

RATINGS_PATH = CONFIG_DIR / "leagues" / "ratings.yaml"
HEADER = ("# Per-league rating overrides estimated by scripts/tune_ratings.py\n"
          "# (walk-forward grid search on data/historical/, accepted only when they\n"
          "# beat the family default OUT-OF-SAMPLE under a rolling-origin holdout).\n"
          "# Re-validate on new games and re-tune after season changes.\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", nargs="+", required=True)
    ap.add_argument("--warmup", type=int, default=60)
    ap.add_argument("--write", action="store_true",
                    help="Persist best values to configs/leagues/ratings.yaml")
    ap.add_argument("--ha-grid", nargs="+", type=float, default=None,
                    help="Custom elo_home_adv grid (e.g. --ha-grid 150 200 250 300)")
    ap.add_argument("--rho-grid", nargs="+", type=float, default=None,
                    help="Custom dc_rho grid for three-way leagues")
    ap.add_argument("--holdout-splits", type=int, default=DEFAULT_HOLDOUT_SPLITS,
                    help="Rolling-origin holdout blocks for out-of-sample selection "
                         "(0 = legacy in-sample gating). Default %(default)s.")
    args = ap.parse_args()

    store = ResultsStore(ROOT)
    tuned: dict[str, dict] = {}
    failures = 0
    for league in args.leagues:
        results = store.load(league)
        if len(results) <= args.warmup:
            log.warning("[%s] only %d stored results (<= warmup %d); skipping.",
                        league, len(results), args.warmup)
            failures += 1
            continue
        meta = _league_meta(league)
        if meta["family"] == "baseball":
            StartersStore(ROOT).attach(league, results)
        base_params = dict(meta.get("league_params") or {})
        base_params.pop("elo_home_adv", None)  # tune from scratch, not from a prior override
        base_params.pop("dc_rho", None)
        default_ha = float(FAMILY_PARAMS[meta["family"]].get("elo_home_adv", 60.0))
        ha_grid = tuple(args.ha_grid) if args.ha_grid else DEFAULT_HOME_ADV_GRID
        res = tune_home_advantage(results, league, meta["family"], base_params,
                                  grid=ha_grid, warmup=args.warmup, default_home_adv=default_ha,
                                  n_splits=args.holdout_splits)
        league_tuned: dict[str, float] = {}
        print(f"\n=== {league.upper()} ===")
        print(res["table"].round(4).to_string(index=False))
        print(f"elo_home_adv: best {res['best_home_adv']:.0f} (log_loss {res['best_log_loss']:.4f}) "
              f"vs default {default_ha:.0f} (log_loss {res['default_log_loss']:.4f}) "
              f"-> {res['reason']}")
        if res["accepted"]:
            league_tuned["elo_home_adv"] = res["recommended_home_adv"]
        # de-vig of the draw shape is tuned at the home-adv we'd actually deploy.
        base_params["elo_home_adv"] = res["recommended_home_adv"]
        if meta.get("three_way", False):
            rho_grid = tuple(args.rho_grid) if args.rho_grid else DEFAULT_DC_RHO_GRID
            dc = tune_dc_rho(results, league, meta["family"], base_params,
                             grid=rho_grid, warmup=args.warmup, n_splits=args.holdout_splits)
            print(dc["table"].round(4).to_string(index=False))
            print(f"dc_rho: best {dc['best_dc_rho']:.2f} "
                  f"(log_loss_threeway {dc['best_log_loss_threeway']:.4f}, "
                  f"{dc['n_draws']} draws) -> {dc['reason']}")
            if dc["accepted"]:
                league_tuned["dc_rho"] = dc["recommended_dc_rho"]
        tuned[league] = league_tuned  # may be empty: "evaluated, no override survives"
        if not league_tuned:
            print(f"[{league}] no override met the gates; family defaults will be used.")

    if args.write and tuned:
        existing = (load_yaml(RATINGS_PATH).get("leagues") or {}) if RATINGS_PATH.exists() else {}
        # Authoritative only for the leagues actually tuned this run: set accepted
        # values and drop rejected tunable keys (reverting them to family default),
        # while preserving any non-tunable keys (e.g. MLB pitcher params).
        for league, params in tuned.items():
            entry = {k: v for k, v in (existing.get(league) or {}).items()
                     if k not in TUNABLE_KEYS}
            entry.update(params)
            if entry:
                existing[league] = entry
            else:
                existing.pop(league, None)
        RATINGS_PATH.write_text(HEADER + yaml.safe_dump({"leagues": existing}, sort_keys=True),
                                encoding="utf-8")
        log.info("Wrote ratings overrides for %d tuned league(s) to %s "
                 "(rejected tunable keys reverted to family default).",
                 len(tuned), RATINGS_PATH)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
