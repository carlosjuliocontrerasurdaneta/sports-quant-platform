"""Discriminating guards for isolated pregame training and capture."""
import json

import numpy as np
import pandas as pd
import pytest

from sqp.evaluation import feature_shadow as shadow
from sqp.features.research import build_research_dataset


def history():
    return pd.DataFrame([{"date": f"2025-01-{i + 1:02}", "game_id": str(i),
                          "home": "A", "away": "B", "home_score": 100 + i % 3,
                          "away_score": 101} for i in range(24)])


def test_unplayed_fixtures_have_no_labels_and_do_not_update_state():
    f = pd.DataFrame([{"date": "2025-02-01", "game_id": "x", "home": "A", "away": "B"},
                      {"date": "2025-02-02", "game_id": "y", "home": "A", "away": "B"}])
    d = build_research_dataset(history(), "nba", "basketball", fixtures=f)
    a = d.frame.tail(2)
    assert a.target_h2h.isna().all() and a.target_total.isna().all()
    assert a.form_home_n.tolist() == [20, 20]
    assert a.form_home_scored.nunique() == 1
    assert a.base_home.nunique() == 1
    with pytest.raises(ValueError, match="must not contain results"):
        build_research_dataset(history(), "nba", "basketball", fixtures=f.assign(home_score=3))
    with pytest.raises(ValueError, match="must follow"):
        build_research_dataset(history(), "nba", "basketball", fixtures=f.assign(date="2025-01-03"))


def test_training_pair_uses_only_selected_features():
    d = build_research_dataset(history(), "nba", "basketball")
    p = shadow.fit_pair(d, {"target": "h2h", "block": "schedule"})
    cols = p["pair"]["candidate"]["columns"]
    assert all(c.startswith(("base_", "schedule_")) for c in cols)
    assert "target_h2h" not in cols
    assert p["n_train"] == 16  # Eight draws must not become away wins.
    x = shadow.design(d.frame, "h2h")
    pred = p["pair"]["candidate"]["model"].predict_proba(x[cols])
    assert np.isfinite(pred).all()
    np.testing.assert_allclose(pred.sum(axis=1), 1)


def test_capture_archive_deduplicates_first_and_rejects_postgame(tmp_path):
    (tmp_path / "protocol.json").write_text('{}')
    for name, captured, probability in (("a", "2025-01-01T10:00Z", .3), ("b", "2025-01-01T11:00Z", .8)):
        folder = tmp_path / "captures" / f"batch_{name}"
        folder.mkdir(parents=True)
        payload = {"protocol_sha256": shadow.digest(tmp_path / "protocol.json"),
                   "predictions": [{"candidate_id": "nba/h2h/schedule", "source": "test", "game_id": "x",
                                    "captured_at": captured, "start_time": "2025-01-01T12:00Z", "candidate": probability}]}
        (folder / "predictions.json").write_text(json.dumps(payload))
    assert shadow.captured_rows(tmp_path)[0]["candidate"] == .3
    payload["predictions"][0]["captured_at"] = "2025-01-01T13:00Z"
    (folder / "predictions.json").write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="post-start"):
        shadow.captured_rows(tmp_path)


def test_evaluation_cannot_peek_before_end(tmp_path, monkeypatch):
    monkeypatch.setattr(shadow, "load_protocol", lambda *a: {"end_exclusive": "2099-01-01T00:00Z"})
    with pytest.raises(ValueError, match="has not ended"):
        shadow.evaluate(tmp_path, tmp_path, tmp_path / "absent.csv")


def test_capture_rejects_outcomes_and_naive_kickoff(tmp_path, monkeypatch):
    monkeypatch.setattr(shadow, "load_protocol", lambda *a: {})
    path = tmp_path / "fixtures.csv"
    fixture = pd.DataFrame([{"league": "nba", "source": "test", "game_id": "x", "home": "A", "away": "B",
                             "start_time": "2099-01-01T12:00:00"}])
    fixture.to_csv(path, index=False)
    with pytest.raises(ValueError, match="explicit timezone"):
        shadow.capture(tmp_path, tmp_path, path)
    fixture.assign(home_score=123).to_csv(path, index=False)
    with pytest.raises(ValueError, match="exactly"):
        shadow.capture(tmp_path, tmp_path, path)


