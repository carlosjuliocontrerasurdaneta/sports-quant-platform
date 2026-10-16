"""AUD-003, seguimiento: el movimiento de linea (``line_movement``) y el CLV por
movimiento (``clv_movement``) usan la misma exclusion de casas con Draw que el
consenso diario. Hoy el termino de movimiento es inerte (penalizaciones a 0);
esto evita que activarlo reintroduzca el baseline mezclado."""
from __future__ import annotations

import pandas as pd
import pytest

from sqp.audit.clv_movement import (exclude_two_way_draw_books,
                                    pre_pick_movement, snapshot_consensus_price)
from sqp.markets.line_movement import event_line_movement
from sqp.pipeline import revalidation

HOME, AWAY = "Carolina Hurricanes", "Boston Bruins"
T0, T1 = "2026-10-10T12:00:00+00:00", "2026-10-10T18:00:00+00:00"


def _snap(captured_at: str, us_home: float, eu_home: float) -> list[dict]:
    """Una casa a dos vias y una casa europea con 1X2 reglamentario: con
    dos precios la mediana es su media, asi que la europea la desplaza."""
    base = {"event_id": "e1", "captured_at": captured_at, "market": "h2h",
            "point": None}
    return [
        {**base, "bookmaker": "us1", "outcome": HOME, "price_decimal": us_home},
        {**base, "bookmaker": "us1", "outcome": AWAY, "price_decimal": 2.0},
        {**base, "bookmaker": "eu1", "outcome": HOME, "price_decimal": eu_home},
        {**base, "bookmaker": "eu1", "outcome": AWAY, "price_decimal": 2.6},
        {**base, "bookmaker": "eu1", "outcome": "Draw", "price_decimal": 4.4},
    ]


def _odds() -> pd.DataFrame:
    # La casa a 1X2 se mueve mucho y la americana poco: con la europea en la
    # mediana el movimiento sale distinto del de la casa comparable.
    return pd.DataFrame(_snap(T0, 1.80, 2.30) + _snap(T1, 1.75, 3.50))


def test_consensus_without_league_keeps_old_behaviour():
    snap = pd.DataFrame(_snap(T0, 1.80, 2.30))
    assert snapshot_consensus_price(snap, "h2h", HOME, None) == pytest.approx(2.05)
    eu_only = snap[snap.bookmaker == "eu1"]
    assert snapshot_consensus_price(eu_only, "h2h", HOME, None) == pytest.approx(2.30)


def test_two_way_league_drops_the_draw_quoting_book():
    snap = pd.DataFrame(_snap(T0, 1.80, 2.30))
    kept = exclude_two_way_draw_books(snap, "nhl")
    assert set(kept.bookmaker) == {"us1"}
    assert snapshot_consensus_price(snap, "h2h", HOME, None,
                                    league="nhl") == pytest.approx(1.80)
    eu_only = snap[snap.bookmaker == "eu1"]
    assert snapshot_consensus_price(eu_only, "h2h", HOME, None,
                                    league="nhl") is None


def test_three_way_league_is_untouched():
    snap = pd.DataFrame(_snap(T0, 1.80, 2.30))
    assert len(exclude_two_way_draw_books(snap, "epl")) == len(snap)


def test_event_line_movement_uses_only_comparable_books():
    odds = _odds()
    mixed = event_line_movement(odds, "e1", "h2h", HOME, None)
    assert mixed is not None
    assert mixed.movement_pp == pytest.approx((1 / 2.625 - 1 / 2.05) * 100.0)
    lm = event_line_movement(odds, "e1", "h2h", HOME, None, league="nhl")
    assert lm is not None
    expected = (1 / 1.75 - 1 / 1.80) * 100.0
    assert lm.movement_pp == pytest.approx(expected)
    assert lm.n_snapshots == 2


def test_pre_pick_movement_uses_only_comparable_books():
    mov = pre_pick_movement(_odds(), market="h2h", selection=HOME, point=None,
                            picked_at="2026-10-10T19:00:00+00:00", league="nhl")
    assert mov is not None
    assert mov["movement_pp"] == pytest.approx((1 / 1.75 - 1 / 1.80) * 100.0)


def test_revalidation_keeps_its_private_name():
    assert revalidation._exclude_two_way_draw_books is exclude_two_way_draw_books
