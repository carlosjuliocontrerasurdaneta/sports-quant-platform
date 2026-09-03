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
from dataclasses import dataclass
from statistics import median
from typing import TYPE_CHECKING, Callable
from sqp.calibration.calibrator import calibrate_probability
from sqp.domain.models import EventOdds
from sqp.features.rest_form import (h2h_p_adjustment, home_away_form_p_adjustment,
                                    margin_p_adjustment, off_def_p_adjustment,
                                    over_under_rate_p_adjustment,
                                    rest_form_p_adjustment, streak_p_adjustment,
                                    team_avg_conceded, team_avg_margin,
                                    team_avg_scored, team_avg_total,
                                    team_h2h_form, team_over_rate,
                                    team_recent_form, team_recent_form_away,
                                    team_recent_form_home, team_rest_days,
                                    team_streak, totals_tendency_p_adjustment)
from sqp.features.weather import weather_p_adjustment
from sqp.logging_config import get_logger
from sqp.markets.odds import is_usable_price
from sqp.markets.vig import remove_vig_power

if TYPE_CHECKING:
    from sqp.config import RiskConfig, WeatherConfig

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


def _consensus_spread(eo: EventOdds) -> dict:
    """Std dev of implied probabilities (1/price) across books per key.

    Returns None for keys with fewer than 2 valid quotes (no spread to measure).
    A high spread signals market disagreement and increases uncertainty about
    the fair price; used as an extra penalty term in adjusted_edge.
    """
    from statistics import stdev
    groups: dict[tuple, list[float]] = defaultdict(list)
    for ln in eo.lines:
        if not is_usable_price(ln.price_decimal):
            continue
        groups[(ln.market, ln.outcome, ln.point)].append(1.0 / ln.price_decimal)
    return {k: stdev(v) for k, v in groups.items() if len(v) >= 2}


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
        # El `point` DEBE ser None en h2h: es el contrato del mercado. Recoger
        # todas las claves h2h sin mirarlo mezclaba lineas de puntos distintos y
        # de-vig-eaba 4 desenlaces como si fueran 2 (auditoria 2026-08-05,
        # QNT-08). Filtrar degrada a "mercado incompleto" -- el camino
        # default-deny ya probado -- en vez de adivinar el emparejamiento.
        # Alcanzabilidad medida el 2026-08-25: 0 de 2.091.866 lineas h2h reales
        # traen `point`, asi que hoy es un no-op y manana un guard.
        keys = [k for k in cons if k[0] == "h2h" and k[2] is None]
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


def build_model_map(est, event, spread, total) -> dict:
    """(mercado, seleccion, punto) -> probabilidad estimada del modelo.

    Punto unico de verdad para el run diario y para el backtest de ROI. Estaba
    duplicado literalmente en ``pipeline.daily`` y ``backtesting.roi_engine``
    con las mismas seis entradas y las mismas convenciones de signo: anadir un
    mercado o cambiar un signo exigia dos ediciones coherentes, y una sola
    producia un backtest que evaluaba una politica distinta de la desplegada,
    en silencio (auditoria 2026-08-05, F-10).
    """
    mm: dict[tuple[str, str, float | None], float | None] = {
        ("h2h", event.home, None): est.home_win_estimated_probability,
        ("h2h", event.away, None): est.away_win_estimated_probability}
    if est.draw_estimated_probability is not None:
        mm[("h2h", "Draw", None)] = est.draw_estimated_probability
    if est.home_cover_estimated_probability is not None and spread is not None:
        mm[("spreads", event.home, spread)] = est.home_cover_estimated_probability
        mm[("spreads", event.away, -spread)] = est.away_cover_estimated_probability
    if est.over_estimated_probability is not None and total is not None:
        mm[("totals", "Over", total)] = est.over_estimated_probability
        mm[("totals", "Under", total)] = est.under_estimated_probability
    return mm


