"""Tests for the ported probability calibrator. SYNTHETIC data only."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.isotonic import IsotonicRegression

from sqp.calibration import calibrator as cal
from sqp.calibration.metrics import expected_calibration_error


def _miscalibrated(n: int = 3000, seed: int = 0):
    """Estimated probs with a monotone systematic bias vs true outcome rate."""
    rng = np.random.default_rng(seed)
    model_prob = rng.uniform(0.1, 0.9, n)
    true_prob = np.clip(model_prob ** 1.8, 0.02, 0.98)  # systematic overconfidence
    outcomes = (rng.uniform(size=n) < true_prob).astype(float)
    return pd.DataFrame({"probability": model_prob, "home_win": outcomes})


def test_beta_calibrator_bounds():
    rng = np.random.default_rng(1)
    p = rng.uniform(0.05, 0.95, 500)
    y = (rng.uniform(size=500) < p).astype(float)
    out = cal.BetaCalibrator().fit(p, y).predict(p)
    assert out.shape == p.shape
    assert np.all(out >= 0.01) and np.all(out <= 0.99)


def test_apply_without_model_is_noop():
    probs = np.array([0.2, 0.5, 0.8])
    out = cal.apply_calibration(probs, sport="no_such_sport_xyz")
    assert np.allclose(out, probs)  # unchanged when no model exists


def test_train_improves_oos_calibration(tmp_path, monkeypatch):
    # Redirect model persistence to a temp dir (don't touch the project's data/).
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")

    df = _miscalibrated()
    split = int(len(df) * 0.8)
    raw_val_ece = expected_calibration_error(
        df.iloc[split:]["probability"], df.iloc[split:]["home_win"])

    res = cal.train_calibration(df, sport="unit_test")

    assert res["n_train"] + res["n_val"] == len(df)
    assert (tmp_path / "models" / "unit_test_calibration_iso.joblib").exists()
    # Calibration must not worsen out-of-sample; here it clearly improves.
    assert res["val_metrics"]["ece"] <= raw_val_ece

    # Round-trip: a trained model now transforms inputs within bounds.
    out = cal.apply_calibration(np.array([0.3, 0.6, 0.9]), sport="unit_test")
    assert np.all(out >= 0.01) and np.all(out <= 0.99)


def test_train_rejects_tiny_dataset(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    df = pd.DataFrame({"probability": [0.5] * 10, "home_win": [0, 1] * 5})
    with pytest.raises(ValueError):
        cal.train_calibration(df, sport="too_small")


def test_persist_or_remove_writes_and_cleans_stale(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    (tmp_path / "models").mkdir()
    cal._load_calibrator.cache_clear()
    p = cal._model_path("x_h2h", "iso")
    # keep=True persists the model
    assert cal._persist_or_remove(IsotonicRegression(), p, keep=True) is True
    assert p.exists()
    # keep=False removes the stale model -> live application falls back to no-op
    assert cal._persist_or_remove(IsotonicRegression(), p, keep=False) is False
    assert not p.exists()
    # removing an already-absent model is safe
    assert cal._persist_or_remove(IsotonicRegression(), p, keep=False) is False


def test_train_keeps_improving_model_and_reports_flags(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    cal._load_calibrator.cache_clear()
    res = cal.train_calibration(_miscalibrated(), sport="unit_keep")
    # clearly miscalibrated input -> calibration helps -> persisted
    assert res["iso_persisted"] is True and res["persisted"] is True
    assert "beta_val_ece" in res
    assert (tmp_path / "models" / "unit_keep_calibration_iso.joblib").exists()


def test_train_drops_worsening_model_and_removes_stale(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    cal._load_calibrator.cache_clear()
    iso_path = cal._model_path("unit_drop", "iso")
    iso_path.parent.mkdir(parents=True, exist_ok=True)
    iso_path.write_bytes(b"stale")  # a previously-persisted model now on disk

    # Force the isotonic OOS ECE to look worse than raw so the gate must drop it.
    monkeypatch.setattr(cal, "calibration_report", lambda probs, outcomes: {"ece": 1.0})
    res = cal.train_calibration(_miscalibrated(), sport="unit_drop")

    assert res["iso_persisted"] is False        # worsening model not kept
    assert not iso_path.exists()                # and the stale file is cleaned
    # live application for this market is now a safe no-op
    assert cal.apply_calibration(np.array([0.5]), sport="unit_drop")[0] == 0.5
