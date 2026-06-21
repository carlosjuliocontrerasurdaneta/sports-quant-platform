#!/usr/bin/env python
"""Backfill per-start FIP for MLB starters (v2 starter signal).

Pulls one boxscore per completed game from the MLB Stats API (free, but ~2,400
requests for a full season, so this is slow and one-off) and stores each
starter's per-start FIP in data/historical/starter_fip_mlb.csv. Idempotent:
re-running upserts by game_id.

  python scripts/backfill_starter_fip.py --days 365

The daily run attaches this file to historical results; enable the v2 signal by
setting `pitcher_signal: fip` (and a non-zero `pitcher_bound`) for mlb in
configs/leagues/ratings.yaml ONLY after validating it out-of-sample
(scripts/validate_oos.py / a walk-forward backtest).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.config import ROOT
from sqp.logging_config import get_logger
from sqp.providers.mlb_statsapi import MLBStatsProvider
from sqp.storage.starter_fip import StarterFIPStore

log = get_logger("sqp.backfill_fip")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=365, help="Days back to backfill")
    ap.add_argument("--league", default="mlb")
    args = ap.parse_args()

    log.info("[%s] fetching per-start FIP for the last %d days "
             "(one boxscore per game; this is slow)...", args.league, args.days)
    rows = MLBStatsProvider().fetch_starter_fip(days_back=args.days, log=log)
    with_fip = sum(1 for r in rows
                   if r.get("home_starter_fip") is not None
                   or r.get("away_starter_fip") is not None)
    total = StarterFIPStore(ROOT).save(args.league, rows)
    log.info("[%s] %d games fetched (%d with at least one FIP); store now holds %d rows.",
             args.league, len(rows), with_fip, total)
    print(f"FIP backfill: {len(rows)} games, {with_fip} with FIP; store={total} rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
