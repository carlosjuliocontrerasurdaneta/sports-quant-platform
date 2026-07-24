"""Settlement orchestration: fetch final scores and grade a league's candidates.

Shared by scripts/settle_bets.py (one league) and scripts/settle_all.py (every
league with pending candidates). Append-only and idempotent: a candidate already
settled in a prior run is never graded twice.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from sqp.config import ROOT, Settings
from sqp.logging_config import get_logger
from sqp.pipeline.daily import _league_meta
from sqp.providers.odds_api import OddsAPIClient
from sqp.settlement.settle import (STALE_VOID_DAYS, settle_candidates,
                                   void_stale_candidates)
from sqp.sports.team_names import normalize_key
from sqp.storage.served_store import ServedStore

log = get_logger("sqp.settle")

DEDUP_KEY = ["event_id", "market", "selection", "line", "generated_at"]


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
    """
    if settled.empty:
        return settled
    settled = settled.copy()
    for col in ("home", "away", "game_date"):
        settled[col] = settled["event_id"].map(
            lambda e: meta.get(str(e), {}).get(col, ""))
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


def _persist_settled(league: str, settled: pd.DataFrame) -> pd.DataFrame:
    """Dedup against prior settled rows and persist. Idempotent.

    Reconciles columns across schema versions before writing. When the
    BetCandidate schema gains a field (e.g. calibrated_probability), older
    settled_*.csv files lack that column; a plain append (mode='a', no header)
    would write the new rows in a different column order than the existing header
    and silently misalign every value on re-read. So we take the union of the
    prior and new columns (prior order first) and rewrite the file aligned, which
    also self-heals any file written by a previous schema. Returns the NEWLY
    settled rows (post-dedup)."""
    out = ROOT / "data" / "bets" / f"settled_{league}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
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


def _atomic_write_csv(df: pd.DataFrame, out: Path) -> None:
    """Write ``df`` to ``out`` via a sibling temp file + ``os.replace``.

    settled_*.csv is the single source feeding the ROI audit, the bankroll
    ledger (which sizes live stakes) and calibrator training; a crash mid-write
    must never leave it truncated. ``os.replace`` is atomic on the same volume,
    so readers only ever see the old file or the complete new one."""
    tmp = out.with_suffix(out.suffix + ".tmp")
    try:
        df.to_csv(tmp, index=False)
        os.replace(tmp, out)
    finally:
        tmp.unlink(missing_ok=True)  # no-op after a successful replace


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
                  days_from: int | None = None) -> int:
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
        graded = store.append_graded(league, settle_candidates(pending, scores))
        if not graded.empty:
            log.info("[%s] served stream: %d probabilities graded for calibration "
                     "(%d still pending scores).", league, len(graded),
                     len(pending) - len(graded))
        return len(graded)
    except Exception as exc:
        log.warning("[%s] could not grade the served-probability stream: %s",
                    league, exc)
        return 0


def _settle_tennis(league: str, days_from: int, provider=None) -> pd.DataFrame:
    """Grade tennis candidates via ESPN results matched by player name + date.
    Players and the match date come from predictions_<league>.csv (written by the
    same run that produced the candidates)."""
    pred_dir = ROOT / "data" / "predictions"
    cand_path = pred_dir / f"candidates_{league}.csv"
    pred_path = pred_dir / f"predictions_{league}.csv"
    pending_served = ServedStore(ROOT).pending(league)
    if not cand_path.exists() and pending_served.empty:
        return pd.DataFrame()
    if provider is None:
        from sqp.providers.espn_tennis import ESPNTennisResultsProvider
        provider = ESPNTennisResultsProvider()
    try:
        results = provider.fetch_results(league, days_back=max(days_from + 2, 5))
    except Exception as exc:
        log.warning("[%s] could not fetch ESPN tennis results: %s", league, exc)
        return pd.DataFrame()
    # Served rows carry their own players/date, so the calibration stream grades
    # even when there were no candidates that day.
    if not pending_served.empty:
        _grade_served(league, tennis_scores_map(pending_served, results))
    if not cand_path.exists():
        return pd.DataFrame()
    if not pred_path.exists() or pred_path.stat().st_size <= 1:
        log.warning("[%s] no predictions file to recover players/date for tennis "
                    "settlement; skipped.", league)
        return pd.DataFrame()
    cands = pd.read_csv(cand_path)
    preds = pd.read_csv(pred_path)
    scores = tennis_scores_map(preds, results)
    settled = settle_candidates(cands, scores)
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
    if not cand_path.exists() and pending_served.empty:
        return pd.DataFrame()
    client = client or OddsAPIClient(settings.odds_api_key, settings.regions)
    raw = client.fetch_scores(meta["sport_key"], days_from=days_from)
    scores = _scores_map(raw)
    # Calibration stream first (stake 0, best-effort): shares this scores fetch,
    # and grades even on days the league produced no candidates.
    if not pending_served.empty:
        _grade_served(league, scores, days_from=days_from)
    if not cand_path.exists():
        return pd.DataFrame()
    cands = pd.read_csv(cand_path)
    settled = settle_candidates(cands, scores)
    settled = _with_stale_voids(league, cands, settled, scores,
                                _prediction_start_times(league))
    settled = _attach_event_meta(settled, _event_meta_map(raw))
    return _persist_settled(league, settled)


def realized_roi(settled: pd.DataFrame) -> float:
    """Realized ROI over staked (win/loss) rows; 0.0 if nothing graded."""
    if settled.empty:
        return 0.0
    graded = settled[settled["result"].isin(["win", "loss"])]
    staked = graded["stake"].sum()
    return float(settled["pnl"].sum() / staked) if staked else 0.0
