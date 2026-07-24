"""Lock exclusivo entre procesos via archivo sidecar O_CREAT|O_EXCL.

Extraido de odds_store (auditoria 2026-07-24, I-5) para serializar tambien los
escritores de candidates_*.csv: el run diario (11:00) y la revalidacion que
sigue a cada captura de cierre horaria (:00/:30) hacen read-modify-write sobre
los mismos archivos; sin lock, uno puede pisar los candidates recien generados
o una revocacion recien escrita (lost update).
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqp.logging_config import get_logger

log = get_logger("sqp.storage.lock")

LOCK_TIMEOUT_S = 30.0   # espera maxima por el lock antes de degradar
LOCK_STALE_S = 300.0    # un .lock mas viejo que esto es de un proceso muerto


@contextmanager
def locked(target: Path, timeout_s: float = LOCK_TIMEOUT_S,
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
                            "(degraded, risk of interleaved write)", lock.name)
                break
            time.sleep(0.25)
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
            lock.unlink(missing_ok=True)
