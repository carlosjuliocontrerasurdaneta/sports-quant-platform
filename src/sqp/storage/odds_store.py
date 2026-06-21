"""Daily odds snapshots (data/odds/odds_{league}_{YYYYMM}.csv).

Append-only: every live run adds one timestamped snapshot of all quoted
lines. Closing odds are reconstructed downstream as the last snapshot
strictly before each event's commence_time. This is the forward-looking,
out-of-sample dataset for realized-ROI and CLV validation (plan block A).
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from sqp.domain.models import EventOdds

COLUMNS = ["captured_at", "event_id", "commence_time", "home", "away",
           "market", "outcome", "point", "price_decimal", "bookmaker"]


class OddsStore:
    def __init__(self, root: Path):
        self.dir = root / "data" / "odds"

    def path(self, league: str, month: str) -> Path:
        return self.dir / f"odds_{league}_{month}.csv"

    def append_snapshot(self, league: str, events: list[EventOdds],
                        captured_at: str | None = None) -> int:
        """Persist one snapshot of all lines for the given events. Returns
        the number of rows written. ``captured_at`` defaults to now (live runs);
        pass the snapshot's real timestamp when backfilling historical odds."""
        captured_at = captured_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
        rows = [{"captured_at": captured_at, "event_id": eo.event.event_id,
                 "commence_time": eo.event.start_time, "home": eo.event.home,
                 "away": eo.event.away, "market": ln.market, "outcome": ln.outcome,
                 "point": ln.point, "price_decimal": ln.price_decimal,
                 "bookmaker": ln.bookmaker}
                for eo in events for ln in eo.lines]
        if not rows:
            return 0
        df = pd.DataFrame(rows)[COLUMNS]
        p = self.path(league, captured_at[:7].replace("-", ""))
        self.dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(p, mode="a", header=not p.exists(), index=False)
        return len(df)
