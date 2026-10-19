"""Activacion de tilt_scale en la NHL (2026-09-30): la configuracion canonica lo aplica.

Pre-registro y resultado: docs/research/2026-09-29-preregistro-tilt-nhl.md y
docs/research/2026-09-30-resultado-tilt-nhl.md. Fija que `_league_meta("nhl")`
entrega `tilt_scale = 0.439`, que las demas ligas de hockey o Poisson no lo
reciben por arrastre, y que el tilt nuevo reparte menos las probabilidades que
el 0,9 de la familia sin tocar el total esperado.
"""
from __future__ import annotations

import pytest

from sqp.domain.models import Event
from sqp.pipeline.daily import _league_meta
from sqp.sports.registry import get_adapter

TILT_NHL = 0.439


def test_nhl_config_carries_the_preregistered_tilt():
    params = _league_meta("nhl").get("league_params") or {}
    assert params.get("tilt_scale") == TILT_NHL


@pytest.mark.parametrize("league", ["mlb", "epl", "mls"])
def test_other_poisson_leagues_keep_their_own_tilt(league):
    params = _league_meta(league).get("league_params") or {}
    assert params.get("tilt_scale") != TILT_NHL


def _fitted(tilt: float):
    meta = _league_meta("nhl")
    params = dict(meta.get("league_params") or {})
    params["tilt_scale"] = tilt
    adapter = get_adapter("nhl", meta["family"], params)
    fed = [
        {"date": f"2026-01-{d:02d}", "home": "Boston Bruins", "away": "Buffalo Sabres",
         "home_score": 5, "away_score": 1, "neutral": False}
        for d in range(1, 21)
    ]
    for r in fed:
        adapter.observe(r)
    return adapter


def test_lower_tilt_shrinks_the_favourite_without_moving_the_total():
    ev = Event(event_id="t", sport_key="icehockey_nhl", league="nhl",
               home="Boston Bruins", away="Buffalo Sabres",
               start_time="2026-02-01T00:00:00Z")
    new = _fitted(TILT_NHL).estimate(ev, None, 5.5)
    old = _fitted(0.9).estimate(ev, None, 5.5)
    # El favorito (Boston, 20 victorias) queda menos extremo con el tilt nuevo.
    assert 0.5 < new.home_win_estimated_probability < old.home_win_estimated_probability
    # Con el gol del empate reglamentario (AUD-001, ronda audit-2026-10-18) el
    # total ya NO es exactamente independiente del reparto: dos equipos parejos
    # empatan mas a menudo y esa masa pasa a 2k+1. El total ESPERADO se conserva
    # (lo fija `test_aud001_expected_final_total_is_preserved`); la P(Over) se
    # mueve poco con el tilt.
    assert new.over_estimated_probability == pytest.approx(
        old.over_estimated_probability, abs=0.01)


def test_without_the_tie_goal_the_total_does_not_depend_on_the_tilt(monkeypatch):
    """La invariancia original, sobre la rejilla sin el gol del empate."""
    from sqp.sports.adapters import HockeyAdapter

    monkeypatch.setattr(HockeyAdapter, "TIE_ADDS_GOAL", False)
    ev = Event(event_id="t", sport_key="icehockey_nhl", league="nhl",
               home="Boston Bruins", away="Buffalo Sabres",
               start_time="2026-02-01T00:00:00Z")
    new = _fitted(TILT_NHL).estimate(ev, None, 5.5)
    old = _fitted(0.9).estimate(ev, None, 5.5)
    assert new.over_estimated_probability == pytest.approx(
        old.over_estimated_probability, abs=1e-4)
