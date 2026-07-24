"""ESPN public scoreboard API (site.api.espn.com) as historical results vendor.

Free and unauthenticated; used to backfill full-season final scores so ratings
are not limited to The Odds API 3-day scores window. Unofficial endpoint: the
schema may change without notice, so the backfill script reports per-league
counts to make silent breakage visible.
"""
from __future__ import annotations
import time
from datetime import date, timedelta
import requests
from sqp.exceptions import ProviderNotConfiguredError
from sqp.logging_config import get_logger
from .base import ResultsProvider

log = get_logger("sqp.espn")

BASE = "https://site.api.espn.com/apis/site/v2/sports"

# ESPN's unofficial endpoint intermittently 5xx's specific date chunks (often
# offseason windows). Retry transient server errors, then skip the chunk so one
# bad window never aborts a whole league's multi-year backfill.
_RETRY_STATUS = frozenset({500, 502, 503, 504})
_MAX_ATTEMPTS = 4
_BACKOFF_SECONDS = 2.0  # multiplied by attempt number (linear backoff)

# league_id -> ESPN scoreboard config. Soccer slugs use ESPN's country.tier scheme.
# College basketball rejects date ranges (404) and defaults to top-25 games only,
# so it needs day_by_day queries with groups=50 (full Division I). Verified 2026-06.
ESPN_PATHS: dict[str, dict] = {
    "mlb":         {"path": "baseball/mlb"},
    "nba":         {"path": "basketball/nba"},
    "wnba":        {"path": "basketball/wnba"},
    "ncaab":       {"path": "basketball/mens-college-basketball",
                    "day_by_day": True, "params": {"groups": 50}},
    "wncaab":      {"path": "basketball/womens-college-basketball",
                    "day_by_day": True, "params": {"groups": 50}},
    "nfl":         {"path": "football/nfl"},
    "ncaaf":       {"path": "football/college-football"},
    "nhl":         {"path": "hockey/nhl"},
    "epl":         {"path": "soccer/eng.1"},
    "laliga":      {"path": "soccer/esp.1"},
    "bundesliga":  {"path": "soccer/ger.1"},
    "seriea":      {"path": "soccer/ita.1"},
    "ligue1":      {"path": "soccer/fra.1"},
    "ucl":         {"path": "soccer/uefa.champions"},
    "ligamx":      {"path": "soccer/mex.1"},
    "mls":         {"path": "soccer/usa.1"},
    "brasileirao": {"path": "soccer/bra.1"},
    "chile":       {"path": "soccer/chi.1"},
    "uwcl":        {"path": "soccer/uefa.wchampions"},
    # frauen_bundesliga: NOT available on ESPN (no German women's league in its
    # catalog as of 2026-06); needs a different results vendor.
}

_CHUNK_DAYS = 30  # range queries are capped server-side; chunk to avoid dropped events


class ESPNResultsProvider(ResultsProvider):
    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def fetch_results(self, league: str, days_back: int = 365) -> list[dict]:
        cfg = ESPN_PATHS.get(league)
        if cfg is None:
            raise ProviderNotConfiguredError(
                f"No ESPN scoreboard path registered for league '{league}'. "
                "Add it to ESPN_PATHS in sqp/providers/espn_results.py.")
        end = date.today()
        start = end - timedelta(days=days_back)
        out: list[dict] = []
        if cfg.get("day_by_day", False):
            day = start
            while day <= end:
                out.extend(self._fetch(cfg, f"{day:%Y%m%d}"))
                day += timedelta(days=1)
                # Pausa de cortesia: el backfill anual dispara ~365 requests
                # seguidos contra un endpoint no oficial (auditoria 2026-07-24, M-12).
                if day <= end:
                    time.sleep(0.3)
        else:
            chunk_start = start
            while chunk_start <= end:
                chunk_end = min(chunk_start + timedelta(days=_CHUNK_DAYS - 1), end)
                out.extend(self._fetch(cfg, f"{chunk_start:%Y%m%d}-{chunk_end:%Y%m%d}"))
                chunk_start = chunk_end + timedelta(days=1)
        out.sort(key=lambda r: r["date"])
        return out

    def _fetch(self, cfg: dict, dates: str) -> list[dict]:
        """Fetch one date window. Retries transient 5xx/timeouts with linear
        backoff; if the window keeps failing it is skipped (logged) instead of
        aborting the whole league backfill."""
        params = {"dates": dates, "limit": 500, **cfg.get("params", {})}
        url = f"{BASE}/{cfg['path']}/scoreboard"
        last_error: str | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                r = self.session.get(url, params=params, timeout=60)
                if r.status_code == 404:
                    return []  # ESPN 404s some offseason dates instead of empty events
                if r.status_code in _RETRY_STATUS:
                    last_error = f"{r.status_code} {r.reason}"
                else:
                    r.raise_for_status()
                    return parse_scoreboard(r.json())
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = str(exc)
            if attempt < _MAX_ATTEMPTS:
                time.sleep(_BACKOFF_SECONDS * attempt)
        log.warning("[%s] ESPN window %s failed after %d attempts (%s); "
                    "skipping this window, keeping the rest.",
                    cfg["path"], dates, _MAX_ATTEMPTS, last_error)
        return []


def parse_scoreboard(payload: dict) -> list[dict]:
    """Completed events only, in ResultsProvider dict format."""
    out: list[dict] = []
    for ev in payload.get("events", []):
        comp = (ev.get("competitions") or [{}])[0]
        status = (comp.get("status") or ev.get("status") or {}).get("type", {})
        if not status.get("completed"):
            continue
        home = away = None
        for c in comp.get("competitors", []):
            if c.get("homeAway") == "home":
                home = c
            elif c.get("homeAway") == "away":
                away = c
        if not home or not away:
            continue
        try:
            home_score = int(float(home["score"]))
            away_score = int(float(away["score"]))
        except (KeyError, TypeError, ValueError):
            continue
        out.append({"date": str(ev.get("date", ""))[:10],
                    "home": home["team"]["displayName"],
                    "away": away["team"]["displayName"],
                    "home_score": home_score, "away_score": away_score,
                    "neutral": bool(comp.get("neutralSite", False)),
                    "game_id": str(ev.get("id", ""))})
    return out
