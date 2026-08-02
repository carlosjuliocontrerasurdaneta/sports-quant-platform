"""Observatorio intradía ampliado a spreads/totals (v2, 2026-08-02): mismo
aislamiento de timing (misma probabilidad servida, precio posterior), con match
de línea EXACTA — si la línea se movió, la probabilidad servida ya no aplica y
la fila se omite."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from sqp.pipeline.intraday_scan import INTRADAY_LOG_FILENAME, log_intraday_edges

NOW = datetime(2026, 7, 20, 16, 0, tzinfo=timezone.utc)


def _served(market, selection, line, prob=0.60):
    return dict(league="wnba", event_id="ev1", home="A", away="B",
                start_time="2026-07-20T17:00:00Z", game_date="2026-07-20",
                market=market, selection=selection, line=line,
                price_decimal=1.90, bookmaker="bk", model_probability=prob,
                estimated_probability=prob, calibrated_probability=prob,
                implied_probability_novig=0.5, estimated_edge=0.05,
                books_count=3, stake=0.0, data_label="real", flags="",
                generated_at="2026-07-20T15:00:00+00:00")


def _odds_row(market, outcome, point, price=2.00):
    return dict(event_id="ev1", commence_time="2026-07-20T17:00:00Z",
                home="A", away="B", market=market, bookmaker="bk",
                outcome=outcome, price_decimal=price, point=point,
                captured_at="2026-07-20T15:45:00+00:00")


def _setup(tmp_path: Path, served_rows, odds_rows):
    cal = tmp_path / "data" / "calibration"
    odds = tmp_path / "data" / "odds"
    pred = tmp_path / "data" / "predictions"
    for d in (cal, odds, pred):
        d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(served_rows).to_csv(cal / "served_wnba.csv", index=False)
    pd.DataFrame(odds_rows).to_csv(odds / "odds_wnba_202607.csv", index=False)
    return pred


def _read_log(tmp_path: Path) -> pd.DataFrame:
    return pd.read_csv(tmp_path / "data" / "bets" / INTRADAY_LOG_FILENAME)


def test_scans_spreads_and_totals_with_exact_line(tmp_path):
    pred = _setup(tmp_path, [
        _served("h2h", "A", ""),
        _served("spreads", "A", -3.5),
        _served("totals", "Over", 160.5),
    ], [
        _odds_row("h2h", "A", None),
        _odds_row("spreads", "A", -3.5, price=1.95),
        _odds_row("totals", "Over", 160.5, price=1.88),
    ])
    s = log_intraday_edges(pred, tmp_path, min_edge=0.02, now=NOW)
    assert s["scanned"] == 3
    log = _read_log(tmp_path)
    assert sorted(log["market"]) == ["h2h", "spreads", "totals"]
    sp = log[log.market == "spreads"].iloc[0]
    assert sp["line"] == -3.5 and sp["price_now"] == 1.95
    tot = log[log.market == "totals"].iloc[0]
    assert tot["line"] == 160.5 and tot["price_now"] == 1.88


def test_moved_line_is_skipped_not_repriced(tmp_path):
    # La probabilidad servida es para -3.5; el snapshot fresco solo cotiza -4.5.
    pred = _setup(tmp_path, [_served("spreads", "A", -3.5)],
                  [_odds_row("spreads", "A", -4.5, price=2.10)])
    s = log_intraday_edges(pred, tmp_path, min_edge=0.02, now=NOW)
    assert s["scanned"] == 0
    assert not (tmp_path / "data" / "bets" / INTRADAY_LOG_FILENAME).exists()


def test_is_candidate_matches_line_for_lined_markets(tmp_path):
    pred = _setup(tmp_path, [
        _served("spreads", "A", -3.5),
        _served("spreads", "A", -5.5),
    ], [
        _odds_row("spreads", "A", -3.5, price=1.95),
        _odds_row("spreads", "A", -5.5, price=2.05),
    ])
    # El pick de las 11:00 fue la línea -3.5; la -5.5 servida NO es candidato.
    pd.DataFrame([dict(event_id="ev1", market="spreads", selection="A",
                       line=-3.5)]).to_csv(pred / "candidates_wnba.csv",
                                           index=False)
    log_intraday_edges(pred, tmp_path, min_edge=0.02, now=NOW)
    log = _read_log(tmp_path).set_index("line")
    assert bool(log.loc[-3.5, "is_candidate"]) is True
    assert bool(log.loc[-5.5, "is_candidate"]) is False


def test_would_generate_uses_min_edge_on_current_price(tmp_path):
    # p=0.60 y precio 1.95 -> edge_now = 0.17 (>= min_edge); precio 1.60 -> -0.04.
    pred = _setup(tmp_path, [
        _served("totals", "Over", 160.5),
        _served("totals", "Under", 160.5),
    ], [
        _odds_row("totals", "Over", 160.5, price=1.95),
        _odds_row("totals", "Under", 160.5, price=1.60),
    ])
    s = log_intraday_edges(pred, tmp_path, min_edge=0.02, now=NOW)
    assert s["scanned"] == 2 and s["would_generate"] == 1
