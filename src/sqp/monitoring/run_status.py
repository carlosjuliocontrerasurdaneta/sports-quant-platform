"""Centinela del estado del ultimo run diario (auditoria 2026-07-29, S-1).

El 2026-07-29 `SQP_Diario_Completo_Cdev` termino con `LastTaskResult = 1` y el
fallo estuvo 24 h invisible. Los BAT propagaban el codigo de salida
correctamente, pero **no habia ningun consumidor**: el error moria en el
Programador de tareas, cuyo log operativo ademas esta deshabilitado en esta
maquina.

Este modulo cierra ese hueco sin credenciales ni servicios externos: los BAT
escriben un centinela al fallar y lo borran al terminar bien, y
`sqp.monitoring.health` lo eleva a ERROR, que es lo que ya leen
`scripts/health_check.py` (exit 1) y el dashboard.

El centinela vive en `logs/` porque `.gitignore` ya ignora ese directorio: es
estado operativo de una maquina, no algo que deba versionarse.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqp.logging_config import get_logger

log = get_logger("sqp.run_status")

STATUS_FILENAME = "last_run_status.json"


def _path(root: Path) -> Path:
    return root / "logs" / STATUS_FILENAME


def record_run_failure(root: Path, stage: str, exit_code: int) -> Path:
    """Registra que la etapa `stage` del run diario fallo con `exit_code`.

    `stage` es "settle" o "run": distinguirlas importa porque un fallo en la
    liquidacion ABORTA el run (para no sobrescribir picks sin liquidar), asi que
    las consecuencias son distintas.
    """
    out = _path(root)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "failed": True,
        "stage": stage,
        "exit_code": int(exit_code),
        "failed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    log.error("Run diario FALLIDO en la etapa '%s' (exit %s); centinela -> %s",
              stage, exit_code, out)
    return out


def clear_run_status(root: Path) -> None:
    """Borra el centinela tras un run correcto. Idempotente."""
    _path(root).unlink(missing_ok=True)


def read_run_status(root: Path) -> dict | None:
    """Estado del ultimo run fallido, o None si no hay fallo registrado.

    Un centinela ausente O corrupto devuelve None: este modulo alimenta el health
    check, y un JSON truncado no debe tumbar el diagnostico. La perdida de un
    aviso es preferible a romper la herramienta que lo reporta.
    """
    p = _path(root)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Centinela de run ilegible (%s): se ignora.", exc)
        return None
    return data if isinstance(data, dict) else None
