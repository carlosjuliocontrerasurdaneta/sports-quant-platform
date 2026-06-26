import pandas as pd
from sqp.settlement.runner import _event_meta_map, _attach_event_meta


def test_event_meta_map_extracts_teams_and_date():
    raw = [{"id": "evt1", "home_team": "NYY", "away_team": "BOS",
            "commence_time": "2026-06-25T23:05:00Z", "completed": True,
            "scores": [{"name": "NYY", "score": "5"}, {"name": "BOS", "score": "3"}]}]
    meta = _event_meta_map(raw)
    assert meta["evt1"] == {"home": "NYY", "away": "BOS", "game_date": "2026-06-25"}


def test_attach_event_meta_adds_columns_by_event_id():
    settled = pd.DataFrame([{"event_id": "evt1", "market": "h2h", "result": "win"},
                            {"event_id": "missing", "market": "h2h", "result": "loss"}])
    meta = {"evt1": {"home": "NYY", "away": "BOS", "game_date": "2026-06-25"}}
    out = _attach_event_meta(settled, meta)
    assert out.loc[0, "home"] == "NYY" and out.loc[0, "away"] == "BOS"
    assert out.loc[0, "game_date"] == "2026-06-25"
    assert out.loc[1, "home"] == ""  # unmatched event_id -> empty, not error


def test_attach_event_meta_empty_df_is_noop():
    out = _attach_event_meta(pd.DataFrame(), {})
    assert out.empty
