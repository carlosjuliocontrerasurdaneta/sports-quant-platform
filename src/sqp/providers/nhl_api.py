"""NHL public API (api-web.nhle.com) as goalie-starter vendor.

Free, unauthenticated and undocumented (no published rate limit). Used
exclusively for goalie data: ESPN's own scoreboard/summary does NOT carry a
`starter` flag for NHL (verified 2026-09-26 with test calls across four
`game_id` eras -- see `docs/research/2026-09-26-preregistro-portero-nhl.md`,
section 3.2), so deducing the starter from ESPN's box score would require
guessing from time-on-ice, which is biased against a starter pulled early
after a bad period.

Two endpoints:

- ``/v1/score/{date}``: the day's schedule + final score, keyed by the NHL's
  LOCAL calendar date. Used only to discover which game ids fall on a given
  UTC date (via each game's own `startTimeUTC`), never for the score itself
  (the historical result of record is ESPN's, via `ResultsStore`).
- ``/v1/gamecenter/{id}/boxscore``: per-goalie `starter`, `toi`,
  `shotsAgainst`, `saves`, confirmed present as far back as the 2007-08
  season in test calls.

Rate limiting is the CALLER's responsibility (the backfill script paces
requests at 1/s per the pre-registro); this module only retries a single
request that failed transiently.
"""
from __future__ import annotations

import time
from typing import Any

import requests

from sqp.logging_config import get_logger
from sqp.providers.espn_results import retry_wait_seconds

log = get_logger("sqp.providers.nhl_api")

BASE = "https://api-web.nhle.com/v1"

# Mismo criterio que espn_results.py / mlb_statsapi.py: 429/5xx se reintentan
# con espera lineal; el resto de errores sube de inmediato.
_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
_MAX_ATTEMPTS = 4
_BACKOFF_SECONDS = 2.0
_DEFAULT_TIMEOUT_S = 20.0  # pre-registro seccion 3.3: timeout=20


def _get_with_retry(session: requests.Session, url: str, **kwargs: Any) -> requests.Response:
    """GET con timeout obligatorio y reintento lineal en 429/5xx/red.

    Respeta `Retry-After` si el servidor lo manda (igual que
    `espn_results.retry_wait_seconds`, reutilizada aqui en vez de duplicada)."""
    kwargs.setdefault("timeout", _DEFAULT_TIMEOUT_S)
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        r: requests.Response | None = None
        try:
            r = session.get(url, **kwargs)
            if getattr(r, "status_code", None) not in _RETRY_STATUS:
                r.raise_for_status()
                return r
            last_exc = requests.HTTPError(response=r)
        except requests.RequestException as exc:
            last_exc = exc
        if attempt < _MAX_ATTEMPTS:
            time.sleep(retry_wait_seconds(r, attempt, _BACKOFF_SECONDS))
    assert last_exc is not None
    raise last_exc


def fetch_score(date_str: str, session: requests.Session) -> dict:
    """Raw `/v1/score/{date}` payload for one LOCAL calendar date (YYYY-MM-DD)."""
    return _get_with_retry(session, f"{BASE}/score/{date_str}").json()


def fetch_boxscore(nhl_game_id: str, session: requests.Session) -> dict:
    """Raw `/v1/gamecenter/{id}/boxscore` payload for one NHL game id."""
    return _get_with_retry(session, f"{BASE}/gamecenter/{nhl_game_id}/boxscore").json()


# `gameState` values observed on `/v1/gamecenter/{id}/boxscore`: a completed
# game is "OFF" (officially over) or "FINAL"; everything else (LIVE, CRIT,
# FUT, PRE...) is a game that has not finished yet. A boxscore's stats are
# only immutable once the game is over -- ingesting a LIVE/CRIT snapshot would
# freeze partial stats forever, because `GoalieAppearanceStore.save` dedupes
# by keeping the FIRST row it ever sees for a (game, side, goalie) (revision
# independiente de Fable, B2, 2026-09-26).
FINAL_GAME_STATES = frozenset({"OFF", "FINAL"})


def is_final_game_state(payload: dict) -> bool:
    """True only if the boxscore's own `gameState` says the game is over."""
    return str(payload.get("gameState") or "").upper() in FINAL_GAME_STATES


def parse_score_games(payload: dict) -> list[dict]:
    """Games listed in a `/v1/score/{date}` payload, in a compact form used to
    decide which UTC date each game belongs to and to look up its box score.

    Returns: nhl_game_id, game_type (1 preseason/2 regular/3 playoffs),
    start_time_utc (full ISO), date_utc (its first 10 chars),
    home_name/away_name (NHL's own short/common name for that team AT THAT
    TIME -- e.g. "Coyotes" in Phoenix-era games, "Ducks" even in the 2005-06
    Mighty Ducks season; see `sqp.sports.nhl_goalie_matching`)."""
    out = []
    for g in payload.get("games", []):
        start = str(g.get("startTimeUTC") or "")
        if not start:
            continue
        home = g.get("homeTeam") or {}
        away = g.get("awayTeam") or {}
        out.append({
            "nhl_game_id": str(g.get("id", "")),
            "game_type": g.get("gameType"),
            "start_time_utc": start,
            "date_utc": start[:10],
            "home_name": (home.get("name") or {}).get("default", ""),
            "away_name": (away.get("name") or {}).get("default", ""),
        })
    return out


def parse_boxscore_goalies(payload: dict, nhl_game_id: str) -> list[dict]:
    """Every goalie appearance (starter and backup, including a backup who
    never touched the ice) from a `/v1/gamecenter/{id}/boxscore` payload.

    One row per (side, goalie). A goalie with `starter` missing entirely
    (older seasons / malformed payload) is skipped rather than guessed at --
    that game side is simply left unmatched, which the backfill's coverage
    report surfaces by name (pre-registro section 3.3, "cobertura, no
    umbral")."""
    stats = payload.get("playerByGameStats") or {}
    game_type = payload.get("gameType")
    start_time_utc = str(payload.get("startTimeUTC") or "")
    out: list[dict] = []
    for side, key in (("home", "homeTeam"), ("away", "awayTeam")):
        for g in (stats.get(key) or {}).get("goalies", []):
            if "starter" not in g:
                continue
            name = g.get("name") or {}
            out.append({
                "nhl_game_id": str(nhl_game_id),
                "game_type": game_type,
                "start_time_utc": start_time_utc,
                "team_side": side,
                "goalie_player_id": str(g.get("playerId", "")),
                "goalie_name": name.get("default", ""),
                "starter": bool(g.get("starter")),
                "shots_against": g.get("shotsAgainst"),
                "saves": g.get("saves"),
                "goals_against": g.get("goalsAgainst"),
                "toi": g.get("toi"),
            })
    return out
