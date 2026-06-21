#!/usr/bin/env python
"""Consolidated pick history (wins/losses) + performance pattern analysis.

Replays the realized-ROI backtest over every league with captured historical
odds, writes ONE consolidated per-bet file (data/processed/pick_history.csv)
with team, side (home/away or Over/Under) and result, then prints the hit-rate
breakdowns:

  - by market (moneyline / handicap / totals)
  - moneyline & handicap: home vs away (frequency = n, and hit rate)
  - totals: Over vs Under (frequency = n, and hit rate)
  - highest hit-rate situations (market x side)
  - per-team wins/losses

  python scripts/build_pick_history.py

The analysis logic lives in sqp.audit.patterns so the daily run / dashboard can
reuse it. This is a BACKTEST over a single pre-game snapshot proxy for closing
odds (limited coverage); hit rate is realized but it is not a profit guarantee
and estimated edge is not realized ROI. MLB totals are paused from LIVE staking
but included here so the totals pattern can be analyzed.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.audit.patterns import (MIN_N_SITUATION, MIN_N_TEAM, PICK_HISTORY_PATH,
                                build_pick_history, conclusions,
                                pattern_breakdowns)
from sqp.logging_config import get_logger

log = get_logger("sqp.pick_history")


def main() -> int:
    hist = build_pick_history(write=True)
    if hist.empty:
        log.warning("Historial vacio: corre backfill_historical_odds.py / "
                    "backfill_results.py para sembrar odds y resultados.")
        return 1

    graded = hist[hist["result"].isin(["win", "loss"])]
    n_push = int((hist["result"] == "push").sum())
    print(f"\n=== HISTORIAL CONSOLIDADO DE PICKS (backtest) -> {PICK_HISTORY_PATH} ===")
    print(f"ligas: {', '.join(sorted(hist['league'].unique()))}")
    print(f"picks totales: {len(hist)} | graduados (win/loss): {len(graded)} | "
          f"pushes: {n_push} | rango fechas: {hist['date'].min()} .. {hist['date'].max()}")

    breaks = pattern_breakdowns(hist)

    print("\n## 1) Aciertos por tipo de mercado")
    m = breaks["by_market"]
    print(m[["market_label", "n", "wins", "losses", "hit_rate_%", "roi_%", "mean_edge"]].to_string(index=False))

    print("\n## 2) Situaciones con mayor tasa de acierto (mercado x lado, "
          f"min {MIN_N_SITUATION} graduados)")
    s = breaks["by_situation"]
    print(s[["market_label", "side", "n", "wins", "hit_rate_%", "roi_%"]].to_string(index=False)
          if s is not None and not s.empty else "(sin combinaciones con muestra suficiente)")

    print("\n## 3) Moneyline (ganador): local (home) vs visitante (away)")
    ml = breaks["moneyline_side"]
    print(ml[["side", "n", "wins", "losses", "hit_rate_%", "roi_%"]].to_string(index=False)
          if not ml.empty else "(sin datos)")

    print("\n## 4) Handicap (spreads): local (home) vs visitante (away)")
    sp = breaks["handicap_side"]
    print(sp[["side", "n", "wins", "losses", "hit_rate_%", "roi_%"]].to_string(index=False)
          if not sp.empty else "(sin datos)")

    print("\n## 5) Totales: Over (alta) vs Under (baja)")
    to = breaks["totals_side"]
    print(to[["side", "n", "wins", "losses", "hit_rate_%", "roi_%"]].to_string(index=False)
          if not to.empty else "(sin datos)")

    print(f"\n## 6) Por equipo (moneyline + handicap; selecciones por equipo, min {MIN_N_TEAM} graduados)")
    top, bot = breaks["team_top"], breaks["team_bottom"]
    if top is None or top.empty:
        print("(ningun equipo con muestra suficiente)")
    else:
        print("-- Top 10 por tasa de acierto --")
        print(top[["team", "n", "wins", "losses", "hit_rate_%", "roi_%"]].to_string(index=False))
        print("-- Bottom 10 por tasa de acierto --")
        print(bot[["team", "n", "wins", "losses", "hit_rate_%", "roi_%"]].to_string(index=False))

    print("\n## Lectura (frecuencia = n picks graduados)")
    for line in conclusions(breaks):
        print(" - " + line.replace("**", ""))

    print("\nBACKTEST sobre un proxy de cierre (snapshot unico, cobertura limitada). "
          "La tasa de acierto es realizada pero NO garantiza resultados futuros; el "
          "edge estimado no es ROI realizado. Auditar antes de operar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
