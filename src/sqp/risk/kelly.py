"""Staking. Fractional Kelly (default 25%) with hard caps.

Probability estimates are uncertain; full Kelly over-bets under estimation
error. Caps: per-bet max stake pct and minimum edge threshold.
"""
from __future__ import annotations

import math


def edge(estimated_probability: float, price_decimal: float) -> float:
    """Estimated edge = p * price - 1.

    EV por unidad RESUELTA: con p = pW/(pW+pL) (condicionada a no-push) es
    EV_incondicional/(1 - P(push)). Mismo signo; en lineas enteras el filtro
    `min_edge` es algo mas laxo (AUD-011, audit-2026-11-03).
    """
    return estimated_probability * price_decimal - 1.0


def stake_price(price_decimal: float, execution_price: float | None) -> float:
    """Precio con el que se DIMENSIONA el stake: el menor entre la mediana del
    consenso y el de ejecucion (AUD-005, audit-2026-11-03).

    Kelly, el edge y el tope son monotonos crecientes en el precio, asi que el
    minimo exige `min_edge` en ambos precios y nunca sube el stake por la cuota
    de una sola casa (que puede estar obsoleta). Sin ejecucion valida (NaN,
    infinita o <= 1) devuelve la mediana, como antes."""
    if (execution_price is not None and math.isfinite(execution_price)
            and execution_price > 1.0):
        return min(price_decimal, execution_price)
    return price_decimal


def kelly_fraction_stake(estimated_probability: float, price_decimal: float,
                         bankroll: float, fraction: float = 0.25,
                         max_stake_pct: float = 0.02, min_edge: float = 0.02) -> tuple[float, float]:
    """Return (stake_amount, kelly_pct_applied). 0 if below min edge."""
    # bankroll <= 0 (banca dinamica agotada) devolveria stake negativo (M-17).
    # La finitud se comprueba APARTE porque las comparaciones de rango no la
    # ven: `inf <= 0` es False y toda comparacion con `nan` es False, asi que
    # ambos se colaban y producian un stake no finito (AUD-005, Codex
    # 2026-09-05). Defensa en profundidad: `Settings.validate` ya rechaza una
    # banca no finita, pero esta funcion es publica y la banca dinamica la
    # calcula en runtime.
    if not (math.isfinite(bankroll) and math.isfinite(estimated_probability)
            and math.isfinite(price_decimal)):
        return 0.0, 0.0
    if not (0.0 < estimated_probability < 1.0) or price_decimal <= 1.0 or bankroll <= 0:
        return 0.0, 0.0
    e = edge(estimated_probability, price_decimal)
    if e < min_edge:
        return 0.0, 0.0
    b = price_decimal - 1.0
    full_kelly = (estimated_probability * b - (1.0 - estimated_probability)) / b
    pct = max(0.0, min(full_kelly * fraction, max_stake_pct))
    return round(bankroll * pct, 2), pct
