"""Integration boundaries for the recovered offline research tools."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from sqp.evaluation import feature_shadow
from sqp.storage import feature_store


def load_script(name):
    path = Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_report_hashes_the_bytes_evaluated_even_if_source_is_updated(tmp_path, monkeypatch):
    module = load_script("evaluate_feature_blocks")
    source = tmp_path / "data/historical/results_nba.csv"
    source.parent.mkdir(parents=True)
    original = b"date,game_id,home,away,home_score,away_score\n2025-01-01,001,A,B,100,90\n"
    source.write_bytes(original)
    destination = tmp_path / "report.json"
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "fingerprint", lambda root: "stable")
    monkeypatch.setattr(module, "_league_meta", lambda league: {"family": "basketball"})
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout="fixture"))

    def build(raw, *args, **kwargs):
        assert raw.game_id.tolist() == ["001"]
        assert raw.home_score.tolist() == [100]
        source.write_bytes(original.replace(b",100,", b",999,"))
        return object()

    monkeypatch.setattr(module, "build_research_dataset", build)
    monkeypatch.setattr(module, "evaluate_blocks", lambda *a, **k: {
        "status": "EXPLORATORY_NOT_FOR_PROMOTION", "tasks": {"h2h": {"status": "MEASURED"}}})
    monkeypatch.setattr(sys, "argv", ["evaluate_feature_blocks", "--leagues", "nba", "--out", str(destination)])
    assert module.main() == 0
    report = json.loads(destination.read_text())
    assert report["reports"][0]["source_sha256"] == hashlib.sha256(original).hexdigest()
    assert report["reports"][0]["source_sha256"] != hashlib.sha256(source.read_bytes()).hexdigest()


@pytest.mark.parametrize("league", ["mlb", "nba", "nfl", "nhl"])
@pytest.mark.parametrize("dependency", ["_temporal_module", "_common_module"])
def test_shared_feature_code_invalidates_all_affected_caches(monkeypatch, league, dependency):
    before = feature_store.builder_fingerprint(league)
    original = feature_store._module_source
    changed = getattr(feature_store, dependency)
    monkeypatch.setattr(feature_store, "_module_source",
                        lambda module: original(module) + (b"\n# changed" if module is changed else b""))
    assert feature_store.builder_fingerprint(league) != before


def test_candidate_selection_requires_stable_discovery_code():
    module = load_script("prepare_feature_candidates")
    with pytest.raises(ValueError, match="unchanged"):
        module.prepare({"code_changed_during_run": True}, "hash")


def test_forward_scoring_matches_participants_and_reports_calibration(tmp_path, monkeypatch):
    candidate_id = "nba/h2h/schedule"
    protocol = {"end_exclusive": "2025-02-01T00:00Z", "bootstrap": 40,
                "seed": 42, "alpha": .05, "comparisons": 2,
                "candidates": [{"id": candidate_id, "target": "h2h"}]}
    monkeypatch.setattr(feature_shadow, "load_protocol", lambda *a: protocol)
    monkeypatch.setattr(feature_shadow, "utc_now", lambda: pd.Timestamp("2025-02-02T00:00Z"))
    rows = [{"candidate_id": candidate_id, "league": "nba", "source": "fixture",
             "game_id": str(i), "date": f"2025-01-0{i}", "start_time": f"2025-01-0{i}T12:00Z",
             "home": "A", "away": "B", "candidate": probability,
             "baseline": .5, "operational": .6}
            for i, probability in enumerate([.8, .2, .9], start=1)]
    monkeypatch.setattr(feature_shadow, "captured_rows", lambda *a: rows)
    (tmp_path / "protocol.json").write_text(json.dumps(protocol))
    outcomes = pd.DataFrame([{k: row[k] for k in ("league", "source", "game_id", "home", "away", "start_time")}
                             for row in rows])
    outcomes["home_score"], outcomes["away_score"] = 110, 100
    outcomes.loc[1, ["home", "away"]] = ["B", "A"]  # Reverse the provider's orientation.
    outcomes.loc[2, "start_time"] = "2025-01-03T13:00Z"  # Rescheduled: not the same cutoff.
    path = tmp_path / "outcomes.csv"
    outcomes.to_csv(path, index=False)
    result = feature_shadow.evaluate(tmp_path, tmp_path, path)
    report = result["reports"][0]
    assert (report["n_captured"], report["n_matched"], report["n_excluded"]) == (3, 2, 1)
    assert report["mean_loss"]["candidate"] == pytest.approx(.04)
    assert report["mean_loss"]["baseline"] == pytest.approx(.25)
    assert report["contrasts"]["baseline"]["mean_delta"] == pytest.approx(-.21)
    assert report["calibration"]["candidate"]["brier_score"] == pytest.approx(.04)
    assert report["calibration"]["candidate"]["ece"] == pytest.approx(.2)
    assert report["calibration"]["candidate"]["n_samples"] == 2
    assert result["promotion"] is False
