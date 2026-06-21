"""ESPN results provider: transient 5xx retry, persistent-failure skip, 404 empty."""
import requests

from sqp.providers import espn_results
from sqp.providers.espn_results import ESPNResultsProvider


class _Resp:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self.reason = "Error" if status_code >= 400 else "OK"
        self._payload = payload or {"events": []}

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


class _FakeSession:
    """Returns the queued responses in order, one per GET call."""
    def __init__(self, responses: list[_Resp]):
        self._responses = responses
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        resp = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return resp


_GAME = {"events": [{
    "date": "2024-01-15T00:00Z",
    "competitions": [{
        "status": {"type": {"completed": True}},
        "competitors": [
            {"homeAway": "home", "score": "2", "team": {"displayName": "A"}},
            {"homeAway": "away", "score": "1", "team": {"displayName": "B"}},
        ],
    }],
    "id": "1",
}]}


def test_retry_recovers_after_transient_5xx(monkeypatch):
    monkeypatch.setattr(espn_results.time, "sleep", lambda *_: None)
    session = _FakeSession([_Resp(500), _Resp(503), _Resp(200, _GAME)])
    provider = ESPNResultsProvider(session=session)
    rows = provider._fetch({"path": "soccer/ita.1"}, "20240101-20240130")
    assert len(rows) == 1 and rows[0]["home"] == "A"
    assert session.calls == 3  # two failures then success


def test_persistent_5xx_is_skipped_not_raised(monkeypatch):
    monkeypatch.setattr(espn_results.time, "sleep", lambda *_: None)
    session = _FakeSession([_Resp(500)])
    provider = ESPNResultsProvider(session=session)
    rows = provider._fetch({"path": "soccer/mex.1"}, "20251002-20251031")
    assert rows == []                       # skipped, no exception
    assert session.calls == espn_results._MAX_ATTEMPTS


def test_404_returns_empty_without_retry(monkeypatch):
    monkeypatch.setattr(espn_results.time, "sleep", lambda *_: None)
    session = _FakeSession([_Resp(404)])
    provider = ESPNResultsProvider(session=session)
    assert provider._fetch({"path": "soccer/eng.1"}, "20240101-20240130") == []
    assert session.calls == 1               # 404 is terminal, not retried


def test_one_bad_window_does_not_abort_league(monkeypatch):
    """A league spanning several windows keeps good windows when one persistently fails."""
    monkeypatch.setattr(espn_results.time, "sleep", lambda *_: None)
    # First window: good. Then a window that always 500s (4 attempts). Then good.
    responses = [_Resp(200, _GAME)] + [_Resp(500)] * espn_results._MAX_ATTEMPTS + [_Resp(200, _GAME)]
    session = _FakeSession(responses)
    provider = ESPNResultsProvider(session=session)
    # Drive _fetch three times as fetch_results would across windows.
    total = []
    for win in ("w1", "w2", "w3"):
        total.extend(provider._fetch({"path": "soccer/usa.1"}, win))
    assert len(total) == 2                   # two good windows survive the bad one
