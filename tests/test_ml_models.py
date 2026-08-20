"""Tests for the ported ML training/prediction/blend. SYNTHETIC data only."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from sqp.models import ml_predict, ml_train
from sqp.models.blend import blend_probabilities


def _synthetic_dataset(n: int = 240, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    f1, f2 = rng.normal(size=n), rng.normal(size=n)
    p = 1 / (1 + np.exp(-(1.5 * f1 - 1.0 * f2)))  # learnable signal
    y = (rng.uniform(size=n) < p).astype(int)
    return pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=n, freq="D"),
        "home_team": "A", "away_team": "B", "game_id": range(n),
        "home_win": y, "total_pts": rng.normal(210, 10, n),
        "home_feat": f1, "away_feat": f2,
    })


def test_feature_columns_excludes_labels_and_meta():
    df = _synthetic_dataset(60)
    cols = ml_train.feature_columns(df)
    assert set(cols) == {"home_feat", "away_feat"}
    assert "home_win" not in cols and "total_pts" not in cols and "game_id" not in cols


@pytest.mark.slow
def test_train_and_predict_round_trip(tmp_path):
    df = _synthetic_dataset()
    res = ml_train.train_moneyline(df, "nba", root=tmp_path)
    assert (tmp_path / "data" / "models" / "nba_moneyline_model.joblib").exists()
    assert (tmp_path / "data" / "models" / "registry.json").exists()
    assert res["metrics"]["cv_roc_auc_mean"] > 0.5  # learns the signal

    # predict with columns in a different order + an extra column (must reindex)
    probe = df.head(5)[["away_feat", "home_feat"]].copy()
    probe["irrelevant"] = 1.0
    p = ml_predict.predict_moneyline(probe, "nba", root=tmp_path)
    assert p.shape == (5,)
    assert np.all((p >= 0.01) & (p <= 0.99))


@pytest.mark.slow
def test_train_totals(tmp_path):
    df = _synthetic_dataset()
    res = ml_train.train_totals(df, "nba", root=tmp_path)
    assert (tmp_path / "data" / "models" / "nba_totals_model.joblib").exists()
    assert res["metrics"]["cv_mae_mean"] >= 0.0


@pytest.mark.slow
def test_oos_metrics_gate(tmp_path):
    df = _synthetic_dataset()
    m = ml_train.oos_moneyline_metrics(df, "nba")
    for k in ("ece", "brier_score", "log_loss", "n_samples"):
        assert k in m


def test_blend_weights():
    p_sim = np.array([0.4, 0.6])
    p_ml = np.array([0.8, 0.2])
    assert np.allclose(blend_probabilities(p_sim, p_ml, 0.0), p_sim)   # blend off
    assert np.allclose(blend_probabilities(p_sim, p_ml, 1.0), p_ml)    # pure ML
    assert np.allclose(blend_probabilities(p_sim, p_ml, 0.5), [0.6, 0.4])


def test_predict_missing_model_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        ml_predict.predict_moneyline(pd.DataFrame({"home_feat": [0.1]}), "nfl", root=tmp_path)


def test_register_corrupt_registry_backed_up_not_silently_discarded(tmp_path, caplog):
    reg_path = tmp_path / "data" / "models" / "registry.json"
    reg_path.parent.mkdir(parents=True)
    reg_path.write_text("{corrupto, no es json", encoding="utf-8")
    with caplog.at_level("WARNING", logger="sqp.models.ml_train"):
        ml_train._register(tmp_path, {"sport": "nba", "model": "moneyline"})
    # El contenido corrupto queda preservado en un backup, no descartado.
    backups = list(reg_path.parent.glob("registry.json.corrupt-*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "{corrupto, no es json"
    assert any("registry" in r.message.lower() for r in caplog.records)
    # El registro nuevo arranca limpio con la entrada agregada.
    import json as _json
    assert _json.loads(reg_path.read_text(encoding="utf-8")) == [
        {"sport": "nba", "model": "moneyline"}]
