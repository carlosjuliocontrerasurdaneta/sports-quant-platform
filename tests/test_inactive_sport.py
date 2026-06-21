"""Live-mode guard: inactive or unknown sport keys skip fetch with empty output."""
from sqp.config import Settings
from sqp.pipeline.daily import run_league
from sqp.providers.odds_api import OddsAPIClient


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        return _FakeResponse(self.payload)


def test_is_sport_active_states_and_cache():
    session = _FakeSession([{"key": "soccer_mexico_ligamx", "active": False},
                            {"key": "basketball_wnba", "active": True}])
    client = OddsAPIClient("test-key", session=session)
    assert client.is_sport_active("soccer_mexico_ligamx") is False
    assert client.is_sport_active("basketball_wnba") is True
    assert client.is_sport_active("soccer_unknown") is None
    assert session.calls == 1  # /sports fetched once, then served from cache


def test_run_league_skips_inactive_sport(monkeypatch):
    def _fail(*args, **kwargs):
        raise AssertionError("fetch must not be called for an inactive sport")

    monkeypatch.setattr(OddsAPIClient, "is_sport_active", lambda self, key: False)
    monkeypatch.setattr(OddsAPIClient, "fetch_odds", _fail)
    monkeypatch.setattr(OddsAPIClient, "fetch_scores", _fail)
    df = run_league("ligamx", Settings.load(), mode="live")
    assert df.empty


def test_already_started_guard():
    from sqp.pipeline.daily import _already_started
    assert _already_started("2020-01-01T00:00:00Z") is True
    assert _already_started("2099-01-01T00:00:00Z") is False
    assert _already_started("") is False


def test_within_horizon_drops_far_future_events():
    from datetime import datetime, timedelta, timezone
    from sqp.domain.models import Event, EventOdds
    from sqp.pipeline.daily import _within_horizon

    def _ev(days: int) -> EventOdds:
        t = (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return EventOdds(event=Event(event_id=str(days), sport_key="x", league="nfl",
                                     home="A", away="B", start_time=t))

    events = [_ev(1), _ev(3), _ev(88)]               # 88d = next-season opener
    assert [e.event.event_id for e in _within_horizon(events, 7)] == ["1", "3"]
    assert _within_horizon(events, 0) == events       # 0/None disables the filter


def test_finalize_removes_stale_candidates_when_none(tmp_path, monkeypatch):
    import sqp.pipeline.daily as daily
    monkeypatch.setattr(daily, "ROOT", tmp_path)
    cand = tmp_path / "data" / "predictions" / "candidates_nfl.csv"
    cand.parent.mkdir(parents=True)
    cand.write_text("event_id,stake\nold,5.0\n", encoding="utf-8")  # stale from a prior run
    daily._finalize("nfl", [{"home": "A", "away": "B"}], [], mode="live")
    assert not cand.exists()  # stale picks must be cleared, not left behind


def test_run_league_skips_unknown_sport_key(monkeypatch):
    monkeypatch.setattr(OddsAPIClient, "is_sport_active", lambda self, key: None)
    df = run_league("ligamx", Settings.load(), mode="live")
    assert df.empty
