"""Calendario por liga (data/historical/schedule_{league}.csv): la IDENTIDAD de
cada partido -- id del vendor, hora UTC de inicio y estado --, aplazados
incluidos (KI-059, 2026-09-24).

Una fila por APARICION en el calendario, clave ``(game_id, date)``. Un aplazado
que se recupera conserva su ``gamePk`` y aparece dos veces: en su fecha original
como ``Postponed`` y en la de recuperacion. Un suspendido y reanudado, igual.
Deduplicar por ``game_id`` a secas borraba la aparicion aplazada, y entonces el
pick del juego aplazado de un doubleheader tomaba como mas cercano el OTRO juego
y se liquidaba con su marcador (revision Fable, FABLE-K-001, reproducido con
BOS-BAL 2025-05-23). Dentro de una aparicion, la re-ingesta mas reciente gana:
su estado cambia (programado -> final) y su hora puede moverse.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from sqp.storage.atomic import atomic_write_csv
from sqp.storage.lock import locked

COLUMNS = ["game_id", "date", "start_time", "home", "away", "state",
           "abstract_state", "start_time_tbd", "double_header", "game_number",
           "ingested_at"]
KEY = ["game_id", "date"]


class ScheduleStore:
    def __init__(self, root: Path):
        self.dir = root / "data" / "historical"

    def path(self, league: str) -> Path:
        return self.dir / f"schedule_{league}.csv"

    def load(self, league: str) -> pd.DataFrame:
        """Calendario almacenado; vacio si no existe o no se puede leer."""
        p = self.path(league)
        if not p.exists():
            return pd.DataFrame(columns=COLUMNS)
        try:
            return pd.read_csv(p, dtype={"game_id": str, "date": str})
        except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError):
            return pd.DataFrame(columns=COLUMNS)

    def upsert(self, league: str, rows: list[dict]) -> int:
        """Inserta o reemplaza por APARICION ``(game_id, date)``; gana la ingesta
        mas reciente. Lectura, fusion y escritura bajo lock, como los demas
        stores (AUD-009). Devuelve el total de filas almacenadas."""
        if not rows:
            return 0
        new = pd.DataFrame(rows)
        new["game_id"] = new["game_id"].astype(str)
        new["date"] = new["date"].astype(str)
        new["ingested_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        new = new.reindex(columns=COLUMNS)
        p = self.path(league)
        self.dir.mkdir(parents=True, exist_ok=True)
        with locked(p):
            if p.exists():
                cur = pd.read_csv(p, dtype={"game_id": str, "date": str})
                merged = pd.concat([cur, new], ignore_index=True).drop_duplicates(
                    subset=KEY, keep="last")
            else:
                merged = new.drop_duplicates(subset=KEY, keep="last")
            merged = merged.sort_values(["date", "start_time"], kind="stable")
            atomic_write_csv(merged, p)
        return len(merged)
