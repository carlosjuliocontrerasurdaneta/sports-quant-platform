"""Vigila, desde OTRA tarea, que el run diario se haya lanzado (AUD-005).

Lo llama `CAPTURE_CLOSE.bat` cada 30 min, sin bloquear. Si
`SQP_Diario_Completo_Cdev` no llego a lanzarse en su disparador (maquina
reiniciando, disparador que no salto), registra el centinela de la etapa
`diario_no_lanzado`, que el tablero y `health_check` ya muestran. Si el run se
lanzo, borra solo ese centinela. No relanza nada.

Sale siempre con 0 salvo error inesperado: quien lo llama no debe fallar por el.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sqp.monitoring.health import _scheduled_tasks_raw, daily_launch_missed  # noqa: E402
from sqp.monitoring.run_status import clear_run_status, record_run_failure  # noqa: E402

STAGE = "diario_no_lanzado"


def main() -> int:
    raw = _scheduled_tasks_raw()
    if raw is None:
        print("No se pudo consultar el Programador; no se cambia nada.")
        return 0
    motivo = daily_launch_missed(raw, datetime.now().astimezone())
    if motivo:
        record_run_failure(ROOT, STAGE, 1)
        print(f"AVISO: {motivo}. Centinela '{STAGE}' registrado.")
    elif clear_run_status(ROOT, STAGE):
        print(f"El run diario se lanzo; centinela '{STAGE}' retirado.")
    else:
        print("El run diario se lanzo en su disparador.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
