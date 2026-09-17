"""Unit-stake pricing, including pushes and exact Asian quarter lines.

This research API does not change the legacy ledger/settlement contract.
Probabilities describe five mutually exclusive settlement states, not stakes.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from sqp.markets.odds import is_usable_price


@dataclass(frozen=True)
class SettlementProbabilities:
    full_win: float
    half_win: float = 0.0
    push: float = 0.0
    half_loss: float = 0.0
    full_loss: float = 0.0

    def __post_init__(self) -> None:
        values = tuple(asdict(self).values())
        if any(not math.isfinite(p) or p < 0 or p > 1 for p in values):
            raise ValueError("settlement probabilities must be finite and in [0, 1]")
        if not math.isclose(math.fsum(values), 1.0, abs_tol=1e-10, rel_tol=0):
            raise ValueError("settlement probabilities must sum to one")

    @property
    def win_units(self) -> float:
        return self.full_win + 0.5 * self.half_win

    @property
    def loss_units(self) -> float:
        return self.full_loss + 0.5 * self.half_loss

    @property
    def decision_probability(self) -> float | None:
        """pW/(pW+pL); stake-weighted equivalent for quarter lines.

        None when every stake is returned. This is not raw P(full win).
        """
        resolved = self.win_units + self.loss_units
        return self.win_units / resolved if resolved else None

    @property
    def fair_decimal(self) -> float | None:
        # None is JSON-safe: with no winning mass there is no unique finite
        # fair price (all-push), or no finite fair price at all (loss mass >0).
        return 1.0 + self.loss_units / self.win_units if self.win_units else None

    def expected_value(self, decimal: float) -> float:
        if not is_usable_price(decimal):
            raise ValueError("decimal odds must be finite and > 1")
        return self.win_units * (decimal - 1.0) - self.loss_units

    def report(self, decimal: float | None = None) -> dict:
        return {
            **asdict(self),
            "decision_probability": self.decision_probability,
            "fair_decimal": self.fair_decimal,
            "ev_per_unit": None if decimal is None else self.expected_value(decimal),
        }


def is_quarter_line(line: float) -> bool:
    """Linea asiatica de cuarto (+-x.25 / +-x.75): liquida a medias.

    Unico predicado compartido por la liquidacion (`settle._grade`) y el
    pricing (`distributions.poisson_match_probs`): tenerlo duplicado es como
    se reintroduciria AUD-001 en silencio (revision fable, 2026-09-17)."""
    return (math.isfinite(line) and float(line * 4).is_integer()
            and not float(line * 2).is_integer())


def split_asian_line(line: float) -> tuple[float, float]:
    """Side-oriented line; -0.25 -> (-0.5, 0), -0.75 -> (-1, -0.5)."""
    if not math.isfinite(line) or not float(line * 4).is_integer():
        raise ValueError("line must be a finite multiple of 0.25")
    return math.floor(line * 2) / 2, math.ceil(line * 2) / 2


def combine_adjacent_lines(
    first: tuple[float, float, float], second: tuple[float, float, float],
) -> SettlementProbabilities:
    """Combine (win,push,loss) on identical or adjacent half-point lines.

    The outcomes are nested functions of the SAME integer-valued score. Their
    differing win/loss masses become half wins/losses; never assume independence.
    """
    w1, p1, l1 = first
    w2, p2, l2 = second
    return SettlementProbabilities(
        full_win=min(w1, w2), half_win=abs(w1 - w2), push=min(p1, p2),
        half_loss=abs(l1 - l2), full_loss=min(l1, l2),
    )


def proportional_no_vig(prices: dict[str, float]) -> tuple[dict[str, float], float]:
    """Caller must supply a complete, matched two/three-way market."""
    if len(prices) not in (2, 3) or any(not is_usable_price(p) for p in prices.values()):
        raise ValueError("a complete market requires two or three valid decimal prices")
    raw = {side: 1.0 / price for side, price in prices.items()}
    total = math.fsum(raw.values())
    return {side: p / total for side, p in raw.items()}, total - 1.0
