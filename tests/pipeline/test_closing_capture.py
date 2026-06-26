from datetime import datetime, timezone
import pandas as pd
from sqp.pipeline.closing_capture import leagues_with_imminent_bets, _parse_utc


def _seed(pred_dir, league, cand_ids, pred_rows):
    pd.DataFrame([{"event_id": e} for e in cand_ids]).to_csv(
        pred_dir / f"candidates_{league}.csv", index=False)
    pd.DataFrame(pred_rows).to_csv(pred_dir / f"predictions_{league}.csv", index=False)


def test_parse_utc_handles_z_suffix_and_naive():
    assert _parse_utc("2026-06-26T23:05:00Z").tzinfo is not None
    assert _parse_utc("2026-06-26T23:05:00").tzinfo is not None  # naive -> assumed UTC
    assert _parse_utc("garbage") is None


def test_only_bet_events_inside_window(tmp_path):
    now = datetime(2026, 6, 26, 22, 0, tzinfo=timezone.utc)
    _seed(tmp_path, "mlb", ["e1", "e2"], [
        {"event_id": "e1", "start_time": "2026-06-26T23:00:00Z"},  # in 60 min -> include
        {"event_id": "e2", "start_time": "2026-06-27T05:00:00Z"},  # in 7h -> exclude
        {"event_id": "e3", "start_time": "2026-06-26T23:10:00Z"},  # soon but NOT bet -> exclude
    ])
    out = leagues_with_imminent_bets(tmp_path, now, window_min=120)
    assert out == {"mlb": ["e1"]}


def test_league_without_imminent_bet_is_omitted(tmp_path):
    now = datetime(2026, 6, 26, 22, 0, tzinfo=timezone.utc)
    _seed(tmp_path, "wnba", ["w1"],
          [{"event_id": "w1", "start_time": "2026-06-27T02:00:00Z"}])  # 4h out
    assert leagues_with_imminent_bets(tmp_path, now, window_min=120) == {}


from sqp.pipeline.closing_capture import spent_today, add_spent


def test_credit_counter_accumulates_and_isolates_by_day(tmp_path):
    assert spent_today(tmp_path, "20260626") == 0
    assert add_spent(tmp_path, "20260626", 12) == 12
    assert add_spent(tmp_path, "20260626", 24) == 36     # accumulates same day
    assert spent_today(tmp_path, "20260626") == 36
    assert spent_today(tmp_path, "20260627") == 0        # new day resets
    assert add_spent(tmp_path, "20260626", -5) == 36     # negative ignored


def test_credit_counter_survives_corrupt_file(tmp_path):
    (tmp_path / ".closing_credits_20260626").write_text("not-a-number")
    assert spent_today(tmp_path, "20260626") == 0        # tolerant
