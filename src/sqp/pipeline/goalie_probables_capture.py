"""Prospective capture of ESPN's NHL probable-starting-goalie announcements,
with OUR OWN capture timestamp (ESPN gives no announcement time).

Implements `docs/research/2026-09-26-preregistro-portero-nhl.md`, section 12
(operator decision, 2026-09-26: start capturing now, before the regular
season, independent of the historical measurement). Writes ONLY to
`data/historical/goalie_probables_nhl.csv` (via
`sqp.storage.goalies.log_goalie_probable_capture`), one row per (event,
team-side), appended only when the probable goalie or its status changed
since the last capture of that (event, side). Never reads or writes results,
candidates, stakes, gates or calibration files, and NEVER touches
probabilities or picks -- this is capture only.

Fetches today's and tomorrow's ESPN NHL scoreboard (UTC), keeps only events
that have not started yet (`captured_at < commence_time`), and logs every row
that carries a `probableStartingGoalie`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from sqp.config import ROOT
from sqp.logging_config import get_logger
from sqp.providers.date_window import utc_today
from sqp.providers.espn_goalies import (
    fetch_scoreboard,
    parse_active_sides,
    parse_goalie_probables,
)
from sqp.storage.goalies import log_goalie_probable_capture

log = get_logger("sqp.pipeline.goalie_probables_capture")


def _parse_utc(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _not_yet_started(rows: list[dict], as_of: datetime) -> list[dict]:
    """Keeps only rows for events that have not started as of `as_of`.

    A `commence_time` that fails to parse is DISCARDED, not kept: guessing
    that an unparseable start time means "still upcoming" could log a
    probable for a game that already started or finished (revision
    independiente de Fable, menor, 2026-09-26)."""
    out = []
    for row in rows:
        if row["completed"]:
            continue
        commence = _parse_utc(row["commence_time"])
        if commence is None:
            continue
        if commence <= as_of:
            continue  # ya en curso o pasado: fuera de "a la hora del pick"
        out.append(row)
    return out


def run(source_run: str = "capture", root: Path = ROOT,
        now: datetime | None = None) -> tuple[int, int]:
    """Fetches today's + tomorrow's ESPN NHL scoreboard, keeps only
    not-yet-started probables, and logs them. Returns (rows_seen, rows_appended).

    The instant recorded as `captured_at` for each date's rows is taken right
    after THAT date's scoreboard response is received, not before it was
    requested -- two fetches in the same call can legitimately carry
    different capture instants (revision independiente de Fable, menor,
    2026-09-26). `now`, when given (tests only), overrides both the capture
    instant and the not-yet-started cutoff for every date fetched in this
    call, since there is then no real per-fetch clock to read.
    """
    session = requests.Session()
    today = utc_today()
    total_seen = 0
    total_appended = 0
    for d in (today, today + timedelta(days=1)):
        date_str = f"{d:%Y%m%d}"
        try:
            payload = fetch_scoreboard(date_str, session)
        except (requests.RequestException, ValueError) as exc:
            log.warning("Fallo consultando el scoreboard ESPN NHL de %s (%s): %s",
                        date_str, exc.__class__.__name__, exc)
            continue
        captured_at = now if now is not None else datetime.now(timezone.utc)

        seen = _not_yet_started(parse_goalie_probables(payload), captured_at)
        active = _not_yet_started(parse_active_sides(payload), captured_at)

        total_seen += len(seen)
        total_appended += log_goalie_probable_capture(
            root, seen, source_run=source_run, captured_at=captured_at,
            active_pairs=active)

    return total_seen, total_appended
