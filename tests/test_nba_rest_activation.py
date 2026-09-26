"""Activacion del descanso NBA (2026-09-26): la configuracion canonica lo aplica.

Pre-registro y resultado: docs/research/2026-09-26-preregistro-descanso-basket.md
y docs/research/2026-09-26-resultado-descanso-basket.md. Fija dos cosas: que
`_league_meta("nba")` entrega `rest_points_per_day = 0.795` (y ninguna otra liga
de basket lo recibe), y que un back-to-back conocido mueve el margen del
adaptador de produccion en el sentido y la cuantia esperados.
"""
from __future__ import annotations

import pytest

from sqp.domain.models import Event
from sqp.pipeline.daily import _league_meta
from sqp.sports.registry import get_adapter

RPPD_NBA = 0.795


def _adapter(league: str):
    meta = _league_meta(league)
    return get_adapter(league, meta["family"], meta.get("league_params"))


def test_nba_config_carries_the_preregistered_rest_value():
    params = _league_meta("nba").get("league_params") or {}
    assert params.get("rest_points_per_day") == RPPD_NBA


@pytest.mark.parametrize("league", ["wnba", "ncaab", "wncaab"])
def test_other_basketball_leagues_do_not_receive_rest(league):
    params = _league_meta(league).get("league_params") or {}
    assert not params.get("rest_points_per_day")


def test_known_back_to_back_shifts_the_home_margin():
    """Local descansado 3 dias contra visitante en back-to-back (1 dia):
    Δr = 3 - 1 = 2 -> el margen del local sube 2 * 0,795 = 1,59 puntos."""
    adapter = _adapter("nba")
    fed = [
        {"date": "2026-01-01", "home": "Boston Celtics", "away": "Miami Heat",
         "home_score": 110, "away_score": 100, "neutral": False},
        {"date": "2026-01-03", "home": "Chicago Bulls", "away": "New York Knicks",
         "home_score": 100, "away_score": 99, "neutral": False},
    ]
    for r in fed:
        adapter.observe(r)
    # Boston: ultimo partido el 01/01 -> 3 dias el 04/01. Knicks: 03/01 -> 1 dia.
    shift = adapter.rest.margin_adjustment("Boston Celtics", "New York Knicks",
                                           "2026-01-04")
    assert shift == pytest.approx(2 * RPPD_NBA)
    ev = Event(event_id="b2b", sport_key="basketball_nba", league="nba",
               home="Boston Celtics", away="New York Knicks",
               start_time="2026-01-04T00:30:00Z")
    base = _adapter("nba")
    for r in fed:
        base.observe(r)
    base.rest.points_per_day = 0.0
    p_rest = adapter.estimate(ev, None, None).home_win_estimated_probability
    p_base = base.estimate(ev, None, None).home_win_estimated_probability
    assert p_rest > p_base
