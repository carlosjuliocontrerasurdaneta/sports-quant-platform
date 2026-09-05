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

from sqp.exceptions import LockNoAdquiridoError
from sqp.logging_config import get_logger

log = get_logger("sqp.storage.lock")

# 30 -> 120 s el 2026-09-05, junto con dejar de degradar (AUD-002). Mientras el
# timeout ENTRABA sin lock, su valor solo decidia cuanto se esperaba antes de
# arriesgarse; ahora decide cuando se ABORTA, asi que 30 s convertiria en fallo
# duro cualquier seccion critica legitimamente lenta. La mas lenta que hay es
# `revalidate_pitchers`, que retiene el lock durante `fetch_probables` (MLB
# Stats API, 1-2 dias, llamadas de hasta 60 s): con 30 s el pipeline diario
# habria empezado a abortar donde antes perdia escrituras en silencio.
# 120 s deja margen holgado sobre esa espera y sigue MUY por debajo de
# `LOCK_STALE_S`, que es quien rescata de un lock huerfano.
LOCK_TIMEOUT_S = 120.0  # espera maxima antes de ABORTAR (ya no se degrada)
LOCK_STALE_S = 300.0    # un .lock mas viejo que esto es de un proceso muerto


@contextmanager
def locked(target: Path, timeout_s: float = LOCK_TIMEOUT_S,
           stale_s: float = LOCK_STALE_S) -> Iterator[None]:
    """Lock exclusivo entre procesos via archivo sidecar O_CREAT|O_EXCL.

    Un lock huerfano (proceso muerto) se rompe pasado ``stale_s``. Si aun asi
    no se consigue en ``timeout_s``, se lanza ``LockNoAdquiridoError``: NO se
    entra a la seccion critica sin exclusion.

    Hasta el 2026-09-05 se degradaba con un warning, razonando que "bloquear el
    pipeline diario seria peor que el riesgo de intercalado". El razonamiento
    tenia un agujero: la degradacion se activa justo cuando HAY contencion, es
    decir cuando el intercalado no es un riesgo teorico sino el escenario en
    curso. Y el modo de fallo no es un error visible sino una escritura perdida
    en silencio."""
    lock = target.with_suffix(target.suffix + ".lock")
    deadline = time.monotonic() + timeout_s
    fd: int | None = None
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:
                stale = time.time() - lock.stat().st_mtime > stale_s
            except OSError:
                # El otro proceso lo libero entre exists y stat -- o stat falla
                # de forma PERSISTENTE (permisos, disco, recurso de red caido).
                # Antes esta rama hacia `continue`, saltandose tanto la
                # comprobacion de deadline como el sleep: un fallo persistente
                # giraba sin salida al 100% de CPU y `timeout_s` no rescataba,
                # colgando el run diario (auditoria 2026-08-05, F-08).
                stale = False
            if stale:
                lock.unlink(missing_ok=True)
                continue
            if time.monotonic() >= deadline:
                # NO se entra sin lock (AUD-002). Antes se degradaba con un
                # warning "proceeding WITHOUT lock", y eso convertia el caso de
                # MAXIMA contencion en el de MINIMA proteccion: los consumidores
                # hacen read-modify-write, asi que el segundo escritor pisaba lo
                # que el primero acababa de leer. Reproducido: A lee "old", B
                # entra degradado y escribe "new", A persiste su copia y "new"
                # desaparece. Fallar es ruidoso; perder una revocacion o unos
                # candidatos recien generados, no.
                raise LockNoAdquiridoError(
                    f"no se obtuvo el lock de {lock.name} en {timeout_s:g}s; "
                    f"otro proceso VIVO lo retiene (un lock huerfano se habria "
                    f"roto a los {stale_s:g}s). No se entra a la seccion critica "
                    f"sin exclusion: el read-modify-write perderia la escritura.")
            time.sleep(0.25)
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
            lock.unlink(missing_ok=True)
