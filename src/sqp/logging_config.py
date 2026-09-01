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
    `UnicodeEncodeError: '\\u0107'` (Cetkovic, US Open). Vive aqui y no en cada
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


def get_logger(name: str = "sqp") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    sh = logging.StreamHandler(sys.stdout); sh.setFormatter(fmt); logger.addHandler(sh)
    logdir = Path(__file__).resolve().parents[2] / "logs"
    if logdir.exists():
        # Rotacion: sqp.log crecia sin limite (auditoria 2026-07-24, M-3).
        fh = RotatingFileHandler(logdir / "sqp.log", maxBytes=5_000_000,
                                 backupCount=3, encoding="utf-8")
        fh.setFormatter(fmt); logger.addHandler(fh)
    return logger
