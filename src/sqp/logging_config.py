import logging
import sys
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
        fh = logging.FileHandler(logdir / "sqp.log", encoding="utf-8"); fh.setFormatter(fmt); logger.addHandler(fh)
    return logger
