#!/usr/bin/env python
"""Fase 1 del pre-registro de derivados: captura diaria de team_totals MLB.

  python scripts/collect_team_totals_mlb.py --mode live  # una captura (gasta cuota)
  python scripts/collect_team_totals_mlb.py --report   # liquida y resume (gratis)

La captura sella la probabilidad PURA del motor junto a cada cuota del libro
(`data/odds/team_totals_mlb_YYYYMM.csv`), bajo el tope pre-registrado de 45
creditos/dia y 1.400/mes (`sqp.pipeline.team_totals_capture`). Stake 0 siempre:
no produce picks. El informe liquida contra `results_mlb.csv`, sin cuota, y
muestra el avance hacia el n >= 300 del gate; NO decide nada: el gate es la
misma regla de salida del prediction_gate y se evalua aparte.

Las cifras del informe son probabilidad estimada, probabilidad implicita sin
vig y ROI realizado sobre muestra historica. Ninguna es una promesa de ganancia.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402

from sqp.config import ROOT, Settings  # noqa: E402
from sqp.pipeline.team_totals_capture import (capture_team_totals,  # noqa: E402
                                              consensus_novig,
                                              grade_captures, load_captures)
from sqp.storage.results_store import ResultsStore  # noqa: E402

GATE_MIN_N = 300  # pre-registro Fase 1: n >= 300 selecciones graduadas


def report(league: str) -> int:
    caps = load_captures(ROOT, league)
    if caps.empty:
        print(f"[{league}] sin capturas de team_totals todavia.")
        return 0
    from sqp.pipeline.daily import _league_meta
    from sqp.sports.registry import get_adapter
    meta = _league_meta(league)
    adapter = get_adapter(league, meta["family"], meta.get("league_params"))
    graded = grade_captures(caps, ResultsStore(ROOT).load(league), adapter.normalize)
    cons = consensus_novig(graded)
    done = cons[cons["result"].isin(["win", "loss"])]
    n_sel = len(cons)
    print(f"[{league}] capturas: {caps['captured_at'].nunique()} | eventos: {caps['event_id'].nunique()} "
          f"| selecciones (evento, equipo, linea, lado): {n_sel} | graduadas: {len(done)} "
          f"(gate n>={GATE_MIN_N}: {len(done) / GATE_MIN_N:.0%})")
    if done.empty:
        return 0
    y = (done["result"] == "win").astype(float).to_numpy()
    pm = done["model_probability"].to_numpy(dtype=float)
    pk = done["implied_probability_novig"].to_numpy(dtype=float)
    print(f"  Brier modelo puro: {np.mean((pm - y) ** 2):.5f} | Brier mercado sin vig: "
          f"{np.mean((pk - y) ** 2):.5f} | hit rate observado: {y.mean():.4f}")
    edge = pm - pk
    picked = edge > 0
    if picked.any():
        price = done["price_median"].to_numpy(dtype=float)
        roi = np.where(y[picked] > 0, price[picked] - 1.0, -1.0)
        print(f"  donde el modelo declara edge>0 (n={int(picked.sum())}): hit "
              f"{y[picked].mean():.4f}, ROI plano realizado {roi.mean():+.4f} "
              f"(sin IC hasta que haya muestra; no es una promesa)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--league", default="mlb")
    ap.add_argument("--report", action="store_true", help="solo liquidar y resumir; no gasta cuota")
    ap.add_argument("--mode", default="live", choices=["live", "demo"],
                    help="igual que run_all.py: el BAT diario pasa --mode live")
    args = ap.parse_args()
    if args.report:
        return report(args.league)
    settings = Settings.load()
    if args.mode == "demo":
        print("modo demo: no se captura team_totals (no hay libro real).")
        return 0
    s = capture_team_totals(settings, league=args.league)
    print(f"[{s['league']}] {s['day']}: {s['events']} eventos, {s['rows']} filas, "
          f"{s['credits_spent']} creditos" + (f"; parada: {s['stop']}" if s["stop"] else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
