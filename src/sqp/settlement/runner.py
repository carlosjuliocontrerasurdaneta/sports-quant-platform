"""Settlement orchestration: fetch final scores and grade a league's candidates.

Shared by scripts/settle_bets.py (one league) and scripts/settle_all.py (every
league with pending candidates). Append-only and idempotent: a candidate already
settled in a prior run is never graded twice.
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from sqp.config import ROOT, Settings
from sqp.logging_config import get_logger
from sqp.pipeline.daily import _league_meta
from sqp.providers.odds_api import OddsAPIClient
from sqp.settlement.settle import settle_candidates

log = get_logger("sqp.settle")

DEDUP_KEY = ["event_id", "market", "selection", "line", "generated_at"]


def _scores_map(raw: list[dict]) -> dict[str, tuple[int, int, str]]:
    scores: dict[str, tuple[int, int, str]] = {}
    for s in raw:
        if not (s.get("completed") and s.get("scores")):
            continue
        sc = {x["name"]: x["score"] for x in s["scores"]}
        home, away = sc.get(s["home_team"]), sc.get(s["away_team"])
        if home is None or away is None:  # score names don't match teams
            continue
        scores[s["id"]] = (int(home), int(away), s["home_team"])
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
        except (pd.errors.EmptyDataError, pd.errors.ParserError):
            prior = None  # empty / corrupt prior: treat as a fresh file
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


def fetch_and_settle(league: str, settings: Settings, days_from: int = 2,
                     client: OddsAPIClient | None = None) -> pd.DataFrame:
    """Grade the league's pending candidates against final scores. Returns the
    NEWLY settled rows (empty if no candidates, no scores, or all already done)."""
    meta = _league_meta(league)
    if not meta.get("has_scores"):
        log.info("[%s] no scores in The Odds API; skipped (needs a secondary source).", league)
        return pd.DataFrame()
    cand_path = ROOT / "data" / "predictions" / f"candidates_{league}.csv"
    if not cand_path.exists():
        return pd.DataFrame()
    cands = pd.read_csv(cand_path)
    client = client or OddsAPIClient(settings.odds_api_key, settings.regions)
    raw = client.fetch_scores(meta["sport_key"], days_from=days_from)
    scores = _scores_map(raw)
    settled = settle_candidates(cands, scores)
    settled = _attach_event_meta(settled, _event_meta_map(raw))
    return _persist_settled(league, settled)


def realized_roi(settled: pd.DataFrame) -> float:
    """Realized ROI over staked (win/loss) rows; 0.0 if nothing graded."""
    if settled.empty:
        return 0.0
    graded = settled[settled["result"].isin(["win", "loss"])]
    staked = graded["stake"].sum()
    return float(settled["pnl"].sum() / staked) if staked else 0.0
