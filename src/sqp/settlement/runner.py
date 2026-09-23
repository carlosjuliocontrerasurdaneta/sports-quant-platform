"""Settlement orchestration: fetch final scores and grade a league's candidates.

Shared by scripts/settle_bets.py (one league) and scripts/settle_all.py (every
league with pending candidates). Append-only and idempotent: a candidate already
settled in a prior run is never graded twice.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from sqp.config import ROOT, Settings
from sqp.logging_config import get_logger
from sqp.pipeline.daily import _league_meta
from sqp.storage.atomic import atomic_write_csv as _atomic_write_csv
from sqp.storage.lock import locked
from sqp.providers.odds_api import OddsAPIClient
from sqp.settlement.settle import (STALE_VOID_DAYS, _parse_start, realized_roi_parts,
                                   settle_candidates, void_stale_candidates)
from sqp.sports.team_names import normalize_key
from sqp.storage.served_store import ServedStore

log = get_logger("sqp.settle")

DEDUP_KEY = ["event_id", "market", "selection", "line", "generated_at"]

# Identidad de un PICK (sin generacion): la que ve el operador en la lista.
_PICK_IDENTITY = ["event_id", "market", "selection", "line"]
SUPERSEDED_FLAG = "superseded"
# Dias de archivo que se revisan buscando picks que dejaron la lista antes del
# partido. Sobra con el horizonte de eventos (7 dias) mas margen.
SUPERSEDED_LOOKBACK_DAYS = 14
# `_<dia>.csv` o, si ese hueco ya lo ocupaba otra generacion del mismo dia,
# `_<dia>_<HHMMSS>.csv` (AUD-012, ronda audit-2026-09-23; ver
# `daily._archive_existing`). El grupo 1 es siempre el dia.
_ARCHIVE_DAY = re.compile(r"_(\d{4}-\d{2}-\d{2})(?:_\d{6})?\.csv$")


def _pick_identity(df: pd.DataFrame) -> pd.Series:
    line = pd.to_numeric(df["line"], errors="coerce").map(str)
    return (df["event_id"].astype(str) + "|" + df["market"].astype(str) + "|"
            + df["selection"].astype(str) + "|" + line)


def superseded_candidates(league: str, current: pd.DataFrame | None, *,
                          pred_dir: Path | None = None,
                          now: datetime | None = None,
                          lookback_days: int = SUPERSEDED_LOOKBACK_DAYS) -> pd.DataFrame:
    """Picks REALES publicados en los ultimos ``lookback_days`` (archivo
    ``archive/candidates_<liga>_<dia>.csv``) que YA NO estan en el fichero
    vigente: una fila por identidad (evento, mercado, seleccion, linea), la de
    su ULTIMA generacion, con flag ``superseded``.

    El ledger solo graduaba la ultima vista de ``candidates_<liga>.csv``. Un
    pick listado el dia D para un partido de D+k que no sobrevive al refresco
    de D+1 (edge por debajo de ``min_edge``, linea distinta) desaparecia sin
    `revoke` ni `void`: medido entre el 2026-08-16 y el 2026-09-08, 132 de 730
    unidades (evento, mercado) listadas nunca recibieron veredicto pese a que
    el stream servido las graduo (auditoria integral 2026-09-13,
    AUD-MED-003). Con stake real, un pick apostado el dia D no se liquidaria
    nunca y la banca dinamica quedaria desalineada del dinero.

    Una fila por IDENTIDAD, no por generacion: el operador apuesta un pick una
    vez, aunque lo vea listado siete dias. Se conserva la generacion mas
    reciente porque es el ultimo precio/stake que se le mostro. Los picks que
    siguen en el fichero vigente los gradua la ruta normal; los que ya estan
    en ``settled_`` los descarta ``_persist_settled`` por ``DEDUP_KEY``.

    Best-effort: un archivo ilegible se salta; sin archivo, frame vacio."""
    pred_dir = Path(pred_dir) if pred_dir is not None else ROOT / "data" / "predictions"
    archive = pred_dir / "archive"
    if not archive.is_dir():
        return pd.DataFrame()
    now = now or datetime.now(timezone.utc)
    suelo = (now - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    frames: list[pd.DataFrame] = []
    for f in sorted(archive.glob(f"candidates_{league}_*.csv")):
        m = _ARCHIVE_DAY.search(f.name)
        if m is None or m.group(1) < suelo:
            continue
        try:
            df = pd.read_csv(f)
        except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
            continue
        if df.empty or not set(_PICK_IDENTITY + ["generated_at"]).issubset(df.columns):
            continue
        if "data_label" in df.columns:
            df = df[df["data_label"].astype(str) == "real"]
        if not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    todo = pd.concat(frames, ignore_index=True)
    todo["_id"] = _pick_identity(todo)
    # Orden cronologico por sello parseado (no por texto): sobrevive la
    # generacion mas reciente de cada identidad.
    todo["_ts"] = pd.to_datetime(todo["generated_at"], errors="coerce", utc=True,
                                 format="ISO8601")
    todo = (todo.sort_values("_ts", kind="stable", na_position="first")
                .drop_duplicates("_id", keep="last"))
    if (current is not None and not current.empty
            and set(_PICK_IDENTITY).issubset(current.columns)):
        vivas = set(_pick_identity(current))
        todo = todo[~todo["_id"].isin(vivas)]
    todo = todo.drop(columns=["_id", "_ts"]).reset_index(drop=True)
    if todo.empty:
        return todo
    flags = (todo["flags"].fillna("").astype(str).replace("nan", "")
             if "flags" in todo.columns else pd.Series("", index=todo.index))
    todo["flags"] = (flags + ";" + SUPERSEDED_FLAG).str.lstrip(";")
    return todo


def _scores_map(raw: list[dict]) -> dict[str, tuple[int, int, str]]:
    scores: dict[str, tuple[int, int, str]] = {}
    for s in raw:
        # Per-entry guard: one malformed score entry (missing key, non-numeric
        # score) must skip that game, not abort the whole league's settlement
        # (audit 2026-07-24, M-10).
        try:
            if not (s.get("completed") and s.get("scores")):
                continue
            sc = {x["name"]: x["score"] for x in s["scores"]}
            home, away = sc.get(s["home_team"]), sc.get(s["away_team"])
            if home is None or away is None:  # score names don't match teams
                continue
            scores[s["id"]] = (int(home), int(away), s["home_team"])
        except (KeyError, TypeError, ValueError) as exc:
            log.warning("malformed score entry skipped (id=%s): %s",
                        s.get("id", "?"), exc)
    return scores


def _event_meta_map(raw: list[dict]) -> dict[str, dict]:
    """event_id -> {home, away, game_date} from raw /scores entries.

    game_date is the commence date (YYYY-MM-DD); empty when the API omits it.
    """
    out: dict[str, dict] = {}
    for s in raw:
        eid = s.get("id")
        if not eid:
            continue
        out[str(eid)] = {
            "home": s.get("home_team", "") or "",
            "away": s.get("away_team", "") or "",
            "game_date": str(s.get("commence_time") or "")[:10],
        }
    return out


def _attach_event_meta(settled: pd.DataFrame, meta: dict[str, dict]) -> pd.DataFrame:
    """Add home/away/game_date columns to settled rows, keyed by event_id.

    Unmatched event_ids get empty strings (cosmetic; backfill fills them later).

    RELLENA, NO PISA (AUD-MED-001, auditoria integral 2026-09-10). Desde que
    `BetCandidate` lleva `home`/`away`, las filas liquidadas ya llegan con la
    identidad que registro el pick. La version anterior asignaba la columna
    entera desde el payload de /scores, asi que un evento AUSENTE de ese payload
    -- normal: la ventana de scores son 3 dias -- borraba a "" una identidad que
    el pick si tenia. Se conserva lo que ya hay y solo se completa lo vacio.
    """
    if settled.empty:
        return settled
    settled = settled.copy()
    for col in ("home", "away", "game_date"):
        desde_scores = settled["event_id"].map(
            lambda e: meta.get(str(e), {}).get(col, ""))
        if col in settled.columns:
            previo = settled[col].fillna("").astype(str)
            settled[col] = previo.where(previo.str.strip() != "", desde_scores)
        else:
            settled[col] = desde_scores
    return settled


def _day_diff(a: str, b: str) -> int:
    from datetime import date
    try:
        return abs((date.fromisoformat(a[:10]) - date.fromisoformat(b[:10])).days)
    except ValueError:
        return 99


def tennis_scores_map(predictions: pd.DataFrame, results: list[dict],
                      tol_days: int = 1) -> dict[str, tuple[int, int, str]]:
    """Map each tennis event_id to a synthetic (home_score, away_score, home)
    by matching its two players (normalized, order-insensitive) and date to an
    ESPN result. Winner gets 1, loser 0, so the existing h2h grader applies.
    No event_id correspondence exists between The Odds API and ESPN, hence the
    name+date match (within `tol_days`)."""
    matches = [(frozenset({normalize_key(m["home"]), normalize_key(m["away"])}),
                str(m.get("date", ""))[:10], normalize_key(m["winner"]))
               for m in results if m.get("winner")]
    scores: dict[str, tuple[int, int, str]] = {}
    for r in predictions.itertuples():
        eid, home, away = str(r.event_id), str(r.home), str(r.away)
        day = str(getattr(r, "start_time", ""))[:10]
        pair = frozenset({normalize_key(home), normalize_key(away)})
        winner = next((w for (mp, md, w) in matches
                       if mp == pair and _day_diff(md, day) <= tol_days), None)
        if winner is None:
            continue
        if winner == normalize_key(home):
            scores[eid] = (1, 0, home)
        elif winner == normalize_key(away):
            scores[eid] = (0, 1, home)
    return scores


def history_scores_map(pending: pd.DataFrame, results: list[dict],
                       tol_days: int = 1) -> dict[str, tuple[int, int, str]]:
    """event_id -> (home_score, away_score, home) matching served rows to the
    historical ResultsStore by ORDERED normalized (home, away) + date within
    ``tol_days``. Ordered on purpose: home/away identity decides h2h sides and
    spreads in team sports (tennis has its own order-insensitive map). No
    event_id correspondence exists between The Odds API and ESPN/statsapi.

    An ambiguous match (two results for the same pair within tolerance, e.g. an
    MLB doubleheader) is SKIPPED: grading with the wrong game's score would
    corrupt the calibration evidence, so ambiguity never grades."""
    keyed: dict[tuple[str, str], list[tuple[str, int, int]]] = {}
    for m in results:
        try:
            k = (normalize_key(str(m["home"])), normalize_key(str(m["away"])))
            keyed.setdefault(k, []).append(
                (str(m.get("date", ""))[:10], int(m["home_score"]), int(m["away_score"])))
        except (KeyError, TypeError, ValueError):
            continue
    scores: dict[str, tuple[int, int, str]] = {}
    for r in pending.itertuples():
        eid, home, away = str(r.event_id), str(r.home), str(r.away)
        day = (str(getattr(r, "game_date", "")) or str(getattr(r, "start_time", "")))[:10]
        hits = [(hs, as_) for (md, hs, as_)
                in keyed.get((normalize_key(home), normalize_key(away)), [])
                if _day_diff(md, day) <= tol_days]
        if len(hits) == 1:
            scores[eid] = (hits[0][0], hits[0][1], home)
    return scores


def tennis_history_results(league: str) -> list[dict]:
    """Resultados del TOUR (data/historical/results_{atp,wta}.csv) en el
    formato que consume ``tennis_scores_map`` (con ``winner``).

    El historico de tenis se guarda orientado home=ganador (espn_tennis), asi
    que el emparejamiento ORDENADO de ``history_scores_map`` fallaba cada vez
    que The Odds API listaba al ganador como visitante. ``tennis_scores_map``
    empareja sin orden por (par de jugadores, fecha), que es lo correcto en
    tenis. Best-effort: [] si no hay tour o no hay historico."""
    from sqp.providers.espn_tennis import tour_from_league
    from sqp.storage.results_store import ResultsStore
    tour = tour_from_league(league)
    if not tour:
        return []
    out: list[dict] = []
    for m in ResultsStore(ROOT).load(tour):
        try:
            hs, as_ = int(m["home_score"]), int(m["away_score"])
        except (KeyError, TypeError, ValueError):
            continue
        if hs == as_:
            continue
        out.append({"home": m.get("home", ""), "away": m.get("away", ""),
                    "date": m.get("date", ""),
                    "winner": m.get("home") if hs > as_ else m.get("away")})
    return out


def _grade_served_from_history(league: str, three_way: bool = False) -> int:
    """Fallback for served rows the daily scores feed can never grade (older
    than The Odds API 3-day window; audit 2026-08-02, M-01): match them against
    data/historical/ by ordered names + date. Best-effort: a failure here must
    never abort the settlement of real picks."""
    try:
        from sqp.providers.espn_tennis import tour_from_league
        from sqp.storage.results_store import ResultsStore
        still = ServedStore(ROOT).pending(league)
        if still.empty:
            return 0
        # El stream servido se guarda bajo la liga de The Odds API
        # ('tennis_atp_canadian_open'), pero el histórico de tenis se backfillea
        # por TOUR ('atp'/'wta'). Buscarlo con el nombre de la liga devolvía 0
        # filas, así que ninguna fila servida de tenis se graduó nunca por esta
        # vía: caducaban por stale_void con la evidencia ya descargada en
        # data/historical/ (auditoría 2026-08-05).
        history_key = tour_from_league(league) or league
        if history_key != league:
            # Tenis: emparejamiento sin orden por par de jugadores + fecha
            # (AUD-MED-004, 2026-09-13); el ordenado dejaba sin graduar la
            # mitad de las filas, las del ganador listado como visitante.
            scores = tennis_scores_map(still, tennis_history_results(league))
        else:
            results = ResultsStore(ROOT).load(history_key)
            if not results:
                return 0
            scores = history_scores_map(still, results)
        if not scores:
            return 0
        return _grade_served(league, scores, three_way=three_way)
    except Exception as exc:
        log.warning("[%s] history fallback for the served stream failed: %s",
                    league, exc)
        return 0


def _void_stale_served(league: str, stale_days: int = STALE_VOID_DAYS,
                       now: datetime | None = None) -> int:
    """Void served rows still pending ``stale_days`` after their start, once
    the daily feed AND the historical fallback both failed to grade them.

    Mirrors the candidates' stale_void policy (decision 2026-07-12): a
    postponed game is a void by betting convention (grading it against its
    doubleheader replay is undecidable), and a fixture with no results vendor
    (e.g. a cup game priced under a league key) would otherwise rot until
    ``pending``'s cutoff silently drops it (audit 2026-08-02, M-01). Void rows
    are excluded downstream by ``train_market_calibrators``, so they never
    contaminate calibration. Idempotent via ``append_graded``. Best-effort."""
    try:
        store = ServedStore(ROOT)
        pending = store.pending(league)
        if pending.empty:
            return 0
        now = now or datetime.now(timezone.utc)
        stale_mask = []
        for s in pending["start_time"]:
            dt = _parse_start(s)
            stale_mask.append(dt is not None and (now - dt).days >= stale_days)
        voided = pending[stale_mask].copy()
        if voided.empty:
            return 0
        voided["result"] = "void"
        voided["pnl"] = 0.0
        voided["settled_at"] = now.isoformat()
        flags = (voided["flags"].fillna("").astype(str)
                 if "flags" in voided.columns else pd.Series("", index=voided.index))
        voided["flags"] = (flags + ";stale_void").str.lstrip(";")
        n = len(store.append_graded(league, voided))
        if n:
            log.info("[%s] served stream: %d stale row(s) voided (no gradable "
                     "result %d+ days after start).", league, n, stale_days)
        return n
    except Exception as exc:
        log.warning("[%s] could not void the stale served rows: %s", league, exc)
        return 0


def _persist_settled(league: str, settled: pd.DataFrame) -> pd.DataFrame:
    """Dedup against prior settled rows and persist. Idempotent.

    Reconciles columns across schema versions before writing. When the
    BetCandidate schema gains a field (e.g. calibrated_probability), older
    settled_*.csv files lack that column; a plain append (mode='a', no header)
    would write the new rows in a different column order than the existing header
    and silently misalign every value on re-read. So we take the union of the
    prior and new columns (prior order first) and rewrite the file aligned, which
    also self-heals any file written by a previous schema. Returns the NEWLY
    settled rows (post-dedup).

    TODA la transaccion -- comprobar, leer, deduplicar, combinar y escribir --
    corre BAJO EL LOCK del fichero (AUD-20260906-02, Codex, HIGH, REPRODUCED).
    El temporal unico y `os.replace` protegen contra un fichero a medio escribir,
    pero NO contra que un escritor sustituya el resultado completo de otro: es un
    read-modify-write, y sin exclusion el segundo en escribir pisa lo que el
    primero acababa de anadir. Reproducido con un intercalado determinista (A lee
    y prepara, B liquida entero, A escribe): de dos liquidaciones de -400
    sobrevivio SOLO una, y el saldo daba 600 en vez de 200.

    `prior` se lee DENTRO del lock a proposito. Leerlo fuera y escribir dentro no
    arregla nada -- el estado podria haber cambiado entre ambos --, que es
    exactamente la correccion que `revalidation.py` ya aplico en d27fdd4.

    La seccion critica no toca la red: es lectura y escritura de un CSV local.
    Se activa por una liquidacion manual solapada con la programada, o por dos
    ligas que compartan fichero."""
    out = ROOT / "data" / "bets" / f"settled_{league}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with locked(out):
        prior: pd.DataFrame | None = None
        if out.exists():
            try:
                prior = pd.read_csv(out)
            except pd.errors.EmptyDataError:
                prior = None  # empty prior: genuinely a fresh file
            # ParserError PROPAGATES on purpose: treating a corrupt settled_*.csv as
            # fresh would rewrite it with only today's rows and wipe the PnL history
            # feeding the ROI audit, bankroll ledger and calibrators. Fix the file
            # instead (audit 2026-07-24, M-21).
        if not settled.empty and prior is not None and set(DEDUP_KEY).issubset(prior.columns):
            have = {tuple(map(str, r)) for r in prior[DEDUP_KEY].values.tolist()}
            keep = [tuple(map(str, r)) not in have for r in settled[DEDUP_KEY].values.tolist()]
            settled = settled[keep]
        if settled.empty:
            return settled
        if prior is not None:
            cols = list(prior.columns) + [c for c in settled.columns if c not in prior.columns]
            combined = pd.concat([prior.reindex(columns=cols), settled.reindex(columns=cols)],
                                 ignore_index=True)
            _atomic_write_csv(combined, out)
        else:
            _atomic_write_csv(settled, out)
    return settled



def _prediction_start_times(league: str) -> dict[str, str]:
    """event_id -> start_time desde predictions_<league>.csv (misma fuente que
    usa cleanup.unsettled_completed_picks). Vacio si no se puede leer."""
    pf = ROOT / "data" / "predictions" / f"predictions_{league}.csv"
    if not pf.exists() or pf.stat().st_size <= 1:
        return {}
    try:
        preds = pd.read_csv(pf, usecols=lambda c: c in ("event_id", "start_time"))
    except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return {}
    if "start_time" not in preds.columns:
        return {}
    return {str(r.event_id): str(r.start_time) for r in preds.itertuples()}


def _with_stale_voids(league: str, cands: pd.DataFrame, settled: pd.DataFrame,
                      scores: dict[str, tuple[int, int, str]],
                      start_times: dict[str, str]) -> pd.DataFrame:
    """Anade voids por expiracion (partidos comenzados hace >STALE_VOID_DAYS
    sin score: cancelados/pospuestos) a las filas recien liquidadas, para que
    un partido cancelado no deje su liga bloqueada indefinidamente."""
    stale = void_stale_candidates(cands, scores, start_times)
    if stale.empty:
        return settled
    log.warning("[%s] %d pick(s) comenzados hace >%dd sin resultado: se "
                "liquidan como VOID (flag stale_void, pnl 0).",
                league, len(stale), STALE_VOID_DAYS)
    return pd.concat([settled, stale], ignore_index=True) if not settled.empty else stale


def _grade_served(league: str, scores: dict[str, tuple[int, int, str]],
                  days_from: int | None = None, three_way: bool = False) -> int:
    """Grade the league's pending served-probability rows (stake-0 calibration
    stream) against final scores and persist them append-only. Idempotent: a
    served row already graded is skipped by the store. Returns rows graded.

    ``days_from``: depth of the scores fetch that produced ``scores``. Pending
    rows older than that window can never grade from this feed (the API stops
    listing them), so they are counted and WARNED instead of silently rotting
    until ``pending``'s 7-day cutoff drops them (audit 2026-07-24, M-25).

    Best-effort by design: the served stream is evidence gathering, so a failure
    here must never abort the settlement of real picks."""
    try:
        store = ServedStore(ROOT)
        pending = store.pending(league)
        if pending.empty:
            return 0
        if days_from is not None:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days_from + 1)
                      ).strftime("%Y-%m-%dT%H:%M:%SZ")
            expired = int((pending["start_time"].astype(str) < cutoff).sum())
            if expired:
                log.warning("[%s] served stream: %d pending row(s) older than "
                            "the %d-day scores window; they will not grade from "
                            "this feed (re-run settlement with a deeper window "
                            "or accept the gap).", league, expired, days_from)
        graded = store.append_graded(league,
                                     settle_candidates(pending, scores, three_way))
        if not graded.empty:
            log.info("[%s] served stream: %d probabilities graded for calibration "
                     "(%d still pending scores).", league, len(graded),
                     len(pending) - len(graded))
        return len(graded)
    except Exception as exc:
        log.warning("[%s] could not grade the served-probability stream: %s",
                    league, exc)
        return 0


def _con_superseded(league: str, cands: pd.DataFrame) -> pd.DataFrame:
    """Candidates vigentes + picks desplazados (``superseded_candidates``),
    alineados por union de columnas. Best-effort: si el archivo falla, se
    liquida solo lo vigente, que es lo que se hacia hasta el 2026-09-13."""
    try:
        extra = superseded_candidates(league, cands)
    except Exception as exc:
        log.warning("[%s] no se pudieron recuperar los picks desplazados del "
                    "archivo: %s", league, exc)
        return cands
    if extra.empty:
        return cands
    log.info("[%s] %d pick(s) que dejaron la lista antes del partido entran a "
             "liquidacion con flag '%s'.", league, len(extra), SUPERSEDED_FLAG)
    if cands is None or cands.empty:
        return extra
    cols = list(cands.columns) + [c for c in extra.columns if c not in cands.columns]
    return pd.concat([cands.reindex(columns=cols), extra.reindex(columns=cols)],
                     ignore_index=True)


def _prediction_metadata(league: str, cands: pd.DataFrame) -> pd.DataFrame:
    """Latest known metadata per event, including displaced predictions.

    Nacio para tenis (AUD-MED-004) y desde la ronda audit-2026-09-23 la usan
    tambien los deportes de equipo: un pick desplazado (`superseded`) ya no
    esta en el ``predictions`` vigente, y sin su `start_time` ni expiraba ni
    podia buscarse en el historico (AUD-003/AUD-004).

    Event IDs are stable within this provider. Prefer the current schedule;
    otherwise use the newest archived snapshot within the candidate lookback.
    Predictions historically lack generated_at, so archive day is the available
    snapshot ordering, not an invented match-time or generation timestamp.
    """
    pred_dir = ROOT / "data" / "predictions"
    floor = (datetime.now(timezone.utc) - timedelta(days=SUPERSEDED_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    paths = [p for p in sorted((pred_dir / "archive").glob(f"predictions_{league}_*.csv"))
             if (m := _ARCHIVE_DAY.search(p.name)) and m.group(1) >= floor]
    paths.append(pred_dir / f"predictions_{league}.csv")
    ids = set(cands["event_id"].astype(str))
    frames = []
    for path in paths:
        try:
            frame = pd.read_csv(path)
        except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
            continue
        if not {"event_id", "home", "away", "start_time"}.issubset(frame.columns):
            continue
        frame["event_id"] = frame["event_id"].astype(str)
        frames.append(frame[frame["event_id"].isin(ids)])
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).drop_duplicates("event_id", keep="last")


def _candidate_metadata(league: str, cands: pd.DataFrame) -> pd.DataFrame:
    """`_prediction_metadata` reducido a lo que usa la liquidacion de equipos.
    Best-effort: ante cualquier fallo, frame vacio (se liquida como antes)."""
    try:
        preds = _prediction_metadata(league, cands)
    except Exception as exc:
        log.warning("[%s] no se pudieron leer los metadatos archivados de los "
                    "candidatos: %s", league, exc)
        return pd.DataFrame(columns=["event_id", "home", "away", "start_time"])
    if preds.empty:
        return pd.DataFrame(columns=["event_id", "home", "away", "start_time"])
    return preds[["event_id", "home", "away", "start_time"]].reset_index(drop=True)


def _settle_tennis(league: str, days_from: int, provider=None) -> pd.DataFrame:
    """Grade tennis candidates via ESPN results matched by player name + date.
    Players and match dates come from current predictions, with archived
    metadata as fallback for candidates displaced by a later daily run."""
    pred_dir = ROOT / "data" / "predictions"
    cand_path = pred_dir / f"candidates_{league}.csv"
    pending_served = ServedStore(ROOT).pending(league)
    # Picks que dejaron la lista antes del partido (AUD-MED-003): se graduan
    # con los mismos resultados, una fila por identidad, flag `superseded`.
    # Se leen AQUI para que una liga sin fichero vigente ni stream pendiente
    # pero con picks archivados por liquidar no salga antes de tiempo.
    cands = _con_superseded(
        league, pd.read_csv(cand_path) if cand_path.exists() else pd.DataFrame())
    if cands.empty and pending_served.empty:
        return pd.DataFrame()
    if provider is None:
        from sqp.providers.espn_tennis import ESPNTennisResultsProvider
        provider = ESPNTennisResultsProvider()
    try:
        results = provider.fetch_results(league, days_back=max(days_from + 2, 5))
    except Exception as exc:
        log.warning("[%s] could not fetch ESPN tennis results: %s", league, exc)
        return pd.DataFrame()
    # Puerta de salud del payload antes de CUALQUIER anulacion (AUD-HIGH-002).
    #
    # Misma regla que `fetch_and_settle` aplica desde la auditoria 2026-08-31
    # (N-A-3) y que esta ruta se quedo sin heredar: una respuesta que no entrega
    # ni un resultado utilizable significa "esto no nos dijo nada", que NO es lo
    # mismo que "estos partidos no tienen resultado". Anular es FINAL
    # (`DEDUP_KEY` no lleva `result`, asi que el grado real de manana colisiona
    # con el `void` de hoy y se descarta), de modo que una sola respuesta mala
    # anulaba permanentemente todo pick y toda fila servida de 3+ dias del
    # torneo, a pnl 0 e indistinguible de una cancelacion real.
    #
    # La confianza se mide sobre el PAYLOAD, no sobre el mapa de marcadores.
    # `tennis_scores_map` se construye a partir de las filas pendientes, asi que
    # un mapa vacio confunde dos cosas distintas: proveedor mudo (aplazar) y
    # proveedor sano que no cubre ESTOS partidos (anular por expiracion, que es
    # justo la politica del 2026-07-12: un partido cancelado no puede bloquear la
    # liga para siempre). El criterio equivalente a `_scores_map` es "entradas
    # con ganador", que es lo que `tennis_scores_map` sabe consumir.
    #
    # Riesgo residual ACEPTADO, el mismo que la ruta general: si ESPN entrega
    # resultados sanos pero con los nombres derivados, el payload se considera de
    # fiar y la expiracion sigue corriendo. No es distinguible de una cancelacion
    # sin una fuente tercera, y endurecerlo mas resucitaria el bloqueo indefinido.
    usable = [m for m in results if m.get("winner")]
    results_trusted = bool(usable)
    if not results_trusted:
        log.error("[%s] ESPN no devolvio ni un resultado utilizable (%d fila(s) "
                  "crudas): NO se anula nada en esta pasada. Anular es "
                  "irreversible, asi que un payload vacio o ilegible no puede "
                  "leerse como cancelacion masiva.", league, len(results))
    # Served rows carry their own players/date, so the calibration stream grades
    # even when there were no candidates that day.
    if not pending_served.empty:
        _grade_served(league, tennis_scores_map(pending_served, results))
        # Igual que en la ruta general (M-01): lo que el feed vivo no gradúa aún
        # puede graduarse contra data/historical/. Sin esta llamada, una fila de
        # tenis con resultado ya descargado se ANULABA por stale_void, destruyendo
        # evidencia de calibración recuperable (auditoría 2026-08-05).
        _grade_served_from_history(league)
        if results_trusted:
            _void_stale_served(league)
    if cands.empty:
        return pd.DataFrame()
    preds = _prediction_metadata(league, cands)
    if preds.empty:
        log.warning("[%s] no predictions file to recover players/date for tennis "
                    "settlement; skipped.", league)
        return pd.DataFrame()
    # Lo que el feed vivo de ESPN no cubre puede estar ya en data/historical/
    # (backfill diario del tour): mismo fallback que el stream servido tiene
    # desde el 2026-08-05 y que los candidates no heredaron. Sin el, un pick
    # de tenis listado el dia del partido se quedaba sin veredicto y el run
    # siguiente lo sobrescribia (18 unidades medidas, AUD-MED-004). El feed
    # vivo manda cuando ambos responden.
    scores = {**tennis_scores_map(preds, tennis_history_results(league)),
              **tennis_scores_map(preds, results)}
    settled = settle_candidates(cands, scores)
    # Misma puerta de salud del payload que arriba (ya registrada en el log).
    if results_trusted:
        start_times = {str(r.event_id): str(getattr(r, "start_time", ""))
                       for r in preds.itertuples()}
        settled = _with_stale_voids(league, cands, settled, scores, start_times)
    meta = {str(r.event_id): {"home": str(r.home), "away": str(r.away),
                              "game_date": str(getattr(r, "start_time", ""))[:10]}
            for r in preds.itertuples()}
    settled = _attach_event_meta(settled, meta)
    return _persist_settled(league, settled)


def fetch_and_settle(league: str, settings: Settings, days_from: int = 2,
                     client: OddsAPIClient | None = None) -> pd.DataFrame:
    """Grade the league's pending candidates against final scores. Returns the
    NEWLY settled rows (empty if no candidates, no scores, or all already done)."""
    meta = _league_meta(league)
    if meta.get("family") == "tennis":
        return _settle_tennis(league, days_from)
    if not meta.get("has_scores"):
        log.info("[%s] no scores in The Odds API; skipped (needs a secondary source).", league)
        return pd.DataFrame()
    cand_path = ROOT / "data" / "predictions" / f"candidates_{league}.csv"
    pending_served = ServedStore(ROOT).pending(league)
    # Picks que dejaron la lista antes del partido (AUD-MED-003), leidos antes
    # de decidir si hay algo que liquidar: sin ellos una liga sin fichero
    # vigente salia aqui con picks archivados sin veredicto.
    cands = _con_superseded(
        league, pd.read_csv(cand_path) if cand_path.exists() else pd.DataFrame())
    if cands.empty and pending_served.empty:
        return pd.DataFrame()
    client = client or OddsAPIClient(settings.odds_api_key, settings.regions)
    raw = client.fetch_scores(meta["sport_key"], days_from=days_from)
    scores = _scores_map(raw)
    three_way = bool(meta.get("three_way"))
    # Payload health gate before ANY voiding (audit 2026-08-31, N-A-3).
    #
    # An empty `scores` map means "this response told us nothing", which is NOT
    # the same as "the world says these games have no result" -- yet the voiding
    # path treated them identically. Two ways to get here without an exception,
    # so `settle_all` never marks the league as failed: the provider returns 200
    # with an empty list (out-of-season sport key, glitch), or its schema changes
    # and `_scores_map`'s per-entry guard drops every entry.
    #
    # Voiding is FINAL: DEDUP_KEY carries no `result`, so tomorrow's real grade
    # collides with today's persisted `void` and gets discarded. One bad response
    # would permanently void every pick and served row 3-7 days old in the league,
    # at pnl 0, indistinguishable from a genuine postponement. Deferring costs a
    # day; a single healthy response resumes the expiry policy.
    scores_trusted = bool(scores)
    if not scores_trusted and (not pending_served.empty or cand_path.exists()):
        log.error("[%s] scores response carried no usable entry (%d raw): NOT "
                  "voiding anything this pass. Voiding is irreversible, so an "
                  "empty payload must not be read as mass cancellation.",
                  league, len(raw) if raw is not None else 0)
    # Calibration stream first (stake 0, best-effort): shares this scores fetch,
    # and grades even on days the league produced no candidates.
    if not pending_served.empty:
        _grade_served(league, scores, days_from=days_from, three_way=three_way)
        # What the 3-day feed could not grade may still grade from the
        # historical store (backfilled daily); whatever remains ungradable
        # past the stale window is voided (audit 2026-08-02, M-01).
        _grade_served_from_history(league, three_way=three_way)
        if scores_trusted:
            _void_stale_served(league)
    if cands.empty:
        return pd.DataFrame()
    # Metadatos (home/away/start_time) de TODOS los candidatos, desplazados
    # incluidos: el `predictions` vigente solo describe el run de hoy, asi que
    # un pick `superseded` quedaba sin `start_time`, nunca expiraba y a los
    # SUPERSEDED_LOOKBACK_DAYS salia del escaneo sin veredicto (AUD-004, ronda
    # audit-2026-09-23).
    preds = _candidate_metadata(league, cands)
    start_times = {**{str(r.event_id): str(r.start_time) for r in preds.itertuples()},
                   **_prediction_start_times(league)}
    # SIN fallback historico para candidatos de equipo, a proposito (AUD-003,
    # ronda audit-2026-09-23: BLOQUEADO). Se implemento con `history_scores_map`
    # y la revision Fable lo tumbo con una reproduccion: emparejar por (local,
    # visitante) +-1 dia NO prueba identidad, y en una serie MLB el pick de HOY,
    # sin jugar, se liquidaba con el marcador de AYER -- de forma irreversible,
    # porque DEDUP_KEY no lleva `result`. Es el problema abierto de identidad
    # entre proveedores (AUD-002, remediacion 2026-09-14). Hasta decidirlo, un
    # candidato fuera de la ventana del feed sigue la politica de expiracion.
    settled = settle_candidates(cands, scores, three_way)
    if scores_trusted:
        settled = _with_stale_voids(league, cands, settled, scores, start_times)
    settled = _attach_event_meta(settled, _event_meta_map(raw))
    return _persist_settled(league, settled)


def realized_roi(settled: pd.DataFrame) -> float:
    """Realized ROI over staked (win/loss) rows; 0.0 if nothing graded."""
    # Definicion canonica en `settle.realized_roi_parts` (AUD-002): las medias
    # (linea asiatica de cuarto, AUD-MED-002) entran en numerador Y
    # denominador; push/void en ninguno.
    pnl, staked = realized_roi_parts(settled)
    return pnl / staked if staked else 0.0
