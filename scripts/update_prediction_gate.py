"""Reescribe data/bets/prediction_gate.json, la regla de salida por mercado.

Un (liga, mercado) queda aprobado para stake real solo si su modelo PURO bate al
mercado en test de signo pareado FUERA DE MUESTRA (n >= 300 no empatadas,
p < 0.05) y su EV a stake plano es positivo. Default-deny: lo que no aparece o no
pasa, va a stake 0.

Fuente: el stream servido graduado (todos los lados priceados, sin sesgo de
seleccion), filtrado a partidos POSTERIORES al pre-registro del 2026-08-16.

Solo lectura sobre los datos + escritura del registro. No gasta cuota de API.
Pensado para correr tras la liquidacion diaria, junto a la auditoria CLV.

Criterio: docs/research/2026-08-16-preregistro-regla-de-salida.md

Uso:
    PYTHONPATH=src python scripts/update_prediction_gate.py
    PYTHONPATH=src python scripts/update_prediction_gate.py --dry-run
"""
from __future__ import annotations

import argparse
import sys


from sqp.config import ROOT
from sqp.risk.prediction_gate import (PREDICTION_GATE_ALPHA,
                                      PREDICTION_GATE_MIN_N, VALIDATION_START,
                                      evaluate_markets, write_prediction_gate)
from sqp.storage.served_store import ServedStore


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="evalua y muestra, pero no escribe el registro")
    ap.add_argument("--min-n", type=int, default=PREDICTION_GATE_MIN_N)
    ap.add_argument("--alpha", type=float, default=PREDICTION_GATE_ALPHA)
    args = ap.parse_args()

    graded = ServedStore(ROOT).load_all_graded()
    print(f"Stream servido graduado: {len(graded)} filas")
    print(f"Ventana de validacion: partidos POSTERIORES a {VALIDATION_START}")
    print(f"Criterio: n >= {args.min_n} no empatadas, p < {args.alpha}, EV > 0\n")

    decided = evaluate_markets(graded, min_n=args.min_n, alpha=args.alpha)
    if decided.empty:
        print("Ningun (liga, mercado) tiene filas dentro de la ventana de "
              "validacion todavia. Default-deny: ningun mercado lleva stake.")
    else:
        print(decided.to_string(index=False,
                                float_format=lambda v: f"{v:.4f}"))
        ok = decided[decided["allowed"]]
        print(f"\nAprobados para stake real: {len(ok)} de {len(decided)}")
        for r in ok.itertuples():
            print(f"  {r.league}/{r.market}: {r.wins}/{r.n} "
                  f"(p={r.p_value:.4f}, EV={r.ev_flat:+.4f})")

    if args.dry_run:
        print("\n[dry-run] registro NO escrito.")
        return 0
    path = write_prediction_gate(graded, ROOT / "data" / "bets",
                                 min_n=args.min_n, alpha=args.alpha)
    print(f"\nRegistro escrito: {path}")
    print("Probabilidades ESTIMADAS. Pasar el gate no promete rentabilidad: "
          "es la condicion minima para arriesgar capital.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
