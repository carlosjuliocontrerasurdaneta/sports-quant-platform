"""Odds conversions. Pure functions, fully tested."""
from __future__ import annotations


def american_to_decimal(american: float) -> float:
    if american == 0:
        raise ValueError("American odds cannot be 0")
    return 1 + (american / 100.0 if american > 0 else 100.0 / abs(american))


def decimal_to_american(decimal: float) -> float:
    if decimal <= 1:
        raise ValueError("Decimal odds must be > 1")
    return (decimal - 1) * 100 if decimal >= 2 else -100 / (decimal - 1)


def implied_probability(decimal: float) -> float:
    """Raw implied probability (includes vig)."""
    if decimal <= 1:
        raise ValueError("Decimal odds must be > 1")
    return 1.0 / decimal
