"""Tests for the pipeline health report. SYNTHETIC only."""
from __future__ import annotations

import pandas as pd

from sqp.monitoring.health import ML_LEAGUES, generate_health_report


def test_empty_root_warns(tmp_path):
    r = generate_health_report(root=tmp_path)
    assert r["status"] == "WARN"
    assert set(r["leagues"]) == set(ML_LEAGUES)
    assert any("no stored results" in w for w in r["warnings"])
    assert (tmp_path / "data" / "output" / "pipeline_health.json").exists()


def test_present_artifacts_reduce_warnings(tmp_path):
    data = tmp_path / "data"
    (data / "historical").mkdir(parents=True)
    (data / "features").mkdir(parents=True)
    (data / "models").mkdir(parents=True)
    pd.DataFrame({"date": ["2024-01-01"], "home": ["A"], "away": ["B"],
                  "game_id": ["1"], "home_score": [1], "away_score": [0]}
                 ).to_csv(data / "historical" / "results_nba.csv", index=False)
    pd.DataFrame({"home_win": [1, 0]}).to_csv(
        data / "features" / "nba_training_dataset.csv", index=False)
    (data / "models" / "nba_moneyline_model.joblib").write_bytes(b"x")

    r = generate_health_report(root=tmp_path)
    assert r["leagues"]["nba"]["results_rows"] == 1
    assert r["leagues"]["nba"]["moneyline_model"] is True
    # nba no longer warns about missing results/model; other leagues still do
    assert not any(w.startswith("nba: no stored results") for w in r["warnings"])
    assert any(w.startswith("mlb:") for w in r["warnings"])
    assert r["status"] == "WARN"  # still WARN because mlb/nfl/nhl incomplete


def test_health_detects_per_market_calibration_registry(tmp_path):
    models = tmp_path / "data" / "models"
    models.mkdir(parents=True)
    (models / "mlb_spreads_calibration_iso.joblib").write_bytes(b"x")
    (models / "calibration_methods.json").write_text(
        '{"mlb_spreads": "isotonic"}', encoding="utf-8")
    r = generate_health_report(root=tmp_path)
    assert r["leagues"]["mlb"]["calibration"] is True
    assert r["leagues"]["mlb"]["calibration_markets"] == ["spreads"]
