#!/usr/bin/env python
"""Registra o limpia el centinela de fallo del run diario (auditoria 2026-07-29, S-1).

Lo invocan los BAT de produccion:

    python scripts/run_status.py --fail --stage settle --exit-code 1
    python scripts/run_status.py --clear                    # las dos etapas
    python scripts/run_status.py --clear --only-stage run   # solo esa etapa

Siempre sale con 0: este script es instrumentacion de la alerta, y un fallo suyo
no debe alterar el codigo de salida real del pipeline ni enmascarar el error que
esta intentando registrar.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.config import ROOT
from sqp.monitoring.run_status import clear_run_status, record_run_failure


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--fail", action="store_true",
                   help="registrar que el run fallo")
    g.add_argument("--clear", action="store_true",
                   help="borrar el centinela tras un run correcto")
    ap.add_argument("--stage", default="run", choices=["settle", "run"],
                    help="etapa que fallo (default: run)")
    ap.add_argument("--only-stage", default=None, choices=["settle", "run"],
                    help="con --clear, borrar solo si el fallo registrado es de "
                         "esa etapa (para los BAT que arreglan una sola)")
    ap.add_argument("--exit-code", type=int, default=1)
    args = ap.parse_args()

    try:
        if args.clear:
            if clear_run_status(ROOT, args.only_stage):
                print("Centinela de run limpiado (ultimo run OK).")
            else:
                print("Sin centinela que limpiar para esa etapa.")
        else:
            path = record_run_failure(ROOT, stage=args.stage, exit_code=args.exit_code)
            print(f"FALLO registrado en {path}")
            print("El health check lo reportara como ERROR hasta el proximo run correcto.")
    except OSError as exc:
        # No propagar: el BAT ya esta en su rama de error y su exit code manda.
        print(f"[WARN] no se pudo actualizar el centinela: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
