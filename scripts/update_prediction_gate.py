"""Reescribe data/bets/prediction_gate.json, la regla de salida por mercado.

Un (liga, mercado) queda aprobado para stake real solo si su modelo PURO bate al
mercado en test de signo pareado FUERA DE MUESTRA (n >= 300 no empatadas,
p < 0.05) y su EV a stake plano es positivo. Default-deny: lo que no aparece o no
pasa, va a stake 0.

Fuente: el stream servido graduado (todos los lados priceados, sin sesgo de
seleccion), filtrado a partidos POSTERIORES al pre-registro del 2026-08-16.

Solo lectura sobre los datos + escritura del registro. No gasta cuota de API.
Pensado para correr tras la liquidacion diaria, junto a la auditoria CLV.

Histeresis del pre-registro: un corte que paso el gate y luego lo perdio queda
con el PESTILLO armado (latched) y no reentra aunque vuelva a cumplir los
criterios. Solo una liberacion humana explicita lo desarma; la reentrada la
decide la siguiente evaluacion, no la liberacion.

Criterio: docs/research/2026-08-16-preregistro-regla-de-salida.md

Uso:
    PYTHONPATH=src python scripts/update_prediction_gate.py
    PYTHONPATH=src python scripts/update_prediction_gate.py --dry-run
    PYTHONPATH=src python scripts/update_prediction_gate.py \
        --release "brasileirao|totals" --by "Carlos" --note "revisado a mano"
"""
from __future__ import annotations

import argparse
import sys


from sqp.config import ROOT
from sqp.risk.prediction_gate import (PREDICTION_GATE_ALPHA,
                                      PREDICTION_GATE_LATCH_LOG,
                                      PREDICTION_GATE_MIN_N, VALIDATION_START,
                                      evaluate_markets, load_prediction_gate,
                                      release_prediction_gate_latch,
                                      write_prediction_gate)
from sqp.storage.served_store import ServedStore


def _release(key: str, by: str | None, note: str) -> int:
    if "|" not in key:
        print("--release espera la clave 'liga|mercado', p. ej. 'brasileirao|totals'.")
        return 2
    if not by or not by.strip():
        print("--release exige --by con la identidad de quien revisa "
              "(rastro auditable).")
        return 2
    league, market = key.split("|", 1)
    bets_dir = ROOT / "data" / "bets"
    if release_prediction_gate_latch(bets_dir, league, market,
                                     released_by=by, note=note):
        print(f"Pestillo LIBERADO para {key} por {by.strip()}. La reentrada la "
              "decide la proxima evaluacion del gate, no esta liberacion.")
        print(f"Rastro: {bets_dir / PREDICTION_GATE_LATCH_LOG}")
        return 0
    print(f"{key} no tiene pestillo armado (o no existe en el registro): "
          "nada que liberar.")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="evalua y muestra, pero no escribe el registro")
    ap.add_argument("--min-n", type=int, default=PREDICTION_GATE_MIN_N)
    ap.add_argument("--alpha", type=float, default=PREDICTION_GATE_ALPHA)
    ap.add_argument("--release", metavar="LIGA|MERCADO",
                    help="libera el pestillo de un corte (revision humana)")
    ap.add_argument("--by", help="identidad de quien libera (obligatorio con --release)")
    ap.add_argument("--note", default="", help="nota opcional para el rastro")
    args = ap.parse_args()

    if args.release:
        return _release(args.release, args.by, args.note)

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
        print(f"\nCumplen los criterios estadisticos: {len(ok)} de {len(decided)}")
        for r in ok.itertuples():
            print(f"  {r.league}/{r.market}: {r.wins}/{r.n} "
                  f"(p={r.p_value:.4f}, EV={r.ev_flat:+.4f})")
        print("La decision FINAL (con el pestillo aplicado) es la del registro "
              "escrito, no esta tabla.")

    if args.dry_run:
        print("\n[dry-run] registro NO escrito.")
        return 0
    path = write_prediction_gate(graded, ROOT / "data" / "bets",
                                 min_n=args.min_n, alpha=args.alpha)
    print(f"\nRegistro escrito: {path}")
    gate = load_prediction_gate(ROOT / "data" / "bets")
    allowed = sorted(k for k, e in gate.items()
                     if isinstance(e, dict) and e.get("allowed")
                     and not e.get("latched"))
    latched = sorted(k for k, e in gate.items()
                     if isinstance(e, dict) and e.get("latched"))
    print("Aprobados para stake real (final): "
          + (", ".join(allowed) if allowed else "ninguno (default-deny)"))
    if latched:
        print("Pestillos armados (no reentran sin revision humana --release): "
              + ", ".join(latched))
    print("Probabilidades ESTIMADAS. Pasar el gate no promete rentabilidad: "
          "es la condicion minima para arriesgar capital.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
