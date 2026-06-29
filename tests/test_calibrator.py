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


def test_is_monotone_increasing_detects_non_monotone():
    # An increasing calibrator passes the guard.
    assert cal._is_monotone_increasing(lambda x: np.asarray(x, dtype=float)) is True
    # A U-shaped map (decreasing then increasing) inverts rank order and is rejected,
    # even though it is a perfectly valid probability in [0, 1].
    assert cal._is_monotone_increasing(lambda x: (np.asarray(x, dtype=float) - 0.5) ** 2) is False


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


class _UShapedBeta:
    """A calibrator whose predict() is U-shaped (decreasing then increasing) -- it
    inverts rank order at the low end, exactly the mlb_spreads degeneracy."""

    def fit(self, probs, outcomes):
        return self

    def predict(self, probs):
        probs = np.asarray(probs, dtype=float)
        return np.clip((probs - 0.5) ** 2 + 0.4, 0.01, 0.99)


def test_train_drops_non_monotone_calibrator_despite_good_ece(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    cal._load_calibrator.cache_clear()
    # Make the isotonic OOS ECE worse than raw so iso is dropped; only beta is a
    # candidate to persist.
    monkeypatch.setattr(cal, "calibration_report", lambda probs, outcomes: {"ece": 1.0})
    # Raw ECE high, beta ECE low -> beta BEATS raw on ECE, so without the
    # monotonicity guard it WOULD persist. Stub statefully: 1st call raw, 2nd beta.
    calls = {"n": 0}

    def fake_ece(*a, **k):
        calls["n"] += 1
        return 0.5 if calls["n"] == 1 else 0.0

    monkeypatch.setattr(cal, "expected_calibration_error", fake_ece)
    # Force the beta calibrator to be non-monotone (U-shaped).
    monkeypatch.setattr(cal, "BetaCalibrator", _UShapedBeta)

    res = cal.train_calibration(_miscalibrated(), sport="unit_ushape")

    # Beats raw on ECE but is rejected purely for non-monotonicity.
    assert res["beta_persisted"] is False
    assert res["best_method"] is None
    assert not (tmp_path / "models" / "unit_ushape_calibration_beta.joblib").exists()
    # live application for this market is therefore a safe no-op
    assert cal.apply_calibration(np.array([0.3]), sport="unit_ushape", method="auto")[0] == 0.3


def test_method_registry_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    assert cal._load_method_registry() == {}          # absent -> empty
    cal._set_best_method("mlb_spreads", "beta")
    cal._set_best_method("nhl_h2h", "isotonic")
    assert cal._load_method_registry() == {"mlb_spreads": "beta",
                                           "nhl_h2h": "isotonic"}
    cal._set_best_method("mlb_spreads", None)          # clear -> group drops out
    assert cal._load_method_registry() == {"nhl_h2h": "isotonic"}


def test_train_records_best_method_and_auto_matches_it(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    cal._load_calibrator.cache_clear()
    res = cal.train_calibration(_miscalibrated(), sport="unit_auto")

    best = res["best_method"]
    assert best in ("isotonic", "beta")               # a winner was chosen
    assert cal._load_method_registry()["unit_auto"] == best
    # method="auto" must resolve to exactly the recorded method's model.
    probs = np.array([0.3, 0.6, 0.9])
    assert np.allclose(cal.apply_calibration(probs, "unit_auto", "auto"),
                       cal.apply_calibration(probs, "unit_auto", best))


def test_apply_auto_noop_when_unregistered(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    probs = np.array([0.2, 0.5, 0.8])
    out = cal.apply_calibration(probs, sport="never_trained", method="auto")
    assert np.allclose(out, probs)                     # no registry entry -> no-op


def test_train_drops_worsening_model_clears_registry(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    cal._load_calibrator.cache_clear()
    cal._set_best_method("unit_noauto", "beta")        # stale entry from a prior fit
    # Force raw to look better than both calibrators so neither persists. raw and
    # beta both call expected_calibration_error, so stub it statefully: 1st call
    # (raw) low, 2nd call (beta) high; iso's ECE comes from calibration_report.
    monkeypatch.setattr(cal, "calibration_report", lambda probs, outcomes: {"ece": 1.0})
    calls = {"n": 0}

    def fake_ece(*a, **k):
        calls["n"] += 1
        return 0.0 if calls["n"] == 1 else 1.0

    monkeypatch.setattr(cal, "expected_calibration_error", fake_ece)
    res = cal.train_calibration(_miscalibrated(), sport="unit_noauto")
    assert res["iso_persisted"] is False and res["beta_persisted"] is False
    assert res["best_method"] is None                  # nothing helped
    assert "unit_noauto" not in cal._load_method_registry()   # stale entry cleared
    # "auto" therefore falls back to a no-op for this group.
    assert cal.apply_calibration(np.array([0.5]), "unit_noauto", "auto")[0] == 0.5


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
