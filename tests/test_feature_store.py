"""Tests for the ported feature store + generic builder. SYNTHETIC data only."""
from __future__ import annotations

import pytest

from sqp.features.builders import CONFIGS, build_team_rolling_dataset
from sqp.storage import feature_store as fs
from sqp.storage.results_store import ResultsStore


def _seed_results(root, league="nba"):
    """A small chronological set of games (base CSV schema: home/away)."""
    games = [
        {"date": "2024-01-01", "home": "LAL", "away": "BOS", "game_id": "1",
         "home_score": 110, "away_score": 100},
        {"date": "2024-01-03", "home": "BOS", "away": "LAL", "game_id": "2",
         "home_score": 105, "away_score": 108},
        {"date": "2024-01-05", "home": "LAL", "away": "MIA", "game_id": "3",
         "home_score": 99, "away_score": 101},
        {"date": "2024-01-07", "home": "MIA", "away": "BOS", "game_id": "4",
         "home_score": 120, "away_score": 115},
        {"date": "2024-01-09", "home": "BOS", "away": "MIA", "game_id": "5",
         "home_score": 98, "away_score": 97},
    ]
    ResultsStore(root).upsert(league, games)
    return games


def test_builder_is_temporal_and_complete(tmp_path):
    df = fs._results_df(tmp_path, "nba")  # empty -> seed first
    _seed_results(tmp_path, "nba")
    df = fs._results_df(tmp_path, "nba")
    out, state = build_team_rolling_dataset(df, CONFIGS["nba"])

    assert len(out) == 5
    # core label/columns present
    for col in ("home_win", "total_pts", "home_win_rate", "home_pts_l5", "diff_rest_days"):
        assert col in out.columns
    # temporal correctness: earliest game has no prior games for either team
    first = out.sort_values("date").iloc[0]
    assert first["home_games"] == 0 and first["away_games"] == 0
    # a team that has played shows accumulated games later
    assert out["home_games"].max() >= 1
    assert set(state) == {"LAL", "BOS", "MIA"}


def test_build_training_dataset_persists_and_reuses(tmp_path):
    _seed_results(tmp_path, "nba")
    out = fs.build_training_dataset("nba", root=tmp_path)
    assert len(out) == 5
    assert fs._feature_path(tmp_path, "nba").exists()
    assert fs._manifest_path(tmp_path, "nba").exists()
    assert (tmp_path / "data" / "feature_store" / "nba_team_state.csv").exists()
    # unchanged source -> reused (current)
    assert fs.dataset_is_current(tmp_path, "nba")


def test_unknown_league_rejected(tmp_path):
    with pytest.raises(ValueError):
        fs.build_training_dataset("epl", root=tmp_path)  # no ML builder for soccer


def test_nhl_uses_total_goals(tmp_path):
    _seed_results(tmp_path, "nhl")
    out = fs.build_training_dataset("nhl", root=tmp_path)
    assert "total_goals" in out.columns and "total_pts" not in out.columns
