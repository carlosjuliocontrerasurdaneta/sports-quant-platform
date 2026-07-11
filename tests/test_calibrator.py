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


def test_temporal_holdout_keeps_event_sides_together(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    # Two complementary rows per event. A row-level 80/20 split would count
    # eight validation rows as eight independent observations and can split an
    # event at the boundary; the grouped split must report four events.
    rows = []
    for i in range(20):
        day = f"2026-05-{i + 1:02d}"
        rows += [
            {"probability": 0.70, "won": float(i % 2 == 0),
             "date": day, "event_id": f"e{i}"},
            {"probability": 0.30, "won": float(i % 2 != 0),
             "date": day, "event_id": f"e{i}"},
        ]
    res = cal.train_calibration(
        pd.DataFrame(rows), prob_col="probability", outcome_col="won",
        sport="grouped", time_col="date", group_col="event_id")
    assert res["n_train_events"] == 16
    assert res["n_val_events"] == 4
    assert res["n_train"] == 32 and res["n_val"] == 8


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
    monkeypatch.setattr(cal, "calibration_report", lambda probs, outcomes: {"ece": 1.0, "brier_score": 1.0})
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


def test_train_reports_per_gate_verdicts(tmp_path, monkeypatch):
    """Observabilidad del gate: el resultado debe decir CUAL condicion paso/fallo
    (ECE / Brier / monotonia) por modelo. El 2026-07-02 un mlb_spreads que
    MEJORABA el ECE OOS fue descartado y el log solo decia '(dropped)': hubo que
    reproducir el fit a mano para descubrir que fue el Brier. La persistencia
    debe ser exactamente la conjuncion de los tres veredictos."""
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    cal._load_calibrator.cache_clear()
    res = cal.train_calibration(_miscalibrated(), sport="unit_gates")
    for key in ("iso_gate", "beta_gate"):
        assert set(res[key]) == {"ece_ok", "brier_ok", "monotone_ok"}
        for v in res[key].values():
            assert isinstance(v, bool)
    assert res["iso_persisted"] == all(res["iso_gate"].values())
    assert res["beta_persisted"] == all(res["beta_gate"].values())


def test_train_gate_verdicts_flag_brier_failure(tmp_path, monkeypatch):
    """Cuando el drop es por Brier (pasa ECE, es monotono), el veredicto debe
    senalar brier_ok=False y los otros dos True."""
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    cal._load_calibrator.cache_clear()
    monkeypatch.setattr(cal, "calibration_report",
                        lambda probs, outcomes: {"ece": 0.0, "brier_score": 1.0})
    monkeypatch.setattr(cal, "expected_calibration_error", lambda *a, **k: 0.5)
    brier_calls = {"n": 0}

    def fake_brier(*a, **k):
        brier_calls["n"] += 1
        return 0.1 if brier_calls["n"] == 1 else 1.0

    monkeypatch.setattr(cal, "brier_score", fake_brier)

    res = cal.train_calibration(_miscalibrated(), sport="unit_gate_brier")

    assert res["iso_gate"] == {"ece_ok": True, "brier_ok": False, "monotone_ok": True}
    assert res["iso_persisted"] is False


def test_train_drops_calibrator_that_passes_ece_but_worsens_brier(tmp_path, monkeypatch):
    """A monotone calibrator can pass the binned-ECE gate yet be overconfident in
    a way a proper scoring rule exposes: pushing favorites toward 0.9 inflates the
    out-of-sample Brier score even when each ECE bin's average looks fine. That is
    exactly the mlb_spreads regression -- a monotone-but-overfit isotonic step that
    manufactured phantom edges. The gate must reject it on OOS Brier."""
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    cal._load_calibrator.cache_clear()
    # iso PASSES the ECE gate (cal ECE 0.0 <= raw ECE 0.5) but its Brier is worse.
    monkeypatch.setattr(cal, "calibration_report",
                        lambda probs, outcomes: {"ece": 0.0, "brier_score": 1.0})
    monkeypatch.setattr(cal, "expected_calibration_error", lambda *a, **k: 0.5)
    # brier_score: 1st call = raw (low 0.1), 2nd = beta (high 1.0) -> raw beats both.
    brier_calls = {"n": 0}

    def fake_brier(*a, **k):
        brier_calls["n"] += 1
        return 0.1 if brier_calls["n"] == 1 else 1.0

    # raising=False: the production code does not reference brier_score yet (RED).
    monkeypatch.setattr(cal, "brier_score", fake_brier, raising=False)

    res = cal.train_calibration(_miscalibrated(), sport="unit_brier")

    # Passes ECE + is monotone, but worsens OOS Brier -> dropped.
    assert res["iso_persisted"] is False
    assert res["best_method"] is None
    assert not (tmp_path / "models" / "unit_brier_calibration_iso.joblib").exists()
    # live application for this market is therefore a safe no-op
    assert cal.apply_calibration(np.array([0.7]), sport="unit_brier", method="auto")[0] == 0.7


def test_train_to_staging_does_not_promote_to_live(tmp_path, monkeypatch):
    """A retrain must never make a calibrator live in the same cycle. Training
    with staging=True writes the candidate model + a STAGING registry, but leaves
    the LIVE registry untouched, so the pipeline (apply method='auto') stays a
    no-op until an explicit promotion. This is the architectural guard against a
    degenerate daily-retrained calibrator auto-installing itself into production."""
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    cal._load_calibrator.cache_clear()

    res = cal.train_calibration(_miscalibrated(), sport="unit_stage", staging=True)
    assert res["persisted"] is True  # a good candidate was produced

    # LIVE registry untouched -> pipeline still a no-op for this market.
    assert "unit_stage" not in cal._load_method_registry()
    assert cal.apply_calibration(np.array([0.85]), "unit_stage", method="auto")[0] == 0.85
    # ...but the candidate is staged, ready to promote.
    assert "unit_stage" in cal._load_method_registry(staging=True)


def test_promote_calibrators_moves_staging_to_live(tmp_path, monkeypatch):
    """The explicit, separate promotion step copies a staged candidate into the
    live registry (and its model file), after which the pipeline applies it."""
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    cal._load_calibrator.cache_clear()
    cal.train_calibration(_miscalibrated(), sport="unit_promote", staging=True)

    promoted = cal.promote_calibrators()

    assert "unit_promote" in promoted
    assert "unit_promote" in cal._load_method_registry()          # now live
    # the live model file exists and the pipeline now transforms inputs
    assert cal._model_path("unit_promote", "iso").exists()
    out = cal.apply_calibration(np.array([0.85]), "unit_promote", method="auto")[0]
    assert out != 0.85 and 0.01 <= out <= 0.99


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
    monkeypatch.setattr(cal, "calibration_report", lambda probs, outcomes: {"ece": 1.0, "brier_score": 1.0})
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
    monkeypatch.setattr(cal, "calibration_report", lambda probs, outcomes: {"ece": 1.0, "brier_score": 1.0})
    res = cal.train_calibration(_miscalibrated(), sport="unit_drop")

    assert res["iso_persisted"] is False        # worsening model not kept
    assert not iso_path.exists()                # and the stale file is cleaned
    # live application for this market is now a safe no-op
    assert cal.apply_calibration(np.array([0.5]), sport="unit_drop")[0] == 0.5
