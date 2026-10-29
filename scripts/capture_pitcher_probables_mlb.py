#!/usr/bin/env python
"""Captura prospectiva de los abridores probables de MLB con nuestra marca de
hora UTC. Envoltorio CLI fino; ver `sqp.pipeline.pitcher_probables_capture.run`
(implementacion y docstring, comprobable sin CLI ni red).

Pensado para correr desde `CAPTURE_CLOSE.bat` (cada 30 min).

Ejemplo:
  python scripts/capture_pitcher_probables_mlb.py --source-run capture
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqp.logging_config import get_logger
from sqp.pipeline.pitcher_probables_capture import run

log = get_logger("sqp.capture_pitcher_probables_mlb")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source-run", default="capture", choices=["capture", "daily"],
                     help="Marca el origen de la fila (por defecto 'capture').")
    args = ap.parse_args()
    seen, appended = run(args.source_run)
    log.info("Captura de abridores probables MLB: %d lado(s) de partido no "
              "comenzado con lanzador, %d fila(s) nueva(s)/cambiada(s) guardadas.",
              seen, appended)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
