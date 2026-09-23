"""Fase 1 del pre-registro de mercados derivados (2026-08-24): team_totals MLB.

Recoleccion FORWARD de cuotas de team_totals contra el libro, con la
probabilidad PURA del motor sellada en el instante de captura. El motor no
expone este mercado: la probabilidad es la marginal por equipo que ya calcula
el adaptador (`score_pmf(lam_equipo)`), la misma que paso la Fase 0
(`scripts/research/measure_team_totals_calibration.py`). Sin este fichero no
se puede medir edge realizado hacia atras: The Odds API solo sirve mercados
adicionales por evento y no los guarda en el historico del proyecto.

Guardarrailes copiados del pre-registro, no reinventados:

  - tope de creditos `<= 45/dia` y `<= 1.400/mes`, con auto-stop;
  - stake 0 siempre: este modulo no produce candidatos ni picks;
  - solo eventos NO comenzados (`captured_at < commence_time`, KI-019);
  - fuera de muestra: la fecha de captura es posterior al pre-registro por
    construccion.

Autorizacion explicita del operador para el gasto: 2026-09-19 («Sí, hazlo»),
registrada en `Obsidian/Bitácora/2026-09-19.md`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

import pandas as pd

from sqp.config import ROOT, Settings
from sqp.domain.models import Event, EventOdds
from sqp.logging_config import get_logger
from sqp.markets.odds import is_usable_price
from sqp.models.distributions import score_pmf
from sqp.pipeline.closing_capture import add_spent, spent_today
from sqp.storage.atomic import atomic_write_csv
from sqp.storage.lock import locked
from sqp.storage.results_store import ResultsStore

log = get_logger("sqp.team_totals")

MARKET = "team_totals"
# Pre-registro 2026-08-24, Fase 1: tope de creditos con auto-stop.
MAX_CREDITS_PER_DAY = 45
MAX_CREDITS_PER_MONTH = 1400
MIN_REMAINING = 500  # no se toca el colchon del run diario
CREDITS_PREFIX = ".team_totals_credits_"
HORIZON_HOURS = 30  # partidos de hoy y de manana temprano; una captura por dia
# Coste de una peticion por evento con `us,eu`. Se comprueba ANTES de pedir: la
# guarda antigua miraba "¿ya me pase?" en vez de "¿me pasare si pido esto?", y
# con el tope impar (45) y saltos de 2 el dia cerraba en 46. Reproducido en
# produccion el 2026-09-19 -- el propio log imprimia `tope de creditos alcanzado
# (46/45 hoy)` -- (auditoria integral 2026-09-22, AUD-003).
CREDITS_PER_EVENT = 2
# Cobertura: dias de historico que forman la linea base y fraccion por debajo de
# la cual se avisa. La Fase 1 existe para ACUMULAR muestra fuera de muestra, y
# una caida de cobertura la degrada en silencio: el 2026-09-21 se capturaron 3
# eventos frente a 15 el dia anterior, sin motivo de parada y sin que ningun
# control lo dijera (auditoria integral 2026-09-22, AUD-002). El resumen contaba
# lo capturado, pero no habia expectativa contra la que compararlo.
COVERAGE_BASELINE_DAYS = 7
COVERAGE_MIN_FRACTION = 0.5

# La fecha oficial MLB es la fecha LOCAL del partido; un nocturno de la costa
# oeste comienza tras las 00:00Z y su fecha UTC va un dia por delante. La fecha
# en hora del Este resuelve el caso sin adivinar, salvo partidos que pasen de
# medianoche ET, que quedan sin graduar antes que mal graduados.
MLB_TZ = ZoneInfo("America/New_York")

COLUMNS = ["captured_at", "event_id", "commence_time", "home", "away", "team",
           "side", "point", "price_decimal", "bookmaker", "model_probability",
           "home_pitcher", "away_pitcher"]


def tail_over(lam: float, line: float, max_score: int, dispersion_k: float | None) -> float:
    """P(carreras del equipo > linea) desde la marginal del motor. Las lineas
    son medias, asi que no hay masa de push."""
    pmf = score_pmf(lam, max_score, dispersion_k)
    thr = int(line) + 1
    return sum(pmf[thr:]) / max(1e-12, sum(pmf))


def team_total_rows(eo: EventOdds, lam_home: float, lam_away: float, *,
                    max_score: int, dispersion_k: float | None,
                    captured_at: str) -> list[dict[str, Any]]:
    """Una fila por (casa, equipo, lado, linea) con la probabilidad del motor.

    Solo lineas medias (`.5`): una linea entera introduce push y la Fase 0 no
    la calibro. Los precios degenerados se conservan (igual que `odds_store`),
    el consenso los descarta al leer via `is_usable_price`.
    """
    ev = eo.event
    lam_by_team = {ev.home: lam_home, ev.away: lam_away}
    rows: list[dict[str, Any]] = []
    for ln in eo.lines:
        if ln.market != MARKET or ln.point is None or ln.description not in lam_by_team:
            continue
        side = str(ln.outcome).lower()
        if side not in ("over", "under"):
            continue
        point = float(ln.point)
        if abs(point - round(point)) != 0.5:
            continue
        p_over = tail_over(lam_by_team[ln.description], point, max_score, dispersion_k)
        rows.append({
            "captured_at": captured_at, "event_id": ev.event_id,
            "commence_time": ev.start_time, "home": ev.home, "away": ev.away,
            "team": ln.description, "side": side, "point": point,
            "price_decimal": float(ln.price_decimal), "bookmaker": ln.bookmaker,
            "model_probability": p_over if side == "over" else 1.0 - p_over,
            "home_pitcher": ev.home_pitcher, "away_pitcher": ev.away_pitcher,
        })
    return rows


def _parse_utc(s: object) -> datetime | None:
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def spent_this_month(odds_dir: Path, day: str) -> int:
    """Suma de los contadores diarios del mes de `day` (YYYY-MM-DD)."""
    total = 0
    for p in odds_dir.glob(f"{CREDITS_PREFIX}{day[:7]}-*"):
        total += spent_today(odds_dir, p.name[len(CREDITS_PREFIX):], CREDITS_PREFIX)
    return total


def store_path(root: Path, league: str, month: str) -> Path:
    return root / "data" / "odds" / f"team_totals_{league}_{month}.csv"


def coverage_baseline(root: Path, league: str, *, day: str,
                      days: int = COVERAGE_BASELINE_DAYS) -> float | None:
    """Mediana de eventos capturados por dia en los ``days`` dias ANTERIORES.

    ``None`` cuando no hay historico suficiente (los primeros dias de la Fase 1,
    o tras una pausa larga): sin linea base no se avisa, porque un aviso que no
    puede distinguir "hoy hay pocos partidos" de "hoy fallo la recoleccion" no
    informa de nada.

    El dia en curso se EXCLUYE a proposito: es lo que se quiere juzgar.
    """
    try:
        caps = load_captures(root, league)
    except (OSError, ValueError):
        return None
    if caps.empty or "captured_at" not in caps.columns:
        return None
    dias = caps["captured_at"].astype(str).str[:10]
    previos = caps[(dias < day) & (dias >= _dias_antes(day, days))]
    if previos.empty:
        return None
    por_dia = previos.groupby(previos["captured_at"].astype(str).str[:10])["event_id"].nunique()
    return float(por_dia.median()) if len(por_dia) else None


def _dias_antes(day: str, days: int) -> str:
    try:
        d = datetime.strptime(day, "%Y-%m-%d")
    except ValueError:
        return ""
    return (d - timedelta(days=days)).strftime("%Y-%m-%d")


def append_rows(root: Path, league: str, rows: list[dict[str, Any]]) -> int:
    """Persiste las filas en el fichero mensual propio de team_totals. Es un
    artefacto NUEVO: no toca el contrato de `odds_<liga>_<mes>.csv`."""
    if not rows:
        return 0
    df = pd.DataFrame(rows)[COLUMNS]
    p = store_path(root, league, str(rows[0]["captured_at"])[:7].replace("-", ""))
    p.parent.mkdir(parents=True, exist_ok=True)
    with locked(p):
        if p.exists():
            prior = pd.read_csv(p)
            if list(prior.columns) != COLUMNS:
                cols = list(prior.columns) + [c for c in COLUMNS if c not in prior.columns]
                atomic_write_csv(pd.concat([prior.reindex(columns=cols),
                                            df.reindex(columns=cols)], ignore_index=True), p)
                return len(df)
        df.to_csv(p, mode="a", header=not p.exists(), index=False)
    return len(df)


def _fit_adapter(league: str, root: Path):
    """Mismo ajuste que la ruta live de `daily.run_league` para beisbol."""
    from sqp.pipeline.daily import _league_meta
    from sqp.sports.registry import get_adapter
    from sqp.storage.starter_fip import StarterFIPStore
    from sqp.storage.starters import StartersStore

    meta = _league_meta(league)
    if meta["family"] != "baseball":
        raise ValueError(f"team_totals Fase 1 esta pre-registrada solo para beisbol; "
                         f"{league!r} es {meta['family']!r}")
    adapter = get_adapter(league, meta["family"], meta.get("league_params"))
    results = ResultsStore(root).load(league)
    if results:
        StartersStore(root).attach(league, results)
        StarterFIPStore(root).attach(league, results)
        adapter.fit_results(results)
    return adapter, meta


def capture_team_totals(settings: Settings, *, league: str = "mlb", client=None,
                        root: Path | None = None, now: datetime | None = None,
                        pitcher_provider=None,
                        clock: Callable[[], datetime] | None = None) -> dict[str, Any]:
    """Una captura de team_totals para los partidos no comenzados del horizonte.

    Devuelve un resumen con eventos capturados, filas, creditos gastados y el
    motivo de parada si el presupuesto corta. Nunca lanza por un evento
    concreto: se registra y se sigue con el siguiente.

    `clock` da la hora ANTES de cada peticion: el `captured_at` de cada fila es
    el de su propia llamada, y un evento que comience mientras el bucle avanza
    (abridores, reintentos) se salta en vez de sellarse como prepartido. `now`
    fija el reloj (tests); sin ninguno de los dos, UTC real.
    """
    root = root or ROOT
    if clock is None:
        fixed = now
        clock = (lambda: fixed) if fixed is not None else (lambda: datetime.now(timezone.utc))
    now = clock()
    day = now.strftime("%Y-%m-%d")
    odds_dir = root / "data" / "odds"
    summary: dict[str, Any] = {"league": league, "day": day, "events": 0, "rows": 0,
                               "credits_spent": 0, "skipped": [], "stop": None,
                               # Cuantos eventos habia DISPONIBLES en el horizonte
                               # (AUD-002): sin este numero, "3 eventos" no se
                               # distingue de "3 partidos hoy".
                               "candidates": 0, "coverage_baseline": None}
    already_day = spent_today(odds_dir, day, CREDITS_PREFIX)
    already_month = spent_this_month(odds_dir, day)
    if already_day >= MAX_CREDITS_PER_DAY or already_month >= MAX_CREDITS_PER_MONTH:
        summary["stop"] = (f"presupuesto agotado antes de empezar: {already_day}/{MAX_CREDITS_PER_DAY} "
                           f"hoy, {already_month}/{MAX_CREDITS_PER_MONTH} este mes")
        log.warning("team_totals: %s", summary["stop"])
        return summary

    if client is None:
        from sqp.providers.odds_api import OddsAPIClient
        client = OddsAPIClient(settings.odds_api_key, settings.regions, settings.odds_format)
    adapter, meta = _fit_adapter(league, root)
    max_score = int(adapter.params.get("max_score", 15))
    disp_k = adapter.params.get("dispersion_k")

    horizon_end = now + timedelta(hours=HORIZON_HOURS)
    upcoming = []
    for e in client.list_events(meta["sport_key"]):
        t = _parse_utc(e.get("commence_time"))
        if t is None or t <= now or t > horizon_end:
            continue
        upcoming.append(e)
    summary["candidates"] = len(upcoming)
    # Cobertura (AUD-002): el aviso mira los CANDIDATOS, no lo capturado, porque
    # una recoleccion que se queda corta puede fallar en dos sitios distintos --
    # el proveedor devuelve pocos eventos, o el presupuesto corta el bucle -- y
    # solo el primero se ve aqui. El segundo lo delata `stop`, mas abajo.
    base = coverage_baseline(root, league, day=day)
    summary["coverage_baseline"] = base
    if base is not None and len(upcoming) < COVERAGE_MIN_FRACTION * base:
        log.warning("team_totals: [%s] COBERTURA BAJA -- %d evento(s) en el "
                    "horizonte de %d h frente a una mediana de %.1f en los "
                    "ultimos %d dias. La Fase 1 acumula muestra fuera de "
                    "muestra: una caida de cobertura la degrada en silencio. "
                    "Revisar el calendario de la liga y la respuesta del "
                    "proveedor antes de dar el dia por bueno.",
                    league, len(upcoming), HORIZON_HOURS, base,
                    COVERAGE_BASELINE_DAYS)
    if not upcoming:
        summary["stop"] = "sin eventos no comenzados en el horizonte"
        return summary

    # Abridores probables ANTES de pedir cuotas: la lambda que se sella lleva
    # la misma informacion que produccion tenia a esa hora.
    events = [EventOdds(event=Event(event_id=str(e["id"]), sport_key=meta["sport_key"],
                                    league=league, home=e["home_team"], away=e["away_team"],
                                    start_time=str(e["commence_time"]), data_label="real"))
              for e in upcoming]
    try:
        from sqp.pipeline.daily import _attach_probable_pitchers
        _attach_probable_pitchers(events, league, adapter.normalize,
                                  provider=pitcher_provider, root=root)
    except Exception as exc:  # best-effort, igual que el run diario
        log.warning("team_totals: abridores no disponibles: %s", exc)

    spent = 0
    for eo in events:
        # Coste PREVISTO, no gasto consumado (AUD-003): parar cuando esta
        # peticion rebasaria el tope, no cuando ya lo rebaso.
        if (already_day + spent + CREDITS_PER_EVENT > MAX_CREDITS_PER_DAY
                or already_month + spent + CREDITS_PER_EVENT > MAX_CREDITS_PER_MONTH):
            summary["stop"] = (f"tope de creditos alcanzado ({already_day + spent}/{MAX_CREDITS_PER_DAY} "
                               f"hoy, {already_month + spent}/{MAX_CREDITS_PER_MONTH} mes)")
            summary["skipped"].append(eo.event.event_id)
            continue
        remaining = getattr(client, "requests_remaining", None)
        if remaining is not None and remaining < MIN_REMAINING:
            summary["stop"] = f"requests_remaining {remaining} < {MIN_REMAINING}"
            summary["skipped"].append(eo.event.event_id)
            continue
        # Guard prepartido por EVENTO y en el instante de la peticion (KI-019):
        # el filtro del horizonte se hizo con la hora de arranque del bucle.
        at = clock()
        start = _parse_utc(eo.event.start_time)
        if start is None or start <= at:
            summary["skipped"].append(eo.event.event_id)
            log.info("team_totals: [%s] comenzado antes de la peticion; no se captura",
                     eo.event.event_id)
            continue
        try:
            fetched = client.fetch_event_odds(league, meta["sport_key"], eo.event.event_id, MARKET)
        except Exception as exc:
            log.warning("team_totals: [%s] fallo al pedir cuotas: %s", eo.event.event_id, exc)
            summary["skipped"].append(eo.event.event_id)
            continue
        delta = int(getattr(client, "requests_last", 0) or 0)
        if delta:
            add_spent(odds_dir, day, delta, CREDITS_PREFIX)
        spent += delta
        if not fetched:
            continue
        if getattr(client, "last_response_cached", False):
            # La respuesta ya se persistio en la peticion que la origino; volver
            # a sellarla con la hora de ahora falsearia `captured_at`.
            continue
        # La cuota es de cuando LLEGA la respuesta, no de cuando se pidio: con
        # reintentos o red lenta el partido puede haber comenzado entre medias
        # y el libro ya estaria en vivo. Se comprueba otra vez y se sella con
        # la hora de llegada; el credito ya gastado se cuenta igual.
        at = clock()
        if start <= at:
            summary["skipped"].append(eo.event.event_id)
            log.warning("team_totals: [%s] la respuesta llego tras el comienzo; "
                        "cuotas descartadas (credito gastado: %d)", eo.event.event_id, delta)
            continue
        captured_at = at.isoformat(timespec="seconds")
        # Cuotas del proveedor sobre el evento con los abridores ya adjuntos.
        eo.lines = fetched[0].lines
        lam_h, lam_a = adapter._rates(eo.event)
        rows = team_total_rows(eo, lam_h, lam_a, max_score=max_score,
                               dispersion_k=disp_k, captured_at=captured_at)
        n = append_rows(root, league, rows)
        summary["events"] += 1
        summary["rows"] += n
    summary["credits_spent"] = spent
    log.info("team_totals: [%s] %d eventos de %d candidatos, %d filas, %d creditos "
             "(%d hoy / %d mes)%s%s",
             league, summary["events"], summary["candidates"], summary["rows"], spent,
             already_day + spent, already_month + spent,
             f"; mediana reciente {base:.1f}" if base is not None else "",
             f"; parada: {summary['stop']}" if summary["stop"] else "")
    return summary


def load_captures(root: Path, league: str) -> pd.DataFrame:
    files = sorted((root / "data" / "odds").glob(f"team_totals_{league}_*.csv"))
    if not files:
        return pd.DataFrame(columns=COLUMNS)
    return pd.concat([pd.read_csv(f) for f in files], ignore_index=True)


def grade_captures(captures: pd.DataFrame, results: list[dict], normalize=None) -> pd.DataFrame:
    """Liquida cada fila contra las carreras reales del equipo (sin cuota extra).

    Empareja por (fecha UTC del partido, casa, visitante) normalizados. Las filas
    sin resultado quedan con `result` NaN; no hay push porque solo se guardan
    lineas medias.
    """
    nk = normalize or (lambda s: str(s or "").strip().lower())
    runs: dict[tuple[str, str, str], list[tuple[float, float]]] = {}
    for r in results:
        try:
            runs.setdefault((str(r.get("date"))[:10], nk(r["home"]), nk(r["away"])), []).append(
                (float(r["home_score"]), float(r["away_score"])))
        except (KeyError, TypeError, ValueError):
            continue
    out = captures.copy()
    team_runs: list[float | None] = []
    for row in out.itertuples(index=False):
        start = _parse_utc(row.commence_time)
        if start is None:
            team_runs.append(None)
            continue
        key = (start.astimezone(MLB_TZ).strftime("%Y-%m-%d"), nk(row.home), nk(row.away))
        found = runs.get(key, [])
        # Un doubleheader deja dos resultados con la misma clave y el evento no
        # dice cual es: sin graduar antes que graduado con el otro partido.
        if len(found) != 1:
            team_runs.append(None)
            continue
        scores = found[0]
        team_runs.append(scores[0] if nk(row.team) == nk(row.home) else scores[1])
    out["team_runs"] = team_runs
    over = out["team_runs"] > out["point"]
    out["result"] = None
    has = out["team_runs"].notna()
    out.loc[has & (out["side"] == "over"), "result"] = over[has & (out["side"] == "over")].map(
        {True: "win", False: "loss"})
    out.loc[has & (out["side"] == "under"), "result"] = (~over[has & (out["side"] == "under")]).map(
        {True: "win", False: "loss"})
    return out


def consensus_novig(graded: pd.DataFrame) -> pd.DataFrame:
    """Probabilidad implicita sin vig por (evento, equipo, linea, lado): mediana
    entre casas del par Over/Under de cada casa, con el devig proporcional.

    Una fila por seleccion: si un evento se capturo mas de una vez (relanzar el
    script el mismo dia gasta cuota y anade otra captura), se conserva la
    PRIMERA, que es la que menos mira hacia el cierre. Contar cada captura
    como una seleccion repetiria el error del stream servido (2,19x)."""
    d = graded[graded["price_decimal"].map(is_usable_price)].copy()
    d["implied"] = 1.0 / d["price_decimal"]
    key = ["captured_at", "event_id", "team", "point", "bookmaker"]
    pair_sum = d.groupby(key)["implied"].transform("sum")
    pair_n = d.groupby(key)["implied"].transform("size")
    d = d[pair_n == 2].copy()
    d["novig"] = d["implied"] / pair_sum[pair_n == 2]
    agg = (d.groupby(["captured_at", "event_id", "team", "point", "side"])
            .agg(implied_probability_novig=("novig", "median"), books_count=("novig", "size"),
                 price_median=("price_decimal", "median"), model_probability=("model_probability", "first"),
                 result=("result", "first"), commence_time=("commence_time", "first"),
                 home=("home", "first"), away=("away", "first"))
            .reset_index())
    agg = agg.sort_values("captured_at", kind="stable").drop_duplicates(
        ["event_id", "team", "point", "side"], keep="first")
    return agg.reset_index(drop=True)
