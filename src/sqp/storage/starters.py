"""Starter map per game (data/historical/starters_{league}.csv), joined to
results by game_id. Unlike results, starter announcements are mutable
(probable -> actual), so re-ingested rows REPLACE older ones for the same
game_id.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

COLUMNS = ["game_id", "date", "home_starter", "away_starter", "ingested_at"]


class StartersStore:
    def __init__(self, root: Path):
        self.dir = root / "data" / "historical"

    def path(self, league: str) -> Path:
        return self.dir / f"starters_{league}.csv"

    def save(self, league: str, rows: list[dict]) -> int:
        """Upsert by game_id; newest ingestion wins. Returns total rows stored."""
        if not rows:
            return 0
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        new = pd.DataFrame(rows)
        new["game_id"] = new["game_id"].astype(str)
        new["ingested_at"] = now
        new = new[COLUMNS]
        p = self.path(league)
        if p.exists():
            cur = pd.read_csv(p, dtype={"game_id": str})
            merged = pd.concat([cur, new], ignore_index=True)
            merged = merged.drop_duplicates(subset=["game_id"], keep="last")
        else:
            self.dir.mkdir(parents=True, exist_ok=True)
            merged = new.drop_duplicates(subset=["game_id"], keep="last")
        merged = merged.sort_values("date", kind="stable")
        merged.to_csv(p, index=False)
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
