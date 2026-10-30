"""Regresion del Elo entre temporadas (pre-registro 2026-10-29, §4 y §12.1)."""
from __future__ import annotations

import logging

import pytest

from sqp.domain.models import Event
from sqp.models.elo import EloRatings
from sqp.sports.registry import get_adapter

LAM = 0.25


def _seq() -> list[tuple[str, str, float, float, str]]:
    return [
        ("A", "B", 110, 100, "2026-04-10"),
        ("B", "C", 90, 95, "2026-04-12"),
        ("A", "C", 101, 99, "2026-06-12"),
        ("C", "B", 120, 100, "2026-09-12"),  # hueco 92 dias
        ("A", "B", 100, 105, "2026-09-14"),
    ]


def _run(lam: float, with_date: bool, split: bool = False) -> EloRatings:
    e = EloRatings(season_regression=lam, use_home_away_split=split)
    for h, a, hs, as_, d in _seq():
        if with_date:
            e.update(h, a, hs, as_, date=d)
        else:
            e.update(h, a, hs, as_)
    return e


def _event(d: str) -> Event:
    return Event(event_id="e", sport_key="basketball_nba", league="nba",
                 home="A", away="B", start_time=d)


def test_default_zero_is_exact_identity() -> None:
    plain, dated = _run(0.0, False), _run(0.0, True)
    assert plain.ratings == dated.ratings
    assert plain.games_played == dated.games_played
    assert dated.advance_to("2027-01-01") is False


@pytest.mark.parametrize("gap,expected", [(29, False), (30, True)])
def test_threshold_30_days(gap: int, expected: bool) -> None:
    e = EloRatings(season_regression=LAM)
    e.update("A", "B", 110, 100, date="2026-01-01")
    before = dict(e.ratings)
    from datetime import date, timedelta
    d = (date(2026, 1, 1) + timedelta(days=gap)).isoformat()
    assert e.advance_to(d) is expected
    if expected:
        assert e.ratings["A"] == pytest.approx(1500 + (1 - LAM) * (before["A"] - 1500))
    else:
        assert e.ratings == before


def test_all_star_break_does_not_regress() -> None:
    e = EloRatings(season_regression=LAM)
    e.update("A", "B", 110, 100, date="2026-02-10")
    before = dict(e.ratings)
    e.update("A", "B", 100, 100, date="2026-02-17")
    assert e._regressed_for is None
    assert e.ratings != before  # solo la actualizacion normal
    e2 = EloRatings(season_regression=LAM)
    e2.update("A", "B", 110, 100, date="2026-02-10")
    assert e2.advance_to("2026-02-17") is False


def test_first_event_does_not_regress() -> None:
    e = EloRatings(season_regression=LAM)
    assert e.advance_to("2026-10-21") is False


def test_relative_difference_scales_by_one_minus_lambda() -> None:
    e = _run(LAM, True)
    # Reconstruir sin el ultimo evento: la regresion ocurre en el de 2026-09-12.
    e0 = EloRatings(season_regression=LAM)
    for h, a, hs, as_, d in _seq()[:3]:
        e0.update(h, a, hs, as_, date=d)
    diff0 = e0.ratings["A"] - e0.ratings["B"]
    e0.advance_to("2026-09-12")
    assert e0.ratings["A"] - e0.ratings["B"] == pytest.approx((1 - LAM) * diff0)
    assert e.games_played["A"] == 3  # games_played no se reinicia


def test_full_iso_date_and_single_regression_per_boundary() -> None:
    e = EloRatings(season_regression=LAM)
    e.update("A", "B", 110, 100, date="2026-06-20T23:30:00Z")
    assert e.advance_to("2026-10-21T23:30:00Z") is True
    after = dict(e.ratings)
    assert e.advance_to("2026-10-21T01:00:00Z") is False  # idempotente
    e.update("A", "B", 100, 100, date="2026-10-21T23:30:00Z")  # mismo dia: sin 2a regresion
    assert e._regressed_for == "2026-10-21"
    assert e._last_date == "2026-10-21"
    assert abs(e.ratings["A"] - after["A"]) < 20  # solo el paso K normal
    # evento posterior en la misma temporada no regresa
    assert e.advance_to("2026-10-25") is False


@pytest.mark.parametrize("order", [("2026-10-21", "2026-10-22"),
                                   ("2026-10-22", "2026-10-21")])
