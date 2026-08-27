#!/usr/bin/env python
"""Marcador del fin ultimo: bate el modelo al mercado, y vale algo su edge?

Une las dos mediciones que responden si el sistema puede ganar dinero, y que
hasta ahora solo existian como codigo de libreria sin ningun punto de entrada
operativo (`sqp.evaluation.model_vs_market` solo se ejecutaba en tests):

  1. Brier/log-loss del modelo frente al no-vig del mercado, por segmento y
     agregado, con IC95 agrupado por evento.
  2. Escalera de `min_edge`: ROI realizado en funcion del umbral de edge. Si el
     edge declarado tuviera informacion, subir el umbral mejoraria el ROI.

Fuente: `data/calibration/graded_*.csv` -- todas las caras priceadas, no solo
las apostadas. Solo lee datos guardados; no consume cuota de API ni escribe en
`data/`.

  python scripts/model_vs_market_report.py
  python scripts/model_vs_market_report.py --price-floor 0.35 --n-boot 4000

Salida: `audit/model_vs_market_YYYYMMDD.md` y por stdout.

Las cifras son probabilidad estimada, probabilidad implicita sin vig, edge
declarado y ROI REALIZADO sobre muestra historica, cada uno con su intervalo.
Ninguna es una promesa de ganancia.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from sqp.config import ROOT
from sqp.evaluation.edge_information import (
    DEFAULT_THRESHOLDS,
    cap_ladder,
    edge_ladder,
    edge_signal,
    one_row_per_pick,
)
from sqp.evaluation.model_vs_market import score_model_vs_market
from sqp.storage.served_store import ServedStore

_MODEL_COLS = ("model_probability", "calibrated_probability")
_SEG_COLS = ["league", "market", "n_rows", "n_events", "brier_model",
             "brier_market", "brier_diff", "brier_diff_lo", "brier_diff_hi",
             "veredicto"]


def _md_table(df: pd.DataFrame) -> str:
    """Tabla markdown sin dependencias. `DataFrame.to_markdown` exige `tabulate`,
    que no esta en `requirements.lock` y no justifica anadirlo para esto."""
    head = [str(c) for c in df.columns]
    rows = [["" if pd.isna(v) else str(v) for v in rec]
            for rec in df.itertuples(index=False, name=None)]
    return "\n".join(["| " + " | ".join(head) + " |",
                      "|" + "|".join("---" for _ in head) + "|",
                      *("| " + " | ".join(r) + " |" for r in rows)])


def _pooled(df: pd.DataFrame, model_col: str, n_boot: int, seed: int) -> pd.DataFrame:
    """Un solo segmento sintetico: maxima potencia para la pregunta agregada.

    Los ~38 segmentos por (liga, mercado) sufren comparaciones multiples: con
    alpha=0.05, un par de veredictos "modelo MEJOR" es lo que produce el azar.
    El agregado no tiene ese problema y es el numero que debe leerse primero.
    """
    return score_model_vs_market(df.assign(_all="TODO"), by=["_all"],
                                 model_col=model_col, n_boot=n_boot, seed=seed)


def build_report(df: pd.DataFrame, *, price_floor: float, n_boot: int,
                 seed: int) -> str:
    lines: list[str] = [
        "# Modelo vs mercado y valor del edge",
        "",
        f"Generado: {date.today().isoformat()} - filas servidas: {len(df)} - "
        f"picks unicos: {len(one_row_per_pick(df))} - "
        f"eventos: {df['event_id'].nunique()}",
        "",
        "Fuente: stream servido (`data/calibration/graded_*.csv`), todas las "
        "caras priceadas antes de cualquier filtro de stake. Intervalos al 95% "
        "por bootstrap agrupado por evento.",
        "",
        "**Unidades.** El stream guarda una fila por dia de horizonte, asi que "
        "el mismo pick aparece varias veces (2,19x el 2026-08-27). Las secciones "
        "de ROI (3, 4 y 5) miden POLITICA y colapsan a **una fila por apuesta** "
        "-- una apuesta se hace una vez. La seccion 1 (Brier) se queda sobre "
        "todas las servidas a proposito: cada servida es una prediccion distinta "
        "a un precio distinto, la comparacion es pareada contra el mercado en la "
        "misma fila y el IC ya agrupa por evento.",
        "",
        "ROI REALIZADO sobre muestra historica. NO es una promesa de ganancia.",
        "",
        "## 1. Agregado: modelo vs mercado",
        "",
        "`brier_diff = modelo - mercado`; NEGATIVO = el modelo gana. El veredicto "
        "lo fija el intervalo, no el punto estimado.",
        "",
    ]
    for col in _MODEL_COLS:
        pooled = _pooled(df, col, n_boot, seed)
        if pooled.empty:
            lines.append(f"- `{col}`: sin filas puntuables.")
            continue
        r = pooled.iloc[0]
        lines.append(
            f"- `{col}`: n={r.n_rows}, eventos={r.n_events}, "
            f"brier modelo={r.brier_model} vs mercado={r.brier_market}, "
            f"diff={r.brier_diff:+} IC95=[{r.brier_diff_lo:+}, "
            f"{r.brier_diff_hi:+}] -> **{r.veredicto}**")

    lines += ["", "## 2. Por (liga, mercado)", "",
              "Atencion a las comparaciones multiples: con ~38 segmentos y "
              "alpha=0.05, un par de veredictos extremos son ruido esperado.", ""]
    seg = score_model_vs_market(df, model_col="calibrated_probability",
                                n_boot=n_boot, seed=seed)
    lines += [_md_table(seg[_SEG_COLS]), ""]

    lines += ["## 3. Escalera de `min_edge`: vale algo el edge declarado?", "",
              "Si el edge tuviera informacion, `roi_flat` CRECERIA con el umbral.",
              ""]
    for floor in sorted({0.0, price_floor}):
        lad = edge_ladder(df, thresholds=DEFAULT_THRESHOLDS, price_floor=floor,
                          n_boot=n_boot, seed=seed)
        lines += [f"### Suelo de probabilidad implicita = {floor:.2f}", "",
                  _md_table(lad), ""]

    lines += [
        "## 4. Cap de plausibilidad: esta cortando lo peor o picks buenos?", "",
        "`risk.max_plausible_edge` descarta candidatos cuyo edge declarado es "
        "implausible. Es el control con MAS trabajo efectivo del sistema: en un "
        "run real el 63% de las filas descartadas llevan su flag, mas que el "
        "gate de prediccion. Un cap util corta lo que rinde PEOR.", "",
        "AVISO: el techo se barre sobre la misma muestra que se evalua, asi que "
        "el mejor punto esta sesgado al alza. Sirve para VIGILAR que el cap "
        "sigue funcionando, no para optimizarlo.", "",
        _md_table(cap_ladder(df, n_boot=n_boot, seed=seed)),
        "",
    ]

    sig = edge_signal(df, n_boot=n_boot, seed=seed)
    lines += [
        "## 5. Contraste directo de la seleccion",
        "",
        f"- ROI donde el modelo apuesta (edge>0): **{sig['roi_picked']:+.4f}** "
        f"(n={int(sig['n_picked'])})",
        f"- ROI en el resto (edge<=0): **{sig['roi_rest']:+.4f}** "
        f"(n={int(sig['n_rest'])})",
        f"- Delta = **{sig['delta']:+.4f}**, IC95 = "
        f"[{sig['delta_lo']:+.4f}, {sig['delta_hi']:+.4f}]",
        "",
        "Delta negativo con IC que excluye 0 significa que la regla de seleccion "
        "RESTA valor: el sistema apuesta el peor lado de cada mercado.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--price-floor", type=float, default=0.35,
                    help="probabilidad implicita sin vig minima para la segunda "
                         "escalera (separa el efecto del sesgo favorito-longshot)")
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    df = ServedStore(ROOT).load_all_graded()
    if df.empty:
        print("Sin stream graduado en data/calibration: nada que medir.")
        return 1

    report = build_report(df, price_floor=args.price_floor,
                          n_boot=args.n_boot, seed=args.seed)
    out = args.out or ROOT / "audit" / f"model_vs_market_{date.today():%Y%m%d}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nReporte escrito en: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
