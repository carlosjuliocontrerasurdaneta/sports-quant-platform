"""Tests for the MLB feature builder (runs + pitcher form). SYNTHETIC only."""
from __future__ import annotations

from sqp.features.mlb import build_mlb_dataset
from sqp.storage import feature_store as fs
from sqp.storage.results_store import ResultsStore
from sqp.storage.starters import StartersStore


def _seed_mlb(root):
    games = [
        {"date": "2024-04-01", "home": "NYY", "away": "BOS", "game_id": "1",
         "home_score": 5, "away_score": 3},
        {"date": "2024-04-02", "home": "NYY", "away": "BOS", "game_id": "2",
         "home_score": 2, "away_score": 4},
        {"date": "2024-04-04", "home": "BOS", "away": "TB", "game_id": "3",
         "home_score": 7, "away_score": 1},
        {"date": "2024-04-06", "home": "TB", "away": "NYY", "game_id": "4",
         "home_score": 0, "away_score": 6},
    ]
    ResultsStore(root).upsert("mlb", games)
    StartersStore(root).save("mlb", [
        {"game_id": "1", "date": "2024-04-01", "home_starter": "Cole", "away_starter": "Sale"},
        {"game_id": "2", "date": "2024-04-02", "home_starter": "Rodon", "away_starter": "Crochet"},
        {"game_id": "3", "date": "2024-04-04", "home_starter": "Sale", "away_starter": "Bradley"},
        {"game_id": "4", "date": "2024-04-06", "home_starter": "Pepiot", "away_starter": "Cole"},
    ])


def test_mlb_builder_has_runs_and_pitcher_features():
    import pandas as pd
    df = pd.DataFrame([
        {"date": "2024-04-01", "game_id": "1", "home_team": "NYY", "away_team": "BOS",
         "home_score": 5, "away_score": 3, "home_pitcher": "Cole", "away_pitcher": "Sale"},
        {"date": "2024-04-06", "game_id": "2", "home_team": "BOS", "away_team": "NYY",
         "home_score": 2, "away_score": 1, "home_pitcher": "Sale", "away_pitcher": "Cole"},
    ])
    out, stats = build_mlb_dataset(df)
    assert len(out) == 2
    for col in ("total_runs", "home_rf_l7", "home_p_ra_l5", "away_p_starts", "home_win"):
        assert col in out.columns
    # Cole started game 1 (and allowed away=3 runs); appears in pitcher state.
    assert "__p_Cole" in stats


def test_mlb_feature_store_joins_starters(tmp_path):
    _seed_mlb(tmp_path)
    out = fs.build_training_dataset("mlb", root=tmp_path)
    assert len(out) == 4
    # starters were joined from the starters store (not present in results)
    assert (out["home_pitcher"] != "").any()
    assert fs._feature_path(tmp_path, "mlb").exists()
    assert (tmp_path / "data" / "feature_store" / "mlb_pitcher_state.csv").exists()
    assert "mlb" in fs.SUPPORTED


def test_rest_days_helper_semantics():
    from sqp.features.common import rest_days
    assert rest_days("2024-04-01", "2024-04-03") == 2.0
    assert rest_days("2024-04-01", "2024-04-01") == 1.0  # clamped to >= 1
    assert rest_days("2024-03-01", "2024-04-30", cap=15) == 15.0  # clamped to cap
    assert rest_days(None, "2024-04-03") == 3.0  # no prior game -> neutral default
    assert rest_days("not-a-date", "2024-04-03") == 3.0  # unparseable -> default


def test_mlb_rest_days_matches_shared_helper():
    import pandas as pd
    df = pd.DataFrame([
        {"date": "2024-04-01", "game_id": "1", "home_team": "NYY", "away_team": "BOS",
         "home_score": 5, "away_score": 3},
        {"date": "2024-04-06", "game_id": "2", "home_team": "NYY", "away_team": "BOS",
         "home_score": 2, "away_score": 4},
    ])
    out, _ = build_mlb_dataset(df)
    assert out.loc[0, "home_rest_days"] == 3.0  # first game: default
    assert out.loc[1, "home_rest_days"] == 5.0  # 04-01 -> 04-06
