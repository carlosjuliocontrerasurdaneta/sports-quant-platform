"""Probabilidades de mercado y de decisión del pipeline diario.

Helpers puros extraídos de ``pipeline.daily`` (auditoría 2026-07-02, hallazgo
M2: daily.py concentraba fetch, merge, probabilidades, edge, staking y
persistencia). Aquí vive el camino cuotas -> consenso -> no-vig -> probabilidad
de decisión; ``daily`` los re-importa, así que los consumidores existentes
(scripts/clv_analysis.py, tests) no cambian.
"""
from __future__ import annotations
import math
from collections import defaultdict
from statistics import median
from sqp.calibration.calibrator import calibrate_probability
from sqp.domain.models import EventOdds
from sqp.logging_config import get_logger
from sqp.markets.odds import is_usable_price
from sqp.markets.vig import remove_vig_power

log = get_logger("sqp.probabilities")


def _consensus_lines(eo: EventOdds) -> dict:
    """Median price per (market, outcome, point) across books; plus the de-vig
    no-vig probability per market used as the fair benchmark."""
    groups: dict[tuple, list[float]] = defaultdict(list)
    n_non_finite = 0
    for ln in eo.lines:
        # Degenerate quotes (price_decimal <= 1.0 means "no payout") corrupt the
        # fair benchmark: 1/1.0 = 1.0 is an implied CERTAINTY, and remove_vig_power
        # then normalizes the whole market around it. Such rows exist in the
        # captured history (audit 2026-07-24) and `clv_movement._consensus` already
        # filters them; the live consensus did not (audit 2026-07-29, B-13).
        # `is_usable_price` also rejects NaN/inf, which the old `<= 1.0` guard let
        # through -- every comparison with NaN is False (audit 2026-08-05, F-01).
        if not is_usable_price(ln.price_decimal):
            if ln.price_decimal is not None and not math.isfinite(ln.price_decimal):
                n_non_finite += 1
            continue
        groups[(ln.market, ln.outcome, ln.point)].append(ln.price_decimal)
    if n_non_finite:
        # Telemetria: sin esto el descarte era invisible y un evento podia
        # desaparecer de los picks sin dejar rastro en ningun contador.
        log.warning("evento %s (%s): %d linea(s) con precio no finito "
                    "descartadas del consenso. Precio ausente o corrupto en el "
                    "origen; revisar la ingestion.",
                    eo.event.event_id, eo.event.league, n_non_finite)
    # ``statistics.median`` averages the two central values for an even number
    # of books. Picking ``sorted(v)[len(v)//2]`` was the *upper* median and
    # systematically biased every even-book consensus toward that one quote.
    cons = {k: float(median(v)) for k, v in groups.items()}
    return cons


def _consensus_counts(eo: EventOdds) -> dict:
    """How many bookmakers quoted each (market, outcome, point). Feeds the
    thin-market term of the edge penalty (a one-book line is less reliable)."""
    counts: dict[tuple, int] = defaultdict(int)
    for ln in eo.lines:
        # Mismo predicado que _consensus_lines: contar lineas que el consenso
        # descarto inflaba books_count y desactivaba la penalizacion por mercado
        # fino justo donde hacia falta (auditoria 2026-08-05, COR-03).
        if not is_usable_price(ln.price_decimal):
            continue
        counts[(ln.market, ln.outcome, ln.point)] += 1
    return dict(counts)


def _novig_probs(cons: dict, market: str, point=None,
                 three_way: bool = False) -> dict:
    """No-vig fair probabilities for h2h and totals. h2h pairs every outcome
    (2-way, or 1X2 for soccer with ``three_way=True``); totals share a single
    point (Over/Under at the same line). Spreads need the home/away team
    identities, so use _spread_novig.

    Requires the COMPLETE complementary market (same guard as _spread_novig):
    a lone quoted side would de-vig to 1.0 (any single implied probability
    normalizes to certainty) and a 1X2 missing the draw inflates both team
    probabilities. Incomplete markets return {} so callers flag them instead
    of blending a fabricated fair probability (audit 2026-07-24, C-1)."""
    if market == "h2h":
        keys = [k for k in cons if k[0] == "h2h"]
        required = 3 if three_way else 2
    else:
        keys = [k for k in cons if k[0] == market and k[2] == point]
        required = 2
    if len(keys) < required:
        return {}
    if not all(is_usable_price(cons[k]) for k in keys):
        # Un precio no finito degrada al camino YA existente y probado de
        # "mercado incompleto" ({} -> flag incomplete_market, stake 0) en vez de
        # propagar NaN a las probabilidades justas de todo el mercado
        # (auditoria 2026-08-05, F-01).
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
    if not all(is_usable_price(cons[k]) for k in present):
        return {}   # mismo criterio que _novig_probs (auditoria 2026-08-05, F-01)
    fair = remove_vig_power([1.0 / cons[k] for k in present])
    return {k[1]: p for k, p in zip(present, fair)}


def _pick_main_lines(eo: EventOdds) -> tuple[float | None, float | None]:
    """Main spread (home point) and total line = most-quoted point."""
    spread_counts: dict[float, int] = defaultdict(int)
    total_counts: dict[float, int] = defaultdict(int)
    for ln in eo.lines:
        if ln.market == "spreads" and ln.outcome == eo.event.home and ln.point is not None:
            spread_counts[ln.point] += 1
        if ln.market == "totals" and ln.point is not None:
            total_counts[ln.point] += 1
    spread = max(spread_counts, key=lambda p: spread_counts[p]) if spread_counts else None
    total = max(total_counts, key=lambda p: total_counts[p]) if total_counts else None
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
