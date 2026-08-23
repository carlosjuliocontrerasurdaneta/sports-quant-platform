"""Market-edge adjustment: deflate the raw EV by how far the model strays from
the no-vig market, plus a thin-market penalty.

Ported from project 2's ``adjusted_market_edge`` and adapted to this base's
decimal-price edge convention (``e = p*d - 1``). Rationale: an estimated edge is
suspicious in proportion to how much the model disagrees with the consensus
no-vig price, so the EV is cut by ``gap * uncertainty_penalty`` (continuous),
with an extra bump past an anomaly gap and a penalty for too-few books. This is a
more realistic control than a flat ``market_shrink`` because the cut scales with
the disagreement that the realized-ROI audit showed to be overconfidence.

The penalty is folded back into an EFFECTIVE probability so it also shrinks the
Kelly stake, not just the bet/no-bet decision: ``e_adj = p_eff*d - 1`` ->
``p_eff = (e_adj + 1)/d``.

All coefficients default to 0, so with the shipped RiskConfig dataclass defaults
this is a no-op (``adjusted_edge == raw_edge``, ``effective_probability == p``);
``configs/default.yaml`` activates the recommended values.
"""
from __future__ import annotations
from dataclasses import dataclass

from sqp.markets.odds import is_usable_price


@dataclass
class AdjustedEdge:
    raw_edge: float
    penalty: float
    adjusted_edge: float
    effective_probability: float


def adjusted_edge(probability: float, price_decimal: float,
                  market_probability: float | None, books_count: int | None,
                  *, uncertainty_penalty: float = 0.0, anomaly_edge_gap: float = 0.0,
                  anomaly_extra_penalty: float = 0.0, low_book_penalty: float = 0.0,
                  min_books_for_consensus: int = 0,
                  line_movement_pp: float | None = None,
                  line_movement_penalty: float = 0.0,
                  line_movement_flat_pp: float = 0.5,
                  line_velocity_pp_per_h: float | None = None,
                  line_velocity_penalty: float = 0.0,
                  line_velocity_flat_pp_per_h: float = 0.5,
                  books_spread: float | None = None,
                  books_spread_penalty: float = 0.0,
                  books_spread_threshold: float = 0.0) -> AdjustedEdge:
    """Deflate the raw EV (``p*d - 1``) by the model-vs-market disagreement, a
    thin-market term, adverse-line-movement and adverse-velocity penalties.

    ``market_probability``: no-vig fair prob of the selection; None skips
    uncertainty/anomaly terms. ``books_count``: bookmakers quoting the line;
    None skips the thin-market term.
    ``line_movement_pp``: implied-prob delta in pp from first to last snapshot
    (negative = against pick); adverse when < -flat_pp → penalty +=
    abs(movement_pp) * line_movement_penalty.
    ``line_velocity_pp_per_h``: movement_pp / lookback_h; adverse when
    < -flat_pp_per_h → penalty += abs(velocity) * line_velocity_penalty.
    ``books_spread``: std dev of implied probs across bookmakers (None when
    fewer than 2 books); above books_spread_threshold → penalty +=
    (spread - threshold) * books_spread_penalty. High spread = market
    disagreement = reduced confidence in the consensus price.
    All penalty coefficients default 0 = no-op.
    """
    if not is_usable_price(price_decimal):
        raise ValueError(f"price_decimal must be a positive finite number, got {price_decimal!r}")
    raw = probability * price_decimal - 1.0
    penalty = 0.0
    if market_probability is not None:
        gap = abs(probability - market_probability)
        penalty += gap * uncertainty_penalty
        if anomaly_edge_gap > 0.0 and gap > anomaly_edge_gap:
            penalty += anomaly_extra_penalty
    if (books_count is not None and min_books_for_consensus > 0
            and books_count < min_books_for_consensus):
        penalty += low_book_penalty
    if (line_movement_pp is not None and line_movement_penalty > 0.0
            and line_movement_pp < -line_movement_flat_pp):
        penalty += abs(line_movement_pp) * line_movement_penalty
    if (line_velocity_pp_per_h is not None and line_velocity_penalty > 0.0
            and line_velocity_pp_per_h < -line_velocity_flat_pp_per_h):
        penalty += abs(line_velocity_pp_per_h) * line_velocity_penalty
    if (books_spread is not None and books_spread_penalty > 0.0
            and books_spread > books_spread_threshold):
        penalty += (books_spread - books_spread_threshold) * books_spread_penalty
    penalty = max(0.0, penalty)
    adj = raw - penalty
    p_eff = (adj + 1.0) / price_decimal
    return AdjustedEdge(raw_edge=raw, penalty=penalty, adjusted_edge=adj,
                        effective_probability=p_eff)