def test_several_unobserved_dates_regress_once(order: tuple[str, str]) -> None:
    # El run diario estima varios dias del horizonte antes de observar ninguno.
    e = EloRatings(season_regression=LAM)
    e.update("A", "B", 110, 100, date="2026-06-20")
    assert e.advance_to(order[0]) is True
    after = dict(e.ratings)
    assert e.advance_to(order[1]) is False
    e.update("A", "B", 100, 100, date="2026-10-21")
    assert e.advance_to("2026-10-23") is False
    assert abs(e.ratings["A"] - after["A"]) < 20  # solo el paso K normal
    # la temporada siguiente vuelve a regresar una vez
    e.update("A", "B", 100, 90, date="2027-06-15")
    assert e.advance_to("2027-10-20") is True


@pytest.mark.parametrize("lam", [-0.1, 1.5])
def test_lambda_out_of_range_rejected(lam: float) -> None:
    with pytest.raises(ValueError):
        EloRatings(season_regression=lam)


def test_past_event_never_regresses() -> None:
    e = EloRatings(season_regression=LAM)
    e.update("A", "B", 110, 100, date="2026-10-21")
    before = dict(e.ratings)
    assert e.advance_to("2026-01-01") is False
    assert e.advance_to("2026-10-21") is False
    assert e.ratings == before


def test_home_away_ratings_also_regress() -> None:
    e = EloRatings(season_regression=LAM, use_home_away_split=True)
    e.update("A", "B", 110, 100, date="2026-06-20")
    h, a, u = e.ratings_home["A"], e.ratings_away["B"], e.ratings["A"]
    assert e.advance_to("2026-10-21") is True
    assert e.ratings_home["A"] == pytest.approx(1500 + (1 - LAM) * (h - 1500))
    assert e.ratings_away["B"] == pytest.approx(1500 + (1 - LAM) * (a - 1500))
    assert e.ratings["A"] == pytest.approx(1500 + (1 - LAM) * (u - 1500))


def test_boundary_outside_june_october_warns(caplog: pytest.LogCaptureFixture) -> None:
    e = EloRatings(season_regression=LAM)
    e.update("A", "B", 110, 100, date="2026-01-01")
    with caplog.at_level(logging.WARNING, logger="sqp.models.elo"):
        assert e.advance_to("2026-03-15") is True
    assert any("outside" in r.message for r in caplog.records)


def _nba(lam: float):
    params = {"elo_season_regression": lam} if lam else {}
    ad = get_adapter("nba", "basketball", params)
    ad.observe({"home": "A", "away": "B", "home_score": 120, "away_score": 100,
                "date": "2026-06-20T01:00:00Z"})
    return ad


def test_adapter_default_has_no_effect_and_key_is_not_in_defaults() -> None:
    ad = get_adapter("nba", "basketball", {})
    assert "elo_season_regression" not in ad.params
    assert ad.elo.season_regression == 0.0
    ref, zero = _nba(0.0), _nba(0.0)
    p1 = ref.estimate(_event("2026-10-21T23:30:00Z"), None, None)
    p2 = zero.estimate(_event("2026-10-21T23:30:00Z"), None, None)
    assert p1.home_win_estimated_probability == p2.home_win_estimated_probability


def test_adapter_regresses_on_estimate_before_observe_and_is_idempotent() -> None:
    ad = _nba(LAM)
    r_before = ad.elo.get("A")
    ad.estimate(_event("2026-10-21T23:30:00Z"), None, None)
    r_est = ad.elo.get("A")
    assert r_est == pytest.approx(1500 + (1 - LAM) * (r_before - 1500))
    ad.estimate(_event("2026-10-21T23:30:00Z"), None, None)
    assert ad.elo.get("A") == r_est
    ad.observe({"home": "A", "away": "B", "home_score": 100, "away_score": 100,
                "date": "2026-10-21T23:30:00Z"})
    # una sola regresion: el observe solo aplica el paso K de un empate
    assert abs(ad.elo.get("A") - r_est) < 20


def test_adapter_estimating_past_event_does_not_regress() -> None:
    ad = _nba(LAM)
    before = dict(ad.elo.ratings)
    ad.estimate(_event("2026-06-01T00:00:00Z"), None, None)
    assert ad.elo.ratings == before


def test_estimate_wrapper_preserves_metadata() -> None:
    ad = get_adapter("nba", "basketball", {})
    assert type(ad).estimate.__name__ == "estimate"
