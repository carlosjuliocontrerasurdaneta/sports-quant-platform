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
    entry = {
        "failed": True,
        "stage": stage,
        "exit_code": int(exit_code),
        "failed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    # Se FUSIONA por etapa en vez de sobrescribir. Sobrescribiendo, un fallo de
    # `settle` seguido de uno de `run` borraba el primero, y entonces el
    # `--clear --only-stage run` de RUN_DIARIO_ALL.bat encontraba `stage == "run"`,
    # daba el visto bueno y borraba el centinela entero: la liquidacion quedaba
    # rota, invisible y en verde (auditoria 2026-08-31, A-02). Es justo lo que el
    # docstring de `clear_run_status` dice que no debe pasar.
    stages = dict(_read_stages(root))
    stages[stage] = entry
    out.write_text(json.dumps({"stages": stages}, indent=2), encoding="utf-8")
    log.error("Run diario FALLIDO en la etapa '%s' (exit %s); centinela -> %s",
              stage, exit_code, out)
    return out


def _read_stages(root: Path) -> dict:
    """Fallos vigentes indexados por etapa. Absorbe el formato PLANO anterior
    (`{"failed": ..., "stage": ...}`) para que un centinela escrito por la
    version previa siga avisando tras actualizar."""
    p = _path(root)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Centinela de run ilegible (%s): se ignora.", exc)
        return {}
    if not isinstance(data, dict):
        return {}
    stages = data.get("stages")
    if isinstance(stages, dict):
        return {k: v for k, v in stages.items() if isinstance(v, dict)}
    if data.get("failed") and data.get("stage") is not None:
        return {str(data["stage"]): data}
    return {}


def clear_run_status(root: Path, stage: str | None = None) -> bool:
    """Borra el centinela tras un run correcto. Idempotente.

    Con `stage` borra SOLO si el fallo registrado es de esa etapa. Lo necesitan
    los BAT parciales: `SETTLE_ALL.bat` y `RUN_DIARIO_ALL.bat` arreglan una
    etapa cada uno, y borrar el centinela entero dejaria el fallo de la otra sin
    avisar. Sin `stage` se borra siempre, que es lo correcto para
    `DIARIO_COMPLETO.bat`, que ejecuta las dos.

    Devuelve True si habia centinela y se borro.
    """
    p = _path(root)
    if not p.exists():
        return False
    if stage is None:
        p.unlink(missing_ok=True)
        return True
    stages = _read_stages(root)
    if stage not in stages:
        return False          # el fallo registrado es de OTRA etapa: no se toca
    del stages[stage]
    if stages:
        # Sobrevive el fallo de la otra etapa, que es el punto de `--only-stage`.
        p.write_text(json.dumps({"stages": stages}, indent=2), encoding="utf-8")
    else:
        p.unlink(missing_ok=True)
    return True


def read_run_status(root: Path) -> dict | None:
    """Estado del ultimo run fallido, o None si no hay fallo registrado.

    Un centinela ausente O corrupto devuelve None: este modulo alimenta el health
    check, y un JSON truncado no debe tumbar el diagnostico. La perdida de un
    aviso es preferible a romper la herramienta que lo reporta.
    """
    stages = _read_stages(root)
    if not stages:
        return None
    # Con fallos en las dos etapas se devuelve el de LIQUIDACION: aborta el run
    # para no sobrescribir picks sin liquidar, asi que es el que manda. La forma
    # devuelta sigue siendo plana (`failed`/`stage`/`exit_code`/`failed_at`)
    # porque `health.py` y el banner del tablero leen esas claves.
    for name in ("settle", "run"):
        if name in stages:
            return dict(stages[name], stages=sorted(stages))
    first = sorted(stages)[0]
    return dict(stages[first], stages=sorted(stages))
