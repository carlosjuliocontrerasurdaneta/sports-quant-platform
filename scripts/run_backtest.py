#!/usr/bin/env python
"""Walk-forward calibration backtest.

Demo: python scripts/run_backtest.py --league nba --mode demo
Live: provide --results-csv with columns date,home,away,home_score,away_score
"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pandas as pd
from sqp.backtesting.engine import walk_forward_backtest
from sqp.audit.report import calibration_report
from sqp.pipeline.daily import _league_meta
from sqp.providers.synthetic import SyntheticProvider


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", required=True)
    ap.add_argument("--mode", choices=["demo", "live"], default="demo")
    ap.add_argument("--results-csv", default=None)
    args = ap.parse_args()
    meta = _league_meta(args.league)
    if args.mode == "demo":
        results = SyntheticProvider(meta["family"]).fetch_results(args.league)
        for r in results:
            r["data_label"] = "demo_synthetic"
    else:
        if not args.results_csv:
            raise SystemExit("Live backtest requires --results-csv (no data is invented).")
        results = pd.read_csv(args.results_csv).to_dict("records")
    res = walk_forward_backtest(results, args.league, meta["family"], meta.get("league_params"))
    path = calibration_report(res)
    print(f"Brier={res['brier_score']:.4f}  LogLoss={res['log_loss']:.4f}  ECE={res['ece']:.4f}")
    print(f"Report: {path}")


if __name__ == "__main__":
    main()
