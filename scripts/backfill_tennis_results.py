#!/usr/bin/env python
"""Backfill tour-wide ESPN tennis results (atp/wta) into data/historical/.

Tennis ratings are per-PLAYER and TOUR-WIDE, so results persist under the tour
key (results_atp.csv / results_wta.csv), NOT per tournament. They feed the
realized-ROI OOS backtest: the per-tournament odds captured in data/odds/ are
matched against the tour results order-insensitively (players have no home/away).

Append-only, deduped by (date, home, away, game_id); home == winner (score 1-0).
Unofficial ESPN endpoint -> the provider reports per-tour counts to surface
silent breakage.

  python scripts/backfill_tennis_results.py --tours atp wta --days 365
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.config import ROOT
from sqp.logging_config import get_logger
from sqp.providers.espn_tennis import ESPNTennisResultsProvider
from sqp.storage.results_store import ResultsStore

log = get_logger("sqp.backfill_tennis")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tours", nargs="+", default=["atp", "wta"], choices=["atp", "wta"])
    ap.add_argument("--days", type=int, default=365, help="Days back to fetch (default 365)")
    args = ap.parse_args()

    store = ResultsStore(ROOT)
    provider = ESPNTennisResultsProvider()
    failures = 0
    for tour in args.tours:
        try:
            results = provider.fetch_results(tour, days_back=args.days)
            added = store.upsert(tour, results)
            log.info("[tennis/%s] fetched %d singles results (%d days back); %d new rows -> %s",
                     tour, len(results), args.days, added, store.path(tour))
            if not results:
                log.warning("[tennis/%s] provider returned 0 results (schema change or "
                            "off-window?).", tour)
        except Exception as exc:
            failures += 1
            log.error("[tennis/%s] backfill failed: %s", tour, exc)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
