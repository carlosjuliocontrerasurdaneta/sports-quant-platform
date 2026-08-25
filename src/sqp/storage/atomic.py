"""Atomic CSV persistence shared by the historical stores.

Temp file + ``os.replace`` (atomic on the same volume): readers only ever see
the old file or the complete new one. results_/starters_/starter_fip_ and the
feature dataset are rebuilt only via slow re-fetches (ESPN, 365 days), so a
crash mid-write must never leave them truncated (audit 2026-07-24, I-2).
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd


def atomic_write_csv(df: pd.DataFrame, out: Path) -> None:
    tmp = out.with_suffix(out.suffix + ".tmp")
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
