#!/usr/bin/env python
"""Backfill historical odds snapshots from The Odds API (paid /historical).

Builds the dataset needed for REALIZED-ROI backtesting (the forward odds store
only grows from today). Historical calls cost ~10x a live call
(10 x markets x regions per snapshot), so this is strictly budget-metered: it
reads the real per-call cost from the response header and stops before the
credit budget is exhausted. One daily snapshot per league at a fixed UTC hour;
downstream matching uses the last snapshot strictly before each commence_time,
so games earlier than the snapshot hour simply go unmatched (no lookahead).

Examples:
  python scripts/backfill_historical_odds.py --leagues mlb wnba --days 180 --budget 3000
  python scripts/backfill_historical_odds.py --leagues mlb --days 30 --dry-run
"""
import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.config import CONFIG_DIR, ROOT, Settings, load_yaml
from sqp.logging_config import get_logger
from sqp.providers.odds_api import SPORT_KEYS, OddsAPIClient
from sqp.storage.odds_store import OddsStore

log = get_logger("sqp.hist_odds")


def _captured_dates(league: str) -> set[str]:
    """Snapshot dates (YYYY-MM-DD) already stored for the league, so re-runs skip
    them instead of re-paying for the same window."""
    days: set[str] = set()
    for f in sorted((ROOT / "data" / "odds").glob(f"odds_{league}_*.csv")):
        try:
            col = pd.read_csv(f, usecols=["captured_at"])["captured_at"].astype(str)
            days.update(col.str[:10].unique())
        except (OSError, ValueError, pd.errors.ParserError) as exc:
            # A corrupt/partial snapshot must be visible: treating its date as
            # uncaptured can trigger another paid API call on the next backfill.
            log.warning("[%s] cannot read captured dates from %s: %s",
                        league, f, exc)
    return days


def _sport_key(league: str) -> str:
    if league in SPORT_KEYS:
        return SPORT_KEYS[league]["sport_key"]
    soccer = load_yaml(CONFIG_DIR / "leagues" / "soccer.yaml").get("leagues", {})
    if league in soccer:
        return soccer[league]["sport_key"]
    raise SystemExit(f"Unknown league '{league}': not in SPORT_KEYS or soccer.yaml.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", nargs="+", required=True)
    ap.add_argument("--days", type=int, default=180, help="Days back to snapshot")
    ap.add_argument("--hour", type=int, default=22, help="UTC hour for the daily snapshot")
    ap.add_argument("--budget", type=int, default=3000, help="Max credits to spend")
    ap.add_argument("--regions", default="us", help="Comma list (cost scales with count)")
    ap.add_argument("--markets", default="h2h,spreads,totals")
    ap.add_argument("--dry-run", action="store_true", help="Estimate cost, make no calls")
    args = ap.parse_args()

    n_markets = len([m for m in args.markets.split(",") if m.strip()])
    n_regions = len([r for r in args.regions.split(",") if r.strip()])
    cost_per_call = 10 * n_markets * n_regions
    sport_keys = {lg: _sport_key(lg) for lg in args.leagues}

    end = datetime.now(timezone.utc).replace(hour=args.hour, minute=0, second=0, microsecond=0)
    dates = [(end - timedelta(days=d)).strftime("%Y-%m-%dT%H:00:00Z") for d in range(args.days)]
    max_calls = args.budget // cost_per_call
    log.info("Plan: %d leagues x %d days = %d possible snapshots; cost/call=%d credits; "
             "budget=%d -> up to %d calls (~%d credits).",
             len(args.leagues), args.days, len(args.leagues) * args.days, cost_per_call,
             args.budget, max_calls, max_calls * cost_per_call)
    if args.dry_run:
        return 0

    settings = Settings.load()
    client = OddsAPIClient(settings.odds_api_key, args.regions, settings.odds_format)
    store = OddsStore(ROOT)
    existing = {lg: _captured_dates(lg) for lg in args.leagues}
    log.info("Already captured: %s", {lg: len(d) for lg, d in existing.items()})
    spent = 0
    snapshots = 0
    rows_total = 0
    skipped = 0
    stop = False
    for date_iso in dates:                       # most recent first
        if stop:
            break
        for league in args.leagues:
            if date_iso[:10] in existing[league]:
                skipped += 1
                continue                         # idempotent: don't re-pay for a stored day
            if spent + cost_per_call > args.budget:
                log.warning("Budget reached (%d/%d credits); stopping.", spent, args.budget)
                stop = True
                break
            try:
                snap = client.fetch_historical_odds(sport_keys[league], date_iso, league, args.markets)
            except Exception as exc:
                log.error("[%s] %s historical fetch failed: %s", league, date_iso, exc)
                spent += cost_per_call          # assume charged; protect the budget
                continue
            spent += client.requests_last or cost_per_call
            n = store.append_snapshot(league, snap["events"], captured_at=snap["timestamp"] or date_iso)
            snapshots += 1
            rows_total += n
            log.info("[%s] %s -> snapshot %s: %d events, %d lines | spent %d/%d (remaining quota %s)",
                     league, date_iso[:10], snap["timestamp"], len(snap["events"]), n,
                     spent, args.budget, client.requests_remaining)
    log.info("DONE: %d snapshots, %d lines, %d credits spent, %d days skipped (already stored). "
             "Quota remaining: %s", snapshots, rows_total, spent, skipped, client.requests_remaining)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
