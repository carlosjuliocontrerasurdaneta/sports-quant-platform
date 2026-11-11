"""Odds conversions. Pure functions, fully tested."""
from __future__ import annotations

import math

# La fuente unica de ``is_usable_price`` vive ahora en ``sqp.domain.prices``
# (para que settlement_math no importe la capa de mercado); se reexporta aqui
# y los importadores existentes no cambian.
from sqp.domain.prices import is_usable_price  # noqa: F401


def american_to_decimal(american: float) -> float:
    if not math.isfinite(american):
        raise ValueError(f"American odds must be finite, got {american}")
    if american == 0:
        raise ValueError("American odds cannot be 0")
    if abs(american) < 100:
        # AUD-026: el formato americano solo existe para |x| >= 100 (+100 es
        # "even"); -50 daria 3.0 en vez de ser una cuota invalida.
        raise ValueError(f"American odds must satisfy abs(x) >= 100, got {american}")
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
