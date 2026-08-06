"""The Odds API historical-odds snapshot parsing and credit-cost capture."""
import pytest
from sqp.providers.odds_api import OddsAPIClient

_SNAPSHOT = {
    "timestamp": "2026-06-10T17:55:37Z",
    "previous_timestamp": "2026-06-10T17:50:37Z",
    "next_timestamp": "2026-06-10T18:00:37Z",
    "data": [{
        "id": "evt1", "commence_time": "2026-06-10T23:05:00Z",
        "home_team": "Rays", "away_team": "Red Sox",
        "bookmakers": [{"key": "dk", "markets": [{"key": "h2h", "outcomes": [
            {"name": "Rays", "price": 1.8}, {"name": "Red Sox", "price": 2.1}]}]}],
    }],
}


class _Resp:
    status_code = 200
    headers = {"x-requests-last": "10", "x-requests-remaining": "19627",
               "x-requests-used": "373"}

    def json(self):
        return _SNAPSHOT

    def raise_for_status(self):
        pass


class _FakeSession:
    def __init__(self):
        self.last_params = None

    def get(self, url, params=None, timeout=None):
        self.last_params = params
        return _Resp()


def test_fetch_historical_odds_parses_snapshot_and_cost(tmp_path):
    session = _FakeSession()
    client = OddsAPIClient("k", regions="us", odds_format="decimal", session=session,
                           cache_dir=tmp_path / "cache")
    snap = client.fetch_historical_odds("baseball_mlb", "2026-06-10T18:00:00Z", "mlb", "h2h")
    assert snap["timestamp"] == "2026-06-10T17:55:37Z"
    assert snap["next_timestamp"] == "2026-06-10T18:00:37Z"
    assert len(snap["events"]) == 1
    ev = snap["events"][0]
    assert ev.event.league == "mlb" and ev.event.home == "Rays"
    assert len(ev.lines) == 2
    # the historical 'date' param and per-call credit cost are wired through
    assert session.last_params["date"] == "2026-06-10T18:00:00Z"
    assert client.requests_last == 10
    assert client.requests_remaining == 19627


def test_fetch_scores_rejects_out_of_range_days_from():
    """days_from fuera de [1, 3] falla en local, no con un 422 por liga.

    El 2026-08-06 un `--days-from 10` produjo cuatro 422 consecutivos que en el
    log son indistinguibles de una caida del proveedor, gastando una llamada
    por liga para averiguar algo conocido de antemano (auditoria F-09 bis)."""
    from sqp.providers.odds_api import OddsAPIClient
    client = OddsAPIClient("dummy-key")
    for bad in (0, 4, 10, -1):
        with pytest.raises(ValueError, match="fuera del rango"):
            client.fetch_scores("baseball_mlb", days_from=bad)
