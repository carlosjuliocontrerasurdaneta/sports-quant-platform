"""Daily pipeline: odds -> model -> de-vig -> edge -> fractional Kelly -> report.

Single bankroll, single risk engine, every league flows through here.
"""
from __future__ import annotations
import shutil
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
import pandas as pd
from sqp.config import Settings, ROOT, CONFIG_DIR, load_yaml
from sqp.domain.models import EventOdds, BetCandidate
from sqp.markets.edge import adjusted_edge
# Helpers de probabilidad extraídos a pipeline.probabilities (auditoría
# 2026-07-02, M2); se re-importan aquí para conservar la API histórica de
# daily (scripts/clv_analysis.py y tests importan varios de estos nombres).
from sqp.pipeline.probabilities import (_consensus_lines, _consensus_counts,
                                        _novig_probs, _spread_novig,
                                        _pick_main_lines, _decision_probability,
                                        build_model_map)
from sqp.providers.odds_api import OddsAPIClient, SPORT_KEYS
from sqp.providers.synthetic import SyntheticProvider
from sqp.risk.clv_gate import load_clv_gate, market_allowed
from sqp.risk.prediction_gate import (load_prediction_gate,
                                      market_allowed as prediction_allowed)
from sqp.storage.atomic import atomic_write_csv
from sqp.storage.lock import locked
from sqp.risk.kelly import kelly_fraction_stake, edge
from sqp.sports.registry import get_adapter
from sqp.storage.odds_store import OddsStore
from sqp.storage.results_store import ResultsStore
from sqp.storage.served_store import ServedStore
from sqp.storage.starters import StartersStore
from sqp.storage.starter_fip import StarterFIPStore
from sqp.logging_config import get_logger

log = get_logger("sqp.pipeline")

MIN_RESULTS_FOR_RATINGS = 50

DISCLAIMER = ("This output contains estimated probabilities only. It does not "
              "represent certainty and does not guarantee profit. Betting markets "
              "are risky and model error is expected.")


def _league_meta(league: str) -> dict:
    if league in SPORT_KEYS:
        meta = dict(SPORT_KEYS[league])
    elif league.startswith("tennis_") or league in ("atp", "wta"):
        # Tennis tournaments are per-tournament Odds API keys; the league id IS
        # the sport key. No scores in The Odds API -> settled via ESPN by player
        # name + date (see settlement.runner). Player Elo is tour-wide.
        meta = {"sport_key": league, "family": "tennis", "three_way": False,
                "has_scores": False}
    else:
        soccer_cfg = load_yaml(CONFIG_DIR / "leagues" / "soccer.yaml").get("leagues", {})
        if league not in soccer_cfg:
            raise KeyError(f"Unknown league '{league}'. Register it in SPORT_KEYS or configs/leagues/.")
        c = soccer_cfg[league]
        meta = {"sport_key": c["sport_key"], "family": "soccer", "three_way": True,
                "has_scores": True, "league_params": {"avg_total": c.get("avg_goals", 2.7)}}
    params = dict(meta.get("league_params") or {})
    ratings_path = CONFIG_DIR / "leagues" / "ratings.yaml"
    if ratings_path.exists():
        params.update((load_yaml(ratings_path).get("leagues") or {}).get(league) or {})
    if params:
        meta["league_params"] = params
    return meta


def _merge_results(history: list[dict], recent: list[dict],
                   normalize: Callable[[str | None], str] | None = None) -> list[dict]:
    """Chronological union; stored history wins over freshly fetched rows.
    Within each source, (day, home, away, game_id) keeps doubleheaders
    distinct. A recent row is dropped whenever history already covers that
    (day, home, away): game ids are not comparable across vendors.

    `normalize` canonicalizes team names for the comparison keys only (rows are
    returned unchanged), so the same game spelled differently by two vendors is
    recognized as one and not double-counted into the ratings."""
    nk = normalize or (lambda s: s or "")
    seen: dict[tuple, dict] = {}
    for r in history:
        day = str(r.get("date", ""))[:10]
        seen.setdefault((day, nk(r["home"]), nk(r["away"]), str(r.get("game_id") or "")), r)
    history_days = {k[:3] for k in seen}
    for r in recent:
        day = str(r.get("date", ""))[:10]
        # Recent rows are dated by commence_time (UTC date); history carries the
        # official local date, which can differ by +-1 day (e.g. west-coast night
        # games start past midnight UTC). Without this tolerance the same game
        # enters the ratings fit twice (audit 2026-07-24, I-3). The row's own key
        # keeps its UTC date: only the drop check is widened.
        if any((d, nk(r["home"]), nk(r["away"])) in history_days
               for d in _adjacent_days(day)):
            continue
        seen.setdefault((day, nk(r["home"]), nk(r["away"]), str(r.get("game_id") or "")), r)
    return [seen[k] for k in sorted(seen, key=lambda k: k[0])]