def test_isolated_train_capture_and_future_evaluation(tmp_path, monkeypatch):
    monkeypatch.setattr(shadow, "ROOT", tmp_path)
    monkeypatch.setattr(shadow, "utc_now", lambda: pd.Timestamp("2025-03-01T12:00Z"))
    store = tmp_path / "data/historical"
    store.mkdir(parents=True)
    source = store / "results_nba.csv"
    history().to_csv(source, index=False)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/feature_shadow.py").write_text('# fixture')
    report = tmp_path / "report.json"
    report.write_text('{}')
    c = {"id": "nba/h2h/schedule", "league": "nba", "target": "h2h", "block": "schedule",
         "source_sha256": shadow.digest(source), "window": 20, "status": "AWAITING_FORWARD_PROTOCOL",
         "discovery_through": "2025-01-24"}
    manifest = tmp_path / "selection.json"
    manifest.write_text(json.dumps({"candidates": [c], "discovery_report_sha256": shadow.digest(report)}))
    out = tmp_path / "isolated"
    p = shadow.train(tmp_path, manifest, report, out, "2025-03-02T00:00Z", "2025-03-04T00:00Z")
    assert not (tmp_path / "data/models").exists()
    assert p["promotion"] is False
    fixture = pd.DataFrame([{"league": "nba", "source": "test", "game_id": str(i), "home": "A", "away": "B",
                             "start_time": f"2025-03-0{i}T12:00:00Z"} for i in (2, 3)])
    path = tmp_path / "fixtures.csv"
    fixture.to_csv(path, index=False)
    calls = []
    builder = shadow.build_research_dataset

    def counted_builder(*args, **kwargs):
        calls.append(1)
        return builder(*args, **kwargs)

    monkeypatch.setattr(shadow, "build_research_dataset", counted_builder)
    captured = shadow.capture(tmp_path, out, path)
    assert captured["n_predictions"] == 2
    assert len(calls) == 1  # One replay for two future dates in the same league.
    rows = shadow.captured_rows(out)
    assert all(r["inputs"]["schedule_home_rest_days"] > 20 for r in rows)
    assert all("target_h2h" not in r["inputs"] for r in rows)
    # Repeated captures must not replace the first prediction.
    shadow.capture(tmp_path, out, path)
    assert len(shadow.captured_rows(out)) == 2
    outcomes = fixture.assign(home_score=[110, 95], away_score=[100, 100])
    results_path = tmp_path / "outcomes.csv"
    outcomes.to_csv(results_path, index=False)
    monkeypatch.setattr(shadow, "utc_now", lambda: pd.Timestamp("2025-03-05T12:00Z"))
    # Speed up this test without changing the real fixed protocol.
    bootstrap = shadow.cluster_bootstrap_ci
    monkeypatch.setattr(shadow, "cluster_bootstrap_ci", lambda *a, **k: bootstrap(*a, **{**k, "n_boot": 20}))
    result = shadow.evaluate(tmp_path, out, results_path)
    assert result["reports"][0]["n_matched"] == 2
    assert result["promotion"] is False
    artifact = out / p["candidates"][0]["artifact"]
    artifact.write_bytes(b'corrupt')
    monkeypatch.setattr(shadow, "utc_now", lambda: pd.Timestamp("2025-03-01T12:00Z"))
    with pytest.raises(ValueError, match="model integrity"):
        shadow.capture(tmp_path, out, path)


def test_horizon_excludes_distant_fixtures_without_loading_models(tmp_path, monkeypatch):
    monkeypatch.setattr(shadow, "utc_now", lambda: pd.Timestamp("2025-03-01T12:00Z"))
    monkeypatch.setattr(shadow, "load_protocol", lambda *a: {
        "start": "2025-03-02T00:00Z", "end_exclusive": "2025-04-01T00:00Z",
        "event_horizon_days": 7, "candidates": [{"league": "nba"}]})
    (tmp_path / "captures").mkdir()
    (tmp_path / "protocol.json").write_text('{}')
    path = tmp_path / "fixtures.csv"
    pd.DataFrame([{"league": "nba", "source": "test", "game_id": "x", "home": "A", "away": "B",
                   "start_time": "2025-03-20T12:00:00Z"}]).to_csv(path, index=False)
    result = shadow.capture(tmp_path, tmp_path, path)
    assert result["n_predictions"] == 0
    assert result["n_input"] == 1
