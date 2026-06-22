"""EV uncertainty penalty (ported from project 2). See sqp.markets.edge."""
import math

from sqp.markets.edge import adjusted_edge


def _raw(p, d):
    return p * d - 1.0


def test_no_op_when_coefficients_are_zero():
    # With all coefficients 0, the adjusted edge equals the raw edge and the
    # effective probability equals the input (this is the shipped default).
    r = adjusted_edge(0.60, 2.0, market_probability=0.50, books_count=1)
    assert r.penalty == 0.0
    assert math.isclose(r.adjusted_edge, _raw(0.60, 2.0))
    assert math.isclose(r.effective_probability, 0.60)


def test_uncertainty_penalty_scales_with_gap():
    # gap = |0.60 - 0.50| = 0.10 -> penalty = 0.10 * 0.35 = 0.035.
    r = adjusted_edge(0.60, 2.0, market_probability=0.50, books_count=5,
                      uncertainty_penalty=0.35)
    assert math.isclose(r.penalty, 0.035, abs_tol=1e-12)
    assert math.isclose(r.adjusted_edge, _raw(0.60, 2.0) - 0.035, abs_tol=1e-12)
    # p_eff yields exactly the adjusted edge at this price.
    assert math.isclose(r.effective_probability * 2.0 - 1.0, r.adjusted_edge, abs_tol=1e-12)
    assert r.effective_probability < 0.60          # penalty shrinks the staked prob


def test_anomaly_bump_applies_only_above_the_gap():
    common = dict(uncertainty_penalty=0.0, anomaly_edge_gap=0.06, anomaly_extra_penalty=0.02)
    below = adjusted_edge(0.55, 2.0, market_probability=0.50, books_count=5, **common)
    above = adjusted_edge(0.60, 2.0, market_probability=0.50, books_count=5, **common)
    assert below.penalty == 0.0                    # gap 0.05 <= 0.06
    assert math.isclose(above.penalty, 0.02)       # gap 0.10 > 0.06


def test_low_book_penalty_only_below_threshold():
    common = dict(low_book_penalty=0.015, min_books_for_consensus=2)
    thin = adjusted_edge(0.55, 2.0, market_probability=0.50, books_count=1, **common)
    thick = adjusted_edge(0.55, 2.0, market_probability=0.50, books_count=3, **common)
    assert math.isclose(thin.penalty, 0.015)
    assert thick.penalty == 0.0


def test_missing_market_or_books_skip_their_terms():
    # No market anchor -> no uncertainty/anomaly term; no book count -> no thin term.
    r = adjusted_edge(0.70, 1.8, market_probability=None, books_count=None,
                      uncertainty_penalty=0.35, low_book_penalty=0.015,
                      min_books_for_consensus=2)
    assert r.penalty == 0.0
    assert math.isclose(r.adjusted_edge, _raw(0.70, 1.8))


def test_penalty_never_negative():
    # A model BELOW the market (gap still positive) must not create a bonus.
    r = adjusted_edge(0.40, 3.0, market_probability=0.55, books_count=5,
                      uncertainty_penalty=0.35)
    assert r.penalty >= 0.0
    assert r.adjusted_edge <= _raw(0.40, 3.0) + 1e-12
