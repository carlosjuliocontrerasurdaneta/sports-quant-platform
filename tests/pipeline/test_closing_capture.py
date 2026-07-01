from datetime import datetime, timezone
import pandas as pd
from sqp.pipeline.closing_capture import (leagues_with_imminent_bets, _parse_utc,
                                          spent_today, add_spent)


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


# ---------------------------------------------------------------------------
# Task 3: capture_closing orchestrator
# ---------------------------------------------------------------------------
from sqp.domain.models import Event, EventOdds, MarketLine  # noqa: E402
from sqp.pipeline.closing_capture import capture_closing  # noqa: E402


class _FakeClient:
    def __init__(self, events, cost=12, remaining=5000):
        self._events = events
        self.requests_last = cost
        self.requests_remaining = remaining
        self.calls = []

    def fetch_odds(self, league_id, sport_key, markets="h2h,spreads,totals"):
        self.calls.append(league_id)
        return self._events


class _FakeStore:
    def __init__(self):
        self.snapshots = []

    def append_snapshot(self, league, events):
        self.snapshots.append((league, [e.event.event_id for e in events]))
        return len(events)


def _eo(eid):
    ev = Event(event_id=eid, sport_key="baseball_mlb", league="mlb",
               home="NYY", away="BOS", start_time="2026-06-26T23:00:00Z", data_label="real")
    return EventOdds(event=ev, lines=[MarketLine(market="h2h", bookmaker="x",
                                                 outcome="NYY", price_decimal=1.9, point=None)])


def _seed_mlb(pred_dir):
    pd.DataFrame([{"event_id": "e1"}]).to_csv(pred_dir / "candidates_mlb.csv", index=False)
    pd.DataFrame([{"event_id": "e1", "start_time": "2026-06-26T23:00:00Z"}]).to_csv(
        pred_dir / "predictions_mlb.csv", index=False)


def test_capture_persists_only_bet_events(tmp_path, monkeypatch):
    monkeypatch.setattr("sqp.pipeline.closing_capture.ROOT", tmp_path)
    _seed_mlb(tmp_path)
    client = _FakeClient([_eo("e1"), _eo("e_other")])  # only e1 is a bet
    store = _FakeStore()
    now = datetime(2026, 6, 26, 22, 0, tzinfo=timezone.utc)
    out = capture_closing(tmp_path, settings=None, now=now, client=client, odds_store=store)
    assert store.snapshots == [("mlb", ["e1"])]      # e_other filtered out
    assert out["captured"] == {"mlb": 1}
    assert out["credits_spent"] == 12
    assert out["leagues_considered"] == ["mlb"]


def test_capture_respects_daily_cap(tmp_path, monkeypatch):
    monkeypatch.setattr("sqp.pipeline.closing_capture.ROOT", tmp_path)
    _seed_mlb(tmp_path)
    odds_dir = tmp_path / "data" / "odds"
    odds_dir.mkdir(parents=True, exist_ok=True)
    (odds_dir / ".closing_credits_20260626").write_text("300")  # cap already reached
    client = _FakeClient([_eo("e1")])
    store = _FakeStore()
    now = datetime(2026, 6, 26, 22, 0, tzinfo=timezone.utc)
    out = capture_closing(tmp_path, settings=None, max_credits=300, now=now,
                          client=client, odds_store=store)
    assert client.calls == []                         # no fetch when capped
    assert out["skipped_budget"] == ["mlb"]


def test_capture_skips_when_quota_low(tmp_path, monkeypatch):
    monkeypatch.setattr("sqp.pipeline.closing_capture.ROOT", tmp_path)
    _seed_mlb(tmp_path)
    client = _FakeClient([_eo("e1")], remaining=50)   # below min_remaining=100
    store = _FakeStore()
    now = datetime(2026, 6, 26, 22, 0, tzinfo=timezone.utc)
    out = capture_closing(tmp_path, settings=None, min_remaining=100, now=now,
                          client=client, odds_store=store)
    assert client.calls == []
    assert out["skipped_budget"] == ["mlb"]


def test_capture_best_effort_one_league_failure_isolated(tmp_path, monkeypatch):
    monkeypatch.setattr("sqp.pipeline.closing_capture.ROOT", tmp_path)
    _seed_mlb(tmp_path)
    pd.DataFrame([{"event_id": "w1"}]).to_csv(tmp_path / "candidates_wnba.csv", index=False)
    pd.DataFrame([{"event_id": "w1", "start_time": "2026-06-26T23:00:00Z"}]).to_csv(
        tmp_path / "predictions_wnba.csv", index=False)

    class _RaisingStore(_FakeStore):
        def append_snapshot(self, league, events):
            if league == "mlb":
                raise RuntimeError("boom")
            return super().append_snapshot(league, events)

    client = _FakeClient([_eo("e1"), _eo("w1")])
    store = _RaisingStore()
    now = datetime(2026, 6, 26, 22, 0, tzinfo=timezone.utc)
    out = capture_closing(tmp_path, settings=None, now=now, client=client, odds_store=store)
    # mlb raised but was caught; wnba still captured; nothing propagated
    assert "wnba" in out["captured"]
    assert "mlb" not in out["captured"]
