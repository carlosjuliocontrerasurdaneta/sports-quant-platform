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


def test_file_cache_expires_when_mtime_is_ahead_of_the_clock(tmp_path, monkeypatch):
    # AUD-MED-001 (2026-09-06). Este es el caso que el test de borde de arriba NO
    # puede producir: al congelar el reloj Y fijar el mtime al mismo valor, la
    # edad nunca sale negativa. En la pata Windows del CI si salia -- `time.time()`
    # y el mtime de NTFS no comparten reloj ni granularidad --, y con edad
    # negativa NINGUN ttl caducaba, ni siquiera 0: el CI de `main` llevaba rojo
    # desde el 2026-09-05 por esto (run 33994699340, 1 failed / 1546 passed).
    #
    # Se fuerza el mtime medio segundo POR DELANTE del reloj, que es exactamente
    # lo que produce esa diferencia de granularidad -- y tambien lo que deja un
    # salto de reloj hacia atras por correccion NTP.
    import os

    c = FileCache(tmp_path)
    k = c.key("/x", {"a": 1})
    c.put(k, {"v": 1})
    f = tmp_path / f"{k}.json"

    frozen = 1_000_000.0
    monkeypatch.setattr("sqp.providers.odds_cache.time.time", lambda: frozen)
    os.utime(f, (frozen + 0.5, frozen + 0.5))       # edad = -0.5

    assert c.get(k, ttl=0) is None                  # ttl=0 nunca sirve nada
    assert c.get(k, ttl=float("inf")) == {"v": 1}   # inf sigue ignorando la edad
    # Una edad negativa se trata como 0, no como "infinitamente joven": con un
    # ttl positivo la entrada sigue siendo servible, que es lo correcto.
    assert c.get(k, ttl=10) == {"v": 1}


class TestOfflineNoConvierteEnAccionable:
    """AUD-20260906-06 (Codex, MEDIUM, REPRODUCED).

    `_get` sustituia el TTL por `inf` en modo offline, asi que el techo de
    frescura que `daily` impone acotando `cache_ttl` -- derivado de
    `revalidation_price_max_age_min`, 90 min canonicos -- dejaba de gobernar la
    lectura. El pipeline persistia candidatos con stake, `data_label="real"` y
    `generated_at` de AHORA sobre cuotas de cuatro horas.

    La separacion correcta, que es la que se implementa: offline SI puede leer
    una respuesta antigua -- ese es su proposito --, pero su antiguedad viaja con
    ella y decide si el precio es ACCIONABLE. Si un precio no vale para MANTENER
    un pick, no vale para CREARLO.
    """

    def test_la_cache_expone_la_antiguedad(self, tmp_path):
        import os
        import time
        c = FileCache(tmp_path)
        k = c.key("/x", {"a": 1})
        assert c.age_s(k) is None, "sin entrada no hay edad"
        c.put(k, {"v": 1})
        f = tmp_path / f"{k}.json"
        os.utime(f, (time.time() - 4 * 3600, time.time() - 4 * 3600))
        edad = c.age_s(k)
        assert edad is not None and 3.9 * 3600 < edad < 4.1 * 3600

    def test_la_edad_nunca_es_negativa(self, tmp_path):
        """Mismo motivo que el piso de `get`: el mtime puede ir por delante."""
        import os
        import time
        c = FileCache(tmp_path)
        k = c.key("/x", {"a": 1}); c.put(k, {"v": 1})
        f = tmp_path / f"{k}.json"
        os.utime(f, (time.time() + 5.0, time.time() + 5.0))
        assert c.age_s(k) == 0.0

    def test_offline_sirve_la_respuesta_vieja_pero_declara_su_edad(self, tmp_path):
        """Las dos mitades a la vez: se PUEDE leer (offline sigue funcionando) y
        se SABE que es vieja (el pipeline puede negarle el stake)."""
        import os
        import time
        session = _CountingSession()
        client = _client(tmp_path, session, offline_mode=True, cache_ttl=60)
        # Se siembra la cache como si un run anterior la hubiera escrito.
        ckey = client._cache.key("/sports/baseball_mlb/odds", {
            "regions": "us", "oddsFormat": "decimal", "markets": "h2h"})
        client._cache.put(ckey, _ODDS)
        f = (tmp_path / "cache" / f"{ckey}.json")
        viejo = time.time() - 4 * 3600
        os.utime(f, (viejo, viejo))

        datos = client._get("/sports/baseball_mlb/odds", cache=True,
                            regions="us", oddsFormat="decimal", markets="h2h")
        assert datos == _ODDS, "offline debe seguir sirviendo lo cacheado"
        assert session.calls == 0, "offline no toca la red"
        assert client.last_response_cached is True
        assert client.last_response_age_s > 3.9 * 3600, (
            "la antiguedad se perdia: el pipeline no podia distinguir esta "
            "respuesta de una recien traida de la red")

    def test_una_respuesta_de_red_declara_edad_cero(self, tmp_path):
        """Contraprueba: sin esto, un umbral de frescura marcaria como vencido
        todo lo que llega de la red."""
        client = _client(tmp_path, _CountingSession(), cache_ttl=1000)
        client.fetch_odds("mlb", "baseball_mlb")
        assert client.last_response_age_s == 0.0
