"""AUD-007 (auditoria 2026-10-15): log_pitcher_confirmation debe tratar
None/NaN/vacio como equivalentes al comparar contra el CSV releido."""
from __future__ import annotations

import pandas as pd

from sqp.storage.starters import log_pitcher_confirmation


def _row(home: object, away: object, eid: str = "e1") -> dict:
    return {"event_id": eid, "game_date": "2026-10-01", "home": "A", "away": "B",
            "home_pitcher": home, "away_pitcher": away}


def _rows_in_log(tmp_path) -> int:
    p = tmp_path / "data" / "historical" / "pitcher_confirmation_log_mlb.csv"
    return len(pd.read_csv(p))


def test_three_identical_calls_with_none_pitcher_yield_one_row(tmp_path):
    rows = [_row("Cole", None)]
    assert log_pitcher_confirmation(tmp_path, "mlb", rows) == 1
    assert log_pitcher_confirmation(tmp_path, "mlb", rows) == 0
    assert log_pitcher_confirmation(tmp_path, "mlb", rows) == 0
    assert _rows_in_log(tmp_path) == 1


def test_none_nan_and_empty_are_equivalent(tmp_path):
    log_pitcher_confirmation(tmp_path, "mlb", [_row("Cole", None)])
    for absent in (float("nan"), "", None, "nan", "None"):
        assert log_pitcher_confirmation(tmp_path, "mlb", [_row("Cole", absent)]) == 0
    assert _rows_in_log(tmp_path) == 1


def test_real_pitcher_change_appends_new_row(tmp_path):
    log_pitcher_confirmation(tmp_path, "mlb", [_row("Cole", None)])
    assert log_pitcher_confirmation(tmp_path, "mlb", [_row("Cole", "Kershaw")]) == 1
    assert log_pitcher_confirmation(tmp_path, "mlb", [_row("Cole", "Kershaw")]) == 0
    assert log_pitcher_confirmation(tmp_path, "mlb", [_row("Gray", "Kershaw")]) == 1
    assert _rows_in_log(tmp_path) == 3
