"""Vig (overround) removal. Supports 2-way and 3-way (soccer 1X2) markets.

- proportional: classic normalization p_i / sum(p).
- power: solves sum(p_i^k) = 1; less biased for favorite-longshot effect.
"""
from __future__ import annotations
from scipy.optimize import brentq


def remove_vig_proportional(implied: list[float]) -> list[float]:
    s = sum(implied)
    if s <= 0:
        raise ValueError("Implied probabilities must be positive")
    return [p / s for p in implied]


def remove_vig_power(implied: list[float]) -> list[float]:
    """Power method: find k such that sum(p_i^k) = 1, return p_i^k."""
    if any(p <= 0 or p >= 1 for p in implied):
        return remove_vig_proportional(implied)

    def f(k: float) -> float:
        return sum(p ** k for p in implied) - 1.0

    try:
        k = brentq(f, 0.5, 5.0)
        return [p ** k for p in implied]
    except ValueError:
        return remove_vig_proportional(implied)
