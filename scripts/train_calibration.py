#!/usr/bin/env python
"""Train per-(league, market) probability calibrators from graded live serves.

By default reads the COMBINED serve-anchored history: settled live bets
(data/bets/settled_*.csv, built by SETTLE_ALL.bat) plus the graded per-event
served-probability stream (data/calibration/graded_*.csv -- every priced market
side the pipeline evaluated, not just placed picks), deduplicated so picks are
not double-weighted. It calibrates the PURE model probability
(model_probability, pre market-blend -- the target daily.py serves since
research 2026-07-02); for every (league, market) with enough graded bets it
fits an isotonic + beta calibrator with a TEMPORAL split (earlier games train,
most recent validate), staging candidates under data/models/staging/. Prints the out-of-sample ECE
before vs after so you can see where calibration actually helps before a
manual or gated automatic promotion into the live registry.

  python scripts/train_calibration.py
  python scripts/train_calibration.py --min-n 60

Use --source backtest to train from data/processed/pick_history.csv instead
(closing-anchored backtest replay; run scripts/build_pick_history.py first or
pass --rebuild). Note: the backtest source anchors to closing lines, so the
trained calibrator will not correct the opening-line overconfidence seen live.

This CLI NEVER touches the live registry: candidates land in staging. The daily
orchestrator may subsequently auto-promote only candidates that pass its OOS and
independent-event gates; `scripts/promote_calibration.py` remains the manual path.
Missing live entries are safe no-ops. These calibrators produce calibrated
ESTIMATED probabilities -- not certainties, not a profit guarantee.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.audit.patterns import build_pick_history, load_pick_history
from sqp.calibration.calibrator import (MODELS_DIR, _gate_label,
                                        train_market_calibrators)
from sqp.calibration.data import (load_calibration_training_history,
                                  load_served_training_history,
                                  load_settled_training_history)
from sqp.logging_config import get_logger

log = get_logger("sqp.train_calibration")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-n", type=int, default=40,
                    help="Minimum graded bets per (league, market) to calibrate")
    ap.add_argument("--rebuild", action="store_true",
                    help="Rebuild pick_history.csv from the backtest first")
    ap.add_argument("--source", choices=["combined", "settled", "served", "backtest"],
                    default="combined",
                    help="Datos de entrenamiento: 'combined' (default: apuestas "
                         "liquidadas + stream servido per-evento, deduplicado -- "
                         "misma fuente que el staging diario), 'settled' (solo "
                         "apuestas liquidadas en vivo), 'served' (solo el stream "
                         "per-evento graduado, muestra sin sesgo de seleccion) o "
                         "'backtest' (historial anclado al cierre).")
    args = ap.parse_args()

    if args.source != "backtest":
        if args.rebuild:
            log.warning("--rebuild solo aplica con --source backtest (reconstruye "
                        "pick_history); con '%s' se IGNORA.", args.source)
        loader = {"combined": load_calibration_training_history,
                  "settled": load_settled_training_history,
                  "served": load_served_training_history}[args.source]
        hist = loader()
        empty_msg = (f"fuente '{args.source}' vacia: corre SETTLE_ALL.bat (liquida "
                     "picks y gradua el stream servido) antes de calibrar.")
    else:
        hist = build_pick_history(write=True) if args.rebuild else load_pick_history()
        empty_msg = ("pick_history vacio: corre scripts/build_pick_history.py "
                     "(o usa --rebuild) antes de calibrar.")
    if hist.empty:
        log.warning(empty_msg)
        return 1

    # Las fuentes serve-anchored (combined/settled/served) calibran la creencia
    # PRE-BLEND que sirve produccion: `adjusted_probability` (= `_p_adj`, modelo
    # + capa de ajustes), con fallback por fila a `model_probability` para filas
    # de esquema antiguo -- el fallback lo aplica ya `_project_training`.
    # Backtest conserva a proposito la semantica legacy sobre la mezcla.
    #
    # Decia `model_probability` (AUD-006, Codex 2026-09-05). El contrato de
    # entrenamiento cambio el 2026-08-23 con la capa de ajustes -- `daily.py`
    # entrega `_p_adj` a `_decision_probability` y `stage_calibrators_from_settled`
    # entrena sobre `adjusted_probability` -- y este entrypoint no se actualizo
    # con el. Resultado: el camino MANUAL ajustaba la curva sobre una variable
    # distinta de la que aplica el camino DIARIO, para los mismos mercados. No
    # es nominal: 2.216 filas del stream graduado tienen las dos columnas
    # distintas. La promocion automatica esta desactivada en el YAML, lo que
    # acota la exposicion pero no la elimina: una promocion manual instalaria
    # una curva aprendida sobre otra cosa.
    prob_col = ("estimated_probability" if args.source == "backtest"
                else "adjusted_probability")
    results = train_market_calibrators(hist, min_n=args.min_n, prob_col=prob_col)
    trained = [r for r in results if r.get("trained")]
    skipped = [r for r in results if not r.get("trained")]

    print(f"\n=== CALIBRADORES POR (liga, mercado) -> {MODELS_DIR} ===")
    print(f"grupos: {len(results)} | entrenados: {len(trained)} | "
          f"omitidos (<{args.min_n} graduados): {len(skipped)}")
    if trained:
        print("\nliga       mercado   val_filas val_eventos  ECE_antes  ECE_mejor  delta    metodo")
        for r in sorted(trained, key=lambda x: (x["league"], x["market"])):
            best = r.get("best_method")
            best_ece = ({"isotonic": r["cal_val_ece"], "beta": r["beta_val_ece"]}
                        .get(best, r["raw_val_ece"]))
            delta = r["raw_val_ece"] - best_ece
            label = best if best else "NINGUNO (no-op)"
            print(f"{r['league']:<10} {r['market']:<8} {r['n_val']:>9} "
                  f"{r['n_val_events']:>11}  "
                  f"{r['raw_val_ece']:>8.4f}  {best_ece:>9.4f}  "
                  f"{delta:>+7.4f}  {label}")
    if skipped:
        small = ", ".join(f"{r['league']}/{r['market']}({r['n']})" for r in skipped)
        print(f"\nomitidos (<{args.min_n} graduados, sin modelo): {small}")

    dropped = [r for r in trained if not r.get("best_method")]
    if dropped:
        print("\nAuto-descartados (fallo alguna condicion del gate OOS; quedan "
              "sin calibrar / no-op):")
        for r in sorted(dropped, key=lambda x: (x["league"], x["market"])):
            print(f"  {r['league']}/{r['market']}: "
                  f"iso {_gate_label(False, r['iso_gate'])} | "
                  f"beta {_gate_label(False, r['beta_gate'])}")
    print("\nLa calibracion produce probabilidades estimadas calibradas, no "
          "certezas ni garantia de ganancia. Actívala solo si el ECE OOS mejora.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
