"""Gate local de tests del evento Stop (lo invoca `run-tests-on-stop.sh`).

POR QUE EXISTE (CLAUDE-005 / H-2, 2026-10-14). El hook corria
`pytest tests/ -m "not slow"` con un autoacotado de 1080 s. Medido el
2026-10-14 con ese comando exacto: 2946 passed en 1080,43 s -- el 100 % del
presupuesto. Serie del mismo subconjunto: 270,73 s (2026-09-04), 489,76 s
(09-18), 796,09 s (09-22), 1080,43 s (10-14). El `timeout` cortaba siempre y el
gate no daba veredicto nunca. Ademas, sin `pytest` en el PATH el hook BORRABA el
centinela sin haber comprobado nada.

DOS SUITES:

- Suite rapida OBLIGATORIA: ``-m "not slow and not heavy"``. Es la que se
  ejecuta en cada Stop con centinela.
- ``heavy``: modulos no-`slow` pero caros (los marca `pytestmark` en cada
  fichero; registro en `pyproject.toml`). Fuera de la suite rapida, pero se
  ejecutan aqui los RELACIONADOS con los ficheros modificados (ver
  `related_heavy_modules`), con el presupuesto que sobre. A mano:
  ``PYTHONPATH=src pytest -m heavy``.
- ``slow``: nunca aqui. CI corre la suite COMPLETA (`pytest -q`, sin `-m`).

TRES VEREDICTOS, nunca confundidos:

- PASS: la suite rapida (y los heavy relacionados, si los hay) termino en
  verde. Borra el centinela. El mensaje dice QUE se comprobo: no es la suite
  completa.
- FAIL: tests en rojo o error de coleccion (pytest rc 1 o 2). exit 2: bloquea
  el cierre del turno y devuelve el fallo al modelo. Conserva el centinela.
- NO VERIFICADO: no hay veredicto (presupuesto agotado, pytest ausente,
  rc 3/4/5 u otro, git ilegible, fallo al lanzar el proceso). exit 0: NO
  BLOQUEA el cierre del turno -- el modelo no puede acortar la suite a mitad de
  turno y bloquear solo produciria un bucle --, pero CONSERVA el centinela
  pendiente y lo anuncia al usuario (`systemMessage`) y por stderr. NO
  VERIFICADO no es una validacion satisfactoria y nunca se presenta como tal.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

# Por debajo del timeout del hook (1200 s en settings.json) para que el veredicto
# salga de aqui y no de un proceso matado por el harness, que no ejecuta ni una
# linea mas.
PRESUPUESTO_S = 1080
MARCADOR = Path(".claude/.tests-pending")
EXPRESION_RAPIDA = "not slow and not heavy"

PASS = "PASS"
FAIL = "FAIL"
NO_VERIFICADO = "NO VERIFICADO"

# Codigos de salida de pytest que SI son un veredicto en rojo: 1 = tests
# fallidos; 2 = interrumpido, que con `-x` incluye los errores de coleccion (un
# ImportError introducido por la edicion es un fallo real). 3 (error interno),
# 4 (uso) y 5 (nada recogido) no dicen nada de la correccion del codigo.
RC_FALLO = (1, 2)


@dataclass(frozen=True)
class Ejecucion:
    rc: int | None  # None = no termino (presupuesto agotado o no se lanzo)
    salida: str
    motivo: str = ""


def clasificar(ejecucion: Ejecucion) -> str:
    if ejecucion.rc == 0:
        return PASS
    if ejecucion.rc in RC_FALLO:
        return FAIL
    return NO_VERIFICADO


def pytest_disponible() -> bool:
    return importlib.util.find_spec("pytest") is not None


def comando_rapido() -> list[str]:
    return [sys.executable, "-m", "pytest", "tests/", "-q", "-x", "--maxfail=1",
            "-m", EXPRESION_RAPIDA]


def comando_heavy(modulos: Sequence[str]) -> list[str]:
    return [sys.executable, "-m", "pytest", *modulos, "-q", "-x", "--maxfail=1",
            "-m", "not slow"]


def ejecutar(cmd: Sequence[str], presupuesto_s: float, cwd: Path) -> Ejecucion:
    if presupuesto_s <= 0:
        return Ejecucion(None, "", "presupuesto agotado antes de empezar")
    env = {**os.environ, "PYTHONPATH": "src"}
    try:
        res = subprocess.run(list(cmd), cwd=cwd, env=env, capture_output=True,
                             text=True, encoding="utf-8", errors="replace",
                             timeout=presupuesto_s)
    except subprocess.TimeoutExpired as exc:
        parcial = exc.stdout or ""
        if isinstance(parcial, bytes):
            parcial = parcial.decode("utf-8", "replace")
        return Ejecucion(None, parcial,
                         f"la suite no cabe en su presupuesto ({presupuesto_s:.0f} s)")
    except OSError as exc:
        return Ejecucion(None, "", f"no se pudo lanzar pytest: {exc}")
    return Ejecucion(res.returncode, (res.stdout or "") + (res.stderr or ""))


def ficheros_modificados(cwd: Path) -> list[str] | None:
    """Rutas cambiadas respecto a HEAD (incluye no rastreadas). None = ilegible."""
    try:
        res = subprocess.run(["git", "status", "--porcelain", "-uall"], cwd=cwd,
                             capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if res.returncode != 0:
        return None
    rutas = []
    for linea in res.stdout.splitlines():
        ruta = linea[3:].split(" -> ")[-1].strip().strip('"')
        if ruta:
            rutas.append(ruta.replace("\\", "/"))
    return rutas


def modulos_heavy(cwd: Path) -> list[str]:
    """Modulos de test con `pytestmark = pytest.mark.heavy` a nivel de modulo."""
    patron = re.compile(r"^pytestmark\s*=.*\bmark\.heavy\b", re.MULTILINE)
    return sorted(p.relative_to(cwd).as_posix()
                  for p in (cwd / "tests").rglob("test_*.py")
                  if patron.search(p.read_text(encoding="utf-8", errors="replace")))


def _referencias(ruta: str) -> list[re.Pattern[str]]:
    """Como citaria un test al fichero `ruta` (import o ruta al script)."""
    if not ruta.endswith(".py"):
        return []
    partes = ruta[:-3].split("/")
    if partes[0] == "src" and len(partes) >= 3:
        mod = partes[1:]
        if mod[-1] == "__init__":
            mod = mod[:-1]
        punteado = re.escape(".".join(mod))
        pats = [re.compile(rf"\b{punteado}\b")]
        if len(mod) >= 2:
            pats.append(re.compile(
                rf"from\s+{re.escape('.'.join(mod[:-1]))}\s+import\s+[^\n]*\b{re.escape(mod[-1])}\b"))
        return pats
    # `scripts/`, `.claude/hooks/` y demas: los tests los cargan por RUTA, asi
    # que se reconocen por el nombre del fichero (`"fable_gate.py"`).
    return [re.compile(rf"\b{re.escape(partes[-1])}\.py\b")]


def related_heavy_modules(modificados: Sequence[str], heavy: Sequence[str],
                          cwd: Path) -> list[str]:
    """Heavy a ejecutar: el propio modulo editado, o uno que cita un fichero
    editado de `src/` (import directo) o de fuera de `src/` -- `scripts/`,
    `.claude/hooks/` -- por su nombre de fichero.

    Solo dependencias DIRECTAS: un cambio en un modulo que el script importa de
    forma transitiva no dispara el heavy. Esa cobertura la da CI, que corre la
    suite completa, o `pytest -m heavy` a mano.
    """
    elegidos = []
    for modulo in heavy:
        if modulo in modificados:
            elegidos.append(modulo)
            continue
        texto = (cwd / modulo).read_text(encoding="utf-8", errors="replace")
        if any(p.search(texto) for ruta in modificados for p in _referencias(ruta)):
            elegidos.append(modulo)
    return elegidos


def _cola(texto: str, n: int) -> str:
    return "\n".join(texto.rstrip().splitlines()[-n:])


def _emitir(veredicto: str, detalle: str, cola: str = "") -> None:
    if veredicto == FAIL:
        print(f"Tests locales: FAIL. {detalle}\n{cola}", file=sys.stderr)
        return
    if veredicto == NO_VERIFICADO:
        detalle = (f"{detalle} Los cambios de este turno quedan SIN comprobar por "
                   "la suite local; el centinela .claude/.tests-pending sigue "
                   "pendiente. Esto NO es una validacion satisfactoria.")
        if cola:
            print(f"Ultimas lineas:\n{cola}", file=sys.stderr)
    mensaje = f"Tests locales: {veredicto}. {detalle}"
    print(mensaje, file=sys.stderr)
    print(json.dumps({"systemMessage": mensaje}, ensure_ascii=False))


def main(stdin: str, cwd: Path, presupuesto_s: float = PRESUPUESTO_S) -> int:
    try:
        activo = json.loads(stdin or "{}").get("stop_hook_active", False)
    except (ValueError, AttributeError):
        activo = False
    # Guard anti-bucle: este Stop lo provoco un bloqueo previo. El centinela se
    # conserva; el siguiente turno lo volvera a intentar.
    if activo is True:
        return 0
    if not (cwd / MARCADOR).is_file():
        return 0
    if not pytest_disponible():
        _emitir(NO_VERIFICADO, f"pytest no esta disponible en {sys.executable}.")
        return 0

    inicio = time.monotonic()
    rapida = ejecutar(comando_rapido(), presupuesto_s, cwd)
    veredicto = clasificar(rapida)
    if veredicto == FAIL:
        _emitir(FAIL, "La suite rapida (not slow and not heavy) tiene tests en "
                "rojo tras las ediciones de este turno:", _cola(rapida.salida, 25))
        return 2
    if veredicto == NO_VERIFICADO:
        motivo = rapida.motivo or f"pytest termino con rc={rapida.rc} sin veredicto."
        _emitir(NO_VERIFICADO, f"Suite rapida: {motivo}", _cola(rapida.salida, 15))
        return 0
    resumen = _cola(rapida.salida, 1)

    modificados = ficheros_modificados(cwd)
    if modificados is None:
        _emitir(NO_VERIFICADO, f"Suite rapida en verde ({resumen}), pero git no "
                "permite saber que tests heavy tocan los ficheros modificados.")
        return 0
    relacionados = related_heavy_modules(modificados, modulos_heavy(cwd), cwd)
    if relacionados:
        restante = presupuesto_s - (time.monotonic() - inicio)
        pesada = ejecutar(comando_heavy(relacionados), restante, cwd)
        v_heavy = clasificar(pesada)
        if v_heavy == FAIL:
            _emitir(FAIL, f"Heavy relacionados en rojo ({', '.join(relacionados)}):",
                    _cola(pesada.salida, 25))
            return 2
        if v_heavy == NO_VERIFICADO:
            motivo = pesada.motivo or f"pytest termino con rc={pesada.rc}."
            _emitir(NO_VERIFICADO, f"Suite rapida en verde ({resumen}), pero los "
                    f"heavy relacionados ({', '.join(relacionados)}) no dieron "
                    f"veredicto: {motivo}", _cola(pesada.salida, 15))
            return 0

    (cwd / MARCADOR).unlink(missing_ok=True)
    extra = (f" Heavy relacionados en verde: {', '.join(relacionados)}."
             if relacionados else " Ningun heavy relacionado con los ficheros modificados.")
    _emitir(PASS, f"Suite rapida (not slow and not heavy) en verde: {resumen}.{extra} "
            "Es la suite LOCAL; slow y el resto de heavy solo los ejecuta CI "
            "(o `PYTHONPATH=src pytest -m heavy` a mano).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.stdin.read(), Path.cwd()))
