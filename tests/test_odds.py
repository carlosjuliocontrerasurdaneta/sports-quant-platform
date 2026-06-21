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
