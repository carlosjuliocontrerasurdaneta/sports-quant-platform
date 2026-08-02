"""Gate de la fase ofensiva intradía (#4): el análisis que decide con datos si
los picks hipotéticos intradía superan a los de las 11:00 (regla 2026-07-14)."""
from __future__ import annotations

import pandas as pd

from sqp.audit.intraday_gate import GATE_MIN_N, evaluate_gate, first_detections


def _log_row(ts="2026-07-20T15:00:00+00:00", league="mlb", event_id="e1",
             selection="Yankees", entry_price=1.9, price_now=2.0,
             would_generate=True, is_candidate=False):
    return dict(timestamp=ts, league=league, event_id=event_id, market="h2h",
                selection=selection, minutes_to_start=100.0, prob_basis=0.55,
                entry_price=entry_price, entry_edge=0.02, price_now=price_now,
                would_generate=would_generate, is_candidate=is_candidate)


def test_first_detections_dedups_and_excludes_ever_candidates():
    df = pd.DataFrame([
        _log_row(ts="2026-07-20T15:00:00+00:00", price_now=2.10),
        _log_row(ts="2026-07-20T16:00:00+00:00", price_now=2.00),  # repetido
        # hipotético que MÁS TARDE fue candidato: se excluye del grupo intradía
        _log_row(event_id="e2", ts="2026-07-20T15:00:00+00:00"),
        _log_row(event_id="e2", ts="2026-07-20T18:00:00+00:00",
                 would_generate=False, is_candidate=True),
        # candidato de las 11:00, dos checks
        _log_row(event_id="e3", ts="2026-07-20T15:00:00+00:00",
                 would_generate=False, is_candidate=True, entry_price=1.80),
        _log_row(event_id="e3", ts="2026-07-20T16:00:00+00:00",
                 would_generate=False, is_candidate=True, entry_price=1.80),
    ])
    hyp, cand = first_detections(df)
    assert len(hyp) == 1 and hyp.iloc[0]["event_id"] == "e1"
    assert hyp.iloc[0]["price_now"] == 2.10  # primer aviso, no el último
    assert set(cand["event_id"]) == {"e2", "e3"}
    assert len(cand) == 2


def _close_lookup(closes):
    def lookup(league, event_id, market, selection, line=None):
        return closes.get((league, str(event_id), market, str(selection)))
    return lookup


def test_evaluate_gate_matches_lined_markets_by_exact_line():
    row = _log_row()
    row.update(market="spreads", line=-3.5, price_now=2.10)
    seen = {}

    def lookup(league, event_id, market, selection, line=None):
        seen["line"] = line
        return 2.00 if line == -3.5 else None

    rep = evaluate_gate(pd.DataFrame([row]), lookup)
    assert seen["line"] == -3.5      # la línea viaja hasta el cierre
    assert rep["n_intraday"] == 1    # y matchea por línea exacta


def test_evaluate_gate_insufficient_sample():
    df = pd.DataFrame([_log_row()])
    rep = evaluate_gate(df, _close_lookup({("mlb", "e1", "h2h", "Yankees"): 1.95}))
    assert rep["verdict"] == "INSUFICIENTE"
    assert rep["n_intraday"] == 1
    assert rep["gate_min_n"] == GATE_MIN_N


def test_evaluate_gate_pass_requires_positive_and_better_median():
    closes = {}
    rows = []
    # 30 hipotéticos con CLV +2% (2.04 vs cierre 2.00)
    for i in range(GATE_MIN_N):
        rows.append(_log_row(event_id=f"h{i}", price_now=2.04))
        closes[("mlb", f"h{i}", "h2h", "Yankees")] = 2.00
    # 30 picks 11:00 con CLV -2%
    for i in range(GATE_MIN_N):
        rows.append(_log_row(event_id=f"c{i}", would_generate=False,
                             is_candidate=True, entry_price=1.96))
        closes[("mlb", f"c{i}", "h2h", "Yankees")] = 2.00
    rep = evaluate_gate(pd.DataFrame(rows), _close_lookup(closes))
    assert rep["verdict"] == "PASS"
    assert rep["median_intraday"] > 0
    assert rep["median_intraday"] > rep["median_1100"]


def test_evaluate_gate_rejects_when_intraday_not_positive():
    closes = {}
    rows = []
    for i in range(GATE_MIN_N):  # intradía CLV 0: no supera
        rows.append(_log_row(event_id=f"h{i}", price_now=2.00))
        closes[("mlb", f"h{i}", "h2h", "Yankees")] = 2.00
    for i in range(GATE_MIN_N):
        rows.append(_log_row(event_id=f"c{i}", would_generate=False,
                             is_candidate=True, entry_price=1.90))
        closes[("mlb", f"c{i}", "h2h", "Yankees")] = 2.00
    rep = evaluate_gate(pd.DataFrame(rows), _close_lookup(closes))
    assert rep["verdict"] == "RECHAZO"


def test_evaluate_gate_unmatched_close_rows_are_dropped_not_zeroed():
    df = pd.DataFrame([_log_row(), _log_row(event_id="e9")])
    rep = evaluate_gate(df, _close_lookup({("mlb", "e1", "h2h", "Yankees"): 2.0}))
    assert rep["n_intraday"] == 1  # e9 sin cierre no cuenta como CLV 0
