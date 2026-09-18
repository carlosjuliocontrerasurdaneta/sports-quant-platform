"""AUD-006 (ronda audit-2026-09-18): la captura de cierre pide los MISMOS
mercados que el run diario genera para la liga. En tenis el run pide solo
`h2h` (5 creditos con 5 regiones); la captura pedia el default
`h2h,spreads,totals` (15 creditos): 22 capturas de tenis en el log = 330
creditos en vez de 110, y snapshots con mercados que ningun pick usa.
"""
from __future__ import annotations

import pytest

from sqp.pipeline import closing_capture
from sqp.pipeline.daily import markets_for_family


class _Cliente:
    requests_remaining = None
    requests_last = 0

    def __init__(self):
        self.llamadas: list[tuple[str, str, str]] = []

    def fetch_odds(self, league_id, sport_key, markets="h2h,spreads,totals"):
        self.llamadas.append((league_id, sport_key, markets))
        return []


class _Store:
    def append_snapshot(self, league, events):
        return 0


class _Ajustes:
    odds_api_key = "dummy"
    regions = "us"


@pytest.mark.parametrize("league, esperado", [
    ("tennis_wta_guadalajara_open", "h2h"),
    ("mlb", "h2h,spreads,totals"),
    ("epl", "h2h,spreads,totals"),
])
def test_closing_capture_pide_los_mercados_del_run_diario(tmp_path, monkeypatch,
                                                         league, esperado):
    monkeypatch.setattr(closing_capture, "ROOT", tmp_path)
    monkeypatch.setattr(closing_capture, "leagues_with_imminent_bets",
                        lambda *a, **k: {league: ["ev1"]})
    monkeypatch.setattr(closing_capture, "spent_today", lambda *a, **k: 0)
    cliente = _Cliente()
    closing_capture.capture_closing(tmp_path, settings=_Ajustes(),
                                    client=cliente, odds_store=_Store())
    assert cliente.llamadas and cliente.llamadas[0][2] == esperado


def test_markets_for_family_es_la_regla_unica():
    assert markets_for_family("tennis") == "h2h"
    for fam in ("baseball", "soccer", "basketball", "hockey", "football"):
        assert markets_for_family(fam) == "h2h,spreads,totals"
