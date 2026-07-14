"""Tests del monitor de degradacion por (liga, mercado). SYNTHETIC only."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from sqp.config import Settings
from sqp.risk.degradation import (DEGRADATION_FILENAME, DEGRADATION_LOG_FILENAME,
                                  degradation_metrics, evaluate_pauses,
                                  load_degradation_registry, paused_from_registry,
                                  run_degradation_monitor,
                                  write_degradation_registry)

TODAY = date(2026, 7, 13)


def _metrics_row(league="mlb", market="totals", n=40, brier_model=0.25,
                 brier_market=0.25, roi_flat=0.0) -> pd.DataFrame:
    return pd.DataFrame([{"league": league, "market": market, "n": n,
                          "brier_model": brier_model, "brier_market": brier_market,
                          "roi_flat": roi_flat}])


def _settled(n: int, *, result="loss", est=0.7, implied=0.5, price=2.0,
             game_date="2026-07-10") -> pd.DataFrame:
    return pd.DataFrame([{"league": "mlb", "market": "totals", "result": result,
                          "estimated_probability": est,
                          "implied_probability_novig": implied,
                          "price_decimal": price, "game_date": game_date,
                          "stake": 0.0, "pnl": 0.0}] * n)


# --- metricas de ventana --------------------------------------------------------

def test_metrics_grading_window_and_values():
    df = pd.concat([
        _settled(3, result="win", game_date="2026-07-10"),
        _settled(1, result="loss", game_date="2026-07-10"),
        _settled(5, result="void", game_date="2026-07-10"),   # no graduada: fuera
        _settled(7, result="loss", game_date="2026-01-01"),   # fuera de ventana
    ], ignore_index=True)
    m = degradation_metrics(df, window_days=60, today=TODAY)
    assert len(m) == 1
    r = m.iloc[0]
    assert r["n"] == 4
    # win: (0.7-1)^2=0.09 x3; loss: (0.7-0)^2=0.49 -> media 0.19
    assert r["brier_model"] == pytest.approx(0.19)
    # implied 0.5: (0.25*3 + 0.25)/4 = 0.25
    assert r["brier_market"] == pytest.approx(0.25)
    # stake plano: 3 wins x (2.0-1) + 1 loss x (-1) = +2 sobre 4 picks
    assert r["roi_flat"] == pytest.approx(0.5)


def test_metrics_empty_and_missing_columns():
    assert degradation_metrics(pd.DataFrame(), today=TODAY).empty
    no_implied = _settled(4).drop(columns=["implied_probability_novig"])
    m = degradation_metrics(no_implied, today=TODAY)
    assert pd.isna(m.iloc[0]["brier_market"])  # sin baseline: no dispara Brier


# --- gate de pausa / reanudacion -------------------------------------------------

def test_pause_on_brier_worse_than_market():
    markets, trans = evaluate_pauses(
        _metrics_row(brier_model=0.30, brier_market=0.25), {}, min_n=30)
    entry = markets["mlb|totals"]
    assert entry["paused"] and entry["reasons"] == ["brier_worse_than_market"]
    assert len(trans) == 1 and trans[0]["action"] == "pause"


def test_pause_on_roi_below_threshold():
    markets, _ = evaluate_pauses(_metrics_row(roi_flat=-0.30), {}, min_n=30)
    assert markets["mlb|totals"]["reasons"] == ["roi_flat_below_threshold"]


def test_no_pause_below_min_n_or_within_thresholds():
    markets, trans = evaluate_pauses(
        _metrics_row(n=10, brier_model=0.40, brier_market=0.25), {}, min_n=30)
    assert not markets["mlb|totals"]["paused"] and not trans
    markets, trans = evaluate_pauses(_metrics_row(roi_flat=-0.10), {}, min_n=30)
    assert not markets["mlb|totals"]["paused"] and not trans


def test_hysteresis_holds_then_resumes():
    paused_prev = {"mlb|totals": {"paused": True, "since": "2026-07-01T00:00:00",
                                  "reasons": ["roi_flat_below_threshold"]}}
    # roi recupero sobre roi_pause pero no llega a roi_resume: sigue pausado
    markets, trans = evaluate_pauses(
        _metrics_row(roi_flat=-0.10), paused_prev, min_n=30,
        roi_pause=-0.15, roi_resume=-0.05)
    entry = markets["mlb|totals"]
    assert entry["paused"] and entry["reasons"] == ["hysteresis_hold"]
    assert entry["since"] == "2026-07-01T00:00:00" and not trans
    # ambas metricas recuperadas: reanuda y deja transicion
    markets, trans = evaluate_pauses(
        _metrics_row(roi_flat=0.02), paused_prev, min_n=30)
    assert not markets["mlb|totals"]["paused"]
    assert len(trans) == 1 and trans[0]["action"] == "resume"


def test_insufficient_sample_never_lifts_a_pause():
    paused_prev = {"mlb|totals": {"paused": True, "since": "2026-07-01T00:00:00",
                                  "reasons": ["brier_worse_than_market"]}}
    for metrics in (pd.DataFrame(), _metrics_row(n=5, roi_flat=0.10)):
        markets, trans = evaluate_pauses(metrics, paused_prev, min_n=30)
        assert markets["mlb|totals"]["paused"] and not trans


# --- registro y fusion ------------------------------------------------------------

def test_registry_roundtrip_and_paused_map(tmp_path):
    markets = {"mlb|totals": {"paused": True, "since": "x", "reasons": ["r"],
                              "n": 40, "brier_model": 0.3, "brier_market": None,
                              "roi_flat": -0.2, "updated_at": "x"},
               "nba|h2h": {"paused": False, "since": None, "reasons": [], "n": 50,
                           "brier_model": 0.2, "brier_market": 0.21,
                           "roi_flat": 0.01, "updated_at": "x"}}
    path = write_degradation_registry(markets, tmp_path, params={"min_n": 30})
    assert path.name == DEGRADATION_FILENAME
    assert load_degradation_registry(tmp_path) == markets
    assert paused_from_registry(markets) == {"mlb": ["totals"]}
    assert load_degradation_registry(tmp_path / "nope") == {}


def test_run_monitor_e2e_pause_and_idempotent_log(tmp_path):
    # 40 picks degradados: siempre pierde con estimada 0.7 (Brier 0.49 vs 0.25
    # del mercado) y ROI plano -1: ambas condiciones de pausa
    _settled(40).to_csv(tmp_path / "settled_mlb.csv", index=False)
    path, trans, paused = run_degradation_monitor(tmp_path, min_n=30, today=TODAY)
    assert paused == {"mlb": ["totals"]}
    assert len(trans) == 1 and trans[0]["reasons"].count(";") == 1
    assert (tmp_path / DEGRADATION_LOG_FILENAME).exists()
    n_log = len(pd.read_csv(tmp_path / DEGRADATION_LOG_FILENAME))
    # segunda corrida: mismo estado, sin transiciones nuevas ni filas de log
    _, trans2, paused2 = run_degradation_monitor(tmp_path, min_n=30, today=TODAY)
    assert paused2 == paused and not trans2
    assert len(pd.read_csv(tmp_path / DEGRADATION_LOG_FILENAME)) == n_log


# --- settings ---------------------------------------------------------------------

def test_settings_degradation_defaults_and_validation():
    s = Settings()
    assert s.degradation_enabled is False  # Settings() directo: monitor apagado
    s.degradation_roi_pause = -0.05
    s.degradation_roi_resume = -0.15  # histeresis invertida: invalida
    with pytest.raises(ValueError, match="DEGRADATION_ROI_RESUME"):
        s.validate()
