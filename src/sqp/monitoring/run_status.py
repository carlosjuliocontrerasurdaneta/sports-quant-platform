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

UN FICHERO POR ETAPA (B-7, orden del operador 2026-09-09)
---------------------------------------------------------

Hasta hoy todas las etapas vivian en un unico JSON, y tanto registrar como
limpiar hacian read-modify-write sobre el: leer las siete etapas, cambiar una y
reescribir el conjunto. Con cinco tareas programadas que pueden solaparse
-- `CAPTURE_CLOSE` cada 30 min contra `DIARIO_COMPLETO` a las 12:00 -- dos
procesos intercalados perdian la etapa del otro, y perder una etapa aqui es
borrar en silencio una alarma vigente: exactamente el modo de averia que este
centinela existe para impedir.

La regla del proyecto desde AUD-002 es "no se entra sin exclusion", pero poner
un lock aqui chocaba con algo peor: si `locked()` agotara su espera,
`record_run_failure` abortaria y el fallo NO se registraria. Perder un fallo
siempre es peor que perderlo raramente.

La salida elegida no arbitra entre esos dos males: ELIMINA el read-modify-write.
Cada etapa tiene su propio fichero en `logs/run_status/<etapa>.json`, asi que
escribir una NO requiere leer las demas y dos procesos concurrentes no comparten
destino. No hay lock porque ya no hay seccion critica. Y la proteccion de A-02
-- que un fallo de `settle` sobreviva a un fallo posterior de `run` y a su
limpieza -- deja de ser una precaucion escrita en el codigo y pasa a ser una
propiedad de la disposicion: son ficheros distintos.

El centinela vive en `logs/` porque `.gitignore` ya ignora ese directorio: es
estado operativo de una maquina, no algo que deba versionarse.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from sqp.logging_config import get_logger
from sqp.storage.atomic import atomic_write_json

log = get_logger("sqp.run_status")

STATUS_DIRNAME = "run_status"
# LEGADO: el fichero unico anterior a B-7. Se sigue LEYENDO y se migra, para que
# un centinela escrito por la version previa no deje de avisar tras actualizar.
STATUS_FILENAME = "last_run_status.json"

# El nombre de etapa pasa a formar parte de una RUTA, cosa que antes no ocurria
# -- viajaba DENTRO del JSON --, asi que ahora tiene que validarse: un
# `../../algo` escribiria fuera de `logs/`. Las etapas reales son constantes del
# repositorio (`scripts/run_status.py:STAGES`), asi que esto no rechaza ningun
# uso legitimo; es el riesgo que introduce el cambio de disposicion, cerrado en
# el mismo commit que lo introduce.
_ETAPA_VALIDA = re.compile(r"[a-z0-9_]{1,40}")


def _validar_etapa(stage: str) -> str:
    s = str(stage)
    if not _ETAPA_VALIDA.fullmatch(s):
        raise ValueError(
            f"nombre de etapa invalido: {stage!r}. Debe ser [a-z0-9_] y como "
            f"mucho 40 caracteres; ahora forma parte de una ruta.")
    return s


def _dir(root: Path) -> Path:
    return Path(root) / "logs" / STATUS_DIRNAME


def stage_path(root: Path, stage: str) -> Path:
    """Fichero centinela de una etapa. Publico a proposito: lo usan las pruebas
    y documenta de forma ejecutable donde vive cada aviso."""
    return _dir(root) / f"{_validar_etapa(stage)}.json"


def _legado(root: Path) -> Path:
    return Path(root) / "logs" / STATUS_FILENAME


def _leer_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Centinela ilegible (%s): %s. Se ignora.", p.name, exc)
        return None


def _etapas_del_legado(root: Path) -> dict:
    """Etapas del fichero unico anterior. Absorbe tambien el formato PLANO
    (`{"failed": ..., "stage": ...}`), que es aun mas viejo."""
    p = _legado(root)
    if not p.exists():
        return {}
    data = _leer_json(p)
    if not isinstance(data, dict):
        return {}
    stages = data.get("stages")
    if isinstance(stages, dict):
        return {k: v for k, v in stages.items() if isinstance(v, dict)}
    if data.get("failed") and data.get("stage") is not None:
        return {str(data["stage"]): data}
    return {}


