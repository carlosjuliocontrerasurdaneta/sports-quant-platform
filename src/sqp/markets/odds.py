"""Odds conversions. Pure functions, fully tested."""
from __future__ import annotations

import math


def is_usable_price(price: float | None) -> bool:
    """Is this decimal quote usable as a real, payable price?

    Single source of truth for the question, shared by the consensus, the book
    count and the de-vig (audit 2026-08-05, F-01). It exists because the same
    predicate was open-coded as ``price is None or price <= 1.0`` and every
    comparison with NaN is False, so non-finite quotes slipped through all of
    them: one NaN price turned the fair probabilities of the WHOLE market into
    NaN and the event dropped out of the picks silently.

    Rejects None, NaN, +-inf and any price <= 1.0 (no payout).
    """
    return price is not None and math.isfinite(price) and price > 1.0


def american_to_decimal(american: float) -> float:
    if not math.isfinite(american):
        raise ValueError(f"American odds must be finite, got {american}")
    if american == 0:
        raise ValueError("American odds cannot be 0")
    return 1 + (american / 100.0 if american > 0 else 100.0 / abs(american))


def decimal_to_american(decimal: float) -> float:
    if not is_usable_price(decimal):
        raise ValueError(f"Decimal odds must be finite and > 1, got {decimal}")
    return (decimal - 1) * 100 if decimal >= 2 else -100 / (decimal - 1)


def implied_probability(decimal: float) -> float:
    """Raw implied probability (includes vig)."""
    if not is_usable_price(decimal):
        raise ValueError(f"Decimal odds must be finite and > 1, got {decimal}")
    return 1.0 / decimal
