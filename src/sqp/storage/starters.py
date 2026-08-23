"""Starter map per game (data/historical/starters_{league}.csv), joined to
results by game_id. Unlike results, starter announcements are mutable
(probable -> actual), so re-ingested rows REPLACE older ones for the same
game_id.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from sqp.logging_config import get_logger
from sqp.storage.atomic import atomic_write_csv

log = get_logger("sqp.storage.starters")

COLUMNS = ["game_id", "date", "home_starter", "away_starter", "ingested_at"]

LOG_COLUMNS = [
    "event_id", "game_date", "home", "away",
    "home_pitcher", "away_pitcher", "confirmed_at_utc",
]


def log_pitcher_confirmation(
    root: Path,
    league: str,
    rows: list[dict],
    confirmed_at: datetime | None = None,
) -> int:
    """Append pitcher confirmations for events matched in the daily run.

    Each row must contain: event_id, game_date, home, away,
    home_pitcher, away_pitcher. Rows where both pitchers are None are skipped.
    Only rows whose (event_id, home_pitcher, away_pitcher) triplet is new or
    changed relative to the last logged entry for that event_id are appended —
    this captures pitcher changes while avoiding duplicates on re-runs.

    Returns the number of new rows appended.
    """
    if not rows:
        return 0
    ts = (confirmed_at or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    p = root / "data" / "historical" / f"pitcher_confirmation_log_{league}.csv"
    p.parent.mkdir(parents=True, exist_ok=True)

    new_rows = [
        {
            "event_id": str(r.get("event_id", "")),
            "game_date": str(r.get("game_date", "")),
            "home": str(r.get("home", "")),
            "away": str(r.get("away", "")),
            "home_pitcher": r.get("home_pitcher"),
            "away_pitcher": r.get("away_pitcher"),
            "confirmed_at_utc": ts,
        }
        for r in rows
        if r.get("home_pitcher") or r.get("away_pitcher")
    ]
    if not new_rows:
        return 0

    new_df = pd.DataFrame(new_rows)[LOG_COLUMNS]

    if p.exists():
        existing = pd.read_csv(p, dtype={"event_id": str})
        # Keep only new or changed pitcher assignments per event_id
        last_by_event = (
            existing.sort_values("confirmed_at_utc")
            .drop_duplicates(subset=["event_id"], keep="last")
            .set_index("event_id")
        )
        to_append = []
        for row in new_rows:
            eid = row["event_id"]
            prev = last_by_event.loc[eid] if eid in last_by_event.index else None
            if prev is None:
                to_append.append(row)
            elif (str(prev.get("home_pitcher")) != str(row["home_pitcher"])
                  or str(prev.get("away_pitcher")) != str(row["away_pitcher"])):
                to_append.append(row)
        if not to_append:
            return 0
        appended = pd.DataFrame(to_append)[LOG_COLUMNS]
        combined = pd.concat([existing, appended], ignore_index=True)
    else:
        combined = new_df
        to_append = new_rows

    atomic_write_csv(combined.sort_values("confirmed_at_utc", kind="stable"), p)
    n = len(to_append) if p.exists() else len(new_rows)
    log.info("[%s] pitcher_confirmation_log: %d fila(s) nuevas/cambiadas.", league, n)
    return n


class StartersStore:
    def __init__(self, root: Path):
        self.dir = root / "data" / "historical"

    def path(self, league: str) -> Path:
        return self.dir / f"starters_{league}.csv"

    def save(self, league: str, rows: list[dict]) -> int:
        """Upsert by game_id; newest ingestion wins. Returns total rows stored.

        A row with BOTH starters missing carries no information and is dropped
        before the upsert: ``fetch_starters`` emits one row per scheduled game
        even when the MLB Stats API does not hydrate ``probablePitcher``, so
        ``keep="last"`` used to overwrite an already-stored starter with NaN on
        every re-run of the backfill. That silently degrades the dominant MLB
        signal and makes the event non-bettable via ``reliability_warning``
        (audit 2026-07-29, D-01).
        """
        if not rows:
            return 0
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        new = pd.DataFrame(rows)
        new["game_id"] = new["game_id"].astype(str)
        new["ingested_at"] = now
        new = new[COLUMNS]
        informative = (new[["home_starter", "away_starter"]].notna()
                       & (new[["home_starter", "away_starter"]].astype(str) != ""))
        dropped = int((~informative.any(axis=1)).sum())
        if dropped:
            new = new[informative.any(axis=1)]
            log.info("[%s] %d fila(s) de abridores sin ningun nombre: no sobrescriben "
                     "lo ya almacenado.", league, dropped)
        if new.empty:
            p = self.path(league)
            return len(pd.read_csv(p, usecols=[0])) if p.exists() else 0
        p = self.path(league)
        if p.exists():
            cur = pd.read_csv(p, dtype={"game_id": str})
            merged = pd.concat([cur, new], ignore_index=True)
            merged = merged.drop_duplicates(subset=["game_id"], keep="last")
        else:
            self.dir.mkdir(parents=True, exist_ok=True)
            merged = new.drop_duplicates(subset=["game_id"], keep="last")
        merged = merged.sort_values("date", kind="stable")
        atomic_write_csv(merged, p)
        return len(merged)

    def attach(self, league: str, results: list[dict]) -> int:
        """Set home_starter/away_starter on result rows by game_id (in place).
        Returns how many rows got both starters."""
        p = self.path(league)
        if not p.exists():
            return 0
        df = pd.read_csv(p, dtype={"game_id": str})
        by_id = {row["game_id"]: row for row in df.to_dict("records")}
        attached = 0
        for r in results:
            s = by_id.get(str(r.get("game_id") or ""))
            if not s:
                continue
            hs = s.get("home_starter")
            as_ = s.get("away_starter")
            r["home_starter"] = hs if isinstance(hs, str) and hs else None
            r["away_starter"] = as_ if isinstance(as_, str) and as_ else None
            if r["home_starter"] and r["away_starter"]:
                attached += 1
        return attached
