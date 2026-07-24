import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

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
