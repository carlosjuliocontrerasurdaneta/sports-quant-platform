#!/usr/bin/env python
"""Build ML feature datasets from the stored results (nba/nfl/nhl).

Reads data/historical/results_{league}.csv and writes
data/features/{league}_training_dataset.csv. Idempotent: a league whose results
are unchanged is reused unless --force is given.

Examples:
  python scripts/build_features.py                 # all supported leagues
  python scripts/build_features.py --leagues nba nhl --force
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.logging_config import get_logger
from sqp.storage.feature_store import SUPPORTED, build_training_dataset

log = get_logger("sqp.build_features")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", nargs="+", default=sorted(SUPPORTED),
                    choices=sorted(SUPPORTED))
    ap.add_argument("--force", action="store_true", help="Rebuild even if unchanged")
    args = ap.parse_args()

    failures = 0
    for league in args.leagues:
        try:
            df = build_training_dataset(league, force=args.force)
            print(f"[OK] {league}: {len(df)} rows, {len(df.columns)} cols")
        except Exception as exc:
            failures += 1
            print(f"[SKIP] {league}: {exc}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
