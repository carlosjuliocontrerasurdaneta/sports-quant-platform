#!/usr/bin/env python
"""Gate de la fase ofensiva intradía (#4): imprime el veredicto repetible.

  PYTHONPATH=src python scripts/intraday_gate_analysis.py

Compara el CLV de los picks hipotéticos intradía (primer aviso de
would_generate en data/bets/intraday_edge_log.csv) contra el de los picks de
las 11:00, emparejando ambos al cierre fresco (<=90 min). Criterios exactos en
sqp/audit/intraday_gate.py. Un PASS habilita CONSTRUIR la generación intradía
(decisión humana), nunca apostar dinero real.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pandas as pd

from sqp.audit.clv import CLOSE_MAX_AGE_MIN
from sqp.audit.intraday_gate import evaluate_gate
from sqp.backtesting.roi_engine import load_closing_odds
from sqp.config import ROOT
from sqp.pipeline.probabilities import _consensus_lines


def main() -> int:
    log_path = ROOT / "data" / "bets" / "intraday_edge_log.csv"
    if not log_path.exists():
        print("Sin log intradía (data/bets/intraday_edge_log.csv); nada que evaluar.")
        return 1
    df = pd.read_csv(log_path)

    cons_cache: dict[str, dict] = {}

    def close_for(league: str, event_id: str, market: str, selection: str,
                  line: float | None):
        if league not in cons_cache:
            cons_cache[league] = {
                eid: _consensus_lines(eo) for eid, eo in
                load_closing_odds(ROOT, league,
                                  max_age_min=CLOSE_MAX_AGE_MIN).items()}
        cons = cons_cache[league].get(str(event_id))
        if not cons:
            return None
        # h2h sin linea; spreads/totals por linea EXACTA (v2 del observatorio).
        return cons.get((market, str(selection), line))

    rep = evaluate_gate(df, close_for)
    print("# Gate fase ofensiva intradía (#4) — regla 2026-07-14")
    print(f"Log: {len(df)} filas | intradía n={rep['n_intraday']} "
          f"(mín {rep['gate_min_n']}) | picks 11:00 n={rep['n_1100']}")
    print(f"CLV intradía : mediana {rep['median_intraday']:+.2%} | "
          f"media {rep['mean_intraday']:+.2%} | beat {rep['beat_intraday']:.0%}")
    print(f"CLV 11:00    : mediana {rep['median_1100']:+.2%} | "
          f"media {rep['mean_1100']:+.2%} | beat {rep['beat_1100']:.0%}")
    if rep["by_league_intraday"]:
        print("Intradía por liga (n / mediana / media):")
        for lg, s in sorted(rep["by_league_intraday"].items()):
            print(f"  {lg:28s} {int(s['count']):3d} / {s['median']:+.4f} / {s['mean']:+.4f}")
    print(f"\nVEREDICTO: {rep['verdict']}")
    if rep["verdict"] == "INSUFICIENTE":
        print("Seguir acumulando observatorio; re-ejecutar cuando n_intradía >= 30.")
    elif rep["verdict"] == "PASS":
        print("Evidencia a favor de CONSTRUIR la generación intradía (decisión humana).")
    else:
        print("Los hipotéticos intradía no superan a las 11:00: la #4 ofensiva se rechaza.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
