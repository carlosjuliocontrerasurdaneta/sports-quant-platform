"""Métricas de calibración: tests de valor conocido y entradas vacías.

Auditoría 2026-08-19 (T2): las funciones estaban monkeypatcheadas en
test_calibrator.py pero sin test de valor conocido ni borde vacío.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from sqp.calibration.metrics import (
    brier_score,
    calibration_report,
    expected_calibration_error,
    log_loss,
    reliability_table,
)


# --- brier_score --------------------------------------------------------------

def test_brier_perfect_predictions_is_zero():
    assert brier_score([1.0, 0.0], [1, 0]) == pytest.approx(0.0)


def test_brier_worst_predictions_is_one():
    assert brier_score([0.0, 1.0], [1, 0]) == pytest.approx(1.0)


def test_brier_uniform_half():
    assert brier_score([0.5, 0.5], [1, 0]) == pytest.approx(0.25)


def test_brier_single_sample():
    assert brier_score([0.7], [1]) == pytest.approx((0.7 - 1) ** 2)


# --- log_loss -----------------------------------------------------------------

def test_log_loss_perfect_predictions_is_finite():
    # p=1.0 se clipea a 1-eps; el resultado debe ser finito, no -inf
    ll = log_loss([1.0, 0.0], [1, 0])
    assert math.isfinite(ll)
    assert ll < 1e-9


def test_log_loss_symmetric():
    # predecir 0.9 en un evento que ocurre == predecir 0.1 en uno que no ocurre
    assert log_loss([0.9], [1]) == pytest.approx(log_loss([0.1], [0]))


def test_log_loss_uniform_50_pct():
    ll = log_loss([0.5], [1])
    assert ll == pytest.approx(math.log(2))


# --- reliability_table --------------------------------------------------------

def test_reliability_table_empty_input():
    tbl = reliability_table([], [])
    assert tbl.empty


def test_reliability_table_bins_cover_all_samples():
    tbl = reliability_table([0.1, 0.5, 0.9], [0, 1, 1])
    assert int(tbl["n"].sum()) == 3


def test_reliability_table_has_required_columns():
    tbl = reliability_table([0.3, 0.7], [0, 1])
    assert {"bin_low", "bin_high", "n",
            "mean_estimated_probability", "observed_frequency"}.issubset(tbl.columns)


# --- expected_calibration_error -----------------------------------------------

def test_ece_empty_input_returns_nan():
    ece = expected_calibration_error([], [])
    assert math.isnan(ece)


def test_ece_perfectly_calibrated_is_zero():
    # Cuando mean_estimated_probability == observed_frequency en cada bin, ECE=0
    p = np.asarray([0.1, 0.5, 0.9])
    ece = expected_calibration_error(p, p)
    assert ece == pytest.approx(0.0, abs=1e-10)


def test_ece_fully_miscalibrated_is_positive():
    # Probabilidades altas, resultados todos cero: ECE > 0
    ece = expected_calibration_error([0.9] * 10, [0] * 10)
    assert ece > 0


# --- calibration_report -------------------------------------------------------

def test_calibration_report_keys():
    report = calibration_report([0.6, 0.4], [1, 0])
    assert {"ece", "brier_score", "log_loss",
            "n_samples", "mean_estimated_probability",
            "observed_frequency"}.issubset(report)


def test_calibration_report_n_samples():
    report = calibration_report([0.6, 0.4, 0.5], [1, 0, 1])
    assert report["n_samples"] == 3
