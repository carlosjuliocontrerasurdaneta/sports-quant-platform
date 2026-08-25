"""Telemetria de cotizaciones degeneradas en INGESTION (hallazgo OOS 2026-07-24).

El lado de LECTURA filtra `price_decimal <= 1.0` desde c210a22 (F-01), asi que
estas lineas no corrompen ningun calculo. Lo que faltaba era audibilidad: se
persistian 1.611 de 3.866.927 lineas del historico (0,042%, medido 2026-08-25)
sin dejar rastro en ningun contador.

Se avisa SIN descartar, mismo criterio que el guard de CLV no finito: descartar
en silencio destruiria la evidencia de que el proveedor las emite, y
data-integrity-rules.md prohibe la mutacion oculta de datos crudos.
"""
from __future__ import annotations

import logging

import pytest

from sqp.providers.odds_api import OddsAPIClient


def _payload(prices):
    return [{
        "id": "e1", "home_team": "H", "away_team": "A",
        "commence_time": "2026-08-25T18:00:00Z",
        "bookmakers": [{"key": "bk", "markets": [{"key": "h2h", "outcomes": [
            {"name": n, "price": p} for n, p in zip(("H", "A"), prices)]}]}],
    }]


@pytest.fixture
def provider():
    return OddsAPIClient(api_key="k")


def test_degenerate_price_is_reported_but_not_dropped(provider, caplog):
    with caplog.at_level(logging.WARNING, logger="sqp.odds_api"):
        out = provider._parse_events(_payload([1.0, 2.05]), "sk", "mlb")
    # NO se descarta: las dos lineas siguen ahi, con su precio original.
    assert [ln.price_decimal for ln in out[0].lines] == [1.0, 2.05]
    msgs = [r.getMessage() for r in caplog.records if r.name == "sqp.odds_api"]
    assert any("degeneradas" in m and "mlb" in m for m in msgs)


def test_clean_payload_emits_no_warning(provider, caplog):
    with caplog.at_level(logging.WARNING, logger="sqp.odds_api"):
        out = provider._parse_events(_payload([1.91, 2.05]), "sk", "mlb")
    assert len(out[0].lines) == 2
    assert not [r for r in caplog.records if r.name == "sqp.odds_api"]


def test_counter_aggregates_per_call_not_per_line(provider, caplog):
    """Con 1.611 casos en el historico, un aviso por fila seria ruido."""
    raw = _payload([1.0, 1.0]) + _payload([0.5, 2.0])
    with caplog.at_level(logging.WARNING, logger="sqp.odds_api"):
        provider._parse_events(raw, "sk", "mlb")
    msgs = [r.getMessage() for r in caplog.records if r.name == "sqp.odds_api"]
    assert len(msgs) == 1
    assert "3 cotizacion" in msgs[0]
