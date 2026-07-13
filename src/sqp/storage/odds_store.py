"""Daily odds snapshots (data/odds/odds_{league}_{YYYYMM}.csv).

Append-only: every live run adds one timestamped snapshot of all quoted
lines. Closing odds are reconstructed downstream as the last snapshot
strictly before each event's commence_time. This is the forward-looking,
out-of-sample dataset for realized-ROI and CLV validation (plan block A).
"""
from __future__ import annotations
import csv
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
import pandas as pd
from sqp.domain.models import EventOdds
from sqp.logging_config import get_logger

log = get_logger("sqp.odds_store")

COLUMNS = ["captured_at", "event_id", "commence_time", "home", "away",
           "market", "outcome", "point", "price_decimal", "bookmaker"]

# Dos procesos escriben este store: el run diario (11:00) y la captura de
# cierre horaria (:30). Si el run sigue vivo cuando dispara la captura, dos
# appends simultaneos intercalarian filas, y la ruta de reconciliacion de
# esquema (rewrite completo via os.replace) perderia el append concurrente.
LOCK_TIMEOUT_S = 30.0   # espera maxima por el lock antes de degradar
LOCK_STALE_S = 300.0    # un .lock mas viejo que esto es de un proceso muerto


@contextmanager
def _locked(target: Path, timeout_s: float = LOCK_TIMEOUT_S,
            stale_s: float = LOCK_STALE_S) -> Iterator[None]:
    """Lock exclusivo entre procesos via archivo sidecar O_CREAT|O_EXCL.

    Un lock huerfano (proceso muerto) se rompe pasado ``stale_s``. Si el lock
    no se consigue en ``timeout_s`` se DEGRADA al comportamiento sin lock con
    un warning: bloquear el pipeline diario seria peor que el riesgo de
    intercalado que este lock mitiga."""
    lock = target.with_suffix(target.suffix + ".lock")
    deadline = time.monotonic() + timeout_s
    fd: int | None = None
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > stale_s:
                    lock.unlink(missing_ok=True)
                    continue
            except OSError:
                continue  # el otro proceso lo libero entre exists y stat
            if time.monotonic() >= deadline:
                log.warning("lock timeout on %s; proceeding WITHOUT lock "
                            "(degraded, risk of interleaved append)", lock.name)
                break
            time.sleep(0.25)
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
            lock.unlink(missing_ok=True)


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
        # Guard de drift de esquema (mismo modo de corrupcion que KI-011 en
        # settled_*.csv): si el header existente no coincide con COLUMNS, un
        # append a ciegas desalinearia cada valor al releer. Se reconcilia por
        # union de columnas y se reescribe alineado (atomico). El caso normal
        # (header identico) sigue siendo un append barato.
        with _locked(p):
            if p.exists() and _header(p) != COLUMNS:
                prior = pd.read_csv(p)
                cols = list(prior.columns) + [c for c in COLUMNS if c not in prior.columns]
                combined = pd.concat([prior.reindex(columns=cols), df.reindex(columns=cols)],
                                     ignore_index=True)
                tmp = p.with_suffix(p.suffix + ".tmp")
                try:
                    combined.to_csv(tmp, index=False)
                    os.replace(tmp, p)
                finally:
                    tmp.unlink(missing_ok=True)  # no-op tras un replace exitoso
            else:
                df.to_csv(p, mode="a", header=not p.exists(), index=False)
        return len(df)


def _header(p: Path) -> list[str]:
    """Primera linea del CSV como lista de columnas (lectura barata, sin pandas)."""
    with p.open(newline="", encoding="utf-8") as fh:
        return next(csv.reader(fh), [])
