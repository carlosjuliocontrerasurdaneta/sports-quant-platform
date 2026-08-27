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
  python scripts/daily_picks.py --market h2h --liga mlb
  python scripts/daily_picks.py --dia todos          # los 7 dias de horizonte
  python scripts/daily_picks.py --dia 2026-08-29
  # Criterio del operador (2026-08-26): probabilidad >= 0.60 y ROI esperado > 0
  python scripts/daily_picks.py --min-prob 0.60 --min-roi 0

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
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from sqp.config import ROOT
from sqp.evaluation.labels import match_label

COLS = ["#", "liga", "partido", "mercado", "seleccion", "linea", "precio", "prob_est",
        "breakeven", "margen", "roi_esp", "prob_mercado", "casas", "estado"]


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


def game_date_local(df: pd.DataFrame) -> pd.Series:
    """Fecha del PARTIDO en hora local, no la de generacion.

    El run guarda eventos con horizonte de 7 dias, asi que "generado hoy"
    incluye partidos de hasta 6 dias despues: de las 541 filas del 2026-08-26
    solo 105 se jugaban ese dia. Llamar "picks de hoy" a las 541 era enganoso.
    Se usa hora LOCAL porque un partido nocturno en la costa oeste de EEUU
    comienza despues de las 00:00Z y en UTC caeria en el dia siguiente.
    """
    st = pd.to_datetime(df.get("start_time"), errors="coerce", utc=True)
    tz = datetime.now(timezone.utc).astimezone().tzinfo
    return st.dt.tz_convert(tz).dt.strftime("%Y-%m-%d").fillna("")


def rank_picks(df: pd.DataFrame, *, min_prob: float = 0.0,
               market: str | None = None,
               min_margin: float | None = None,
               min_roi: float | None = None,
               league: str | None = None,
               game_date: str | None = None,
               orden: str = "prob") -> pd.DataFrame:
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
    d["_roi_esp"] = d["_p"] * d["_price"] - 1.0
    d = d[d["_p"].notna() & d["_be"].notna()]
    if min_prob > 0:
        d = d[d["_p"] >= min_prob]
    if market:
        d = d[d["market"] == market]
    if league:
        d = d[d["league"] == league]
    if game_date:
        d = d[game_date_local(d) == game_date]
    # `margen = prob_est - 1/precio`. Filtrar por el > 0 deja solo las lineas
    # cuya probabilidad estimada supera lo que la cuota exige. NO es una lista
    # de apuestas: sigue sin llevar stake, y el edge declarado ya se midio
    # anti-informativo (bitacora 2026-08-25).
    if min_margin is not None:
        d = d[d["_margen"] >= min_margin]
    # `roi_esp > 0` equivale EXACTAMENTE a `margen > 0`: p*cuota-1 > 0 <=>
    # p > 1/cuota <=> p - breakeven > 0. Se expone igual porque el operador
    # razona en terminos de ROI y la equivalencia no es obvia leyendo la tabla.
    if min_roi is not None:
        d = d[d["_roi_esp"] > min_roi]
    # Por defecto manda la PROBABILIDAD (regla fundamental del operador). `roi` y
    # `margen` existen porque el operador pidio "sin dejar de considerar el ROI":
    # apuntan en sentidos OPUESTOS a la probabilidad en estos datos.
    clave = {"prob": "_p", "roi": "_roi_esp", "margen": "_margen"}[orden]
    d = d.sort_values(clave, ascending=False).reset_index(drop=True)

    flags = d.get("flags", pd.Series([""] * len(d))).fillna("").astype(str)
    stake = pd.to_numeric(d.get("stake"), errors="coerce").fillna(0.0)
    out = pd.DataFrame({
        "#": range(1, len(d) + 1),
        "liga": d["league"],
        # Sin el partido, una fila de `totals` decia solo "Over 8.5": ni el
        # mercado ni la seleccion identifican el encuentro (operador, 2026-08-26).
        "partido": match_label(d),
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
        # ROI esperado por unidad apostada = p*cuota - 1. Es el `estimated_edge`
        # de siempre, llamado por su nombre (encargo del operador 2026-08-26).
        "roi_esp": (d["_p"] * d["_price"] - 1.0).round(4),
        "casas": d.get("books_count"),
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
    ap.add_argument("--orden", default="prob", choices=("prob", "roi", "margen"),
                    help="criterio de orden: prob (default, regla fundamental), "
                         "roi (ROI esperado) o margen")
    ap.add_argument("--min-roi", type=float, default=None,
                    help="ROI esperado ESTRICTAMENTE mayor que este valor. "
                         "--min-roi 0 equivale a --min-margin 0 (mismo filtro).")
    ap.add_argument("--min-margin", type=float, default=None,
                    help="margen minimo (prob_est - 1/precio); usa 0 para ver "
                         "solo las que superan su punto de equilibrio")
    ap.add_argument("--liga", default=None,
                    help="filtrar por liga (mlb, epl, wnba, ...)")
    ap.add_argument("--dia", default="hoy",
                    help="fecha del PARTIDO: 'hoy' (default), 'todos', o "
                         "YYYY-MM-DD. No es la fecha de generacion: el run "
                         "guarda 7 dias de horizonte.")
    ap.add_argument("--all-days", action="store_true",
                    help="no limitar al ultimo run (fecha de GENERACION)")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    pred_dir = ROOT / "data" / "predictions"
    df = load_served(ROOT / "data" / "calibration", today_only=not args.all_days)
    if df.empty:
        print("Sin stream servido en data/calibration. "
              "Corre RUN_DIARIO_ALL.bat primero.")
        return 1
    day = str(df["generated_at"].astype(str).str[:10].max()) if "generated_at" in df else "?"
    hoy = datetime.now(timezone.utc).astimezone().date().isoformat()
    dia = None if args.dia == "todos" else (hoy if args.dia == "hoy" else args.dia)
    ranked = rank_picks(df, min_prob=args.min_prob, market=args.market,
                        min_margin=args.min_margin, min_roi=args.min_roi,
                        league=args.liga,
                        game_date=dia, orden=args.orden)
    etiqueta = f"{day} (generado) - partidos del {dia}" if dia else f"{day} (generado) - todas las fechas"
    report = build_report(ranked, top=args.top, source_day=etiqueta)

    out = args.out or pred_dir / f"picks_ranked_{date.today():%Y%m%d}.md"
    out.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nEscrito en: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
