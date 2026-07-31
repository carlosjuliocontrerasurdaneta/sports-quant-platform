#!/usr/bin/env python
"""Marcador: probabilidades del modelo frente a las del mercado.

Responde la pregunta de la idea fundacional del proyecto -- "determinar la
probabilidad real con la mayor precision posible" -- comparando Brier y log loss
del modelo contra la no-vig del consenso, sobre las MISMAS filas.

El mercado es el patron de medida, no el rival: su no-vig es el mejor estimador
disponible de la probabilidad real, asi que empatar ya es exigente.

  python scripts/model_vs_market.py
  python scripts/model_vs_market.py --by league market --min-rows 100

Lee data/calibration/graded_<liga>.csv (todos los lados con precio, antes de
cualquier filtro de stake: muestra insesgada). Esto NO es una afirmacion de
rentabilidad: mide precision probabilistica, no beneficio.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.config import ROOT
from sqp.evaluation.model_vs_market import score_model_vs_market


def load_graded(root: Path = ROOT) -> pd.DataFrame:
    d = root / "data" / "calibration"
    fs = sorted(p for p in d.glob("graded_*.csv") if p.is_file())
    if not fs:
        return pd.DataFrame()
    return pd.concat([pd.read_csv(p) for p in fs], ignore_index=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--by", nargs="+", default=["league", "market"])
    ap.add_argument("--min-rows", type=int, default=60,
                    help="oculta segmentos con menos filas (default 60)")
    ap.add_argument("--n-boot", type=int, default=1000)
    args = ap.parse_args()

    df = load_graded()
    if df.empty:
        print("Sin datos graduados en data/calibration/.")
        return 1

    res = score_model_vs_market(df, by=args.by, n_boot=args.n_boot)
    res = res[res["n_rows"] >= args.min_rows]
    if res.empty:
        print(f"Ningun segmento alcanza {args.min_rows} filas.")
        return 0

    seg = "/".join(args.by)
    print("=== MODELO vs MERCADO  (Brier: mas bajo = mejor) ===")
    print(f"{seg:<24}{'filas':>7}{'event':>7}{'modelo':>9}{'mercado':>9}"
          f"{'dif':>9}{'IC95 de la dif':>20}   veredicto")
    for _, r in res.iterrows():
        etq = "/".join(str(r[c]) for c in args.by)
        print(f"{etq:<24}{int(r['n_rows']):>7}{int(r['n_events']):>7}"
              f"{r['brier_model']:>9.4f}{r['brier_market']:>9.4f}{r['brier_diff']:>+9.4f}"
              f"   [{r['brier_diff_lo']:>+7.4f},{r['brier_diff_hi']:>+8.4f}]   {r['veredicto']}")

    print("\ndif = Brier(modelo) - Brier(mercado). Negativo = el modelo estima mejor.")
    print("El IC se agrupa por evento (el stream guarda los dos lados de cada mercado).")
    print("Mide precision probabilistica estimada, NO rentabilidad ni ROI realizado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
