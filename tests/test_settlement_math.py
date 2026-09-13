import math

import pytest

from sqp.markets.settlement_math import (
    SettlementProbabilities, combine_adjacent_lines, proportional_no_vig, split_asian_line,
)


def test_push_is_refund_not_loss_and_fair_price_zeroes_ev():
    p = SettlementProbabilities(full_win=0.5, push=0.2, full_loss=0.3)
    assert p.decision_probability == pytest.approx(0.625)
    assert p.fair_decimal == pytest.approx(1.6)
    assert p.expected_value(2) == pytest.approx(0.2)
    assert p.expected_value(p.fair_decimal) == pytest.approx(0)


def test_asian_quarter_uses_half_stakes_not_halfline_approximation():
    # Home -0.25: draw loses half, win wins all. p(win,draw,loss)=.5,.2,.3.
    p = combine_adjacent_lines((0.5, 0, 0.5), (0.5, 0.2, 0.3))
    assert p == SettlementProbabilities(0.5, half_loss=0.2, full_loss=0.3)
    assert p.expected_value(2) == pytest.approx(0.1)
    other = combine_adjacent_lines((0.3, 0.2, 0.5), (0.5, 0, 0.5))
    assert other.half_win == pytest.approx(0.2)
    assert p.expected_value(2) + other.expected_value(2) == pytest.approx(0)


@pytest.mark.parametrize("line,expected", [(-0.25, (-0.5, 0)), (-0.75, (-1, -0.5)),
                                            (2.25, (2, 2.5)), (0, (0, 0)), (2.5, (2.5, 2.5))])
def test_split_line(line, expected):
    assert split_asian_line(float(line)) == expected


@pytest.mark.parametrize("line", [0.1, math.nan, math.inf])
def test_bad_lines_rejected(line):
    with pytest.raises(ValueError): split_asian_line(line)


def test_all_push_has_no_fabricated_conditional_probability_or_price():
    p = SettlementProbabilities(0, push=1)
    assert p.decision_probability is None and p.fair_decimal is None
    assert p.expected_value(2) == 0


@pytest.mark.parametrize("values", [(0.7, 0.4), (math.nan, 0.5), (-0.1, 1.1)])
def test_invalid_probability_rejected(values):
    with pytest.raises(ValueError): SettlementProbabilities(values[0], full_loss=values[1])


def test_complete_no_vig_only():
    probabilities, hold = proportional_no_vig({"home": 1.9, "away": 1.9})
    assert probabilities == {"home": 0.5, "away": 0.5}
    assert hold == pytest.approx(2 / 1.9 - 1)
    with pytest.raises(ValueError): proportional_no_vig({"home": 1.9})


@pytest.mark.parametrize("price", [1, 0, math.nan, math.inf])
def test_invalid_price_rejected(price):
    with pytest.raises(ValueError): SettlementProbabilities(0.5, full_loss=0.5).expected_value(price)
