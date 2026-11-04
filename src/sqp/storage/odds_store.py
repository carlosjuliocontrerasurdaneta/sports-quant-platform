"""Daily odds snapshots (data/odds/odds_{league}_{YYYYMM}.csv).

Append-only: every live run adds one timestamped snapshot of all quoted
lines. Closing odds are reconstructed downstream as the last snapshot
strictly before each event's commence_time. This is the forward-looking,
out-of-sample dataset for realized-ROI and CLV validation (plan block A).
"""
from __future__ import annotations
import csv
import io
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from sqp.domain.models import EventOdds
from sqp.logging_config import get_logger
from sqp.storage.atomic import atomic_write_csv
# Dos procesos escriben este store: el run diario (11:00) y la captura de
# cierre horaria (:30). Si el run sigue vivo cuando dispara la captura, dos
# appends simultaneos intercalarian filas, y la ruta de reconciliacion de
# esquema (rewrite completo via os.replace) perderia el append concurrente.
# El lock vive en sqp.storage.lock desde la auditoria 2026-07-24 (I-5) para
# compartirlo con los escritores de candidates_*.csv.
from sqp.storage.lock import locked as _locked

log = get_logger("sqp.odds_store")

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
        # AUD-016: filas exactamente iguales (todas las columnas) no aportan
        # informacion; una misma captura repetida debe ser idempotente.
        df = pd.DataFrame(rows)[COLUMNS].drop_duplicates()
        p = self.path(league, captured_at[:7].replace("-", ""))
        self.dir.mkdir(parents=True, exist_ok=True)
        # Guard de drift de esquema (mismo modo de corrupcion que KI-011 en
        # settled_*.csv): si el header existente no coincide con COLUMNS, un
        # append a ciegas desalinearia cada valor al releer. Se reconcilia por
        # union de columnas y se reescribe alineado (atomico). El caso normal
        # (header identico) sigue siendo un append barato.
        with _locked(p):
            df = _drop_already_stored(df, p, captured_at)
            if df.empty:
                return 0
            if p.exists() and _header(p) != COLUMNS:
                prior = pd.read_csv(p)
                cols = list(prior.columns) + [c for c in COLUMNS if c not in prior.columns]
                combined = pd.concat([prior.reindex(columns=cols), df.reindex(columns=cols)],
                                     ignore_index=True)
                # Helper canonico: temporal UNICO y fsync. El temporal fijo
                # `.csv.tmp` que habia aqui es el ultimo resto del patron de
                # AUD-002 sobre un fichero que solo se reconstruye volviendo a
                # pagar cuota de API.
                atomic_write_csv(combined, p)
            else:
                df.to_csv(p, mode="a", header=not p.exists(), index=False)
        return len(df)


_TAIL_BYTES = 262144


def _drop_already_stored(df: pd.DataFrame, p: Path, captured_at: str) -> pd.DataFrame:
    """Quita de ``df`` las filas ya presentes en ``p`` con el mismo
    ``captured_at`` (idempotencia de ``append_snapshot``, AUD-016).

    Los snapshots se anexan en orden, asi que una captura repetida deja su
    ``captured_at`` en la cola del fichero: se mira solo la cola (barato) y solo
    si aparece se lee el fichero por bloques para comparar. Comparacion exacta
    sobre el texto de las columnas (sin parsear numeros)."""
    if df.empty or not p.exists():
        return df
    with p.open("rb") as fh:
        fh.seek(0, 2)
        size = fh.tell()
        fh.seek(max(0, size - _TAIL_BYTES))
        tail = fh.read().decode("utf-8", errors="ignore")
    if captured_at not in tail:
        return df
    texto = pd.read_csv(io.StringIO(df.to_csv(index=False)), dtype=str,
                        keep_default_na=False)
    vistos: set[tuple[str, ...]] = set()
    for chunk in pd.read_csv(p, dtype=str, keep_default_na=False,
                             chunksize=200_000):
        if "captured_at" not in chunk.columns:
            continue
        mismo = chunk[chunk["captured_at"] == captured_at].reindex(columns=COLUMNS,
                                                                    fill_value="")
        vistos.update(map(tuple, mismo.fillna("").to_numpy()))
    if not vistos:
        return df
    nuevas = [tuple(r) not in vistos for r in texto.to_numpy()]
    return df[nuevas]


def _header(p: Path) -> list[str]:
    """Primera linea del CSV como lista de columnas (lectura barata, sin pandas)."""
    with p.open(newline="", encoding="utf-8") as fh:
        return next(csv.reader(fh), [])
