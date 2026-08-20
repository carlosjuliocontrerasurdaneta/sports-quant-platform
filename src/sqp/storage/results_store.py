"""Local historical results store: one append-only CSV per league under
data/historical/. Existing rows always win over re-ingested duplicates
(raw data is never mutated), every row carries an ingestion timestamp,
and (date, home, away) is the dedup key.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from sqp.storage.atomic import atomic_write_csv


COLUMNS = ["date", "home", "away", "game_id", "home_score", "away_score", "neutral", "ingested_at"]
KEY = ["date", "home", "away", "game_id"]  # game_id keeps doubleheaders distinct


class ResultsStore:
    def __init__(self, root: Path):
        self.dir = root / "data" / "historical"

    def path(self, league: str) -> Path:
        return self.dir / f"results_{league}.csv"

    _LOAD_COLS = ["date", "home", "away", "game_id", "home_score", "away_score", "neutral"]

    def load(self, league: str) -> list[dict]:
        """Stored results in chronological order, in ResultsProvider dict format."""
        p = self.path(league)
        if not p.exists():
            return []
        df = pd.read_csv(p, usecols=lambda c: c in self._LOAD_COLS,
                         dtype={"date": str, "game_id": str})
        df = self._migrate(df).sort_values("date", kind="stable")
        return df[self._LOAD_COLS].to_dict("records")

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
            # Una fila legacy (game_id == "") ya cubre ese (date, home, away):
            # re-ingerir el mismo juego con game_id real crearia un duplicado
            # dentro del store (auditoria 2026-07-24, M-22). Los doubleheaders
            # genuinos llegan del mismo vendor con ambos game_id no vacios.
            legacy = set(map(tuple, cur.loc[cur["game_id"] == "",
                                            ["date", "home", "away"]]
                             .itertuples(index=False, name=None)))
            if legacy:
                new = new[[(dy, h, a) not in legacy for dy, h, a in
                           new[["date", "home", "away"]].itertuples(index=False, name=None)]]
            merged = pd.concat([cur, new], ignore_index=True).drop_duplicates(subset=KEY, keep="first")
            added = len(merged) - len(cur)
        else:
            self.dir.mkdir(parents=True, exist_ok=True)
            merged, added = new, len(new)
        atomic_write_csv(merged.sort_values("date", kind="stable"), p)
        return added
