#!/usr/bin/env python
"""Clasificacion del Tipster sobre los picks del dia: A / B / C / NO BET.

Implementa la logica de seleccion de `AGENTS Tipster.md` (encargo del operador,
2026-08-26). Solo lee el stream servido: no genera picks, no asigna stake, no
toca gates y no consume cuota de API.

  python scripts/tipster_report.py
  python scripts/tipster_report.py --dia todos --tier A

Salida: `data/predictions/picks_tipster.md`. El dashboard resalta en verde los
tier A y en ambar los B en la pestana "Todos los Picks".
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from sqp.config import ROOT, Settings
from sqp.evaluation.labels import game_date_local, local_today
from sqp.evaluation.tipster import tipster_summary, tipster_table

COLS = ["tier", "fecha", "liga", "partido", "mercado", "seleccion", "linea", "cuota",
        "prob_est", "cuota_justa", "prob_mercado", "edge_pp", "ev", "casas",
        "correlacionado", "motivo"]


def _md(df: pd.DataFrame) -> str:
    head = [str(c) for c in df.columns]
    rows = [["" if pd.isna(v) else str(v) for v in r]
            for r in df.itertuples(index=False, name=None)]
    return "\n".join(["| " + " | ".join(head) + " |",
                      "|" + "|".join("---" for _ in head) + "|",
                      *("| " + " | ".join(r) + " |" for r in rows)])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dia", default="hoy", help="hoy | todos | YYYY-MM-DD")
    ap.add_argument("--tier", default=None, help="A | B | C | 'NO BET'")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    cal = ROOT / "data" / "calibration"
    frames = []
    for f in sorted(cal.glob("served_*.csv")):
        try:
            d = pd.read_csv(f)
        except (pd.errors.EmptyDataError, pd.errors.ParserError):
            continue
        if not d.empty:
            frames.append(d)
    if not frames:
        print("Sin stream servido. Corre RUN_DIARIO_ALL.bat primero.")
        return 1
    df = pd.concat(frames, ignore_index=True)
    gen = df["generated_at"].astype(str).str[:10]
    df = df[gen == gen.max()]

    fecha = game_date_local(df)
    dia = (None if args.dia == "todos"
           else (local_today() if args.dia == "hoy" else args.dia))
    if dia:
        df = df[fecha == dia]
    # Ya NO se sobrescribe `game_date`: `tipster_table` hace ella misma la
    # conversion a hora local, asi que el resultado no depende de este llamador.

    cap = Settings.load().risk.max_plausible_edge
    tab = tipster_table(df, max_plausible_ev=cap)
    resumen = tipster_summary(tab)
    if args.tier:
        tab = tab[tab["tier"] == args.tier]

    lines = [
        f"# Tipster - {dia or 'todas las fechas'}",
        "",
        f"A: **{resumen['A']}** | B: **{resumen['B']}** | C: **{resumen['C']}** "
        f"| NO BET: **{resumen['NO BET']}**",
        "",
        "`cuota_justa = 1/prob_est`. `edge_pp = prob_est - prob_mercado` (sin "
        f"vig). `ev = prob_est x cuota - 1`. Un EV por encima de {cap} se "
        "clasifica **NO BET**: medido, lo que el cap de plausibilidad corta "
        "rinde -22,6% frente al -5,6% de lo que deja pasar.",
        "",
        "`correlacionado` marca varias selecciones del MISMO evento: no son "
        "riesgos independientes.",
        "",
        "**Ninguna linea lleva stake.** No es una recomendacion de apuesta.",
        "",
    ]
    visibles = tab[tab["tier"] != "NO BET"] if not args.tier else tab
    lines += [_md(visibles[COLS].round(4)) if not visibles.empty
              else "_Sin oportunidades por encima de NO BET hoy._", ""]

    out = args.out or ROOT / "data" / "predictions" / "picks_tipster.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nEscrito en: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
