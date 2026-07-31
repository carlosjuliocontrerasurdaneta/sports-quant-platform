"""Marcador modelo vs mercado (decision 2026-07-31).

La pregunta que la idea fundacional del proyecto plantea es: ¿nuestras
probabilidades estimadas son tan buenas como las del mercado? El mercado no es
aqui el rival a batir para ganar dinero, sino el PATRON DE MEDIDA: la no-vig del
consenso es el mejor estimador disponible de la probabilidad real.

Se compara con Brier y log loss sobre las MISMAS filas (comparacion pareada), y
el intervalo se agrupa por evento porque el stream servido guarda los dos lados
de cada mercado y esas filas no son independientes.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from sqp.evaluation.model_vs_market import brier, log_loss_safe, score_model_vs_market


def _rows(pairs, league="mlb", market="h2h", start=0):
    """pairs = [(p_model, p_market, result), ...] -> DataFrame del stream graded."""
    return pd.DataFrame([
        {"league": league, "market": market, "event_id": f"e{start+i}",
         "model_probability": pm, "implied_probability_novig": pk, "result": r}
        for i, (pm, pk, r) in enumerate(pairs)])


# --- metricas base ------------------------------------------------------------

def test_brier_is_mean_squared_error():
    # p=0.7 y gana -> (0.7-1)^2 = 0.09 ; p=0.7 y pierde -> 0.49
    assert brier(np.array([0.7, 0.7]), np.array([1, 0])) == pytest.approx((0.09 + 0.49) / 2)


def test_brier_of_a_perfect_forecast_is_zero():
    assert brier(np.array([1.0, 0.0]), np.array([1, 0])) == pytest.approx(0.0)


def test_log_loss_clips_to_avoid_infinity():
    """Una probabilidad de 0 o 1 equivocada daria log loss infinito y arruinaria
    el promedio de todo el segmento."""
    v = log_loss_safe(np.array([0.0]), np.array([1]))
    assert np.isfinite(v) and v > 0


# --- comparacion --------------------------------------------------------------

def test_identical_probabilities_give_zero_difference():
    df = _rows([(0.6, 0.6, "win"), (0.4, 0.4, "loss"), (0.7, 0.7, "win")])
    out = score_model_vs_market(df, n_boot=200, seed=1)
    assert out["brier_diff"].iloc[0] == pytest.approx(0.0, abs=1e-9)


def test_a_better_model_gets_a_negative_difference():
    """Brier mas bajo = mejor. diff = modelo - mercado, asi que negativo = el
    modelo gana. Modelo clarividente contra mercado que dice 50/50."""
    df = _rows([(1.0, 0.5, "win")] * 20 + [(0.0, 0.5, "loss")] * 20)
    out = score_model_vs_market(df, n_boot=200, seed=1)
    assert out["brier_diff"].iloc[0] < 0
    assert out["brier_model"].iloc[0] < out["brier_market"].iloc[0]


def test_a_worse_model_gets_a_positive_difference():
    df = _rows([(0.5, 1.0, "win")] * 20 + [(0.5, 0.0, "loss")] * 20)
    out = score_model_vs_market(df, n_boot=200, seed=1)
    assert out["brier_diff"].iloc[0] > 0


def test_confidence_interval_excludes_zero_when_the_gap_is_systematic():
    df = _rows([(1.0, 0.5, "win")] * 60 + [(0.0, 0.5, "loss")] * 60)
    out = score_model_vs_market(df, n_boot=500, seed=1).iloc[0]
    assert out["brier_diff_hi"] < 0, "una ventaja clara debe dar IC enteramente negativo"


def test_confidence_interval_includes_zero_when_they_are_equivalent():
    rng = np.random.default_rng(7)
    pairs = []
    for _ in range(150):
        p = float(rng.uniform(0.3, 0.7))
        r = "win" if rng.random() < p else "loss"
        pairs.append((p, p + float(rng.normal(0, 0.001)), r))
    out = score_model_vs_market(_rows(pairs), n_boot=500, seed=1).iloc[0]
    assert out["brier_diff_lo"] <= 0 <= out["brier_diff_hi"]


# --- estructura y robustez ----------------------------------------------------

def test_segments_by_league_and_market():
    df = pd.concat([_rows([(0.6, 0.6, "win")] * 5, "mlb", "h2h"),
                    _rows([(0.6, 0.6, "win")] * 5, "mlb", "totals", start=100),
                    _rows([(0.6, 0.6, "win")] * 5, "wnba", "h2h", start=200)])
    out = score_model_vs_market(df, n_boot=100, seed=1)
    assert len(out) == 3
    assert set(out["league"]) == {"mlb", "wnba"}


def test_counts_events_apart_from_rows():
    """El stream guarda los dos lados de cada mercado: 4 filas pueden ser 2
    eventos, y el intervalo debe agruparse por evento, no por fila."""
    df = _rows([(0.6, 0.6, "win"), (0.4, 0.4, "loss")] * 2)
    df["event_id"] = ["A", "A", "B", "B"]
    out = score_model_vs_market(df, n_boot=100, seed=1)
    assert out["n_rows"].iloc[0] == 4
    assert out["n_events"].iloc[0] == 2


def test_rows_without_a_usable_probability_are_dropped():
    df = _rows([(0.6, 0.6, "win"), (np.nan, 0.5, "win"), (0.5, np.nan, "loss")])
    out = score_model_vs_market(df, n_boot=100, seed=1)
    assert out["n_rows"].iloc[0] == 1


def test_pushes_and_voids_are_excluded():
    df = _rows([(0.6, 0.6, "win"), (0.6, 0.6, "push"), (0.6, 0.6, "void")])
    out = score_model_vs_market(df, n_boot=100, seed=1)
    assert out["n_rows"].iloc[0] == 1


def test_is_reproducible_with_the_same_seed():
    df = _rows([(0.7, 0.5, "win")] * 30 + [(0.3, 0.5, "loss")] * 30)
    a = score_model_vs_market(df, n_boot=300, seed=42)["brier_diff_lo"].iloc[0]
    b = score_model_vs_market(df, n_boot=300, seed=42)["brier_diff_lo"].iloc[0]
    assert a == b
