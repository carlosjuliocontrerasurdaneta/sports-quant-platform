"""Per-start FIP store (data/historical/starter_fip_{league}.csv), joined to
results by game_id. Like the starter-name store, FIP rows are upserted by
game_id (re-ingestion replaces). Feeds the v2 fielding-independent starter
rating; absence of this file simply leaves the v1/neutral path in effect.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

COLUMNS = ["game_id", "date", "home_starter", "home_starter_fip",
           "away_starter", "away_starter_fip", "ingested_at"]


class StarterFIPStore:
    def __init__(self, root: Path):
        self.dir = root / "data" / "historical"

    def path(self, league: str) -> Path:
        return self.dir / f"starter_fip_{league}.csv"

    def save(self, league: str, rows: list[dict]) -> int:
        """Upsert by game_id; newest ingestion wins. Returns total rows stored."""
        if not rows:
            return 0
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        new = pd.DataFrame(rows)
        new["game_id"] = new["game_id"].astype(str)
        new["ingested_at"] = now
        new = new.reindex(columns=COLUMNS)
        p = self.path(league)
        if p.exists():
            cur = pd.read_csv(p, dtype={"game_id": str})
            merged = pd.concat([cur, new], ignore_index=True).drop_duplicates(
                subset=["game_id"], keep="last")
        else:
            self.dir.mkdir(parents=True, exist_ok=True)
            merged = new.drop_duplicates(subset=["game_id"], keep="last")
        merged = merged.sort_values("date", kind="stable")
        merged.to_csv(p, index=False)
        return len(merged)

    def attach(self, league: str, results: list[dict]) -> int:
        """Set home_starter_fip/away_starter_fip (and starter names if missing) on
        result rows by game_id, in place. Returns rows with both FIPs present."""
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
            for side in ("home", "away"):
                fip = s.get(f"{side}_starter_fip")
                r[f"{side}_starter_fip"] = float(fip) if pd.notna(fip) else None
                name = s.get(f"{side}_starter")
                if not r.get(f"{side}_starter") and isinstance(name, str) and name:
                    r[f"{side}_starter"] = name
            if r.get("home_starter_fip") is not None and r.get("away_starter_fip") is not None:
                attached += 1
        return attached
