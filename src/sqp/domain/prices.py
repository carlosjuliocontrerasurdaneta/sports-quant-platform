"""Price predicates with no dependency on the rest of ``sqp``.

Lives in ``sqp.domain`` so that pure line maths (``sqp.markets.settlement_math``)
can use it without importing the market layer (REGLA 2, 06-arquitectura-
recomendada.md section 5.1). ``sqp.markets.odds`` re-exports it.
"""
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
