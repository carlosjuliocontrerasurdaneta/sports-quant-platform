#!/usr/bin/env python
"""Walk-forward backtest over the stored results history (data/historical/).

Examples:
  python scripts/backtest_history.py --leagues nba wnba ligamx
  python scripts/backtest_history.py --leagues nba --warmup 100

Calibration-only: realized ROI requires real historical odds. The home-rate
baseline is computed in-sample over the evaluated games (reference, not a
deployable model).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.backtesting.engine import walk_forward_backtest
from sqp.config import ROOT
from sqp.logging_config import get_logger
from sqp.pipeline.daily import _league_meta
from sqp.storage.results_store import ResultsStore
from sqp.storage.starters import StartersStore

log = get_logger("sqp.backtest")

DISCLAIMER = ("Calibration-only backtest over estimated probabilities. No realized "
              "ROI without real historical odds; never infer profitability from "
              "calibration alone.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", nargs="+", required=True)
    ap.add_argument("--warmup", type=int, default=60,
                    help="Games used only to seed ratings before evaluation (default 60)")
    args = ap.parse_args()

    store = ResultsStore(ROOT)
    failures = 0
    for league in args.leagues:
        results = store.load(league)
        if len(results) <= args.warmup:
            log.warning("[%s] only %d stored results (<= warmup %d); run "
                        "scripts/backfill_results.py first.", league, len(results), args.warmup)
            failures += 1
            continue
        meta = _league_meta(league)
        if meta["family"] == "baseball":
            attached = StartersStore(ROOT).attach(league, results)
            print(f"[{league}] starter map attached to {attached}/{len(results)} results")
        res = walk_forward_backtest(results, league, meta["family"],
                                    meta.get("league_params"), warmup=args.warmup)
        n = res["n_games_evaluated"]
        outcomes = [1.0 if r["home_score"] > r["away_score"] else
                    (0.5 if r["home_score"] == r["away_score"] else 0.0)
                    for r in results[args.warmup:]]
        binary = [o for o in outcomes if o in (0.0, 1.0)]
        home_rate = sum(binary) / len(binary) if binary else float("nan")
        baseline_brier = sum((home_rate - y) ** 2 for y in binary) / len(binary) if binary else float("nan")

        print(f"\n=== {league.upper()} (walk-forward, {len(results)} results, warmup {args.warmup}) ===")
        print(f"games evaluated (sin empates): {n} | empates excluidos: {len(outcomes) - len(binary)}")
        print(f"brier_score: {res['brier_score']:.4f}  (baseline tasa-local in-sample: {baseline_brier:.4f})")
        print(f"log_loss:    {res['log_loss']:.4f}")
        print(f"ece:         {res['ece']:.4f}")
        if res["observed_draw_rate"] is not None:
            print(f"draw: estimated {res['mean_estimated_draw_probability']:.4f} "
                  f"vs observed {res['observed_draw_rate']:.4f}")
            print(f"log_loss_threeway (1X2): {res['log_loss_threeway']:.4f}")
        print("reliability table (estimated probability vs observed frequency):")
        print(res["reliability_table"].round(4).to_string(index=False))
    print(f"\n{DISCLAIMER}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