def _migrar_legado(root: Path) -> None:
    """Reparte el fichero unico en uno por etapa y lo retira. Idempotente.

    El ORDEN importa: primero se escriben los ficheros por etapa y solo despues
    se borra el legado. Si el proceso muere en medio, `_read_stages` une las dos
    fuentes, asi que no se pierde ningun aviso -- como mucho se migra dos veces,
    que es inocuo. Al reves habria una ventana en la que el aviso no esta en
    ningun sitio, que es justo lo que este modulo no puede permitirse.
    """
    p = _legado(root)
    if not p.exists():
        return
    entradas = _etapas_del_legado(root)
    if entradas:
        _dir(root).mkdir(parents=True, exist_ok=True)
    for etapa, entrada in entradas.items():
        if not _ETAPA_VALIDA.fullmatch(str(etapa)):
            log.warning("Etapa con nombre invalido en el centinela legado (%r); "
                        "no se migra.", etapa)
            continue
        destino = stage_path(root, etapa)
        if not destino.exists():        # el formato vigente manda
            atomic_write_json(entrada, destino, sort_keys=False)
    p.unlink(missing_ok=True)
    if entradas:
        log.info("Centinela legado repartido en %d fichero(s) por etapa.",
                 len(entradas))


def record_run_failure(root: Path, stage: str, exit_code: int) -> Path:
    """Registra que la etapa `stage` fallo con `exit_code`.

    Escribe UNICAMENTE el fichero de su etapa: no lee ni reescribe las demas,
    asi que dos BAT que fallen a la vez no pueden pisarse (B-7).

    Distinguir la etapa importa porque las consecuencias no son iguales: un
    fallo en la liquidacion ABORTA el run diario (para no sobrescribir picks sin
    liquidar), mientras que uno de la validacion OOS mensual no detiene nada.

    Las etapas validas las enumera `scripts/run_status.py:STAGES`. Desde
    AUD-MED-003 (2026-09-06) no son solo las dos de la cadena diaria: tambien
    registran centinela `validate_oos`, `backfill`, `capture_close` y
    `refresh_ml`. Antes no podian, y por eso `SQP_Validate_OOS_Cdev` llevaba
    fallando desde el 2026-09-01 sin que nada lo dijera.
    """
    stage = _validar_etapa(stage)
    _migrar_legado(root)
    out = stage_path(root, stage)
    out.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "failed": True,
        "stage": stage,
        "exit_code": int(exit_code),
        "failed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    # Escritura ATOMICA (AUD-2026-09-08b): con `write_text` directo sobre el
    # destino, morir a mitad deja JSON truncado, el lector lo declara ilegible y
    # EL FALLO RECIEN REGISTRADO DESAPARECE.
    atomic_write_json(entry, out, sort_keys=False)
    log.error("Run diario FALLIDO en la etapa '%s' (exit %s); centinela -> %s",
              stage, exit_code, out)
    return out


def _read_stages(root: Path) -> dict:
    """Fallos vigentes indexados por etapa, uniendo el formato vigente -- un
    fichero por etapa -- con el legado que aun no se haya migrado. Ante la misma
    etapa en ambos, manda el fichero por etapa."""
    stages: dict = dict(_etapas_del_legado(root))
    for f in sorted(_dir(root).glob("*.json")):
        entrada = _leer_json(f)
        if isinstance(entrada, dict):
            stages[f.stem] = entrada
    return stages


def clear_run_status(root: Path, stage: str | None = None) -> bool:
    """Borra el centinela tras un run correcto. Idempotente.

    Con `stage` borra SOLO el fichero de esa etapa. Lo necesitan TODOS los BAT:
    cada uno arregla las suyas y borrar el centinela entero dejaria sin avisar
    los fallos de las demas.

    Sin `stage` se borran TODAS. Eso era lo correcto para `DIARIO_COMPLETO.bat`
    mientras solo existian `settle` y `run` y ese bat ejecutaba las dos. Desde
    que el centinela cubre siete etapas (AUD-MED-003 y KI-036, 2026-09-06) ya NO
    lo es: un run diario correcto habria apagado en silencio la alarma de
    `validate_oos`, `backfill`, `capture_close` o `refresh_ml`, que ese bat no
    arregla. `DIARIO_COMPLETO.bat` limpia sus tres etapas una por una. El
    borrado total se conserva para uso manual -- reparar el centinela a mano
    tras un incidente --, no para el flujo diario.

    Devuelve True si habia centinela y se borro.
    """
    _migrar_legado(root)
    if stage is None:
        borrado = False
        for f in sorted(_dir(root).glob("*.json")):
            f.unlink(missing_ok=True)
            borrado = True
        return borrado
    p = stage_path(root, stage)
    if not p.exists():
        return False          # el fallo registrado es de OTRA etapa: no se toca
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
    # Con fallos en varias etapas se devuelve el de LIQUIDACION: aborta el run
    # para no sobrescribir picks sin liquidar, asi que es el que manda. La forma
    # devuelta sigue siendo plana (`failed`/`stage`/`exit_code`/`failed_at`)
    # porque `health.py` y el banner del tablero leen esas claves.
    for name in ("settle", "run"):
        if name in stages:
            return dict(stages[name], stages=sorted(stages))
    first = sorted(stages)[0]
    return dict(stages[first], stages=sorted(stages))
