"""On-disk odds cache: hit within TTL, expiry, force-refresh, offline mode."""
import pytest

from sqp.exceptions import ProviderNotConfiguredError
from sqp.providers.odds_api import OddsAPIClient
from sqp.providers.odds_cache import FileCache

_ODDS = [{
    "id": "e1", "commence_time": "2026-06-14T23:00:00Z",
    "home_team": "A", "away_team": "B",
    "bookmakers": [{"key": "dk", "markets": [{"key": "h2h", "outcomes": [
        {"name": "A", "price": 1.8}, {"name": "B", "price": 2.1}]}]}],
}]


class _Resp:
    status_code = 200
    headers = {"x-requests-remaining": "100", "x-requests-last": "3"}

    def json(self):
        return _ODDS

    def raise_for_status(self):
        pass


class _CountingSession:
    def __init__(self):
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        return _Resp()


def _client(tmp_path, session, **kw):
    return OddsAPIClient("k", regions="us", odds_format="decimal", session=session,
                         cache_dir=tmp_path / "cache", **kw)


def test_file_cache_roundtrip_and_ttl(tmp_path):
    c = FileCache(tmp_path)
    k = c.key("/x", {"a": 1, "apiKey": "secret"})
    assert c.get(k, ttl=100) is None
    c.put(k, {"v": 1})
    assert c.get(k, ttl=100) == {"v": 1}
    assert c.get(k, ttl=0) is None                 # expired immediately
    # api key must not change the key (excluded)
    assert k == c.key("/x", {"a": 1, "apiKey": "other"})


def test_second_fetch_served_from_cache(tmp_path):
    session = _CountingSession()
    client = _client(tmp_path, session, cache_ttl=1000)
    client.fetch_odds("mlb", "baseball_mlb")
    client.fetch_odds("mlb", "baseball_mlb")
    assert session.calls == 1                       # second call hit the cache, 0 credits


def test_force_refresh_bypasses_cache(tmp_path):
    session = _CountingSession()
    client = _client(tmp_path, session, cache_ttl=1000, force_refresh=True)
    client.fetch_odds("mlb", "baseball_mlb")
    client.fetch_odds("mlb", "baseball_mlb")
    assert session.calls == 2                       # always live


def test_offline_mode_uses_cache_only(tmp_path):
    # cold offline cache -> no live call allowed -> raises
    offline = _client(tmp_path, _CountingSession(), offline_mode=True)
    with pytest.raises(ProviderNotConfiguredError):
        offline.fetch_odds("mlb", "baseball_mlb")
    # warm the cache with a live client, then offline serves it with no HTTP
    _client(tmp_path, _CountingSession(), cache_ttl=1000).fetch_odds("mlb", "baseball_mlb")
    sess = _CountingSession()
    warm = _client(tmp_path, sess, offline_mode=True)
    assert warm.fetch_odds("mlb", "baseball_mlb")    # returns parsed events
    assert sess.calls == 0                           # served from disk, no API call


def test_file_cache_ttl_boundary_is_deterministic(tmp_path, monkeypatch):
    # El test de TTL fallaba SOLO en la pata Windows del CI desde (al menos) el
    # 2026-08-02: la condicion era `age > ttl`, asi que con ttl=0 un archivo
    # escrito en el mismo tick del reloj tenia age==0.0 y NO expiraba. La
    # granularidad de mtime del runner lo hacia determinista alli y no en local,
    # y el fallo sobrevivio dias porque nadie miraba el CI.
    # "younger than ttl" significa age < ttl, luego expira con age >= ttl.
    # El reloj se congela para clavar el borde exacto en vez de depender de el.
    import os

    c = FileCache(tmp_path)
    k = c.key("/x", {"a": 1})
    c.put(k, {"v": 1})
    f = tmp_path / f"{k}.json"

    frozen = 1_000_000.0
    monkeypatch.setattr("sqp.providers.odds_cache.time.time", lambda: frozen)

    os.utime(f, (frozen, frozen))               # edad EXACTAMENTE 0
    assert c.get(k, ttl=0) is None              # ttl=0 nunca sirve nada
    assert c.get(k, ttl=float("inf")) == {"v": 1}   # inf ignora la edad

    os.utime(f, (frozen, frozen - 10.0))        # edad EXACTAMENTE 10
    assert c.get(k, ttl=10) is None             # borde: age == ttl -> expira
    assert c.get(k, ttl=11) == {"v": 1}         # mas joven -> sirve
