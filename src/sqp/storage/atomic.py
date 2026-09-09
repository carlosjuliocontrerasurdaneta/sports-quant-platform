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
import uuid
from pathlib import Path

import pandas as pd


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
        os.replace(tmp, out)
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
        os.replace(tmp, out)
    finally:
        tmp.unlink(missing_ok=True)  # no-op tras un replace exitoso
