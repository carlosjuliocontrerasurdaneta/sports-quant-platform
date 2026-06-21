"""Staking. Fractional Kelly (default 25%) with hard caps.

Probability estimates are uncertain; full Kelly over-bets under estimation
error. Caps: per-bet max stake pct and minimum edge threshold.
"""
from __future__ import annotations


def edge(estimated_probability: float, price_decimal: float) -> float:
    """Estimated edge = p * price - 1 (expected value per unit staked)."""
    return estimated_probability * price_decimal - 1.0


def kelly_fraction_stake(estimated_probability: float, price_decimal: float,
                         bankroll: float, fraction: float = 0.25,
                         max_stake_pct: float = 0.02, min_edge: float = 0.02) -> tuple[float, float]:
    """Return (stake_amount, kelly_pct_applied). 0 if below min edge."""
    if not (0.0 < estimated_probability < 1.0) or price_decimal <= 1.0:
        return 0.0, 0.0
    e = edge(estimated_probability, price_decimal)
    if e < min_edge:
        return 0.0, 0.0
    b = price_decimal - 1.0
    full_kelly = (estimated_probability * b - (1.0 - estimated_probability)) / b
    pct = max(0.0, min(full_kelly * fraction, max_stake_pct))
    return round(bankroll * pct, 2), pct
