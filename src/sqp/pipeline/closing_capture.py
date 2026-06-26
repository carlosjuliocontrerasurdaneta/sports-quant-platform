"""Closing-line capture: snapshot fresh odds shortly before bet events start, so
CLV (entry vs close) becomes measurable. Only spends API quota on leagues that
have open candidates with a game commencing within the window. Adds snapshots
only; load_closing_odds / clv_analysis already use the latest pre-commence one.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from sqp.config import ROOT
from sqp.logging_config import get_logger

log = get_logger("sqp.closing_capture")


def _parse_utc(s: object) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def leagues_with_imminent_bets(predictions_dir: Path, now: datetime,
                               window_min: int = 120) -> dict[str, list[str]]:
    """{league: [bet event_ids commencing in (now, now+window_min]]}. No API."""
    out: dict[str, list[str]] = {}
    horizon = now + timedelta(minutes=window_min)
    for cf in sorted(predictions_dir.glob("candidates_*.csv")):
        league = cf.stem.replace("candidates_", "")
        try:
            cands = pd.read_csv(cf, usecols=lambda c: c == "event_id")
        except (pd.errors.EmptyDataError, ValueError):
            continue
        if cands.empty:
            continue
        bet_ids = set(cands["event_id"].astype(str))
        pf = predictions_dir / f"predictions_{league}.csv"
        if not pf.exists() or pf.stat().st_size <= 1:
            continue
        preds = pd.read_csv(pf, usecols=lambda c: c in ("event_id", "start_time"))
        if "start_time" not in preds.columns:
            continue
        imminent = [str(r.event_id) for r in preds.itertuples()
                    if str(r.event_id) in bet_ids
                    and (st := _parse_utc(getattr(r, "start_time", ""))) is not None
                    and now <= st <= horizon]
        if imminent:
            out[league] = imminent
    return out


def _credits_file(odds_dir: Path, day: str) -> Path:
    return odds_dir / f".closing_credits_{day}"


def spent_today(odds_dir: Path, day: str) -> int:
    """Credits already spent on closing capture today (0 if absent/corrupt)."""
    p = _credits_file(odds_dir, day)
    if not p.exists():
        return 0
    try:
        return int(p.read_text().strip() or "0")
    except (ValueError, OSError):
        return 0


def add_spent(odds_dir: Path, day: str, credits: int) -> int:
    """Add credits (negative ignored) to today's total and persist. Returns total."""
    total = spent_today(odds_dir, day) + max(0, int(credits))
    p = _credits_file(odds_dir, day)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(str(total))
    return total


def capture_closing(predictions_dir: Path, settings, *, window_min: int = 120,
                    max_credits: int = 300, min_remaining: int = 100,
                    now: datetime | None = None, client=None, odds_store=None) -> dict:
    """Snapshot fresh closing odds for leagues with imminent bet events.

    Budget-bounded: stops at `max_credits`/day (persisted across hourly runs) and
    skips a league when the API's known `requests_remaining` is below
    `min_remaining` (never starves the morning run). Best-effort per league.
    """
    from sqp.pipeline.daily import _league_meta
    from sqp.providers.odds_api import OddsAPIClient
    from sqp.storage.odds_store import OddsStore

    now = now or datetime.now(timezone.utc)
    day = now.strftime("%Y%m%d")
    odds_dir = ROOT / "data" / "odds"
    targets = leagues_with_imminent_bets(predictions_dir, now, window_min)
    summary = {"captured": {}, "skipped_budget": [], "credits_spent": 0,
               "leagues_considered": list(targets)}
    if not targets:
        return summary
    already = spent_today(odds_dir, day)
    if already >= max_credits:
        summary["skipped_budget"] = list(targets)
        log.info("closing: daily cap %d reached (%d spent); skipping %s",
                 max_credits, already, ", ".join(targets))
        return summary

    if client is None:
        client = OddsAPIClient(settings.odds_api_key, settings.regions, force_refresh=True)
    if odds_store is None:
        odds_store = OddsStore(ROOT)

    spent = 0
    for league, bet_ids in targets.items():
        if already + spent >= max_credits:
            summary["skipped_budget"].append(league)
            continue
        if client.requests_remaining is not None and client.requests_remaining < min_remaining:
            summary["skipped_budget"].append(league)
            log.warning("closing: requests_remaining %s < %d; skipping %s",
                        client.requests_remaining, min_remaining, league)
            continue
        try:
            sport_key = _league_meta(league)["sport_key"]
            events = client.fetch_odds(league, sport_key)
            spent += client.requests_last or 0
            want = set(bet_ids)
            keep = [eo for eo in events if str(eo.event.event_id) in want]
            if keep:
                n = odds_store.append_snapshot(league, keep)
                summary["captured"][league] = n
                log.info("closing: [%s] %d lines snapshotted for %d bet events",
                         league, n, len(keep))
        except Exception as exc:
            log.warning("[%s] closing capture failed: %s", league, exc)
    if spent:
        add_spent(odds_dir, day, spent)
    summary["credits_spent"] = spent
    return summary
