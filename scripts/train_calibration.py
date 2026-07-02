#!/usr/bin/env python
"""Train per-(league, market) probability calibrators from settled live bets.

By default reads data/bets/settled_*.csv (opening-anchored live outcomes built
by SETTLE_ALL.bat) and calibrates the PURE model probability
(model_probability, pre market-blend -- the target daily.py serves since
research 2026-07-02); for every (league, market) with enough graded bets it
fits an isotonic + beta calibrator with a TEMPORAL split (earlier games train,
most recent validate), staging candidates under data/models/staging/. Prints the out-of-sample ECE
before vs after so you can see where calibration actually helps before
promoting a candidate into the live registry.

  python scripts/train_calibration.py
  python scripts/train_calibration.py --min-n 60

Use --source backtest to train from data/processed/pick_history.csv instead
(closing-anchored backtest replay; run scripts/build_pick_history.py first or
pass --rebuild). Note: the backtest source anchors to closing lines, so the
trained calibrator will not correct the opening-line overconfidence seen live.

Training NEVER touches the live registry: candidates land in staging and the
pipeline keeps applying whatever was last PROMOTED (scripts/promote_calibration.py,
a deliberate human step). With calibration.enabled: true and an empty live
registry (the current state), live application is a safe no-op. These calibrators
produce calibrated ESTIMATED probabilities -- not certainties, not a profit
guarantee.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.audit.patterns import build_pick_history, load_pick_history
from sqp.calibration.calibrator import (MODELS_DIR, _gate_label,
                                        train_market_calibrators)
from sqp.calibration.data import load_settled_training_history
from sqp.logging_config import get_logger

log = get_logger("sqp.train_calibration")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-n", type=int, default=40,
                    help="Minimum graded bets per (league, market) to calibrate")
    ap.add_argument("--rebuild", action="store_true",
                    help="Rebuild pick_history.csv from the backtest first")
    ap.add_argument("--source", choices=["settled", "backtest"], default="settled",
                    help="Datos de entrenamiento: 'settled' (apuestas liquidadas "
                         "en vivo, ancladas a la apertura -- corrige el desajuste "
                         "train/serve) o 'backtest' (historial anclado al cierre).")
    args = ap.parse_args()

    if args.source == "settled":
        if args.rebuild:
            log.warning("--rebuild solo aplica con --source backtest (reconstruye "
                        "pick_history); con 'settled' se IGNORA.")
        hist = load_settled_training_history()
        empty_msg = ("no hay apuestas liquidadas (data/bets/settled_*.csv): corre "
                     "SETTLE_ALL.bat antes de calibrar sobre settled.")
    else:
        hist = build_pick_history(write=True) if args.rebuild else load_pick_history()
        empty_msg = ("pick_history vacio: corre scripts/build_pick_history.py "
                     "(o usa --rebuild) antes de calibrar.")
    if hist.empty:
        log.warning(empty_msg)
        return 1

    # settled calibra p_model PURO (pre-blend, el objetivo que sirve daily.py);
    # backtest conserva la semantica legacy sobre la mezcla estimated_probability.
    prob_col = "model_probability" if args.source == "settled" else "estimated_probability"
    results = train_market_calibrators(hist, min_n=args.min_n, prob_col=prob_col)
    trained = [r for r in results if r.get("trained")]
    skipped = [r for r in results if not r.get("trained")]

    print(f"\n=== CALIBRADORES POR (liga, mercado) -> {MODELS_DIR} ===")
    print(f"grupos: {len(results)} | entrenados: {len(trained)} | "
          f"omitidos (<{args.min_n} graduados): {len(skipped)}")
    if trained:
        print("\nliga       mercado   n_val   ECE_antes  ECE_mejor  delta    metodo")
        for r in sorted(trained, key=lambda x: (x["league"], x["market"])):
            best = r.get("best_method")
            best_ece = ({"isotonic": r["cal_val_ece"], "beta": r["beta_val_ece"]}
                        .get(best, r["raw_val_ece"]))
            delta = r["raw_val_ece"] - best_ece
            label = best if best else "NINGUNO (no-op)"
            print(f"{r['league']:<10} {r['market']:<8} {r['n_val']:>5}   "
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
