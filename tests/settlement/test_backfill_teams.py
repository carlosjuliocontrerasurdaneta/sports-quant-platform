# tests/settlement/test_backfill_teams.py
import pandas as pd
from sqp.settlement.backfill_teams import teams_from_odds, backfill_settled_file


def test_teams_from_odds_reads_event_meta(tmp_path):
    odds = tmp_path
    pd.DataFrame([
        {"captured_at": "2026-06-25T09:00:00Z", "event_id": "evt1",
         "commence_time": "2026-06-25T23:05:00Z", "home": "NYY", "away": "BOS",
         "market": "h2h", "outcome": "NYY", "point": "", "price_decimal": 1.9,
         "bookmaker": "x"},
    ]).to_csv(odds / "odds_mlb_202606.csv", index=False)
    meta = teams_from_odds(odds, "mlb")
    assert meta["evt1"] == {"home": "NYY", "away": "BOS", "game_date": "2026-06-25"}


def test_backfill_fills_only_empty_rows_and_is_idempotent(tmp_path):
    path = tmp_path / "settled_mlb.csv"
    pd.DataFrame([
        {"event_id": "evt1", "market": "h2h", "result": "win", "home": "", "away": "", "game_date": ""},
        {"event_id": "evt2", "market": "h2h", "result": "loss", "home": "LAD", "away": "SF", "game_date": "2026-06-24"},
    ]).to_csv(path, index=False)
    meta = {"evt1": {"home": "NYY", "away": "BOS", "game_date": "2026-06-25"}}
    filled, unresolved = backfill_settled_file(path, meta)
    assert (filled, unresolved) == (1, 0)
    df = pd.read_csv(path).fillna("")
    assert df.loc[0, "home"] == "NYY" and df.loc[1, "home"] == "LAD"  # existing untouched
    # second run is a no-op
    assert backfill_settled_file(path, meta) == (0, 0)


def test_backfill_reports_unresolved(tmp_path):
    path = tmp_path / "settled_mlb.csv"
    pd.DataFrame([{"event_id": "ghost", "market": "h2h", "result": "win",
                   "home": "", "away": "", "game_date": ""}]).to_csv(path, index=False)
    filled, unresolved = backfill_settled_file(path, {})
    assert (filled, unresolved) == (0, 1)
