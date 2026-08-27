"""Politica de reintento del cliente de The Odds API.

El 2026-08-27 el run diario perdio el dia entero: The Odds API estuvo
inalcanzable de 11:03:25 a 11:05:42 y cada llamada agotaba sus tres intentos en
~6 segundos. Ningun pick generado, el tablero con los candidatos de la vispera.
Estas pruebas fijan las dos mitades del arreglo: esperar minutos cuando el
servidor no responde, y NO colgar el run cuando el corte es real.
"""
from __future__ import annotations

import pytest
import requests

from sqp.providers import odds_api
from sqp.providers.odds_api import OddsAPIClient


class _Resp:
    def __init__(self, status: int, payload: object = None):
        self.status_code = status
        self.reason = "test"
        self._payload = payload if payload is not None else []
        self.headers: dict[str, str] = {}

    def json(self) -> object:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


class _Session:
    """Devuelve las respuestas programadas; `None` significa 'inalcanzable'."""

    def __init__(self, guion: list[object]):
        self._guion = list(guion)
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        item = self._guion.pop(0) if self._guion else _Resp(200)
        if item is None:
            raise requests.ConnectionError("boom")
        return item


@pytest.fixture
def sin_dormir(monkeypatch):
    dormido: list[float] = []
    monkeypatch.setattr(odds_api.time, "sleep", dormido.append)
    return dormido


def _client(guion: list[object]) -> tuple[OddsAPIClient, _Session]:
    ses = _Session(guion)
    return OddsAPIClient("k", session=ses, cache_ttl=0, offline_mode=False), ses


def test_una_caida_de_dos_minutos_se_supera(sin_dormir):
    """Cuatro fallos de conexion seguidos y a la quinta responde: el caso del
    2026-08-27. Antes se rendia al tercero, en el segundo seis."""
    cli, ses = _client([None, None, None, None, _Resp(200, [{"ok": 1}])])
    assert cli._get("/sports") == [{"ok": 1}]
    assert ses.calls == 5
    assert sum(sin_dormir) >= 120.0, "debe cubrir mas de dos minutos"


def test_un_corte_real_no_cuelga_el_run(sin_dormir):
    """Presupuesto de espera POR CLIENTE: veinte ligas x dos minutos serian 40
    minutos de run colgado. Agotado el presupuesto, se vuelve al fallo rapido."""
    cli, _ = _client([None] * 200)
    for _ in range(6):
        with pytest.raises(requests.ConnectionError):
            cli._get("/sports")
    assert sum(sin_dormir) <= odds_api._CONNECTION_WAIT_BUDGET


def test_un_5xx_sigue_reintentando_rapido(sin_dormir):
    """Un servidor que CONTESTA se recupera rapido; nada cambia para el."""
    cli, ses = _client([_Resp(503), _Resp(503), _Resp(200, [{"ok": 1}])])
    assert cli._get("/sports") == [{"ok": 1}]
    assert ses.calls == 3
    assert sum(sin_dormir) <= 6.0


def test_el_mensaje_no_filtra_la_api_key(sin_dormir):
    """La excepcion de requests lleva la URL completa con `apiKey=`."""
    cli, _ = _client([None] * 10)
    with pytest.raises(requests.ConnectionError) as exc:
        cli._get("/sports")
    assert "apiKey" not in str(exc.value)
    assert "query redacted" in str(exc.value)
