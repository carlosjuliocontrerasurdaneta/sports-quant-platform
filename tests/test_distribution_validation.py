"""Reject invalid inputs and prove vectorization preserves valid probabilities."""
import math

import pytest
from scipy.stats import nbinom, poisson

from sqp.models import distributions as d


@pytest.mark.parametrize("mean,sigma", [(math.nan, 12), (3, 0), (3, -1), (3, math.inf)])
def test_normal_rejects_invalid_parameters(mean, sigma):
    with pytest.raises(ValueError):
        d.normal_margin_probs(mean, sigma, -3.5)
    with pytest.raises(ValueError):
        d.normal_total_probs(mean, sigma, 200.5)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_lines_and_dc_are_rejected(value):
    for call in (
        lambda: d.normal_margin_probs(3, 12, value),
        lambda: d.normal_total_probs(200, 20, value),
        lambda: d.poisson_match_probs(2, 1, value, None),
        lambda: d.poisson_match_probs(2, 1, None, value),
        lambda: d.poisson_match_probs(2, 1, None, None, dc_rho=value),
        lambda: d.score_pmf(2, k=value),
    ):
        with pytest.raises(ValueError):
            call()


@pytest.mark.parametrize("lam", [-1, math.nan, math.inf, -math.inf])
def test_invalid_rate_rejected(lam):
    with pytest.raises(ValueError):
        d.score_pmf(lam)


@pytest.mark.parametrize("maximum", [-1, 2.5, True])
def test_invalid_grid_size_rejected(maximum):
    with pytest.raises(ValueError):
        d.score_pmf(2, maximum)


def test_underflow_grid_rejected_with_diagnostic():
    with pytest.raises(ValueError, match="grid has no finite positive mass"):
        d.poisson_match_probs(1e6, 1e6, None, None)


def _scalar_pmf(lam, max_goals=15, k=None):
    if k is None or k <= 0:
        return [poisson.pmf(i, lam) for i in range(max_goals + 1)]
    return [nbinom.pmf(i, k, k / (k + lam)) for i in range(max_goals + 1)]


@pytest.mark.parametrize("lam", [0, 0.1, 1.6, 3.1, 4.8, 9.5])
@pytest.mark.parametrize("k", [None, -1, 0, 3.8, 1000])
def test_vectorized_pmf_matches_original_scalar_calls(lam, k):
    assert d.score_pmf(lam, 25, k) == _scalar_pmf(lam, 25, k)


@pytest.mark.parametrize("k", [None, 3.8])
@pytest.mark.parametrize("rho", [0, -0.06])
@pytest.mark.parametrize("dc", [0, -0.1])
@pytest.mark.parametrize("line", [-1.5, 0, 1])
def test_full_probabilities_keep_scalar_baseline(monkeypatch, k, rho, dc, line):
    kwargs = dict(max_goals=25, dispersion_k=k, score_rho=rho, dc_rho=dc, three_way=True)
    optimized = d.poisson_match_probs(3.2, 2.9, line, 6.0, **kwargs)
    monkeypatch.setattr(d, "score_pmf", _scalar_pmf)
    assert optimized == d.poisson_match_probs(3.2, 2.9, line, 6.0, **kwargs)
