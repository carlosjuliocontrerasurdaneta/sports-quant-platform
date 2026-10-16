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
from dataclasses import dataclass, field
from statistics import median
from typing import TYPE_CHECKING, Callable, Iterable
from sqp.calibration.calibrator import calibrate_probability
from sqp.domain.models import EventOdds, MarketLine
from sqp.features.rest_form import (StaleTeamIndexError, TeamHistoryIndex,
                                    compute_pregame_features,
                                    h2h_p_adjustment, home_away_form_p_adjustment,
                                    margin_p_adjustment, off_def_p_adjustment,
                                    over_rate_from_index, over_under_rate_p_adjustment,
                                    rest_form_p_adjustment, streak_p_adjustment,
                                    totals_tendency_p_adjustment)
from sqp.features.weather import weather_p_adjustment
from sqp.logging_config import get_logger
from sqp.markets.odds import is_usable_price
from sqp.markets.vig import remove_vig_power
from sqp.providers.odds_api import SPORT_KEYS

if TYPE_CHECKING:
    from sqp.config import RiskConfig, WeatherConfig

log = get_logger("sqp.probabilities")


# --- Elegibilidad de casas en h2h a dos vias (auditoría 2026-10-15, AUD-003) --
#
# En una liga de h2h a DOS vias (NHL y demas ligas con ``three_way: False``)
# una casa europea que cotiza el 1X2 a tiempo reglamentario (outcome "Draw")
# vende OTRO contrato: su Home/Away no paga si el partido se decide en la
# prorroga. Agrupar solo por (market, outcome, point) mezclaba ese precio en la
# mediana del Home/Away americano, y el Draw entraba en el de-vig de un mercado
# de dos desenlaces (Home+Away ~0,84; 331 de 346 pares de served_nhl.csv
# sumaban < 0,95). Todas las lineas h2h de esa casa salen del grupo h2h del
# evento -- no solo la del Draw --, y la regla vive aqui, en UN punto que
# comparten consenso, conteos, dispersion, precios de ejecucion y el snapshot
# de la revalidacion. Totals/spreads de la misma casa no se tocan.

def _book_key(bookmaker: object) -> str:
    """Identidad de casa normalizada (mismo criterio que ``_execution_prices``)."""
    return str(bookmaker).strip().lower()


def _league_three_way(league: object) -> bool | None:
    """``three_way`` declarado para la liga en el registro estatico del
    proveedor (``SPORT_KEYS``); None si la liga no esta registrada (futbol y
    tenis se cargan dinamicamente). None significa "no se sabe" y conserva el
    comportamiento historico: solo se excluye cuando la liga se DECLARA a dos
    vias, nunca por inferencia sobre los precios. Solo aplica cuando el llamador
    no pasa ``three_way``: el run diario lo pasa SIEMPRE desde la config de la
    liga, y en tenis vale False, asi que alli la regla si rige (sin efecto hoy:
    ninguna casa cotiza Draw en tenis, medido 2026-10-16)."""
    meta = SPORT_KEYS.get(str(league or "").strip().lower())
    return None if meta is None else bool(meta.get("three_way"))


def _draw_quoting_books(rows: Iterable[tuple[object, object, object]]) -> frozenset[str]:
    """Casas (normalizadas) que cotizan "Draw" en h2h. ``rows`` son tuplas
    (bookmaker, market, outcome): asi sirve igual para ``MarketLine`` y para
    las filas crudas de un snapshot del store. Se mira la presencia de la
    linea, no la usabilidad de su precio: un Draw con precio corrupto sigue
    delatando que la casa vende el contrato 1X2."""
    return frozenset(_book_key(b) for b, m, o in rows
                     if str(m) == "h2h" and str(o) == "Draw")


def _eligible_lines(eo: EventOdds, three_way: bool | None = None) -> list[MarketLine]:
    """Lineas del evento elegibles para consenso/conteos/dispersion/ejecucion.

    ``three_way`` explicito manda; None lo deriva de la liga del evento
    (``_league_three_way``). Solo con ``three_way`` False se excluyen las
    lineas h2h de las casas que cotizan Draw; con True (futbol 1X2) o liga
    desconocida (None) las lineas pasan intactas."""
    tw = three_way if three_way is not None else _league_three_way(eo.event.league)
    if tw is not False:
        return list(eo.lines)
    excluded = _draw_quoting_books((ln.bookmaker, ln.market, ln.outcome)
                                   for ln in eo.lines)
    if not excluded:
        return list(eo.lines)
    return [ln for ln in eo.lines
            if not (ln.market == "h2h" and _book_key(ln.bookmaker) in excluded)]


