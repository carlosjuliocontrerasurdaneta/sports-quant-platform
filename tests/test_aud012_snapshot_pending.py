"""AUD-012 (ronda audit-2026-10-15): un cache hit no prueba que el snapshot de
la peticion original llegara a `data/odds/`.

`fetch_odds` escribe la cache ANTES de que el run diario persista el snapshot.
Si `append_snapshot` fallaba (o el proceso moria) y se relanzaba dentro del
TTL, la rama de cache anunciaba "snapshot already persisted" sin comprobarlo y
ese snapshot -- evidencia OOS de las cuotas que fundamentan los picks -- no
llegaba nunca a disco. Ahora el run diario marca la respuesta de red como
"snapshot pendiente" y solo la desmarca al persistir; un cache hit con la marca
recupera el snapshot con su instante REAL de adquisicion.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sqp.providers.odds_api import OddsAPIClient
from sqp.providers.odds_cache import FileCache


# --- la marca en la cache y en el cliente -----------------------------------

def test_file_cache_pending_marker_roundtrip(tmp_path):
    c = FileCache(tmp_path / "cache")
    assert not c.is_pending("k")
    c.mark_pending("k")
    assert c.is_pending("k")
    c.clear_pending("k")
    assert not c.is_pending("k")
    c.clear_pending("k")  # idempotente


def test_client_marker_follows_the_last_cache_key(tmp_path):
    cli = OddsAPIClient(api_key="x", cache_dir=tmp_path / "cache", cache_ttl=60)
    assert cli.last_cache_key is None and not cli.snapshot_pending()
    cli.mark_snapshot_pending()          # sin clave: no-op, no revienta
    cli.last_cache_key = "abc"
    cli.mark_snapshot_pending()
    assert cli.snapshot_pending()
    cli.clear_snapshot_pending()
    assert not cli.snapshot_pending()


# --- el run diario ----------------------------------------------------------

class _Cliente:
    """Doble con la superficie de run_league y la marca de snapshot pendiente."""

    def __init__(self, events):
        self._events = events
        self.cache_ttl = 1200.0
        self.last_response_cached = False
        self.last_response_age_s = 0.0
        self.pendiente = False

    def is_sport_active(self, sport_key):      # noqa: ARG002
        return True

    def fetch_odds(self, *a, **k):             # noqa: ARG002
        return self._events

    def fetch_scores(self, *a, **k):           # noqa: ARG002
        return []

    def mark_snapshot_pending(self):
        self.pendiente = True

    def clear_snapshot_pending(self):
        self.pendiente = False

    def snapshot_pending(self):
        return self.pendiente


class _Store:
    llamadas: list = []
    fallar = False

    def __init__(self, root):  # noqa: ARG002
        pass

    def append_snapshot(self, league, events, captured_at=None):
        if _Store.fallar:
            raise OSError("disco lleno (simulado)")
        _Store.llamadas.append((league, len(events), captured_at))
        return len(events)


@pytest.fixture()
def entorno(tmp_path, monkeypatch):
    from sqp.config import Settings
    from sqp.pipeline import daily
    from sqp.providers.synthetic import SyntheticProvider

    cliente = _Cliente(SyntheticProvider("basketball").fetch_odds("nba", three_way=False))
    _Store.llamadas, _Store.fallar = [], False
    monkeypatch.setattr(daily, "ROOT", tmp_path)
    monkeypatch.setattr(daily, "OddsAPIClient", lambda *a, **k: cliente)
    monkeypatch.setattr(daily, "OddsStore", _Store)
    monkeypatch.setattr(daily, "_fetch_recent_scores", lambda *a, **k: [])

    def correr():
        daily.run_league("nba", Settings.load(), mode="live")
    return cliente, correr


def test_a_failed_persist_is_recovered_on_the_cached_retry(entorno):
    cliente, correr = entorno
    _Store.fallar = True
    with pytest.raises(OSError):
        correr()                                   # respuesta de red, persistencia falla
    assert cliente.pendiente, "sin marca el reintento no sabria que falta el snapshot"

    _Store.fallar = False
    cliente.last_response_cached, cliente.last_response_age_s = True, 300.0
    antes = datetime.now(timezone.utc)
    correr()                                       # reintento dentro del TTL
    assert len(_Store.llamadas) == 1, "el snapshot omitido no se recupero"
    _, n, captured_at = _Store.llamadas[0]
    assert n > 0
    adquirido = datetime.fromisoformat(captured_at)
    assert abs((antes - timedelta(seconds=300)) - adquirido) < timedelta(seconds=30), (
        "el snapshot recuperado debe llevar el instante de adquisicion, no el de ahora")
    assert not cliente.pendiente

    correr()                                       # otro cache hit: ya persistido
    assert len(_Store.llamadas) == 1, "un snapshot ya persistido se duplico"


def test_a_cached_response_without_marker_is_not_re_appended(entorno):
    """Comportamiento previo intacto: entradas antiguas y de otros consumidores
    de la cache no tienen marca y no se re-persisten."""
    cliente, correr = entorno
    cliente.last_response_cached = True
    correr()
    assert _Store.llamadas == []


def test_a_network_response_persists_and_clears_the_marker(entorno):
    cliente, correr = entorno
    correr()
    assert len(_Store.llamadas) == 1 and _Store.llamadas[0][2] is None
    assert not cliente.pendiente
