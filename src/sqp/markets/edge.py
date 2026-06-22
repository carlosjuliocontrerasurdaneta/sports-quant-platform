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
                  min_books_for_consensus: int = 0) -> AdjustedEdge:
    """Deflate the raw EV (``p*d - 1``) by the model-vs-market disagreement and a
    thin-market term, and fold the penalty into an effective probability.

    ``market_probability`` is the no-vig fair probability of the same selection;
    when None the uncertainty/anomaly terms are skipped. ``books_count`` is how
    many bookmakers quoted the line; when None the thin-market term is skipped.
    """
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
    penalty = max(0.0, penalty)
    adj = raw - penalty
    p_eff = (adj + 1.0) / price_decimal
    return AdjustedEdge(raw_edge=raw, penalty=penalty, adjusted_edge=adj,
                        effective_probability=p_eff)