def _consensus_lines(eo: EventOdds, three_way: bool | None = None) -> dict:
    """Median price per (market, outcome, point) across books; plus the de-vig
    no-vig probability per market used as the fair benchmark.

    ``three_way``: None (default, compatible con los llamadores historicos) lo
    deriva de la liga del evento; ver ``_eligible_lines`` (AUD-003)."""
    groups: dict[tuple, list[float]] = defaultdict(list)
    n_non_finite = 0
    for ln in _eligible_lines(eo, three_way):
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


def _consensus_counts(eo: EventOdds, three_way: bool | None = None) -> dict:
    """How many bookmakers quoted each (market, outcome, point). Feeds the
    thin-market term of the edge penalty (a one-book line is less reliable).
    ``three_way``: mismo contrato que ``_consensus_lines`` -- una casa
    excluida del consenso h2h tampoco cuenta en books_count (AUD-003)."""
    counts: dict[tuple, int] = defaultdict(int)
    for ln in _eligible_lines(eo, three_way):
        # Mismo predicado que _consensus_lines: contar lineas que el consenso
        # descarto inflaba books_count y desactivaba la penalizacion por mercado
        # fino justo donde hacia falta (auditoria 2026-08-05, COR-03).
        if not is_usable_price(ln.price_decimal):
            continue
        counts[(ln.market, ln.outcome, ln.point)] += 1
    return dict(counts)


def _consensus_spread(eo: EventOdds, three_way: bool | None = None) -> dict:
    """Std dev of implied probabilities (1/price) across books per key.

    Returns None for keys with fewer than 2 valid quotes (no spread to measure).
    A high spread signals market disagreement and increases uncertainty about
    the fair price; used as an extra penalty term in adjusted_edge.
    ``three_way``: mismas casas elegibles que ``_consensus_lines`` (AUD-003).
    """
    from statistics import stdev
    groups: dict[tuple, list[float]] = defaultdict(list)
    for ln in _eligible_lines(eo, three_way):
        if not is_usable_price(ln.price_decimal):
            continue
        groups[(ln.market, ln.outcome, ln.point)].append(1.0 / ln.price_decimal)
    return {k: stdev(v) for k, v in groups.items() if len(v) >= 2}


