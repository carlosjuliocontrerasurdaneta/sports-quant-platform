"""ESPN NHL scoreboard as the goalie-PROBABLES vendor (prospective capture
only; the API here never says who the actual titular was -- that comes from
`sqp.providers.nhl_api`, the official NHL boxscore).

`docs/research/2026-09-26-preregistro-portero-nhl.md`, section 12: ESPN
publishes a `probables` array per competitor on the scoreboard, but keeps no
history of when the announcement was made or changed. The status field was
flagged in the pre-registro as needing verification at implementation time
("Probable"/"Confirmed", to be confirmed) -- live calls on 2026-09-26 across
several look-ahead dates show the ACTUAL values are "Confirmed" and
"Expected" (never "Probable"). Both are stored as observed, unfiltered; no
value is invented.
"""
from __future__ import annotations

import time

import requests

from sqp.logging_config import get_logger
from sqp.providers.espn_results import retry_wait_seconds

log = get_logger("sqp.providers.espn_goalies")

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard"

_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
_MAX_ATTEMPTS = 4
_BACKOFF_SECONDS = 2.0
_DEFAULT_TIMEOUT_S = 20.0


def fetch_scoreboard(date_str: str, session: requests.Session) -> dict:
    """Raw ESPN NHL scoreboard payload for one UTC calendar date (YYYYMMDD).

    Retries transient 429/5xx/network errors with linear backoff (respecting
    `Retry-After`); a persistently failing date raises, so the caller (a
    best-effort capture step) can log and move on rather than fabricate an
    empty result that looks like "no games"."""
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        r: requests.Response | None = None
        try:
            r = session.get(SCOREBOARD_URL, params={"dates": date_str},
                             timeout=_DEFAULT_TIMEOUT_S)
            if getattr(r, "status_code", None) not in _RETRY_STATUS:
                r.raise_for_status()
                return dict(r.json())
            last_exc = requests.HTTPError(response=r)
        except (requests.RequestException, ValueError) as exc:
            last_exc = exc
        if attempt < _MAX_ATTEMPTS:
            time.sleep(retry_wait_seconds(r, attempt, _BACKOFF_SECONDS))
    assert last_exc is not None
    raise last_exc


def parse_goalie_probables(payload: dict) -> list[dict]:
    """One row per (event, team-side) that carries a `probableStartingGoalie`.

    Only events NOT YET STARTED (`status.type.completed` is False AND the
    event's start time has not passed relative to `now`, checked by the
    caller using `commence_time`) should be captured -- this function returns
    every row present in the payload; filtering by time is the caller's job
    because "now" is a capture-time concept, not a parsing concept."""
    out: list[dict] = []
    for ev in payload.get("events", []):
        event_id = str(ev.get("id", ""))
        commence_time = str(ev.get("date", ""))
        completed = bool(((ev.get("status") or {}).get("type") or {}).get("completed", False))
        comp = (ev.get("competitions") or [{}])[0]
        for c in comp.get("competitors", []):
            side = c.get("homeAway")
            team = ((c.get("team") or {}).get("displayName"))
            for p in c.get("probables", []) or []:
                if p.get("name") != "probableStartingGoalie":
                    continue
                athlete = p.get("athlete") or {}
                status = p.get("status") or {}
                out.append({
                    "event_id": event_id,
                    "commence_time": commence_time,
                    "completed": completed,
                    "team_side": side,
                    "team": team,
                    "goalie_espn_id": str(athlete.get("id", "")),
                    "goalie_name": athlete.get("fullName"),
                    "status": status.get("name"),
                    "status_type": status.get("type"),
                })
    return out


def parse_active_sides(payload: dict) -> list[dict]:
    """One row per (event, team-side) present on the scoreboard, WITH or
    WITHOUT a `probableStartingGoalie` -- unlike `parse_goalie_probables`,
    which only ever returns sides that currently carry one.

    Used to detect a probable being WITHDRAWN (ESPN stops publishing one that
    was previously captured) rather than merely absent from a payload that
    never had one: the caller diffs this list's (event_id, team_side) pairs
    against `parse_goalie_probables`'s pairs for the SAME payload, and only
    treats a pair missing from the latter as a withdrawal if it was
    previously logged with a real goalie (`sqp.storage.goalies.
    log_goalie_probable_capture`'s `active_pairs`)."""
    out: list[dict] = []
    for ev in payload.get("events", []):
        event_id = str(ev.get("id", ""))
        commence_time = str(ev.get("date", ""))
        completed = bool(((ev.get("status") or {}).get("type") or {}).get("completed", False))
        comp = (ev.get("competitions") or [{}])[0]
        for c in comp.get("competitors", []):
            out.append({
                "event_id": event_id,
                "commence_time": commence_time,
                "completed": completed,
                "team_side": c.get("homeAway"),
                "team": ((c.get("team") or {}).get("displayName")),
            })
    return out
