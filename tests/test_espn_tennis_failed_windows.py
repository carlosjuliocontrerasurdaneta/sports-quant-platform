"""AUD-005 (ronda audit-2026-10-15): ventanas fallidas del proveedor de tenis.

Una ventana de fechas que agota reintentos se registra en `failed_windows`
(mismo contrato que `ESPNResultsProvider`), el backfill sale con rc=1 y la
liquidacion NO anula por expiracion (irreversible) con ventanas fallidas.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import requests

from sqp.providers import espn_tennis
from sqp.providers.date_window import fetch_window
from sqp.providers.espn_tennis import ESPNTennisResultsProvider, query_days


def _payload(day_iso: str) -> dict:
    return {"events": [{"groupings": [{"competitions": [{
        "id": "m1", "date": f"{day_iso}T12:00Z",
        "status": {"type": {"completed": True}},
        "competitors": [
            {"athlete": {"displayName": "Player A"}, "winner": True},
            {"athlete": {"displayName": "Player B"}, "winner": False},
        ]}]}]}]}


class _Resp:
    def __init__(self, status: int, payload: dict | None = None):
        self.status_code = status
        self.reason = "Service Unavailable" if status >= 400 else "OK"
        self.headers: dict = {}
        self._payload = payload or {"events": []}

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


class _Session:
    """503 en la fecha `bad`; el resto responde con un partido."""
    def __init__(self, bad: str | None):
        self.bad = bad

    def get(self, url, params=None, timeout=None):
        if self.bad is not None and params["dates"] == self.bad:
            return _Resp(503)
        d = params["dates"]
        return _Resp(200, _payload(f"{d[:4]}-{d[4:6]}-{d[6:]}"))


def _setup(monkeypatch, days_back: int = 20):
    monkeypatch.setattr(espn_tennis.time, "sleep", lambda *_: None)
    start, end = fetch_window(days_back)
    days = query_days(start, end)
    assert len(days) >= 2
    return days


def test_ventana_fallida_se_registra_y_el_resto_se_conserva(monkeypatch):
    days = _setup(monkeypatch)
    bad = f"{days[0]:%Y%m%d}"
    prov = ESPNTennisResultsProvider(session=_Session(bad))  # type: ignore[arg-type]
    rows = prov.fetch_results("atp", days_back=20)
    assert len(prov.failed_windows) == 1
    assert bad in prov.failed_windows[0] and "503" in prov.failed_windows[0]
    assert rows  # el partido de la otra ventana llega igualmente


def test_sin_fallos_failed_windows_vacio_y_se_reinicia(monkeypatch):
    days = _setup(monkeypatch)
    prov = ESPNTennisResultsProvider(session=_Session(f"{days[0]:%Y%m%d}"))  # type: ignore[arg-type]
    prov.fetch_results("atp", days_back=20)
    assert prov.failed_windows
    prov.session = _Session(None)  # type: ignore[assignment]
    prov.fetch_results("atp", days_back=20)
    assert prov.failed_windows == []


def test_backfill_tenis_sale_rc1_con_ventana_fallida(tmp_path, monkeypatch):
    days = _setup(monkeypatch, days_back=3)
    raiz = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "backfill_tennis_mod", raiz / "scripts" / "backfill_tennis_results.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    bad = f"{days[0]:%Y%m%d}"

    class _Prov(ESPNTennisResultsProvider):
        def __init__(self) -> None:
            super().__init__(session=_Session(bad))  # type: ignore[arg-type]

    monkeypatch.setattr(mod, "ESPNTennisResultsProvider", _Prov)
    monkeypatch.setattr(sys, "argv", ["b.py", "--tours", "atp", "--days", "3"])
    assert mod.main() == 1
    # Sano: rc=0.
    class _Sano(ESPNTennisResultsProvider):
        def __init__(self) -> None:
            super().__init__(session=_Session(None))  # type: ignore[arg-type]

    monkeypatch.setattr(mod, "ESPNTennisResultsProvider", _Sano)
    assert mod.main() == 0


