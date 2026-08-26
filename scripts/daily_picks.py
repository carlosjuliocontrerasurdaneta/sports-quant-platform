#!/usr/bin/env python
"""Lista diaria de picks de TODOS los deportes y mercados, priorizada.

Encargo del operador (2026-08-26): "generar picks diariamente para todos los
deportes y mercados, priorizando aquellos que presenten las probabilidades mas
altas".

REGLA FUNDAMENTAL del proyecto (operador, 2026-08-26, declarada SACROSANTA E
INAMOVIBLE): "No quiero que realice apuestas, sino que genere picks para todos
los deportes y mercados, priorizando aquellos con las mayores probabilidades."

Generar picks y apostarlos son cosas distintas y esta regla separa las dos: la
lista se produce SIEMPRE y COMPLETA; que una linea lleve dinero lo decide el
gate, aparte.

Fuente: el STREAM SERVIDO (`data/calibration/served_*.csv`), que contiene TODAS
las caras priceadas del dia. NO `candidates_*.csv`, que solo trae lo que el
filtro de edge dejo pasar -- hoy 63 filas frente a 533 servidas. "Todos los
deportes y mercados" exige la fuente completa.

**No genera nada nuevo, no toca stakes, no toca gates y no consume cuota de
API**: es una vista sobre lo que el pipeline ya escribio. Correrlo despues de
RUN_DIARIO_ALL.bat.

  python scripts/daily_picks.py
  python scripts/daily_picks.py --top 20 --min-prob 0.60
  python scripts/daily_picks.py --market h2h --all-days

## Por que la columna `breakeven` no es opcional

Ordenar por probabilidad estimada, a secas, es el `pick_mode: accuracy` que se
activo el 2026-07-28 y se REVIRTIO el 2026-07-31 (commit f6c2130) por decision
del operador: seleccionar por probabilidad >= 0.70 elige favoritos extremos a
cuotas 1.07-1.16, donde el punto de equilibrio es 93.5% de aciertos. Subia el
hit rate y perdia dinero POR CONSTRUCCION.

Por eso esta tabla pone siempre, al lado de la probabilidad estimada, lo que la
CUOTA exige (`breakeven = 1/precio`) y la diferencia entre ambas (`margen`). Una
probabilidad de 0.93 a cuota 1.07 aparece con margen NEGATIVO, que es la verdad
que el ranking por probabilidad sola esconde. La regla del proyecto es explicita:
un hit rate no es una afirmacion de rentabilidad.

Todas las cifras son probabilidad ESTIMADA, probabilidad implicita sin vig, edge
declarado y punto de equilibrio. Ninguna es una promesa de ganancia.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from sqp.config import ROOT

COLS = ["#", "liga", "mercado", "seleccion", "linea", "precio", "prob_est",
        "breakeven", "margen", "prob_mercado", "edge", "libros", "estado"]


def load_served(cal_dir: Path, *, today_only: bool = True) -> pd.DataFrame:
    """Une los served_*.csv de todas las ligas: TODAS las caras priceadas.

    Es la fuente que exige la regla fundamental. `candidates_*.csv` seria la
    fuente equivocada: solo contiene lo que supero `min_edge`, asi que ranquearla
    dejaria fuera la mayor parte de los mercados del dia.
    """
    frames = []
    for f in sorted(cal_dir.glob("served_*.csv")):
        try:
            d = pd.read_csv(f)
        except (pd.errors.EmptyDataError, pd.errors.ParserError):
            continue
        if not d.empty:
            frames.append(d)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    if today_only and "generated_at" in df.columns:
        day = df["generated_at"].astype(str).str[:10]
        newest = day.max()
        df = df[day == newest]
    return df


def rank_picks(df: pd.DataFrame, *, min_prob: float = 0.0,
               market: str | None = None) -> pd.DataFrame:
    """Ordena por probabilidad estimada DESCENDENTE y anota el breakeven.

    `margen = prob_est - 1/precio`. Positivo significa que la probabilidad
    estimada supera lo que la cuota exige para no perder dinero; negativo
    significa que NO, por alta que sea la probabilidad.
    """
    if df.empty:
        return pd.DataFrame(columns=COLS)
    d = df.copy()
    p = pd.to_numeric(d.get("estimated_probability"), errors="coerce")
    price = pd.to_numeric(d.get("price_decimal"), errors="coerce")
    d["_p"] = p
    d["_price"] = price
    d["_be"] = 1.0 / price.where(price > 1.0)
    d["_margen"] = d["_p"] - d["_be"]
    d = d[d["_p"].notna() & d["_be"].notna()]
    if min_prob > 0:
        d = d[d["_p"] >= min_prob]
    if market:
        d = d[d["market"] == market]
    d = d.sort_values("_p", ascending=False).reset_index(drop=True)

    flags = d.get("flags", pd.Series([""] * len(d))).fillna("").astype(str)
    stake = pd.to_numeric(d.get("stake"), errors="coerce").fillna(0.0)
    out = pd.DataFrame({
        "#": range(1, len(d) + 1),
        "liga": d["league"],
        "mercado": d["market"],
        "seleccion": d["selection"],
        "linea": d.get("line"),
        # Desde `d`, no desde `price`: tras el filtrado y el reset_index, un
        # reindex contra el frame original devolvia NaN en toda la columna.
        "precio": d["_price"].round(3),
        "prob_est": d["_p"].round(4),
        "breakeven": d["_be"].round(4),
        "margen": d["_margen"].round(4),
        "prob_mercado": pd.to_numeric(
            d.get("implied_probability_novig"), errors="coerce").round(4),
        "edge": pd.to_numeric(d.get("estimated_edge"), errors="coerce").round(4),
        "libros": d.get("books_count"),
        "estado": [("STAKE %.2f" % s) if s > 0 else (f or "sin stake")
                   for s, f in zip(stake, flags)],
    })
    return out


def _md(df: pd.DataFrame) -> str:
    head = [str(c) for c in df.columns]
    rows = [["" if pd.isna(v) else str(v) for v in r]
            for r in df.itertuples(index=False, name=None)]
    return "\n".join(["| " + " | ".join(head) + " |",
                      "|" + "|".join("---" for _ in head) + "|",
                      *("| " + " | ".join(r) + " |" for r in rows)])


def build_report(ranked: pd.DataFrame, *, top: int, source_day: str) -> str:
    con_margen = int((ranked["margen"] > 0).sum()) if not ranked.empty else 0
    con_stake = int(ranked["estado"].str.startswith("STAKE").sum()) if not ranked.empty else 0
    lines = [
        f"# Picks del dia - {source_day}",
        "",
        f"{len(ranked)} selecciones evaluadas en "
        f"{ranked['liga'].nunique() if not ranked.empty else 0} ligas y "
        f"{ranked['mercado'].nunique() if not ranked.empty else 0} mercados, "
        "ordenadas por PROBABILIDAD ESTIMADA descendente. Fuente: stream "
        "servido (TODAS las caras priceadas del dia).",
        "",
        f"- Con margen positivo sobre el breakeven: **{con_margen}**",
        f"- Con stake real asignado: **{con_stake}**",
        "",
        "`breakeven = 1/precio` es el acierto que la CUOTA exige para no perder "
        "dinero. `margen = prob_est - breakeven`. Un margen negativo significa "
        "que la apuesta pierde a largo plazo POR ALTA QUE SEA la probabilidad: a "
        "cuota 1.07 hace falta acertar el 93.5%.",
        "",
        "Cifras de probabilidad ESTIMADA e implicita. **No son promesas de "
        "ganancia.**",
        "",
    ]
    shown = ranked.head(top) if top > 0 else ranked
    lines += [_md(shown), ""]
    if top > 0 and len(ranked) > top:
        lines += [f"_({len(ranked) - top} selecciones mas omitidas; usa "
                  f"`--top 0` para verlas todas.)_", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--top", type=int, default=30,
                    help="cuantas mostrar (0 = todas)")
    ap.add_argument("--min-prob", type=float, default=0.0,
                    help="probabilidad estimada minima")
    ap.add_argument("--market", default=None, help="h2h | spreads | totals")
    ap.add_argument("--all-days", action="store_true",
                    help="no limitar al dia mas reciente")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    pred_dir = ROOT / "data" / "predictions"
    df = load_served(ROOT / "data" / "calibration", today_only=not args.all_days)
    if df.empty:
        print("Sin stream servido en data/calibration. "
              "Corre RUN_DIARIO_ALL.bat primero.")
        return 1
    day = str(df["generated_at"].astype(str).str[:10].max()) if "generated_at" in df else "?"
    ranked = rank_picks(df, min_prob=args.min_prob, market=args.market)
    report = build_report(ranked, top=args.top, source_day=day)

    out = args.out or pred_dir / f"picks_ranked_{date.today():%Y%m%d}.md"
    out.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nEscrito en: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
