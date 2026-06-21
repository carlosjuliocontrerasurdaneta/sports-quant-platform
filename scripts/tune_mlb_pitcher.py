#!/usr/bin/env python
"""Walk-forward tuning of the MLB starter-feature parameters (and tilt_scale).

Stage 1: grid over (pitcher_prior_starts, pitcher_bound), bound=0.0 = feature
off (control). Stage 2: tilt_scale grid at the stage-1 winner. Scored by walk-
forward log loss. In-sample for the stored history: re-validate on new games.

Example:
  python scripts/tune_mlb_pitcher.py [--write]
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.backtesting.engine import walk_forward_backtest
from sqp.config import CONFIG_DIR, ROOT, load_yaml
from sqp.logging_config import get_logger
from sqp.pipeline.daily import _league_meta
from sqp.storage.results_store import ResultsStore
from sqp.storage.starters import StartersStore

log = get_logger("sqp.tune")

RATINGS_PATH = CONFIG_DIR / "leagues" / "ratings.yaml"
PRIORS = (5.0, 10.0, 20.0, 40.0)
BOUNDS = (0.0, 0.10, 0.20, 0.35)
TILTS = (0.4, 0.6, 0.8)


def _run(results: list[dict], base: dict, **over) -> dict:
    params = {**base, **over}
    res = walk_forward_backtest(results, "mlb", "baseball", params)
    return {**over, "log_loss": res["log_loss"], "brier_score": res["brier_score"],
            "ece": res["ece"], "n": res["n_games_evaluated"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    results = ResultsStore(ROOT).load("mlb")
    attached = StartersStore(ROOT).attach("mlb", results)
    print(f"[mlb] starter map attached to {attached}/{len(results)} results")
    base = dict(_league_meta("mlb").get("league_params") or {})

    rows = [_run(results, base, pitcher_prior_starts=p, pitcher_bound=b)
            for p in PRIORS for b in BOUNDS]
    t1 = pd.DataFrame(rows)
    print("\n=== Stage 1: prior x bound (bound 0 = pitcher feature OFF) ===")
    print(t1.round(4).to_string(index=False))
    best1 = t1.loc[t1["log_loss"].idxmin()]

    rows2 = [_run(results, base, pitcher_prior_starts=float(best1["pitcher_prior_starts"]),
                  pitcher_bound=float(best1["pitcher_bound"]), tilt_scale=t)
             for t in TILTS]
    t2 = pd.DataFrame(rows2)
    print("\n=== Stage 2: tilt_scale at stage-1 winner ===")
    print(t2.round(4).to_string(index=False))
    best2 = t2.loc[t2["log_loss"].idxmin()]

    tuned = {"pitcher_prior_starts": float(best1["pitcher_prior_starts"]),
             "pitcher_bound": float(best1["pitcher_bound"]),
             "tilt_scale": float(best2["tilt_scale"])}
    print(f"\nbest: {tuned} (log_loss {best2['log_loss']:.4f}) | In-sample grid "
          "search: re-validate on subsequent games before trusting it.")
    if args.write:
        existing = (load_yaml(RATINGS_PATH).get("leagues") or {}) if RATINGS_PATH.exists() else {}
        existing.setdefault("mlb", {}).update(tuned)
        header = RATINGS_PATH.read_text(encoding="utf-8").split("leagues:")[0] if RATINGS_PATH.exists() else ""
        RATINGS_PATH.write_text(header + yaml.safe_dump({"leagues": existing}, sort_keys=True),
                                encoding="utf-8")
        log.info("Wrote MLB pitcher/tilt params to %s", RATINGS_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
