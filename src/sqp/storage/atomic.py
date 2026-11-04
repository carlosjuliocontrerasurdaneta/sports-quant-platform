"""Atomic CSV/JSON persistence: the historical stores and the system state
files (prediction/CLV/degradation gates, run sentinel, calibration registry).

Temp file + ``os.replace`` (atomic on the same volume): readers only ever see
the old file or the complete new one. results_/starters_/starter_fip_ and the
feature dataset are rebuilt only via slow re-fetches (ESPN, 365 days), so a
crash mid-write must never leave them truncated (audit 2026-07-24, I-2).
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

import pandas as pd


# Plazo del reintento ante violaciones de uso compartido de Windows. Es una
# CONSTANTE del modulo, no un literal enterrado en la funcion, para que la
# prueba pueda acotarse contra ella en vez de contra un numero de reloj de pared
# elegido a ojo: `tests/test_audit_atomic_readers.py` comparaba con 4 s fijos
# -- solo 2x este plazo -- y se ponia en rojo bajo carga sin que nada hubiera
# cambiado (auditoria integral 2026-09-22, AUD-004).
REPLACE_RETRY_SECONDS = 2.0


def _replace(tmp: Path, out: Path) -> None:
    """Retry transient Windows sharing violations for at most two seconds.

    Readers outside our writer locks may hold a handle without delete sharing.
    MoveFileEx also reports WinError 5 for an open destination on Windows.
    Permanent access denial still raises the original error at the deadline.
    Unrelated errors are never retried.
    """
    deadline = time.monotonic() + REPLACE_RETRY_SECONDS
    while True:
        try:
            os.replace(tmp, out)
            return
        except OSError as exc:
            if getattr(exc, "winerror", None) not in (5, 32, 33) or time.monotonic() >= deadline:
                raise
            time.sleep(min(.05, max(0., deadline - time.monotonic())))


def atomic_write_csv(df: pd.DataFrame, out: Path) -> None:
    # Temporal UNICO por proceso y llamada. Con el nombre fijo `.csv.tmp`, dos
    # escritores concurrentes sobre el mismo destino compartian temporal: uno
    # podia renombrar el fichero a medio escribir del otro, y `os.replace` daba
    # atomicidad sobre datos ya corruptos (Codex, 2026-09-05, AUD-002, causa
    # raiz secundaria). El lock lo hace improbable, no imposible: hay escritores
    # que no pasan por `locked`.
    tmp = _tmp_unico(out)
    try:
        # ``os.replace`` da ATOMICIDAD (nadie ve un archivo a medias), pero no
        # DURABILIDAD: sin fsync el contenido del temporal puede seguir en cache
        # del SO cuando el rename ya se aplico, y un corte de energia deja el
        # nombre bueno apuntando a datos incompletos. Estos stores se reconstruyen
        # solo con re-fetches lentos (ESPN, 365 dias), que es justo el coste que
        # este modulo existe para evitar (auditoria 2026-08-05, COR-07).
        df.to_csv(tmp, index=False)
        # Se reabre en vez de escribir sobre un handle propio: `to_csv` debe
        # seguir recibiendo una RUTA. Los consumidores parchean `to_csv` para
        # simular fallos a mitad de escritura y esperan poder hacer
        # `Path(path_or_buf)` (tests/test_settle_persist.py). Tras el cierre de
        # to_csv los datos estan en cache del SO; este fsync los lleva al disco.
        fd = os.open(tmp, os.O_RDWR)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        _replace(tmp, out)
    finally:
        tmp.unlink(missing_ok=True)  # no-op after a successful replace


def _tmp_unico(out: Path) -> Path:
    """Temporal UNICO por proceso y llamada, hermano del destino.

    Mismo criterio que `atomic_write_csv`: un nombre FIJO (`x.json.tmp`) lo
    comparten dos escritores del mismo destino, y entonces uno renombra el
    fichero a medio escribir del otro -- `os.replace` da atomicidad sobre datos
    ya corruptos (Codex 2026-09-05, AUD-002, causa raiz secundaria).
    """
    return out.with_suffix(f"{out.suffix}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")


def atomic_write_json(payload: object, out: Path, *, indent: int | None = 2,
                      sort_keys: bool = True, ensure_ascii: bool = True) -> None:
    """Persiste `payload` como JSON de forma atomica Y duradera.

    Existe porque `atomic_write_csv` solo cubria los CSV, y los ficheros de
    ESTADO del sistema son JSON: el registro del prediction gate, el del gate de
    CLV, el de degradacion y el centinela de fallo del run. Todos se escribian a
    mano -- unos con temporal de nombre FIJO y sin fsync, el centinela sin
    temporal siquiera -- reproduciendo en JSON el defecto que el proyecto ya
    habia declarado tal para CSV (AUD-002; AUD-MED-003 de la auditoria integral
    del 2026-09-08, que solo alcanzo a los seis sitios que escribian CSV).

    Las dos propiedades importan por separado:

    - ATOMICIDAD: un lector ve el fichero viejo entero o el nuevo entero. Sin
      ella, `write_text` directo sobre el destino -- lo que hacia el centinela --
      deja JSON truncado si el proceso muere a mitad, y `json.loads` falla: el
      consumidor lo trata como "sin fallo registrado" y LA ALARMA SE PIERDE.
    - DURABILIDAD: `os.replace` no garantiza que el contenido este en disco. Sin
      `fsync`, un corte de energia puede dejar el nombre bueno apuntando a datos
      incompletos. En `prediction_gate.json` eso no solo deniega (que seria
      seguro): borra el PESTILLO del pre-registro, que es memoria que no se
      reconstruye midiendo otra vez.
    """
    tmp = _tmp_unico(out)
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, indent=indent, sort_keys=sort_keys,
                                ensure_ascii=ensure_ascii))
            fh.flush()
            os.fsync(fh.fileno())
        _replace(tmp, out)
    finally:
        tmp.unlink(missing_ok=True)  # no-op tras un replace exitoso


def atomic_write_bytes(data: bytes, out: Path) -> None:
    """Persiste bytes crudos (p.ej. JSON gzip de un proveedor) de forma atomica
    y duradera, con el mismo criterio que `atomic_write_csv`/`atomic_write_json`:
    temporal UNICO + fsync + `os.replace`. Existe para el backfill de porteros
    NHL, que preserva el JSON bruto de cada boxscore comprimido (regla de
    integridad de datos: preservar datos en bruto) sin poder reusar
    `atomic_write_csv` (no es un DataFrame) ni `atomic_write_json` (no es texto
    UTF-8: son bytes gzip)."""
    tmp = _tmp_unico(out)
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        _replace(tmp, out)
    finally:
        tmp.unlink(missing_ok=True)  # no-op tras un replace exitoso


def read_json_retrying(path: Path, *, seconds: float = REPLACE_RETRY_SECONDS,
                       wait: float = 0.1) -> object:
    """``json.loads`` del fichero reintentando SOLO ``OSError`` durante
    ``seconds`` (violaciones de uso compartido de Windows mientras otro proceso
    hace ``os.replace``). JSON corrupto o bytes no UTF-8 no se reintentan: con
    escritura atomica eso no es transitorio. El ultimo error se propaga.

    Existe para los escritores de registros con estado (gate de prediccion,
    degradacion): un fallo de lectura TRANSITORIO no debe convertirse en "estado
    desconocido" y bloquear el gate un dia entero (revision cruzada de Codex
    sobre AUD-002, ronda audit-2026-09-22-r2, reproducido)."""
    deadline = time.monotonic() + seconds
    while True:
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except OSError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(wait)


def append_csv_log(new: pd.DataFrame, path: Path) -> None:
    """Append a un rastro CSV append-only reconciliando columnas (union).

    Un fichero ilegible (fila malformada -> ``ParserError``, o columnas
    desplazadas al indice, que pandas 3 produce sin error cuando TODAS las filas
    traen un campo de mas) NO es un log vacio: tratarlo como tal y reescribirlo
    perdia todo el historial. Se aparta a ``<nombre>.corrupt.<UTC>`` con sus
    bytes intactos y se empieza un log nuevo; si no se puede apartar, se lanza
    sin escribir. Mismo criterio que AUD-006 en ``revalidation._append_log``,
    extendido a los demas escritores (NEW-001, verificacion audit-2026-11-03).
    El llamador es responsable del lock si hay escritores concurrentes."""
    import logging
    from datetime import datetime, timezone

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        motivo: str | None = None
        try:
            prior = pd.read_csv(path)
        except pd.errors.EmptyDataError:
            prior = pd.DataFrame()  # 0 bytes: no hay historial que perder
        except pd.errors.ParserError as exc:
            prior, motivo = pd.DataFrame(), f"no parseable ({exc})"
        else:
            # Indice por defecto exacto: una primera columna entera y
            # consecutiva desplazada al indice tambien es un RangeIndex.
            if not prior.index.equals(pd.RangeIndex(len(prior))):
                prior, motivo = pd.DataFrame(), "columnas desplazadas al indice"
        if motivo is not None:
            log = logging.getLogger("sqp.storage.atomic")
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            target = path.with_name(f"{path.name}.corrupt.{stamp}")
            try:
                path.rename(target)
            except OSError as rename_exc:
                log.error("%s %s y no se pudo apartar (%s); no se reescribe "
                          "para no perder filas.", path, motivo, rename_exc)
                raise
            log.error("%s %s; apartado a %s. Reimportar a mano si las filas "
                      "importan.", path, motivo, target.name)
        if not prior.empty:
            cols = list(prior.columns) + [c for c in new.columns
                                          if c not in prior.columns]
            new = pd.concat([prior.reindex(columns=cols),
                             new.reindex(columns=cols)], ignore_index=True)
    atomic_write_csv(new, path)
