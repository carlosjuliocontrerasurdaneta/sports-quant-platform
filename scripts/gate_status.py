"""gate_status.py — muestra qué tan cerca está cada mercado de pasar el prediction gate.

Condiciones del gate (src/sqp/risk/prediction_gate.py):
  1. n >= PREDICTION_GATE_MIN_N (300)
  2. binomtest(wins, n, 0.5, alternative='greater').pvalue < PREDICTION_GATE_ALPHA (0.05)
  3. mean(EV) > 0

Uso:
  python scripts/gate_status.py
  python scripts/gate_status.py --min-n 50
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

import pandas as pd
from scipy.stats import binomtest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sqp.risk.prediction_gate import PREDICTION_GATE_MIN_N, PREDICTION_GATE_ALPHA  # noqa: E402

MIN_N_GATE: int = PREDICTION_GATE_MIN_N
ALPHA: float = PREDICTION_GATE_ALPHA


def main() -> None:
    parser = argparse.ArgumentParser(description="Estado del prediction gate por mercado")
    parser.add_argument("--min-n", type=int, default=0,
                        help="Mostrar solo mercados con n >= este valor (default: 0 = todos)")
    args = parser.parse_args()

    ph = ROOT / "data" / "processed" / "pick_history.csv"
    if not ph.exists():
        print(f"ERROR: {ph} no encontrado. Ejecuta el run diario primero.")
        sys.exit(1)

    df = pd.read_csv(ph)
    settled = df[df["result"].isin(["win", "loss"])].copy()
    settled["implied_prob"] = 1.0 / settled["price_decimal"]
    settled["ev"] = settled["estimated_probability"] - settled["implied_prob"]
    settled["correct"] = (settled["result"] == "win").astype(int)

    rows = []
    for (league, market), g in settled.groupby(["league", "market"]):
        n = len(g)
        wins = int(g["correct"].sum())
        mean_ev = float(g["ev"].mean())
        hit_rate = wins / n

        try:
            p_val = binomtest(wins, n, 0.5, alternative="greater").pvalue
        except Exception:
            p_val = 1.0

        ev_ok = mean_ev > 0
        p_ok = p_val < ALPHA
        n_ok = n >= MIN_N_GATE

        blocks = []
        if not n_ok:
            blocks.append(f"n_falta={MIN_N_GATE - n}")
        if not p_ok:
            blocks.append(f"p={p_val:.3f}")
        if not ev_ok:
            blocks.append(f"EV={mean_ev:.4f}")

        rows.append({
            "mercado": f"{league}|{market}",
            "n": n,
            "wins": wins,
            "hit_rate": round(hit_rate, 3),
            "mean_ev": round(mean_ev, 4),
            "p_value": round(p_val, 4),
            "n_falta": max(0, MIN_N_GATE - n),
            "pasa": len(blocks) == 0,
            "bloqueos": ", ".join(blocks) if blocks else "—",
        })

    result = pd.DataFrame(rows)
    if args.min_n > 0:
        result = result[result["n"] >= args.min_n]

    result = result.sort_values(["pasa", "p_value", "n_falta"], ascending=[False, True, True])

    passes = result[result["pasa"]]
    fails = result[~result["pasa"]]

    print(f"\n=== PREDICTION GATE — umbral: n>={MIN_N_GATE}, p<{ALPHA}, EV>0 ===\n")

    if not passes.empty:
        print("PASAN EL GATE:")
        print(passes[["mercado", "n", "hit_rate", "mean_ev", "p_value"]].to_string(index=False))
        print()

    print(f"FALLAN ({len(fails)} mercados):")
    disp = fails[["mercado", "n", "hit_rate", "mean_ev", "p_value", "n_falta", "bloqueos"]]
    print(disp.to_string(index=False))
    print(f"\nTotal evaluados: {len(result)} | Pasan: {len(passes)} | Fallan: {len(fails)}")


if __name__ == "__main__":
    main()
