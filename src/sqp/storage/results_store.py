"""Local historical results store: one append-only CSV per league under
data/historical/. Existing rows always win over re-ingested duplicates
(raw data is never mutated), every row carries an ingestion timestamp,
and (date, home, away) is the dedup key.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

COLUMNS = ["date", "home", "away", "game_id", "home_score", "away_score", "neutral", "ingested_at"]
KEY = ["date", "home", "away", "game_id"]  # game_id keeps doubleheaders distinct


class ResultsStore:
    def __init__(self, root: Path):
        self.dir = root / "data" / "historical"

    def path(self, league: str) -> Path:
        return self.dir / f"results_{league}.csv"

    def load(self, league: str) -> list[dict]:
        """Stored results in chronological order, in ResultsProvider dict format."""
        p = self.path(league)
        if not p.exists():
            return []
        df = pd.read_csv(p, dtype={"date": str, "game_id": str})
        df = self._migrate(df).sort_values("date", kind="stable")
        return df[["date", "home", "away", "game_id", "home_score", "away_score", "neutral"]].to_dict("records")

    @staticmethod
    def _migrate(df: pd.DataFrame) -> pd.DataFrame:
        if "game_id" not in df.columns:  # legacy schema (pre game_id)
            df["game_id"] = ""
        df["game_id"] = df["game_id"].fillna("").astype(str)
        return df

    def upsert(self, league: str, results: list[dict]) -> int:
        """Add new results; returns how many rows were actually added."""
        if not results:
            return 0
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        new = pd.DataFrame(results)
        new["date"] = new["date"].astype(str).str[:10]
        if "neutral" not in new.columns:
            new["neutral"] = False
        new["neutral"] = new["neutral"].fillna(False).astype(bool)
        new = self._migrate(new)
        new["ingested_at"] = now
        new = new[COLUMNS].drop_duplicates(subset=KEY, keep="first")
        p = self.path(league)
        if p.exists():
            cur = self._migrate(pd.read_csv(p, dtype={"date": str, "game_id": str}))
            merged = pd.concat([cur, new], ignore_index=True).drop_duplicates(subset=KEY, keep="first")
            added = len(merged) - len(cur)
        else:
            self.dir.mkdir(parents=True, exist_ok=True)
            merged, added = new, len(new)
        merged.sort_values("date", kind="stable").to_csv(p, index=False)
        return added
