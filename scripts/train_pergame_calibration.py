#!/usr/bin/env python
"""Calibracion per-game del moneyline: fit sandbox + evaluacion cruzada.

Entrena iso+beta sobre los pares per-game del walk-forward (miles de juegos,
misma model_probability pura que sirve produccion) bajo la clave SANDBOX
"<liga>_h2h_pergame", SOLO en staging: produccion aplica "<liga>_h2h", asi
que nada de esto llega a live. Luego evalua el candidato sobre la cola
temporal de los picks h2h liquidados (distribucion de servicio) contra el
raw y el calibrador live vigente.

  python scripts/train_pergame_calibration.py --leagues mlb
  python scripts/train_pergame_calibration.py --leagues mlb --warmup 100

Adoptar el candidato (cambiar la fuente del retrain diario) es una decision
humana aparte, con esta evidencia delante. Solo probabilidades estimadas.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.calibration.pergame import (cross_evaluate_on_settled,
                                     train_pergame_calibrator)
from sqp.logging_config import get_logger

log = get_logger("sqp.pergame_calibration")


def _fmt(block: dict | None) -> str:
    if block is None:
        return "(sin candidato)"
    return (f"ECE {block['ece']:.4f} | Brier {block['brier']:.4f} | "
            f"prob media {block['mean_prob']:.4f} | acierto {block['hit_rate']:.4f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", nargs="+", required=True)
    ap.add_argument("--warmup", type=int, default=60)
    ap.add_argument("--val-fraction", type=float, default=0.20)
    args = ap.parse_args()
    failures = 0
    for league in args.leagues:
        print(f"\n=== {league.upper()} — calibracion per-game (sandbox) ===")
        try:
            r = train_pergame_calibrator(league, warmup=args.warmup,
                                         val_fraction=args.val_fraction)
        except (ValueError, KeyError) as exc:
            print(f"no entrenable: {exc}")
            failures += 1
            continue
        print(f"juegos: {r['n_games']} | filas train {r['n_train']} / val "
              f"{r['n_val']} (eventos val {r['n_val_events']})")
        print(f"raw val: ECE {r['raw_val_ece']:.4f} | Brier {r['raw_val_brier']:.4f}")
        print(f"iso val: ECE {r['val_metrics']['ece']:.4f} | Brier "
              f"{r['val_metrics']['brier_score']:.4f} | gate {r['iso_gate']} "
              f"-> {'STAGED' if r['iso_persisted'] else 'DROPPED'}")
        print(f"beta val: ECE {r['beta_val_ece']:.4f} | Brier "
              f"{r['beta_val_brier']:.4f} | gate {r['beta_gate']} "
              f"-> {'STAGED' if r['beta_persisted'] else 'DROPPED'}")
        print(f"mejor metodo (staging): {r['best_method']}")
        ev = cross_evaluate_on_settled(league)
        print(f"\n-- evaluacion cruzada sobre picks h2h liquidados "
              f"(cola {ev['n_eval']} de {ev['n_settled']}) --")
        print(f"raw:      {_fmt(ev['raw'])}")
        print(f"per-game: {_fmt(ev['pergame'])}")
        print(f"live:     {_fmt(ev['live'])}")
        if ev["pergame"] and ev["raw"]:
            better = (ev["pergame"]["ece"] < ev["raw"]["ece"]
                      and ev["pergame"]["brier"] <= ev["raw"]["brier"] + 1e-9)
            print("veredicto preliminar: el candidato per-game "
                  + ("MEJORA la distribucion de servicio (revisar adopcion)"
                     if better else "NO mejora la distribucion de servicio"))
    print("\nCandidatos solo en staging bajo clave *_h2h_pergame; produccion "
          "no los aplica. Probabilidades estimadas, nunca certezas.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