def _adjacent_days(day: str) -> tuple[str, ...]:
    """`day` plus its +-1 calendar neighbors (ISO); just `day` if unparsable."""
    try:
        y, m, d = (int(x) for x in day.split("-"))
        base = datetime(y, m, d, tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return (day,)
    return (day, (base - timedelta(days=1)).strftime("%Y-%m-%d"),
            (base + timedelta(days=1)).strftime("%Y-%m-%d"))


def _within_horizon(events: list[EventOdds], max_days: int) -> list[EventOdds]:
    """Keep only events commencing within `max_days`.
    Drops next-season opener lines posted months early (e.g. NFL in June).
    Unparsable start times are kept (conservative: never silently drop an event)."""
    if not max_days or max_days <= 0:
        return events
    cutoff = datetime.now(timezone.utc) + timedelta(days=max_days)
    out = []
    for eo in events:
        dt = _parse_iso_utc(str(eo.event.start_time))
        if dt is None or dt <= cutoff:
            out.append(eo)
    return out


def _already_started(start_time: str) -> bool:
    """True when `start_time` is in the past; The Odds API also returns in-play
    events whose quoted prices are live odds, useless for a pregame model.
    Unparsable timestamps are treated as not started (conservative)."""
    if not start_time:
        return False
    dt = _parse_iso_utc(str(start_time))
    return dt is not None and dt <= datetime.now(timezone.utc)


def _prior_day(day: str) -> str | None:
    """ISO date one calendar day before `day` ('YYYY-MM-DD'), or None if unparsable."""
    try:
        y, m, d = (int(x) for x in day.split("-"))
        return (datetime(y, m, d, tzinfo=timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def _parse_iso_utc(s: str) -> datetime | None:
    """Parse an ISO-8601 UTC timestamp ('...Z' or offset) to an aware datetime."""
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# A probable matched to an event must start within this many hours of it. Guards
# against assigning the wrong game of a series (games are ~24h apart) when only a
# neighbouring date's announcements were available.
_PROBABLE_MATCH_TOLERANCE_S = 12 * 3600


def _attach_probable_pitchers(events: list[EventOdds], league: str,
                              normalize: Callable[[str | None], str] | None = None,
                              provider=None) -> None:
    """Attach announced probable starters to live MLB events, matched by
    (home, away) and then by closest start time.

    `normalize` canonicalizes team names before the (home, away) match: events
    come from The Odds API and probables from the MLB Stats API, which spell
    teams differently. Without it a team whose two vendors disagree on spelling
    silently fails to match, leaves the event flagged 'starter unknown', and
    produces no MLB candidates. Defaults to identity (no normalization).

    A night game on the US west coast commences after 00:00Z, so an event's UTC
    date can run one day ahead of the official MLB game date; probables are
    therefore fetched for each event's UTC date AND the prior calendar date.
    Among the candidates for a team pair, each event takes the one whose start
    time is closest to its own (within a tolerance). This keeps the two games of
    a consecutive-day series from collapsing onto a single pitcher matchup --
    previously the map was keyed on (home, away) only, so the later game
    overwrote the earlier one and both estimates ran with identical starters.

    Best-effort: unmatched events stay flagged 'starter unknown' and produce no
    bet candidates. `provider` is injectable for testing."""
    if provider is None:
        from sqp.providers.mlb_statsapi import MLBStatsProvider
        provider = MLBStatsProvider()
    nk = normalize or (lambda s: s or "")
    fetch_days: set[str] = set()
    for eo in events:
        day = str(eo.event.start_time)[:10]
        fetch_days.add(day)
        if (prior := _prior_day(day)) is not None:
            fetch_days.add(prior)
    by_pair: dict[tuple, list[dict]] = defaultdict(list)
    try:
        for day in sorted(fetch_days):
            for g in provider.fetch_probable_pitchers(day):
                by_pair[(nk(g["home"]), nk(g["away"]))].append(g)
    except Exception as exc:
        log.warning("[%s] Could not fetch probable pitchers: %s", league, exc)
        return
    matched = 0
    confirmed_rows: list[dict] = []
    for eo in events:
        cands = by_pair.get((nk(eo.event.home), nk(eo.event.away)), [])
        ev_t = _parse_iso_utc(str(eo.event.start_time))
        g = _closest_probable(cands, ev_t)
        if g:
            eo.event.home_pitcher = g.get("home_pitcher")
            eo.event.away_pitcher = g.get("away_pitcher")
            matched += 1
            confirmed_rows.append({
                "event_id": eo.event.event_id,
                "game_date": str(eo.event.start_time)[:10],
                "home": eo.event.home,
                "away": eo.event.away,
                "home_pitcher": eo.event.home_pitcher,
                "away_pitcher": eo.event.away_pitcher,
            })
    log.info("[%s] probable starters attached to %d/%d events.", league, matched, len(events))
    if confirmed_rows:
        from sqp.storage.starters import log_pitcher_confirmation
        log_pitcher_confirmation(ROOT, league, confirmed_rows)


def _closest_probable(cands: list[dict], ev_t: datetime | None) -> dict | None:
    """Pick the candidate whose start time is closest to the event's, within
    tolerance. With no usable times, match only when the pair is unambiguous."""
    if not cands:
        return None
    timed = [(abs((gt - ev_t).total_seconds()), g) for g in cands
             if ev_t is not None and (gt := _parse_iso_utc(str(g.get("commence", "")))) is not None]
    if timed:
        dist, g = min(timed, key=lambda x: x[0])
        return g if dist <= _PROBABLE_MATCH_TOLERANCE_S else None
    return cands[0] if len(cands) == 1 else None


def _apply_daily_exposure_cap(candidates: list[BetCandidate], bankroll: float,
                              cap_pct: float) -> float:
    """Scale staked candidates down so the day's total exposure does not exceed
    `bankroll * cap_pct`. Per-bet Kelly caps bound a single stake, but a day with
    many signals can still commit more than the bankroll-level limit; this is the
    only place that limit is enforced.

    Scaling is proportional: every positive stake (and its kelly pct) is
    multiplied by the same factor and flagged 'daily_exposure_scaled' for the
    audit trail. Zero-stake rows (paused / implausible-edge) are untouched.
    Returns the applied factor (1.0 when no cap was needed)."""
    if not candidates or cap_pct <= 0 or bankroll <= 0:
        return 1.0
    total = sum(c.stake for c in candidates if c.stake > 0)
    cap = bankroll * cap_pct
    if total <= cap or total <= 0:
        return 1.0
    factor = cap / total
    for c in candidates:
        if c.stake <= 0:
            continue
        c.stake = round(c.stake * factor, 2)
        c.kelly_stake_pct = round(c.kelly_stake_pct * factor, 4)
        c.flags = f"{c.flags};daily_exposure_scaled" if c.flags else "daily_exposure_scaled"
    return factor


def apply_global_exposure_cap(pred_dir: Path, bankroll: float, cap_pct: float,
                              generated_day: str | None = None) -> float:
    """Cap the WHOLE day's staked exposure across every league at
    ``bankroll * cap_pct``, rewriting the per-league ``candidates_*.csv`` in place.

    ``_apply_daily_exposure_cap`` bounds a SINGLE league's exposure inside
    run_league; with many leagues the day's total could still reach N x that
    fraction. This is the only place the cross-league limit is enforced, so it
    runs once in the orchestrator after all leagues have been written (and after
    out-of-season files are pruned). Scaling is proportional: every positive
    stake (and its kelly pct) is multiplied by the same factor and flagged
    'global_exposure_scaled'. Zero-stake rows (paused / implausible edge) are
    untouched and excluded from the total. Returns the applied factor (1.0 when
    no cap was needed)."""
    if cap_pct <= 0 or bankroll <= 0:
        return 1.0
    # Read-modify-write over every candidates file: hold the shared candidates
    # lock so an hourly revalidation pass cannot interleave (audit 2026-07-24, I-5).
    with locked(pred_dir / "candidates"):
        frames: dict[Path, tuple[pd.DataFrame, pd.Series]] = {}
        total = 0.0
        for f in sorted(pred_dir.glob("candidates_*.csv")):
            try:
                df = pd.read_csv(f)
            except (pd.errors.EmptyDataError, pd.errors.ParserError):
                continue
            if df.empty or "stake" not in df.columns:
                continue
            eligible = df["stake"] > 0
            if generated_day and "generated_at" in df.columns:
                days = df["generated_at"].astype(str).str[:10]
                valid = days.str.fullmatch(r"\d{4}-\d{2}-\d{2}")
                # Old schemas without a usable timestamp retain the legacy behavior;
                # current schemas are scoped strictly to this run day so a
                # budget-skipped league from yesterday is never re-staked/re-scaled.
                if valid.any():
                    eligible &= days == generated_day
            if not eligible.any():
                continue
            frames[f] = (df, eligible)
            total += float(df.loc[eligible, "stake"].sum())
        cap = bankroll * cap_pct
        if total <= cap or total <= 0:
            return 1.0
        factor = cap / total
        for f, (df, mask) in frames.items():
            if not mask.any():
                continue
            df.loc[mask, "stake"] = (df.loc[mask, "stake"] * factor).round(2)
            if "kelly_stake_pct" in df.columns:
                df.loc[mask, "kelly_stake_pct"] = (df.loc[mask, "kelly_stake_pct"] * factor).round(4)
            # An all-empty flags column round-trips through CSV as float64 NaN; coerce
            # to string first or the masked string assignment raises on modern pandas.
            df["flags"] = (df["flags"].fillna("").astype(str)
                           if "flags" in df.columns else "")
            prior = df.loc[mask, "flags"]
            df.loc[mask, "flags"] = [f"{x};global_exposure_scaled" if x else "global_exposure_scaled"
                                     for x in prior]
            atomic_write_csv(df, f)
    return factor


def _archive_existing(path: Path) -> None:
    """Copy an existing predictions/candidates CSV to an `archive/` subfolder,
    keyed by the date in its `generated_at` column, before it is overwritten.

    This protects un-settled picks from being destroyed when the daily run is
    executed before settlement (the documented SETTLE->RUN order). Idempotent:
    re-archiving the same dated file just rewrites an identical copy. Best-effort
    -- archiving must never abort a daily run, so failures are logged, not raised.
    """
    if not path.exists() or path.stat().st_size <= 1:
        return
    try:
        head = pd.read_csv(path, nrows=1)
    except pd.errors.EmptyDataError:
        return  # empty / header-less file (e.g. out-of-season league): no picks to preserve
    except (OSError, pd.errors.ParserError) as exc:
        log.warning("could not archive %s before overwrite: %s", path.name, exc)
        return
    if "generated_at" in head.columns and not head.empty:
        day = str(head["generated_at"].iloc[0])[:10]
    else:
        day = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
    archive_dir = path.parent / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(path, archive_dir / f"{path.stem}_{day}{path.suffix}")
    except OSError as exc:
        log.warning("could not archive %s before overwrite: %s", path.name, exc)


def _finalize(league: str, rows: list[dict], candidates: list[BetCandidate],
              mode: str = "live") -> pd.DataFrame:
    df = pd.DataFrame(rows)
    # Demo outputs go to a separate subdir so a synthetic run can never clobber
    # real live predictions/candidates (they share the same per-league filename).
    base = ROOT / "data" / "predictions"
    outdir = base / "demo" if mode == "demo" else base
    outdir.mkdir(parents=True, exist_ok=True)
    pred_path = outdir / f"predictions_{league}.csv"
    cand_path = outdir / f"candidates_{league}.csv"
    # Archive yesterday's files before overwrite so an out-of-order run (RUN before
    # SETTLE) can never destroy un-settled picks; they stay recoverable in archive/.
    _archive_existing(pred_path)
    # Atomico: predictions_*.csv es la fuente de start_time para cleanup,
    # revalidacion y roi_engine, y un truncado parcial NO lanza error (read_csv
    # devuelve las filas que sobrevivieron), asi que picks vigentes desaparecen
    # del calculo de riesgo sin aviso (auditoria 2026-07-29, D-04).
    atomic_write_csv(df, pred_path)
    # Shared inter-process lock with the hourly revalidation pass (CAPTURE_CLOSE):
    # serializes candidates_*.csv writers so neither a fresh revocation nor the
    # just-generated candidates get overwritten (audit 2026-07-24, I-5).
    with locked(outdir / "candidates"):
        _archive_existing(cand_path)
        if candidates:
            atomic_write_csv(pd.DataFrame([c.__dict__ for c in candidates]), cand_path)
        elif cand_path.exists():
            cand_path.unlink()  # a run with no candidates must not leave stale picks behind
    # A zero-stake row is non-actionable (paused / implausible edge); a scaled
    # row still carries a positive stake and stays counted as actionable.
    flagged = sum(1 for c in candidates if c.stake <= 0)
    log.info("[%s] %d events estimated, %d actionable candidates, %d flagged as "
             "non-actionable (%s). %s",
             league, len(df), len(candidates) - flagged, flagged, mode, DISCLAIMER)
    return df


def _gate_verdicts(prediction_gate: dict[str, dict] | None,
                   clv_gate: dict[str, dict] | None,
                   league: str, market: str) -> tuple[bool, bool]:
    """(prediction_blocked, clv_blocked) para un (liga, mercado).

    ``None`` significa gate APAGADO -> no bloquea. Un registro presente pero sin
    la entrada, o con ``allowed: false``, SI bloquea (default-deny).

    Extraida de la expresion inline que vivia en ``run_league`` (auditoria
    2026-08-17): esa rama solo se evalua con ``mode != "demo"``, y en demo los
    gates son ``None``, asi que el ``and`` corto-circuitaba y la llamada nunca se
    ejecutaba. Un NameError ahi paso los 1073 tests de la suite y solo lo detecto
    ruff. Como funcion pura se puede ejercitar directamente, que es lo que la
    ruta live no permitia.

    No decide precedencia: eso es de ``_zero_stake_flag``."""
    return (prediction_gate is not None
            and not prediction_allowed(prediction_gate, league, market),
            clv_gate is not None
            and not market_allowed(clv_gate, league, market))


def _zero_stake_flag(paused: bool, suspect: bool, shadow: bool,
                     clv_blocked: bool = False,
                     incomplete_market: bool = False,
                     prediction_blocked: bool = False) -> str | None:
    """Reason a selected candidate must be recorded with stake 0, or None to
    stake it. Pausing wins over the plausibility cap; shadow mode (global,
    stake-0 evidence gathering) zeroes whatever remains; then the per-market
    gates block any market not yet proven.

    Two gates, both allow-lists and both default-deny:

    - ``prediction_gate`` (sqp.risk.prediction_gate) is the BINDING exit rule
      since 2026-08-16: the model must beat the market out of sample and its
      flat-stake EV must be positive.
    - ``clv_gate`` (sqp.risk.clv_gate) was the previous rule. It keeps being
      computed as evidence but no longer decides; it only shows up here when
      explicitly enabled.

    Prediction outranks CLV so the reported reason is the rule actually in
    force. Shadow outranks both, so reports keep the shadow_mode flag while
    shadow is on."""
    if paused:
        return "market_paused"
    if incomplete_market:
        return "incomplete_market"
    if suspect:
        return "edge_exceeds_max_plausible"
    if shadow:
        return "shadow_mode"
    if prediction_blocked:
        return "prediction_gate"
    if clv_blocked:
        return "clv_gate"
    return None


def _accuracy_selected(market: str, p_decision: float, threshold: float,
                       incomplete_market: bool,
                       price_decimal: float | None = None) -> bool:
    """Seleccion del modo precision (pick_mode: accuracy, decision 2026-07-27:
    el objetivo es maximizar el porcentaje de aciertos). SOLO moneyline (h2h)
    y solo si la probabilidad de decision calibrada (blend modelo + no-vig)
    alcanza el umbral, inclusive. Un mercado incompleto no tiene ancla no-vig
    valida, asi que nunca produce pick de precision.

    Exige tambien una cuota pagable (``price_decimal > 1.0``). El modo precision
    dimensiona con stake plano y NO pasa por ``kelly_fraction_stake``, que era el
    unico punto del pipeline que rechazaba cuotas degeneradas; sin este guard una
    cuota corrupta de 1.0 (presente en el historico capturado) producia pick
    (auditoria 2026-07-29, B-05)."""
    if price_decimal is not None and price_decimal <= 1.0:
        return False
    return market == "h2h" and not incomplete_market and p_decision >= threshold


def _warn_if_uncalibrated_accuracy(league: str, settings: Settings) -> bool:
    """Avisa cuando el modo precision corre SIN calibrador h2h promovido.

    Devuelve True si falta el calibrador (es decir, si el umbral se esta
    aplicando a una probabilidad no calibrada). Solo observa y registra: NO
    suprime picks, porque dejar de emitirlos es un cambio de politica de
    produccion que requiere decision humana (auditoria 2026-07-29, Q-01)."""
    from sqp.calibration.calibrator import _load_method_registry, calibration_key
    if not settings.calibration_enabled:
        log.warning("[%s] pick_mode=accuracy con calibration_enabled=false: el umbral "
                    "%.2f se aplica a una probabilidad NO calibrada (blend crudo "
                    "modelo + no-vig).", league, settings.accuracy_threshold)
        return True
    key = calibration_key(league, "h2h")
    if _load_method_registry().get(key) is None:
        log.warning("[%s] pick_mode=accuracy sin calibrador promovido para '%s': "
                    "calibrate_probability es un no-op y el umbral %.2f se aplica a "
                    "una probabilidad NO calibrada. El hit rate por banda debe "
                    "juzgarse contra la frecuencia observada, no contra el umbral.",
                    league, key, settings.accuracy_threshold)
        return True
    return False


def _fetch_recent_scores(client, sport_key: str, league: str) -> list[dict]:
    """Recent completed games from The Odds API /scores (has_scores leagues).
    Best-effort: returns [] on failure (logged). Rows whose score names do not
    match the event teams are skipped individually, not the whole batch."""
    recent: list[dict] = []
    try:
        for s in client.fetch_scores(sport_key, days_from=3):
            if not (s.get("completed") and s.get("scores")):
                continue
            by_name = {x["name"]: x["score"] for x in s["scores"]}
            home_raw, away_raw = by_name.get(s["home_team"]), by_name.get(s["away_team"])
            if home_raw is None or away_raw is None:
                log.warning("[%s] score names do not match event teams (id=%s); skipped.",
                            league, s.get("id", ""))
                continue
            recent.append({"date": s.get("commence_time"), "home": s["home_team"],
                           "away": s["away_team"], "game_id": str(s.get("id", "")),
                           "home_score": int(home_raw), "away_score": int(away_raw)})
    except Exception as exc:
        log.warning("[%s] Could not fetch recent scores: %s", league, exc)
    return recent


def _tennis_results(league: str, provider=None) -> list[dict]:
    """Tour-wide player results from ESPN (atp/wta) to fit player Elo. Best-effort:
    on any failure return empty so the run degrades to low-sample warnings rather
    than crashing. `provider` is injectable for testing."""
    if provider is None:
        from sqp.providers.espn_tennis import ESPNTennisResultsProvider
        provider = ESPNTennisResultsProvider()
    try:
        return provider.fetch_results(league)
    except Exception as exc:
        log.warning("[%s] could not fetch tennis results: %s", league, exc)
        return []


def run_league(league: str, settings: Settings, mode: str | None = None) -> pd.DataFrame:
    mode = mode or settings.mode
    meta = _league_meta(league)
    family, three_way = meta["family"], meta.get("three_way", False)
    adapter = get_adapter(league, family, meta.get("league_params"))

    # CLV gate (allow-list por liga|mercado): solo mercados con CLV mediano
    # positivo demostrado sobre muestra liquidada emparejada a cierre pueden
    # llevar stake real (registro escrito por la auditoria CLV diaria). Solo
    # live: el demo sintetico no debe filtrarse por historial real. None =
    # gate apagado; {} = registro ausente/ilegible -> default-deny.
    # Modo precision: el umbral se aplica a `p_decision`, que solo es una
    # probabilidad CALIBRADA si existe calibrador promovido para (liga, h2h).
    # Sin el, `calibrate_probability(..., "auto")` es un no-op y el umbral 0.70
    # recae sobre el blend crudo modelo+no-vig, que el propio nombre de columna
    # (`calibrated_probability`) contradice (auditoria 2026-07-29, Q-01).
    if settings.pick_mode == "accuracy" and mode != "demo":
        _warn_if_uncalibrated_accuracy(league, settings)

    clv_gate: dict[str, dict] | None = None
    if settings.clv_gate_enabled and mode != "demo":
        clv_gate = load_clv_gate(ROOT / "data" / "bets")
        if not clv_gate:
            log.warning("[%s] CLV gate activo sin registro utilizable "
                        "(data/bets/clv_gate.json): default-deny, ningun "
                        "mercado lleva stake real hasta que la auditoria CLV "
                        "diaria lo reescriba.", league)

    # Prediction gate: la regla de salida RECTORA desde 2026-08-16 (sustituye al
    # de CLV). Mismo contrato: solo live, None = apagado, {} = registro
    # ausente/ilegible -> default-deny.
    prediction_gate: dict[str, dict] | None = None
    if settings.prediction_gate_enabled and mode != "demo":
        prediction_gate = load_prediction_gate(ROOT / "data" / "bets")
        if not prediction_gate:
            log.warning("[%s] Prediction gate activo sin registro utilizable "
                        "(data/bets/prediction_gate.json): default-deny, ningun "
                        "mercado lleva stake real hasta que "
                        "scripts/update_prediction_gate.py lo reescriba.",
                        league)

    if mode == "demo":
        provider = SyntheticProvider(family)
        results = provider.fetch_results(league)
        adapter.fit_results(results)
        events = provider.fetch_odds(league, three_way=three_way,
                                     avg_total=adapter.params.get("avg_total"))
        log.info("[%s] DEMO mode: synthetic data, labeled demo_synthetic.", league)
    else:
        client = OddsAPIClient(settings.odds_api_key, settings.regions, settings.odds_format)
        try:
            active = client.is_sport_active(meta["sport_key"])
        except Exception as exc:
            active = True  # status check is best-effort; fall through to the normal fetch
            log.warning("[%s] Could not check sport status on The Odds API: %s", league, exc)
        if active is False:
            log.warning("[%s] Sport '%s' is INACTIVE on The Odds API (out of season). "
                        "No events or recent scores are available; skipping fetch.",
                        league, meta["sport_key"])
            return _finalize(league, [], [], mode)
        if active is None:
            log.error("[%s] Sport key '%s' is not listed by The Odds API /sports. "
                      "Check configs/leagues/ for a typo; skipping fetch.",
                      league, meta["sport_key"])
            return _finalize(league, [], [], mode)
        if family == "tennis":
            # Player Elo is tour-wide; fit from ESPN (atp/wta), not a per-league store.
            results = _tennis_results(league)
            history, recent = results, []
        else:
            history = ResultsStore(ROOT).load(league)
            recent = (_fetch_recent_scores(client, meta["sport_key"], league)
                      if meta.get("has_scores", False) else [])
            results = _merge_results(history, recent, adapter.normalize)
            if family == "baseball" and results:
                attached = StartersStore(ROOT).attach(league, results)
                fip_attached = StarterFIPStore(ROOT).attach(league, results)
                log.info("[%s] starters attached to %d/%d results (names), %d with "
                         "per-start FIP (v2). Refresh: scripts/backfill_starters.py, "
                         "scripts/backfill_starter_fip.py.",
                         league, attached, len(results), fip_attached)
        if results:
            adapter.fit_results(results)
        if len(results) < MIN_RESULTS_FOR_RATINGS:
            log.warning("[%s] Ratings built from only %d results (%d stored + %d recent). "
                        "Run scripts/backfill_results.py before trusting estimates.",
                        league, len(results), len(history), len(recent))
        else:
            log.info("[%s] Ratings built from %d results (%d stored + %d recent).",
                     league, len(results), len(history), len(recent))
        markets = "h2h" if family == "tennis" else "h2h,spreads,totals"
        events = client.fetch_odds(league, meta["sport_key"], markets)
        n_fetched = len(events)
        events = _within_horizon(events, settings.event_horizon_days)
        if len(events) < n_fetched:
            log.info("[%s] %d of %d events dropped as beyond the %d-day horizon "
                     "(e.g. next-season opener lines).",
                     league, n_fetched - len(events), n_fetched, settings.event_horizon_days)
        if events and not client.last_response_cached:
            n_lines = OddsStore(ROOT).append_snapshot(league, events)
            log.info("[%s] odds snapshot persisted: %d lines from %d events "
                     "(forward out-of-sample dataset).", league, n_lines, len(events))
        elif events:
            log.info("[%s] odds served from cache; snapshot already persisted on "
                     "the originating fetch, not re-appending.", league)
        if family == "baseball" and events:
            _attach_probable_pitchers(events, league, adapter.normalize)

    rows: list[dict] = []
    candidates: list[BetCandidate] = []
    served: list[dict] = []
    # One timestamp for the whole run: the served-stream dedup key is
    # (event, market, selection, line, run DAY), so re-running the same day is
    # idempotent while consecutive-day serves of the same event both persist.
    served_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    # Load all captured odds for this league once; used per-selection below to
    # compute pregame line movement (adverse movement deflates adjusted_edge).
    # Empty when no snapshots exist yet (demo mode, new league).
    from sqp.markets.line_movement import event_line_movement, load_league_odds
    _league_odds = load_league_odds(league, ROOT / "data" / "odds")
    for eo in events:
        spread, total = _pick_main_lines(eo)
        est = adapter.estimate(eo.event, spread, total)
        warn = adapter.reliability_warning(eo.event)
        if _already_started(eo.event.start_time):
            started_msg = "Event already started: prices are in-play, pregame estimate invalid, no candidates."
            warn = f"{warn} {started_msg}" if warn else started_msg
        cons = _consensus_lines(eo)
        cons_n = _consensus_counts(eo)
        h2h_fair = _novig_probs(cons, "h2h", three_way=three_way)
        row = {"league": league, "event_id": eo.event.event_id, "home": eo.event.home,
               "away": eo.event.away, "start_time": eo.event.start_time,
               # abridores del MOMENTO DEL PICK (None fuera de beisbol): linea
               # base del guard de cambio de abridor en la revalidacion horaria
               "home_pitcher": eo.event.home_pitcher,
               "away_pitcher": eo.event.away_pitcher,
               "data_label": eo.event.data_label, "warning": warn,
               "spread_line": spread, "total_line": total, **est.as_dict(),
               "market_novig_home": h2h_fair.get(eo.event.home),
               "market_novig_away": h2h_fair.get(eo.event.away),
               "market_novig_draw": h2h_fair.get("Draw")}
        rows.append(row)

        # Edge scan on consensus prices. El mapa lo construye el helper
        # compartido con el backtest, para que ambos no puedan divergir
        # (auditoria 2026-08-05, F-10).
        model_map = build_model_map(est, eo.event, spread, total)

        for key, p_model in model_map.items():
            price = cons.get(key)
            if price is None or p_model is None or warn:
                continue
            if key[0] == "spreads":
                fair = _spread_novig(cons, eo.event.home, eo.event.away, spread).get(key[1])
            else:
                fair = _novig_probs(cons, key[0], key[2],
                                    three_way=three_way).get(key[1])
            # A no-vig probability requires the complete complementary market
            # (both sides, or all three 1X2 outcomes). A lone/malformed quote can
            # still be captured in the served stream, but it must never carry
            # stake: there is no valid market anchor or vig removal for it.
            incomplete_market = fair is None
            p_used, p_decision = _decision_probability(
                p_model, fair, settings.risk.market_shrink, league, key[0], settings)
            e = edge(p_decision, price)
            # Deflate the EV by the model-vs-market disagreement (and thin markets)
            # and stake on the resulting effective probability, so an overconfident
            # edge produces a smaller stake (and often falls below min_edge). No-op
            # when the penalty coefficients are 0. estimated_edge stays the RAW e.
            _lm = event_line_movement(
                _league_odds, eo.event.event_id, key[0], key[1], key[2])
            adj = adjusted_edge(p_decision, price, fair, cons_n.get(key),
                                uncertainty_penalty=settings.risk.uncertainty_penalty,
                                anomaly_edge_gap=settings.risk.anomaly_edge_gap,
                                anomaly_extra_penalty=settings.risk.anomaly_extra_penalty,
                                low_book_penalty=settings.risk.low_book_penalty,
                                min_books_for_consensus=settings.risk.min_books_for_consensus,
                                line_movement_pp=_lm.movement_pp if _lm else None,
                                line_movement_penalty=settings.risk.line_movement_penalty,
                                line_movement_flat_pp=settings.risk.line_movement_flat_pp,
                                line_velocity_pp_per_h=_lm.velocity_pp_per_h if _lm else None,
                                line_velocity_penalty=settings.risk.line_velocity_penalty,
                                line_velocity_flat_pp_per_h=settings.risk.line_velocity_flat_pp_per_h)
            stake, pct = kelly_fraction_stake(adj.effective_probability, price,
                                              settings.bankroll,
                                              settings.risk.kelly_fraction,
                                              settings.risk.max_stake_pct,
                                              settings.risk.min_edge)
            # Served-probability stream: record EVERY priced market side, before
            # any stake/edge filtering. Placed picks alone are a small, adversely
            # selected calibration sample; the full serve distribution lets the
            # calibrator train unbiased (graded later by settlement).
            served.append({
                "league": league, "event_id": eo.event.event_id,
                "home": eo.event.home, "away": eo.event.away,
                "start_time": eo.event.start_time,
                "game_date": str(eo.event.start_time)[:10],
                "market": key[0], "selection": key[1], "line": key[2],
                "price_decimal": price, "bookmaker": "consensus_median",
                "model_probability": round(p_model, 4),
                "estimated_probability": round(p_used, 4),
                "calibrated_probability": round(p_decision, 4),
                "implied_probability_novig": round(fair, 4) if fair is not None else float("nan"),
                "estimated_edge": round(e, 4),
                "books_count": int(cons_n.get(key) or 0),
                "stake": 0.0, "data_label": eo.event.data_label,
                "flags": "served_stream", "generated_at": served_at})
            # An edge above the plausibility cap is almost certainly model
            # miscalibration, not market value: record it for the audit trail but
            # do not stake it.
            suspect = e > settings.risk.max_plausible_edge
            paused = key[0] in settings.paused_markets.get(league, ())
            accuracy = settings.pick_mode == "accuracy"
            if accuracy:
                # Modo precision: la seleccion es por probabilidad de decision,
                # no por edge (el selector por edge favorece underdogs y
                # discrepancias con el mercado, trabajando CONTRA el % de
                # aciertos). Stake plano en lugar de Kelly: sin objetivo de EV
                # no hay fraccion optima que dimensionar. La cadena de stake 0
                # (paused / suspect / shadow / clv gate) aplica igual abajo.
                if not _accuracy_selected(key[0], p_decision,
                                          settings.accuracy_threshold,
                                          incomplete_market, price):
                    continue
                stake = round(settings.bankroll * settings.risk.max_stake_pct, 2)
                pct = settings.risk.max_stake_pct
                # Banca <= 0 produce stake negativo, y settle.py grada una perdida
                # como pnl = -stake, es decir POSITIVO. La rama por edge queda
                # cubierta por kelly_fraction_stake (devuelve 0); el stake plano no
                # pasa por ahi (auditoria 2026-07-29, B-06).
                if stake <= 0:
                    continue
            # Only record a candidate that would otherwise be staked (or is an
            # implausible-edge outlier): below-min-edge lines are ignored whether
            # or not the market is paused, so a paused market does not flood the
            # picks file with non-actionable rows.
            elif stake <= 0 and not suspect:
                continue
            # A paused market is suspended from staking but kept in the audit trail
            # (stake 0, flagged). Pausing takes precedence over the plausibility cap;
            # shadow mode zeroes whatever remains; then the per-market gates
            # block anything not yet proven (allow-lists, default-deny). The
            # prediction gate is the binding rule since 2026-08-16; the CLV one
            # only applies while explicitly enabled.
            pred_blocked, clv_blocked = _gate_verdicts(prediction_gate, clv_gate,
                                                       league, key[0])
            flag = _zero_stake_flag(
                paused, suspect, settings.shadow_mode,
                clv_blocked=clv_blocked,
                incomplete_market=incomplete_market,
                prediction_blocked=pred_blocked) or ""
            if flag:
                stake, pct = 0.0, 0.0
            if accuracy:
                # Marca de origen para el KPI (hit rate por liga y banda) y para
                # que la revocacion por edge del segundo pase salte estos picks.
                flag = f"{flag};accuracy_mode" if flag else "accuracy_mode"
            candidates.append(BetCandidate(
                event_id=eo.event.event_id, league=league, market=key[0],
                selection=key[1], line=key[2], price_decimal=price,
                bookmaker="consensus_median",
                model_probability=round(p_model, 4),
                estimated_probability=round(p_used, 4),
                calibrated_probability=round(p_decision, 4),
                implied_probability_novig=round(fair, 4) if fair is not None else float("nan"),
                estimated_edge=round(e, 4),
                adjusted_edge=round(adj.adjusted_edge, 4),
                edge_penalty=round(adj.penalty, 4),
                books_count=int(cons_n.get(key) or 0),
                kelly_stake_pct=round(pct, 4), stake=stake,
                data_label=eo.event.data_label,
                flags=flag))

    if served:
        n_served = ServedStore(ROOT, demo=(mode == "demo")).append_served(league, served)
        log.info("[%s] served-probability stream: %d rows persisted for "
                 "calibration training (%d already captured today).",
                 league, n_served, len(served) - n_served)

    factor = _apply_daily_exposure_cap(candidates, settings.bankroll,
                                       settings.risk.max_daily_exposure_pct)
    if factor < 1.0:
        log.warning("[%s] daily exposure exceeded %.0f%% of bankroll; staked "
                    "candidates scaled by %.3f to respect the cap.",
                    league, settings.risk.max_daily_exposure_pct * 100, factor)

    return _finalize(league, rows, candidates, mode)
