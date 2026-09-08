import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

def consola_utf8() -> None:
    """Deja stdout/stderr en UTF-8 para que un nombre no-ASCII no tumbe un CLI.

    La consola de Windows es cp1252 y no puede imprimir un nombre eslavo. Los
    informes SIEMPRE se escribian bien (`write_text(..., encoding='utf-8')`); lo
    que reventaba era el eco por pantalla, con el fichero ya en disco. Como
    `DIARIO_COMPLETO.bat` marca esos pasos no bloqueantes, el fallo se tragaba
    con un [AVISO] y el operador veia el informe a medias sin saber por que.

    Reproducido el 2026-09-01 en `daily_picks.py` y `tipster_report.py`:
    `UnicodeEncodeError: '\u0107'` (Cetkovic, US Open). Vive aqui y no en cada
    script porque el modo de fallo dominante de este repo es la deriva entre
    copias.
    """
    for flujo in (sys.stdout, sys.stderr):
        # `reconfigure` solo existe en TextIOWrapper: un StringIO (tests) o un
        # flujo ya envuelto no lo tienen, y ahi no hay nada que arreglar.
        reconfigure = getattr(flujo, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


# UN SOLO handler de fichero por proceso, compartido por todos los loggers
# (AUD-HIGH-001, auditoria integral 2026-09-08, HIGH, REPRODUCIDO).
#
# `get_logger` creaba un `RotatingFileHandler` NUEVO por cada NOMBRE de logger,
# y hay ~50 nombres distintos (`sqp.bankroll`, `sqp.settle`, `sqp.vig`, ...) en
# 53 llamadas. Un solo proceso abria por tanto decenas de descriptores sobre el
# MISMO `logs/sqp.log`. Cuando uno intentaba rotar, `doRollover()` cerraba solo
# SU stream y llamaba a `os.rename`; en Windows los demas descriptores seguian
# abiertos y el rename fallaba con `WinError 32`.
#
# Y no es que no rotara: en `BaseRotatingHandler.emit` el `doRollover()` se
# llama ANTES de escribir y dentro del mismo `try`, asi que al lanzar se salta
# el `emit` y EL REGISTRO SE PIERDE.
#
# Medido el 2026-09-08 sobre produccion: `sqp.log` congelado en 4.999.946 bytes
# contra un `maxBytes` de 5.000.000, con `sqp.log.3` presente y `.1`/`.2`
# ausentes -- la rotacion murio a medio ciclo el 2026-09-06 a las 23:30 --, y
# 1.002 bloques `--- Logging error ---` en `logs/run_diario.log`, uno por
# registro descartado. Reproducido en aislamiento: con 1 handler salen 3
# backups y 0 errores; con 2 handlers sobre el mismo fichero salen 0 backups y
# 162 `PermissionError`, es decir 162 registros perdidos de 200.
#
# La correccion es compartir la INSTANCIA: un unico handler significa un unico
# descriptor abierto, que es la precondicion que `doRollover` necesita. Se
# comparte el objeto en vez de reorganizar la jerarquia de loggers (padre con
# handler + hijos propagando) porque asi NO cambia ninguna otra semantica: cada
# logger conserva su propia lista de handlers, su nivel y su propagacion, y no
# aparece el riesgo de lineas duplicadas. `logging.Handler` lleva su propio
# lock, asi que compartirlo entre loggers es seguro.
_file_handler: RotatingFileHandler | None = None
_file_handler_resuelto = False


def _shared_file_handler(fmt: logging.Formatter) -> RotatingFileHandler | None:
    """El `RotatingFileHandler` del proceso, creado como mucho una vez.

    Devuelve `None` cuando no hay directorio `logs/` (mismo comportamiento que
    antes: sin destino no se anade handler de fichero). El resultado se memoiza
    incluido el `None`, para no volver a mirar el disco en cada llamada.
    """
    global _file_handler, _file_handler_resuelto
    if _file_handler_resuelto:
        return _file_handler
    _file_handler_resuelto = True
    logdir = Path(__file__).resolve().parents[2] / "logs"
    if logdir.exists():
        # Rotacion: sqp.log crecia sin limite (auditoria 2026-07-24, M-3).
        fh = RotatingFileHandler(logdir / "sqp.log", maxBytes=5_000_000,
                                 backupCount=3, encoding="utf-8")
        fh.setFormatter(fmt)
        _file_handler = fh
    return _file_handler


def get_logger(name: str = "sqp") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    sh = logging.StreamHandler(sys.stdout); sh.setFormatter(fmt); logger.addHandler(sh)
    fh = _shared_file_handler(fmt)
    if fh is not None:
        logger.addHandler(fh)
    return logger
