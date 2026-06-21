#!/usr/bin/env python
"""Train ML moneyline + totals models for the supported leagues (mlb/nba/nfl/nhl).

Builds (or reuses) the feature dataset, then trains with temporal CV and persists
to data/models/. With --oos it also prints out-of-sample calibration — the
evidence used to decide whether/how much to blend ML with the simulation model.

Examples:
  python scripts/train_models.py
  python scripts/train_models.py --leagues nba mlb --oos
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.logging_config import get_logger
from sqp.models.ml_train import oos_moneyline_metrics, train_moneyline, train_totals
from sqp.storage.feature_store import SUPPORTED, build_training_dataset

log = get_logger("sqp.train_models")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", nargs="+", default=sorted(SUPPORTED), choices=sorted(SUPPORTED))
    ap.add_argument("--oos", action="store_true", help="report OOS calibration (evidence gate)")
    args = ap.parse_args()

    failures = 0
    for lg in args.leagues:
        try:
            df = build_training_dataset(lg)
            ml = train_moneyline(df, lg)
            tot = train_totals(df, lg)
            print(f"[OK] {lg}: moneyline CV ROC-AUC={ml['metrics']['cv_roc_auc_mean']:.3f} "
                  f"| totals CV MAE={tot['metrics']['cv_mae_mean']:.3f} (n={ml['metrics']['n_train']})")
            if args.oos:
                m = oos_moneyline_metrics(df, lg)
                print(f"     OOS moneyline: Brier={m['brier_score']:.4f} "
                      f"logloss={m['log_loss']:.4f} ECE={m['ece']:.4f} (n={m['n_samples']})")
        except Exception as exc:
            failures += 1
            print(f"[SKIP] {lg}: {exc}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
