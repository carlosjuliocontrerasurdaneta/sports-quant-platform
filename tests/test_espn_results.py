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


# --- ESPN rechaza los rangos de fechas (observado 2026-09-24) -----------------
#
# `dates=A-B` -> 400 "Failed to get events endpoint"; el dia suelto sigue
# funcionando. Sin fallback, TODAS las ligas ESPN devolvian 0 resultados con
# rc=0: el historico estuvo parado del 2026-09-14 al 2026-09-24 sin aviso.


class _RangoRechazadoSession:
    """400 para cualquier rango; 200 con un partido para cada dia suelto."""
    def __init__(self, dia_que_falla: str | None = None):
        self.calls: list[str] = []
        self.dia_que_falla = dia_que_falla

    def get(self, url, params=None, timeout=None):
        dates = params["dates"]
        self.calls.append(dates)
        if "-" in dates:
            return _Resp(400)
        if dates == self.dia_que_falla:
            return _Resp(500)
        return _Resp(200, _GAME)


def test_un_rango_rechazado_se_repite_dia_a_dia(monkeypatch):
    monkeypatch.setattr(espn_results.time, "sleep", lambda *_: None)
    session = _RangoRechazadoSession()
    provider = ESPNResultsProvider(session=session)
    rows = provider.fetch_results("nfl", days_back=3)
    rangos = [c for c in session.calls if "-" in c]
    dias = [c for c in session.calls if "-" not in c]
    assert len(rangos) == 1                     # un solo intento de rango, sin reintentos
    assert len(dias) >= 4 and len(rows) == len(dias)
    assert provider.failed_windows == []


def test_una_ventana_que_falla_del_todo_queda_registrada(monkeypatch):
    monkeypatch.setattr(espn_results.time, "sleep", lambda *_: None)
    from sqp.providers.date_window import fetch_window
    primer_dia = f"{fetch_window(3)[0]:%Y%m%d}"
    provider = ESPNResultsProvider(session=_RangoRechazadoSession(primer_dia))
    provider.fetch_results("nfl", days_back=3)
    assert len(provider.failed_windows) == 1
    assert primer_dia in provider.failed_windows[0]
    # Y se reinicia en cada llamada.
    provider.session = _RangoRechazadoSession()
    provider.fetch_results("nfl", days_back=3)
    assert provider.failed_windows == []


def test_el_backfill_no_sale_en_verde_si_una_ventana_fallo(tmp_path, monkeypatch):
    import importlib.util
    import sys
    from pathlib import Path
    raiz = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "backfill_espn", raiz / "scripts" / "backfill_results.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(espn_results.time, "sleep", lambda *_: None)

    from sqp.providers.date_window import fetch_window
    primer_dia = f"{fetch_window(3)[0]:%Y%m%d}"

    class _Prov(ESPNResultsProvider):
        def __init__(self):
            super().__init__(session=_RangoRechazadoSession(primer_dia))

    monkeypatch.setattr(mod, "ESPNResultsProvider", _Prov)
    monkeypatch.setattr(sys, "argv", ["backfill_results.py", "--days", "3",
                                      "--leagues", "nfl"])
    assert mod.main() == 1
    # Lo que si llego se guarda igualmente.
    from sqp.storage.results_store import ResultsStore
    assert ResultsStore(tmp_path).path("nfl").exists()
