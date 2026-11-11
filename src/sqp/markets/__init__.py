"""Paquete de mercado con reexportaciones perezosas (PEP 562).

Cargar ``sqp.markets.settlement_math`` (matematica pura, REGLA 2) fuerza a
Python a cargar este paquete; por eso ``odds`` y ``vig`` NO se importan aqui de
forma ansiosa, sino bajo demanda al pedir el nombre.
"""
from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # solo para mypy/IDE: no se ejecuta, no carga odds ni vig
    from .odds import american_to_decimal, decimal_to_american, implied_probability  # noqa: F401
    from .vig import remove_vig_power, remove_vig_proportional  # noqa: F401

_LAZY: dict[str, str] = {
    "american_to_decimal": ".odds",
    "decimal_to_american": ".odds",
    "implied_probability": ".odds",
    "remove_vig_proportional": ".vig",
    "remove_vig_power": ".vig",
}

__all__ = [
    "american_to_decimal",
    "decimal_to_american",
    "implied_probability",
    "remove_vig_power",
    "remove_vig_proportional",
]


def __getattr__(name: str) -> object:
    target = _LAZY.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(target, __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY))
