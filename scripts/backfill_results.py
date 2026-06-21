#!/usr/bin/env python
"""Backfill full-season historical results into data/historical/ (KI-001).

Examples:
  python scripts/backfill_results.py --leagues nba wnba ligamx --days 365
  python scripts/backfill_results.py --leagues mlb --days 200

MLB uses the public MLB Stats API; every other supported league uses the
public ESPN scoreboard API (see ESPN_PATHS). The store is append-only with
(date, home, away) dedup, so re-running is safe and incremental.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.config import ROOT
from sqp.logging_config import get_logger
from sqp.providers.espn_results import ESPNResultsProvider, ESPN_PATHS
from sqp.providers.mlb_statsapi import MLBStatsProvider
from sqp.storage.results_store import ResultsStore

log = get_logger("sqp.backfill")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", nargs="+", required=True,
                    help=f"Supported: {', '.join(sorted(ESPN_PATHS))}")
    ap.add_argument("--days", type=int, default=365, help="Days back to fetch (default 365)")
    args = ap.parse_args()

    store = ResultsStore(ROOT)
    espn = ESPNResultsProvider()
    failures = 0
    for league in args.leagues:
        try:
            provider = MLBStatsProvider() if league == "mlb" else espn
            results = provider.fetch_results(league, days_back=args.days)
            added = store.upsert(league, results)
            log.info("[%s] fetched %d completed results (%d days back); %d new rows -> %s",
                     league, len(results), args.days, added, store.path(league))
            if not results:
                log.warning("[%s] provider returned 0 results. Check the league path "
                            "and whether the league played in the requested window.", league)
        except Exception as exc:
            failures += 1
            log.error("[%s] backfill failed: %s", league, exc)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
