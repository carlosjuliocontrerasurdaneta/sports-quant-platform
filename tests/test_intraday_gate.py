"""Gate de la fase ofensiva intradía (#4): el análisis que decide con datos si
los picks hipotéticos intradía superan a los de las 11:00 (regla 2026-07-14)."""
from __future__ import annotations

import pandas as pd

from sqp.audit.intraday_gate import (
    GATE_MIN_NONTIED, evaluate_gate, first_detections)


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
    assert rep["gate_min_nontied"] == GATE_MIN_NONTIED


# Precios contra un cierre de 2.00: CLV positivo, negativo y empate exacto.
_WIN, _LOSS, _TIE = 2.04, 1.96, 2.00


def _population(intraday: list[float], picks_1100: list[float] | None = None):
    """Filas de log + lookup de cierre para los CLV pedidos (cierre 2.00)."""
    closes, rows = {}, []
    for i, price in enumerate(intraday):
        rows.append(_log_row(event_id=f"h{i}", price_now=price))
        closes[("mlb", f"h{i}", "h2h", "Yankees")] = 2.00
    for i, price in enumerate(picks_1100 or []):
        rows.append(_log_row(event_id=f"c{i}", would_generate=False,
                             is_candidate=True, entry_price=price))
        closes[("mlb", f"c{i}", "h2h", "Yankees")] = 2.00
    return pd.DataFrame(rows), _close_lookup(closes)


def test_exact_ties_are_excluded_from_the_sign_test():
    """Un empate de precio es ausencia de información, no evidencia en contra:
    no entra en el test de signo (KI-020, pre-registro 2026-08-05)."""
    df, lookup = _population([_WIN] * GATE_MIN_NONTIED + [_TIE] * 20)
    rep = evaluate_gate(df, lookup)
    assert rep["n_intraday"] == GATE_MIN_NONTIED + 20
    assert rep["n_intraday_nontied"] == GATE_MIN_NONTIED
    assert rep["pos_intraday"] == GATE_MIN_NONTIED


def test_insufficient_counts_non_tied_rows_not_total_rows():
    df, lookup = _population([_WIN] * (GATE_MIN_NONTIED - 1) + [_TIE] * 30)
    rep = evaluate_gate(df, lookup)
    assert rep["n_intraday"] >= GATE_MIN_NONTIED  # sobra muestra total...
    assert rep["verdict"] == "INSUFICIENTE"       # ...pero no informativa


def test_pass_requires_significant_majority_and_beating_1100():
    df, lookup = _population([_WIN] * GATE_MIN_NONTIED,
                             [_LOSS] * GATE_MIN_NONTIED)
    rep = evaluate_gate(df, lookup)
    assert rep["sign_p_intraday"] < 0.05
    assert rep["pos_rate_intraday"] > rep["pos_rate_1100"]
    assert rep["verdict"] == "PASS"


def test_rejects_a_positive_majority_that_is_not_significant():
    """16 de 30 positivas es mayoría, pero indistinguible del azar."""
    df, lookup = _population([_WIN] * 16 + [_LOSS] * 14, [_LOSS] * 30)
    rep = evaluate_gate(df, lookup)
    assert rep["pos_rate_intraday"] > 0.5
    assert rep["sign_p_intraday"] > 0.05
    assert rep["verdict"] == "RECHAZO"


def test_rejects_when_1100_picks_beat_the_close_more_often():
    """Batir al azar no basta: hay que batir al grupo de comparación."""
    df, lookup = _population([_WIN] * 25 + [_LOSS] * 5, [_WIN] * 30)
    rep = evaluate_gate(df, lookup)
    assert rep["sign_p_intraday"] < 0.05
    assert rep["verdict"] == "RECHAZO"


def test_evaluate_gate_unmatched_close_rows_are_dropped_not_zeroed():
    df = pd.DataFrame([_log_row(), _log_row(event_id="e9")])
    rep = evaluate_gate(df, _close_lookup({("mlb", "e1", "h2h", "Yankees"): 2.0}))
    assert rep["n_intraday"] == 1  # e9 sin cierre no cuenta como CLV 0