def _novig_probs(cons: dict, market: str, point=None,
                 three_way: bool = False,
                 outcomes: tuple[str, str] | None = None) -> dict:
    """No-vig fair probabilities for h2h and totals. h2h pairs every outcome
    (2-way, or 1X2 for soccer with ``three_way=True``); totals share a single
    point (Over/Under at the same line). Spreads need the home/away team
    identities, so use _spread_novig.

    Requires the COMPLETE complementary market (same guard as _spread_novig):
    a lone quoted side would de-vig to 1.0 (any single implied probability
    normalizes to certainty) and a 1X2 missing the draw inflates both team
    probabilities. Incomplete markets return {} so callers flag them instead
    of blending a fabricated fair probability (audit 2026-07-24, C-1).

    h2h a dos vias (``three_way=False``) exige EXACTAMENTE dos desenlaces y
    ninguno "Draw"; con ``outcomes=(home, away)`` exige ademas que sean esos
    dos. Sobrar claves es mercado incompleto ({}), no un 1X2 encubierto
    (auditoría 2026-10-15, AUD-003)."""
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
        if not three_way:
            # Antes solo se exigia `len(keys) >= 2`, y con una casa 1X2 en el
            # consenso se de-vig-eaban Home/Away/Draw en un mercado de dos
            # desenlaces: Home+Away ~0,84 (auditoría 2026-10-15, AUD-003). El
            # conjunto debe ser exacto; si no, el camino default-deny de
            # "mercado incompleto" en vez de adivinar que claves sobran.
            sides = {k[1] for k in keys}
            if len(keys) != 2 or "Draw" in sides:
                return {}
            if outcomes is not None and sides != set(outcomes):
                return {}
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
    computarse por clave, no por evento.

    El contrato temporal ya NO es solo del llamador: ``ref_date`` viaja con el
    contexto y cada feature recorta por su cuenta a lo estrictamente anterior
    (AUD-LOW-005, 2026-09-06). Los dos consumidores siguen recortando antes
    -- daily pasa el historico liquidado, el backtest ROI usa ``_prior_games``
    con ``d < rd`` --, asi que el filtro es un no-op exacto sobre lo que hay
    hoy; lo que cambia es que un tercer consumidor que pase el historial
    completo ya no puede introducir look-ahead en diez features sin enterarse."""
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
    # Fecha del evento (YYYY-MM-DD). `None` conserva el comportamiento anterior
    # -- sin recorte-- para cualquier constructor que no la aporte.
    ref_date: str | None = None
    # Indice por equipo de `results` (2026-09-30, optimizacion de coste: ver
    # el comentario de `TeamHistoryIndex` en `features/rest_form.py`).
    # `adjust_model_probability` lo reutiliza para el termino over/under-rate
    # en vez de volver a filtrar `results` desde cero por cada seleccion de
    # totals del mismo evento. Campo AL FINAL y con default `None`: ningun
    # constructor posicional existente (no hay ninguno fuera de este modulo,
    # ver `test_backtest_parity.py`) puede romperse, y un `ctx` construido a
    # mano sin este campo (p.ej. en un test) sigue siendo valido -- se
    # construye un indice transitorio bajo demanda, con el MISMO resultado.
    #
    # `compare=False, repr=False` (revision de Fable, 2026-09-30): es una
    # optimizacion de coste, no un dato del dominio del evento. Sin esto, dos
    # contextos con las 16 features IDENTICAS podian salir "!=" solo porque
    # cada uno cargaba un `TeamHistoryIndex` distinto (dataclass sin `__eq__`
    # de contenido para sus `_DateGroup`, que comparan por identidad) -- una
    # trampa para cualquier test o cache que compare `AdjustmentContext` por
    # igualdad. Con `compare=False` la igualdad depende solo de las features.
    team_index: TeamHistoryIndex | None = field(default=None, compare=False, repr=False)


def build_adjustment_context(home: str, away: str, ref_date: str,
                             results: list[dict], risk: RiskConfig,
                             normalize: Callable[[str], str] | None = None,
                             weather: dict | None = None,
                             team_index: TeamHistoryIndex | None = None) -> AdjustmentContext:
    """Computa las features de la capa de ajustes (2026-08-23) para un evento.

    Punto unico de verdad para el run diario y para el backtest de ROI, por la
    misma razon que ``build_model_map`` (auditoria 2026-08-05, F-10): la capa
    de ajustes existia solo en ``daily`` y el backtest evaluaba una politica
    distinta de la desplegada, en silencio (AUD-MED-006). ``weather`` es la
    observacion prepartido de ``get_event_weather``; el backtest pasa None
    porque no hay pronosticos historicos capturados (termino 0, documentado en
    ``roi_engine``).

    Coste (2026-09-30, autorizado por el operador): hasta hoy este helper
    llamaba a ~15 funciones de ``rest_form``, cada una filtrando ``results``
    desde cero -- O(n) por llamada, O(n^2) en un recorrido walk-forward
    (medido en la bateria de ajustes: ~24 ms/partido en NFL en la fila 250,
    ~116 ms en la 1.750). ``compute_pregame_features`` agrupa ``results`` por
    equipo en UNA sola pasada (``TeamHistoryIndex``, ``rest_form.py``) y
    resuelve el corte temporal con ``bisect`` en vez de un filtro lineal;
    misma seleccion de filas, mismo orden de suma, mismos redondeos --
    equivalencia verificada en ``tests/test_rest_form_index_equivalence.py``.
    ``team_index``: opcional, para un llamador que ya tenga uno construido
    sobre este mismo ``results`` y quiera evitar reconstruirlo; por defecto
    se construye aqui, con el mismo resultado en ambos casos.

    Contrato duro sobre ``team_index`` (revision de Fable, 2026-09-30): si se
    pasa, DEBE haberse construido con este MISMO ``results`` (la misma lista,
    no una copia con el mismo contenido) y el mismo ``normalize`` -- un
    indice de otro evento, otra liga o un ``results`` recortado de otra forma
    devuelve silenciosamente features de OTRO historial. Se verifica aqui con
    ``TeamHistoryIndex.matches_source`` (comprobacion barata: longitud +
    identidad de objeto, no un hash de contenido) y se lanza
    ``StaleTeamIndexError`` -- nunca un resultado silencioso -- si no
    coincide."""
    if team_index is not None and not team_index.matches_source(results, normalize):
        raise StaleTeamIndexError(
            "team_index pasado a build_adjustment_context no coincide con "
            f"`results`/`normalize`: el indice tiene source_len="
            f"{team_index.source_len}, source_id={team_index.source_id}, "
            f"normalize_id={team_index.normalize_id}; se esperaba len="
            f"{len(results)}, id={id(results)}, normalize_id="
            f"{id(normalize) if normalize is not None else None}. "
            "Reconstruyelo con TeamHistoryIndex.build(results, normalize) "
            "para este evento, o no lo pases.")
    idx = team_index if team_index is not None else TeamHistoryIndex.build(results, normalize)
    feats = compute_pregame_features(
        home, away, ref_date, results,
        risk.recent_form_n, risk.h2h_n, risk.totals_tendency_n, risk.off_def_n,
        risk.home_away_form_n, risk.margin_n, normalize, idx)
    return AdjustmentContext(
        **feats,
        weather=weather, results=results, normalize=normalize, ref_date=ref_date,
        team_index=idx)


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
        # `ctx.team_index` viaja con el contexto (ver `AdjustmentContext`,
        # 2026-09-30): sin el, un evento con dos selecciones de totals
        # (Over/Under) filtraba `ctx.results` desde cero dos veces por la
        # misma ventana. Un `ctx` sin indice (construido a mano) recae en uno
        # transitorio, con el mismo resultado que `team_over_rate`.
        idx = ctx.team_index if ctx.team_index is not None else \
            TeamHistoryIndex.build(ctx.results, ctx.normalize)
        over_rate_home = over_rate_from_index(idx, home, point,
                                              risk.over_under_rate_n, ctx.normalize,
                                              ctx.ref_date)
        over_rate_away = over_rate_from_index(idx, away, point,
                                              risk.over_under_rate_n, ctx.normalize,
                                              ctx.ref_date)
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


def _execution_prices(eo: EventOdds, cons: dict, books: Iterable[str], *,
                      max_uplift: float, three_way: bool | None = None) -> dict:
    """(mercado, seleccion, punto) -> (precio de EJECUCION, origen).

    Donde se COBRA un pick, que no es lo mismo que donde se ESTIMA. El benchmark
    no-vig se sigue calculando sobre ``cons`` -- la mediana del consenso COMPLETO
    -- y esta funcion no lo toca ni puede tocarlo: de-vigear precios best-of-N da
    suma < 1 y FABRICA edge que no existe. Lo unico que cambia aqui es el precio
    al que se cobraria.

    ``books`` vacio = line shopping DESACTIVADO (default-deny): devuelve la
    mediana del consenso para todas las claves, byte-identico al comportamiento
    historico. Solo el operador sabe en que casas puede realmente transaccionar,
    y un mejor precio en una casa inalcanzable no es un precio -- produciria
    stake que no se puede tomar. Por eso la lista se declara y no se infiere.

    Con una casa accesible que cotiza la clave, el precio de ejecucion es el
    SUYO aunque no supere a la mediana: la mediana del consenso no es una casa en
    la que se pueda apostar. Solo se vuelve a ella cuando ninguna casa accesible
    cotiza esa linea, o cuando el mejor precio supera a la mediana por mas de
    ``max_uplift``: una cuota muy por encima del consenso es cotizacion obsoleta
    o error de origen mucho antes que valor -- el mismo criterio conservador que
    ``max_plausible_edge``.

    Se aplica el MISMO predicado de usabilidad que ``_consensus_lines``
    (``is_usable_price``), asi que un ``inf`` de una casa permitida no puede
    ganar el maximo -- que es exactamente como una cotizacion corrupta se
    convertiria en el precio de ejecucion de todo el mercado.

    Desempate DETERMINISTA por nombre de casa: dos casas al mismo precio no
    pueden producir dos ejecuciones distintas segun el orden en que el proveedor
    devolvio las lineas.

    ``three_way``: mismas casas elegibles que ``_consensus_lines``. Una casa
    1X2 en una liga a dos vias vende otro contrato y no puede ser el precio de
    ejecucion de un Home/Away americano (auditoría 2026-10-15, AUD-003).
    """
    permitidas = {str(b).strip().lower() for b in (books or ()) if str(b).strip()}
    salida: dict = {k: (float(v), "consensus_median") for k, v in cons.items()}
    if not permitidas:
        return salida
    mejores: dict = {}
    for ln in _eligible_lines(eo, three_way):
        if str(ln.bookmaker).strip().lower() not in permitidas:
            continue
        if not is_usable_price(ln.price_decimal):
            continue
        key = (ln.market, ln.outcome, ln.point)
        if key not in cons:
            continue        # defensa: `cons` cubre toda linea usable
        precio, casa = float(ln.price_decimal), str(ln.bookmaker)
        actual = mejores.get(key)
        if (actual is None or precio > actual[0]
                or (precio == actual[0] and casa < actual[1])):
            mejores[key] = (precio, casa)
    for key, (precio, casa) in mejores.items():
        if precio > float(cons[key]) * (1.0 + max_uplift):
            continue        # uplift implausible: manda la mediana
        salida[key] = (precio, casa)
    return salida
