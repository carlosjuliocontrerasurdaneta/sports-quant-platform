"""Tests for the pipeline health report. SYNTHETIC only."""
from __future__ import annotations

import pandas as pd

from sqp.monitoring.health import ML_LEAGUES, generate_health_report


def test_empty_root_errors(tmp_path):
    # Missing artifacts are ERRORS since the 2026-07-24 audit (M-1): they make
    # the pipeline inoperative and must trip the BAT errorlevel guards.
    r = generate_health_report(root=tmp_path)
    assert r["status"] == "ERROR"
    assert set(r["leagues"]) == set(ML_LEAGUES)
    assert any("no stored results" in e for e in r["errors"])
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
    # nba no longer errors about missing results/model; other leagues still do
    assert not any(e.startswith("nba: no stored results") for e in r["errors"])
    assert any(e.startswith("mlb:") for e in r["errors"])
    assert r["status"] == "ERROR"  # still ERROR because mlb/nfl/nhl incomplete


def test_health_detects_per_market_calibration_registry(tmp_path):
    models = tmp_path / "data" / "models"
    models.mkdir(parents=True)
    (models / "mlb_spreads_calibration_iso.joblib").write_bytes(b"x")
    (models / "calibration_methods.json").write_text(
        '{"mlb_spreads": "isotonic"}', encoding="utf-8")
    r = generate_health_report(root=tmp_path)
    assert r["leagues"]["mlb"]["calibration"] is True
    assert r["leagues"]["mlb"]["calibration_markets"] == ["spreads"]


def test_corrupt_results_file_is_logged_not_silently_counted_as_absent(tmp_path, caplog):
    # An unreadable CSV already reaches the same None/0 branch as a missing one,
    # so the status was never wrong -- but the operator could not tell "never
    # ingested" from "ingested and now corrupt", which need different repairs.
    hist = tmp_path / "data" / "historical"
    hist.mkdir(parents=True)
    corrupt = hist / f"results_{ML_LEAGUES[0]}.csv"
    corrupt.write_bytes(b'a,b\n"unterminated,1\n\x00\x00')

    with caplog.at_level("WARNING", logger="sqp.monitoring.health"):
        generate_health_report(root=tmp_path)

    assert any("no se pudo leer" in rec.getMessage() for rec in caplog.records), \
        "un CSV ilegible debe registrarse, no confundirse con uno ausente"
