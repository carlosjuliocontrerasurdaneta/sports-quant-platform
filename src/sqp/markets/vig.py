"""Vig (overround) removal. Supports 2-way and 3-way (soccer 1X2) markets.

- proportional: classic normalization p_i / sum(p).
- power: solves sum(p_i^k) = 1; less biased for favorite-longshot effect.
"""
from __future__ import annotations
import math

from scipy.optimize import brentq

from sqp.logging_config import get_logger

log = get_logger("sqp.vig")


def _require_finite(implied: list[float]) -> None:
    """Defensa en profundidad (auditoria 2026-08-05, F-01).

    Los guards de abajo (`s <= 0`, `p <= 0 or p >= 1`) son FALSOS ante NaN, asi
    que un valor no finito los atravesaba entero: `sum` daba NaN, el fallback
    proporcional dividia NaN entre NaN y las probabilidades justas del mercado
    COMPLETO salian NaN. Con el consenso filtrando en origen esto no deberia
    alcanzarse nunca; si se alcanza, tiene que fallar ruidoso y no en silencio.
    """
    if not all(math.isfinite(p) for p in implied):
        raise ValueError(f"Implied probabilities must be finite, got {implied}")


def remove_vig_proportional(implied: list[float]) -> list[float]:
    _require_finite(implied)
    s = sum(implied)
    if s <= 0:
        raise ValueError("Implied probabilities must be positive")
    return [p / s for p in implied]


def remove_vig_power(implied: list[float]) -> list[float]:
    """Power method: find k such that sum(p_i^k) = 1, return p_i^k.

    Falls back to the proportional method with a WARNING when the power
    method cannot apply (probabilities at/over 1.0, or no root for k). The
    fallback was silent and is how a one-element list turns into [1.0]
    (audit 2026-07-24, M-16); callers must pass complete markets."""
    _require_finite(implied)
    if any(p <= 0 or p >= 1 for p in implied):
        log.warning("power de-vig inapplicable (implied out of (0,1): %s); "
                    "falling back to proportional", implied)
        return remove_vig_proportional(implied)

    def f(k: float) -> float:
        return sum(p ** k for p in implied) - 1.0

    try:
        k = brentq(f, 0.5, 5.0)
        return [p ** k for p in implied]
    except ValueError:
        log.warning("power de-vig found no root for implied=%s; "
                    "falling back to proportional", implied)
        return remove_vig_proportional(implied)