def _decision_probability(p_model: float, fair: float | None, shrink: float,
                          league: str, market: str, settings) -> tuple[float, float]:
    """(p_used_raw, p_decision) para un candidato.

    La calibración se aplica a la creencia PRE-BLEND, ANTES del shrink al
    mercado: ``p_decision = (1-s)*cal(p_pre) + s*fair``. Calibrar la mezcla
    obligaba al calibrador a corregir el modelo a través de un canal diluido al
    50% por el no-vig (ya bien calibrado); sobre settled, el reblend dominó a
    ``cal(p_used)`` en ECE y Brier OOS en todos los cortes temporales
    (docs/research/2026-07-02-calibrar-pmodel-puro-vs-blend.md).

    OJO con el nombre del parámetro: ``p_model`` recibe ``_p_adj``, la
    probabilidad del modelo YA pasada por la capa de ajustes de features
    (``adjust_model_probability``), no la pura. Desde el 2026-08-23 esa es la
    cantidad calibrada, y el retrain entrena sobre la columna servida
    ``adjusted_probability`` -- con fallback a ``model_probability`` para filas de
    esquema antiguo (``calibration/data.py``, pre-registro del 2026-08-24). Train
    y serve calibran por tanto el mismo objetivo, y no puede haber loop
    calibrar-sobre-calibrado: la ``p_used`` almacenada sigue siendo la mezcla
    CRUDA. El docstring afirmó hasta el 2026-09-03 que se calibraba la
    probabilidad pura y que el retrain usaba ``model_probability``: ambas cosas
    dejaron de ser ciertas con la capa de ajustes (auditoría integral,
    AUD-LOW-001).

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


@dataclass(frozen=True)
class AdjustmentContext:
    """Features pregame por evento para la cadena de ajustes aditivos.

    ``results`` y ``normalize`` viven aqui porque el termino de over/under rate
    depende de la LINEA de cada seleccion de totals (key[2]) y solo puede
    computarse por clave, no por evento. El contrato temporal es del llamador:
    ``results`` debe contener EXCLUSIVAMENTE partidos anteriores al evento
    (daily pasa el historico liquidado; el backtest ROI recorta a fechas
    estrictamente anteriores)."""
    rest_home: int | None
    rest_away: int | None
    form_home: float | None
    form_away: float | None
    h2h_home: float | None
    avg_total_home: float | None
    avg_total_away: float | None
    streak_home: int
    streak_away: int
    avg_scored_home: float | None
    avg_conceded_home: float | None
    avg_scored_away: float | None
    avg_conceded_away: float | None
    form_home_at_home: float | None
    form_away_at_away: float | None
    margin_home: float | None
    margin_away: float | None
    weather: dict | None
    results: list[dict]
    normalize: Callable[[str], str] | None


def build_adjustment_context(home: str, away: str, ref_date: str,
                             results: list[dict], risk: RiskConfig,
                             normalize: Callable[[str], str] | None = None,
                             weather: dict | None = None) -> AdjustmentContext:
    """Computa las features de la capa de ajustes (2026-08-23) para un evento.

    Punto unico de verdad para el run diario y para el backtest de ROI, por la
    misma razon que ``build_model_map`` (auditoria 2026-08-05, F-10): la capa
    de ajustes existia solo en ``daily`` y el backtest evaluaba una politica
    distinta de la desplegada, en silencio (AUD-MED-006). ``weather`` es la
    observacion prepartido de ``get_event_weather``; el backtest pasa None
    porque no hay pronosticos historicos capturados (termino 0, documentado en
    ``roi_engine``)."""
    return AdjustmentContext(
        rest_home=team_rest_days(home, results, ref_date, normalize),
        rest_away=team_rest_days(away, results, ref_date, normalize),
        form_home=team_recent_form(home, results, risk.recent_form_n, normalize),
        form_away=team_recent_form(away, results, risk.recent_form_n, normalize),
        h2h_home=team_h2h_form(home, away, results, risk.h2h_n, normalize),
        avg_total_home=team_avg_total(home, results, risk.totals_tendency_n, normalize),
        avg_total_away=team_avg_total(away, results, risk.totals_tendency_n, normalize),
        streak_home=team_streak(home, results, normalize),
        streak_away=team_streak(away, results, normalize),
        avg_scored_home=team_avg_scored(home, results, risk.off_def_n, normalize),
        avg_conceded_home=team_avg_conceded(home, results, risk.off_def_n, normalize),
        avg_scored_away=team_avg_scored(away, results, risk.off_def_n, normalize),
        avg_conceded_away=team_avg_conceded(away, results, risk.off_def_n, normalize),
        form_home_at_home=team_recent_form_home(home, results,
                                                risk.home_away_form_n, normalize),
        form_away_at_away=team_recent_form_away(away, results,
                                                risk.home_away_form_n, normalize),
        margin_home=team_avg_margin(home, results, risk.margin_n, normalize),
        margin_away=team_avg_margin(away, results, risk.margin_n, normalize),
        weather=weather, results=results, normalize=normalize)


def adjust_model_probability(p_model: float, market: str, selection: str,
                             point: float | None, home: str, away: str,
                             ctx: AdjustmentContext, risk: RiskConfig,
                             weather_cfg: WeatherConfig | None = None) -> float:
    """p_model + los diez terminos aditivos de la capa de ajustes, acotado a
    [0.01, 0.99]. Es EXACTAMENTE la expresion que vivia inline en
    ``daily.run_league`` (mismo orden de suma, mismo clamp): cualquier cambio
    aqui cambia a la vez la politica desplegada y la del backtest. Cada
    termino es 0 cuando su coeficiente es 0 (configuracion por defecto).

    ``weather_cfg=None`` (backtest) equivale a ``ctx.weather=None``: el
    termino meteorologico es exactamente 0.0 en ambos casos."""
    if market == "totals" and point is not None:
        over_rate_home = team_over_rate(home, ctx.results, point,
                                        risk.over_under_rate_n, ctx.normalize)
        over_rate_away = team_over_rate(away, ctx.results, point,
                                        risk.over_under_rate_n, ctx.normalize)
    else:
        over_rate_home = over_rate_away = None
    weather_term = (weather_p_adjustment(market, selection, ctx.weather, weather_cfg)
                    if weather_cfg is not None else 0.0)
    return max(0.01, min(0.99, p_model
               + rest_form_p_adjustment(
                   p_model, market, selection, home, away,
                   ctx.rest_home, ctx.rest_away, ctx.form_home, ctx.form_away,
                   risk.rest_days_coef, risk.recent_form_coef)
               + h2h_p_adjustment(
                   market, selection, home, away, ctx.h2h_home, risk.h2h_coef)
               + weather_term
               + totals_tendency_p_adjustment(
                   market, selection, ctx.avg_total_home, ctx.avg_total_away,
                   point, risk.totals_tendency_coef)
               + streak_p_adjustment(
                   market, selection, home, away, ctx.streak_home,
                   ctx.streak_away, risk.streak_coef)
               + off_def_p_adjustment(
                   market, selection, home, away,
                   ctx.avg_scored_home, ctx.avg_conceded_home,
                   ctx.avg_scored_away, ctx.avg_conceded_away,
                   point, risk.off_def_h2h_coef, risk.off_def_totals_coef)
               + home_away_form_p_adjustment(
                   market, selection, home, away,
                   ctx.form_home_at_home, ctx.form_away_at_away,
                   risk.home_away_form_coef)
               + margin_p_adjustment(
                   market, selection, home, away, ctx.margin_home,
                   ctx.margin_away, risk.margin_coef)
               + over_under_rate_p_adjustment(
                   market, selection, over_rate_home, over_rate_away,
                   risk.over_under_rate_coef)))
