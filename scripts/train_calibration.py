#!/usr/bin/env python
"""Train per-(league, market) probability calibrators from the pick history.

Reads data/processed/pick_history.csv (built by scripts/build_pick_history.py),
and for every (league, market) with enough graded bets fits an isotonic + beta
calibrator with a TEMPORAL split (earlier games train, most recent validate),
persisting them under data/models/. Prints the out-of-sample ECE before vs after
so you can see where calibration actually helps before enabling it.

  python scripts/train_calibration.py
  python scripts/train_calibration.py --min-n 60

Calibration is OFF in the live pipeline until you set calibration.enabled: true
(configs/default.yaml) or CALIBRATION_ENABLED=1. These calibrators produce
calibrated ESTIMATED probabilities -- not certainties, not a profit guarantee.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.audit.patterns import build_pick_history, load_pick_history
from sqp.calibration.calibrator import MODELS_DIR, train_market_calibrators
from sqp.logging_config import get_logger

log = get_logger("sqp.train_calibration")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-n", type=int, default=40,
                    help="Minimum graded bets per (league, market) to calibrate")
    ap.add_argument("--rebuild", action="store_true",
                    help="Rebuild pick_history.csv from the backtest first")
    args = ap.parse_args()

    hist = build_pick_history(write=True) if args.rebuild else load_pick_history()
    if hist.empty:
        log.warning("pick_history vacio: corre scripts/build_pick_history.py "
                    "(o usa --rebuild) antes de calibrar.")
        return 1

    results = train_market_calibrators(hist, min_n=args.min_n)
    trained = [r for r in results if r.get("trained")]
    skipped = [r for r in results if not r.get("trained")]

    print(f"\n=== CALIBRADORES POR (liga, mercado) -> {MODELS_DIR} ===")
    print(f"grupos: {len(results)} | entrenados: {len(trained)} | "
          f"omitidos (<{args.min_n} graduados): {len(skipped)}")
    if trained:
        print("\nliga       mercado   n_val   ECE_antes  ECE_despues  delta    iso")
        for r in sorted(trained, key=lambda x: (x["league"], x["market"])):
            delta = r["raw_val_ece"] - r["cal_val_ece"]
            mark = "MANTENIDO" if r.get("iso_persisted") else "DESCARTADO"
            print(f"{r['league']:<10} {r['market']:<8} {r['n_val']:>5}   "
                  f"{r['raw_val_ece']:>8.4f}  {r['cal_val_ece']:>10.4f}  "
                  f"{delta:>+7.4f}  {mark}")
    if skipped:
        small = ", ".join(f"{r['league']}/{r['market']}({r['n']})" for r in skipped)
        print(f"\nomitidos (<{args.min_n} graduados, sin modelo): {small}")

    dropped = [r for r in trained if not r.get("iso_persisted")]
    if dropped:
        names = ", ".join(f"{r['league']}/{r['market']}" for r in dropped)
        print(f"\nAuto-descartados (la calibracion EMPEORABA el ECE OOS, quedan "
              f"sin calibrar / no-op): {names}")
    print("\nLa calibracion produce probabilidades estimadas calibradas, no "
          "certezas ni garantia de ganancia. Actívala solo si el ECE OOS mejora.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
