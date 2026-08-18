import pytest
from sqp.markets.odds import american_to_decimal, decimal_to_american, implied_probability

def test_american_to_decimal():
    assert american_to_decimal(100) == 2.0
    assert american_to_decimal(-110) == pytest.approx(1.9090909, rel=1e-6)
    assert american_to_decimal(250) == 3.5

def test_round_trip():
    for a in (-300, -110, 120, 450):
        assert decimal_to_american(american_to_decimal(a)) == pytest.approx(a, rel=1e-9)

def test_implied_probability_bounds():
    assert 0 < implied_probability(1.91) < 1
    with pytest.raises(ValueError):
        implied_probability(0.99)


# --- invariante de valor finito (auditoria 2026-08-05, causa raiz RC-1) ------
# Los guards estaban escritos como `american == 0` y `decimal <= 1`, y toda
# comparacion con NaN es False: un no finito atravesaba las tres conversiones y
# salia como NaN, propagando el mismo fallo silencioso que F-01 corrigio en el
# consenso y el de-vig. Aqui se cierra el ultimo punto donde el patron quedaba.

NAN, INF = float("nan"), float("inf")


@pytest.mark.parametrize("bad", [NAN, INF, -INF])
def test_american_to_decimal_rejects_non_finite(bad):
    with pytest.raises(ValueError):
        american_to_decimal(bad)


@pytest.mark.parametrize("bad", [NAN, INF, -INF])
def test_decimal_to_american_rejects_non_finite(bad):
    with pytest.raises(ValueError):
        decimal_to_american(bad)


@pytest.mark.parametrize("bad", [NAN, INF, -INF])
def test_implied_probability_rejects_non_finite(bad):
    with pytest.raises(ValueError):
        implied_probability(bad)
