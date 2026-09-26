#!/usr/bin/env python
"""Prospective capture of ESPN's NHL probable-starting-goalie announcements.
Thin CLI wrapper; see `sqp.pipeline.goalie_probables_capture.run` for the
implementation and docstring (testable without the CLI or the network).

Intended to run from `CAPTURE_CLOSE.bat` (every 30 min) and from the daily
run, per `docs/research/2026-09-26-preregistro-portero-nhl.md`, section 12 --
see this script's proposed `.bat` wiring in the implementation report (not
applied automatically: KI-036 requires it be committed before the 12:00 run,
and `.bat` changes are out of scope here).

Example:
  python scripts/capture_goalie_probables_nhl.py --source-run capture
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqp.logging_config import get_logger
from sqp.pipeline.goalie_probables_capture import run

log = get_logger("sqp.capture_goalie_probables_nhl")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source-run", default="capture", choices=["capture", "daily"],
                     help="Marca el origen de la fila (por defecto 'capture').")
    args = ap.parse_args()
    seen, appended = run(args.source_run)
    log.info("Captura de probables de porteros NHL: %d lado(s) de partido no "
              "comenzado con probable, %d fila(s) nueva(s)/cambiada(s) guardadas.",
              seen, appended)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
