#!/usr/bin/env python
"""Settle candidate bets for ONE league using The Odds API /scores (live mode).
Idempotent. For all leagues at once, use scripts/settle_all.py."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.config import Settings
from sqp.settlement.runner import fetch_and_settle, realized_roi


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", required=True)
    ap.add_argument("--days-from", type=int, default=2)
    args = ap.parse_args()
    settings = Settings.load()
    settled = fetch_and_settle(args.league, settings, days_from=args.days_from)
    if settled.empty:
        print("No new completed events matched pending candidates.")
    else:
        print(f"Settled {len(settled)} new bets. "
              f"Realized ROI this batch: {realized_roi(settled):.2%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
