"""Las vistas del operador deben medir con la probabilidad que DECIDIO el pick.

`_decision_probability` (pipeline/probabilities.py) devuelve dos cosas:
`p_used` es la mezcla CRUDA sin calibrar y se guarda como
`estimated_probability`; `p_decision` lleva el calibrador y se guarda como
`calibrated_probability`, y es la que produce `estimated_edge` (daily.py:841).

`segments` ya usaba la correcta desde el 2026-07-27, pero la lista diaria de
picks y el tipster seguian con la cruda, asi que ordenaban, puntuaban y
clasificaban con una probabilidad que el sistema habia descartado (auditoria
2026-08-31, A-01). Medido sobre las ultimas 2.000 filas de served_mlb.csv:
1.272 filas difieren (hasta 8,95 pp), el signo del margen cambia en 252 y la
lista de "margen positivo" contaba 441 selecciones en vez de 271.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from sqp.evaluation.labels import decision_prob
from sqp.evaluation.tipster import tipster_table


def _served_row(**kw) -> dict:
    base = {
        "league": "mlb", "event_id": "e1", "home": "A", "away": "B",
        # Fecha futura: las vistas filtran por vigencia ("se puede apostar
        # todavia"), no por dia de generacion.
        "start_time": "2099-09-05T23:00:00Z", "game_date": "2099-09-05",
        "market": "h2h", "selection": "A", "line": float("nan"),
        "price_decimal": 2.00, "bookmaker": "consensus_median",
        "model_probability": 0.60, "adjusted_probability": 0.60,
        "estimated_probability": 0.60,     # p_used  -> margen +10 pp
        "calibrated_probability": 0.45,    # p_decision -> margen -5 pp
        "implied_probability_novig": 0.50, "estimated_edge": -0.10,
        "books_count": 25, "stake": 0.0, "data_label": "real",
        "flags": "served_stream", "generated_at": "2099-09-01T11:00:00+00:00",
    }
    base.update(kw)
    return base


# --- el predicado compartido --------------------------------------------------

def test_decision_prob_prefers_the_calibrated_column():
    df = pd.DataFrame([_served_row()])
    assert decision_prob(df).iloc[0] == 0.45


def test_decision_prob_falls_back_per_row_not_per_column():
    """El fallback es POR FILA: una liga sin calibrador convive con otra que si
    lo tiene dentro del mismo dataframe."""
    df = pd.DataFrame([
        _served_row(event_id="con_cal", calibrated_probability=0.45),
        _served_row(event_id="sin_cal", calibrated_probability=float("nan")),
    ])
    assert list(decision_prob(df)) == [0.45, 0.60]


def test_decision_prob_survives_a_missing_calibrated_column():
    """Un stream de esquema antiguo no debe reventar la vista."""
    row = _served_row()
    del row["calibrated_probability"]
    assert decision_prob(pd.DataFrame([row])).iloc[0] == 0.60


def test_segments_reuses_the_shared_predicate():
    """Fuente unica: si `segments` volviera a definir el suyo, podrian divergir
    otra vez, que es como se produjo A-01."""
    from sqp.audit.segments import decision_prob as seg_prob
    assert seg_prob is decision_prob


# --- la lista diaria de picks -------------------------------------------------

def _cal_dir(tmp_path, rows):
    """`_todos_records` lee los `served_*.csv` de un directorio."""
    pd.DataFrame(rows).to_csv(tmp_path / "served_mlb.csv", index=False)
    return tmp_path


def test_todos_records_scores_on_the_decision_probability(tmp_path):
    """La fila tiene margen +10 pp con la cruda y -5 pp con la de decision: el
    signo cambia, que es lo que descuadraba la tarjeta 'Margen positivo'."""
    from sqp.audit.html_report import _todos_records
    recs = _todos_records(_cal_dir(tmp_path, [_served_row()]))
    assert len(recs) == 1
    r = recs[0]
    assert np.isclose(r["prob"], 0.45)
    assert np.isclose(r["breakeven"], 0.50)
    assert np.isclose(r["margen"], -0.05)
    assert np.isclose(r["roi_esp"], -0.10)


def test_todos_records_roi_matches_the_stored_estimated_edge(tmp_path):
    """`roi_esp` se documenta como "el `estimated_edge` de siempre": debe
    coincidir con el que persistio el pipeline."""
    from sqp.audit.html_report import _todos_records
    row = _served_row()
    recs = _todos_records(_cal_dir(tmp_path, [row]))
    assert np.isclose(recs[0]["roi_esp"], row["estimated_edge"])


# --- el tipster ---------------------------------------------------------------

def test_tipster_table_defaults_to_the_decision_probability():
    out = tipster_table(pd.DataFrame([_served_row()]), max_plausible_ev=0.075)
    assert not out.empty
    assert np.isclose(float(out.iloc[0]["prob_est"]), 0.45)


def test_tipster_table_still_accepts_an_explicit_column():
    """La via de diagnostico sigue disponible."""
    out = tipster_table(pd.DataFrame([_served_row()]), max_plausible_ev=0.075,
                        prob_col="estimated_probability")
    assert np.isclose(float(out.iloc[0]["prob_est"]), 0.60)


def test_tipster_tier_changes_when_the_calibrator_disagrees():
    """El tier es la salida que el operador lee: con la cruda esta fila tiene
    EV +20% y con la de decision EV -10%, que es NO BET."""
    crudo = tipster_table(pd.DataFrame([_served_row()]), max_plausible_ev=0.075,
                          prob_col="estimated_probability").iloc[0]
    decision = tipster_table(pd.DataFrame([_served_row()]),
                             max_plausible_ev=0.075).iloc[0]
    assert float(crudo["ev"]) > 0 and float(decision["ev"]) < 0
    assert decision["tier"] == "NO BET"
