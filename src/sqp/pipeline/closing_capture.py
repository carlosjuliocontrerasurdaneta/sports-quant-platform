"""Closing-line capture: snapshot fresh odds shortly before bet events start, so
CLV (entry vs close) becomes measurable. Only spends API quota on leagues that
have open candidates with a game commencing within the window. Adds snapshots
only; load_closing_odds / clv_analysis already use the latest pre-commence one.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

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
