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


def test_power_falls_back_to_proportional_out_of_domain():
    # una implied >= 1 (precio decimal 1.0) inhabilita el metodo power
    fair = remove_vig_power([1.0, 0.5])
    assert fair == pytest.approx([2/3, 1/3])


def test_power_single_element_normalizes_to_certainty():
    # Comportamiento documentado del fallback (auditoria 2026-07-24, C-1/M-16):
    # una lista unilateral normaliza a [1.0]; por eso _novig_probs exige el
    # mercado complementario completo antes de llamar aqui.
    assert remove_vig_power([0.5236]) == pytest.approx([1.0])


def test_proportional_rejects_nonpositive_sum():
    with pytest.raises(ValueError):
        remove_vig_proportional([0.0, 0.0])
