"""Un error del boxscore MLB no puede borrar FIP ya almacenados (AUD-010, ronda
audit-2026-09-23; OPENAI-007, reproducido).

`fetch_starter_fip` hacia `session.get(...).json()` sin mirar el estado HTTP:
un 500 con JSON de error se decodificaba, salia una fila con FIP vacios y el
upsert `keep="last"` de `StarterFIPStore` sustituia 3.2/4.1 por NaN.
"""
from __future__ import annotations

import pandas as pd
import pytest
import requests

from sqp.providers import mlb_statsapi
from sqp.providers.mlb_statsapi import MLBStatsProvider
from sqp.storage.starter_fip import StarterFIPStore


class _Resp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}", response=self)


_SCHEDULE = {"dates": [{"date": "2026-09-01", "games": [
    {"gamePk": 777, "status": {"abstractGameState": "Final",
                               "detailedState": "Final"}}]}]}


def _box_valido():
    def lado(pid, name):
        return {"pitchers": [pid], "players": {f"ID{pid}": {
            "person": {"fullName": name},
            "stats": {"pitching": {"gamesStarted": 1, "homeRuns": 1,
                                   "baseOnBalls": 1, "hitByPitch": 0,
                                   "strikeOuts": 6, "inningsPitched": "6.0"}}}}}
    return {"teams": {"home": lado(1, "Home P"), "away": lado(2, "Away P")}}


class _Session:
    def __init__(self, box_status, box_payload):
        self.box = (box_status, box_payload)

    def get(self, url, **kwargs):  # noqa: ARG002
        if url.endswith("/schedule"):
            return _Resp(200, _SCHEDULE)
        return _Resp(*self.box)


@pytest.fixture(autouse=True)
def _sin_espera(monkeypatch):
    monkeypatch.setattr(mlb_statsapi, "_BACKOFF_SECONDS", 0.0)


def _previo(tmp_path):
    store = StarterFIPStore(tmp_path)
    store.save("mlb", [{"game_id": "777", "date": "2026-09-01",
                        "home_starter": "Home P", "home_starter_fip": 3.2,
                        "away_starter": "Away P", "away_starter_fip": 4.1}])
    return store


@pytest.mark.parametrize("status, payload", [
    (500, {"message": "Internal Server Error"}),
    (429, {"message": "Too Many Requests"}),
    (200, {"message": "no es un boxscore"}),
    (200, ["lista", "no", "objeto"]),
])
def test_boxscore_fallido_no_emite_fila_ni_borra_fip(tmp_path, status, payload):
    store = _previo(tmp_path)
    filas = MLBStatsProvider(_Session(status, payload)).fetch_starter_fip(days_back=5)
    assert filas == []
    store.save("mlb", filas)
    df = pd.read_csv(store.path("mlb"), dtype={"game_id": str})
    fila = df[df["game_id"] == "777"].iloc[0]
    assert fila["home_starter_fip"] == pytest.approx(3.2)
    assert fila["away_starter_fip"] == pytest.approx(4.1)


def test_boxscore_valido_sigue_actualizando():
    filas = MLBStatsProvider(_Session(200, _box_valido())).fetch_starter_fip(days_back=5)
    assert len(filas) == 1
    assert filas[0]["home_starter"] == "Home P"
    assert filas[0]["home_starter_fip"] is not None
