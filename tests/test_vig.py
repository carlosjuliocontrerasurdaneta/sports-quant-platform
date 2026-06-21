import pytest
from sqp.markets.vig import remove_vig_proportional, remove_vig_power

def test_proportional_two_way():
    fair = remove_vig_proportional([1/1.91, 1/1.91])
    assert sum(fair) == pytest.approx(1.0)
    assert fair[0] == pytest.approx(0.5)

def test_power_three_way_sums_to_one():
    implied = [1/2.10, 1/3.40, 1/3.60]  # typical 1X2 with overround
    fair = remove_vig_power(implied)
    assert sum(fair) == pytest.approx(1.0, abs=1e-9)
    assert all(0 < p < 1 for p in fair)
    assert fair[0] > fair[1] and fair[0] > fair[2]
