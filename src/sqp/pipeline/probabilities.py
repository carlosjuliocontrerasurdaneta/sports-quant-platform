"""Probabilidades de mercado y de decisión del pipeline diario.

Helpers puros extraídos de ``pipeline.daily`` (auditoría 2026-07-02, hallazgo
M2: daily.py concentraba fetch, merge, probabilidades, edge, staking y
persistencia). Aquí vive el camino cuotas -> consenso -> no-vig -> probabilidad
de decisión; ``daily`` los re-importa, así que los consumidores existentes
(scripts/clv_analysis.py, tests) no cambian.
"""
from __future__ import annotations
from collections import defaultdict
from sqp.calibration.calibrator import calibrate_probability
from sqp.domain.models import EventOdds
from sqp.markets.vig import remove_vig_power


def _consensus_lines(eo: EventOdds) -> dict:
    """Median price per (market, outcome, point) across books; plus the de-vig
    no-vig probability per market used as the fair benchmark."""
    groups: dict[tuple, list[float]] = defaultdict(list)
    for ln in eo.lines:
        groups[(ln.market, ln.outcome, ln.point)].append(ln.price_decimal)
    cons = {k: sorted(v)[len(v) // 2] for k, v in groups.items()}
    return cons


def _consensus_counts(eo: EventOdds) -> dict:
    """How many bookmakers quoted each (market, outcome, point). Feeds the
    thin-market term of the edge penalty (a one-book line is less reliable)."""
    counts: dict[tuple, int] = defaultdict(int)
    for ln in eo.lines:
        counts[(ln.market, ln.outcome, ln.point)] += 1
    return dict(counts)


def _novig_probs(cons: dict, market: str, point=None) -> dict:
    """No-vig fair probabilities for h2h and totals. h2h pairs every outcome
    (2-way, or 1X2 for soccer); totals share a single point (Over/Under at the
    same line). Spreads need the home/away team identities, so use _spread_novig.
    """
    if market == "h2h":
        keys = [k for k in cons if k[0] == "h2h"]
    else:
        keys = [k for k in cons if k[0] == market and k[2] == point]
    if not keys:
        return {}
    implied = [1.0 / cons[k] for k in keys]
    fair = remove_vig_power(implied)
    return {k[1]: p for k, p in zip(keys, fair)}


def _spread_novig(cons: dict, home: str, away: str, spread: float | None) -> dict:
    """No-vig fair probabilities for the MAIN spread line only: home at `spread`
    paired with away at `-spread`. Books also quote alternate runlines (MLB lists
    both teams at +-1.5), so matching by absolute point would mix 4 outcomes and
    corrupt the de-vig; this pairs exactly the two complementary main-line sides.
    """
    if spread is None:
        return {}
    pair = [("spreads", home, spread), ("spreads", away, -spread)]
    present = [k for k in pair if k in cons]
    if len(present) < 2:
        return {}
    fair = remove_vig_power([1.0 / cons[k] for k in present])
    return {k[1]: p for k, p in zip(present, fair)}


def _pick_main_lines(eo: EventOdds) -> tuple[float | None, float | None]:
    """Main spread (home point) and total line = most-quoted point."""
    spread_counts, total_counts = defaultdict(int), defaultdict(int)
    for ln in eo.lines:
        if ln.market == "spreads" and ln.outcome == eo.event.home and ln.point is not None:
            spread_counts[ln.point] += 1
        if ln.market == "totals" and ln.point is not None:
            total_counts[ln.point] += 1
    spread = max(spread_counts, key=spread_counts.get) if spread_counts else None
    total = max(total_counts, key=total_counts.get) if total_counts else None
    return spread, total


def _decision_probability(p_model: float, fair: float | None, shrink: float,
                          league: str, market: str, settings) -> tuple[float, float]:
    """(p_used_raw, p_decision) para un candidato.

    La calibración se aplica a la probabilidad PURA del modelo ANTES del shrink
    al mercado: ``p_decision = (1-s)*cal(p_model) + s*fair``. Calibrar la mezcla
    obligaba al calibrador a corregir el modelo a través de un canal diluido al
    50% por el no-vig (ya bien calibrado); sobre settled, el reblend dominó a
    ``cal(p_used)`` en ECE y Brier OOS en todos los cortes temporales
    (docs/research/2026-07-02-calibrar-pmodel-puro-vs-blend.md). El retrain
    entrena sobre ``model_probability`` (la misma columna cruda que se almacena),
    así que train y serve calibran el mismo objetivo y no puede haber loop
    calibrar-sobre-calibrado: ``p_used`` almacenada sigue siendo la mezcla CRUDA.
    Sin calibrador para (liga, mercado) -> no-op y ``p_decision == p_used``."""
    p_cal = p_model
    if settings.calibration_enabled:
        p_cal = calibrate_probability(p_model, league, market,
                                      settings.calibration_method)
    if fair is not None and shrink > 0:
        p_used = (1.0 - shrink) * p_model + shrink * fair
        p_decision = (1.0 - shrink) * p_cal + shrink * fair
    else:
        p_used, p_decision = p_model, p_cal
    return p_used, p_decision
