"""ESPN public tennis scoreboard as a results vendor (closes the tennis audit
gap: The Odds API has no tennis scores).

Tennis is structured differently from team sports: the ESPN scoreboard "event"
is a TOURNAMENT (e.g. Roland Garros) whose `groupings` (singles/doubles/quali)
each hold many `competitions` (individual matches), one per match with its own
date, status and two `competitors` carrying an `athlete` and a `winner` flag.

Free and unauthenticated; unofficial endpoint, so the schema may change without
notice -- the backfill reports per-tour counts to surface silent breakage.

Player ratings in tennis are TOUR-WIDE (per player), not per tournament, so this
provider is keyed by tour (atp/wta) derived from the league/sport key.
"""
from __future__ import annotations
import time
from datetime import timedelta
import requests
from sqp.exceptions import ProviderNotConfiguredError
from sqp.logging_config import get_logger
from .base import ResultsProvider
from .date_window import fetch_window

log = get_logger("sqp.espn_tennis")

BASE = "https://site.api.espn.com/apis/site/v2/sports/tennis"
# 429 incluido igual que en `odds_api` (auditoria 2026-07-29, D-05): un
# backfill anual dia-a-dia son ~367 peticiones seguidas contra un endpoint
# no oficial, que es justo donde un rate limit es esperable (N4-M-7).
_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = 2.0
_STEP_DAYS = 7  # tournaments span ~1-2 weeks; step weekly to catch every one


def tour_from_league(league: str) -> str | None:
    """'atp' or 'wta' from a tennis league id / sport key, else None.
    Accepts 'atp', 'wta', or The Odds API keys like 'tennis_atp_wimbledon'."""
    s = (league or "").lower()
    if "atp" in s:
        return "atp"
    if "wta" in s:
        return "wta"
    return None


def parse_tennis_scoreboard(payload: dict, since: str | None = None) -> list[dict]:
    """Completed SINGLES matches from one scoreboard payload, in ResultsProvider
    dict format. Doubles (competitors without a single athlete) are skipped.
    `since` ('YYYY-MM-DD') keeps only matches on/after that date."""
    out: list[dict] = []
    for ev in payload.get("events", []):
        for grouping in ev.get("groupings", []):
            for c in grouping.get("competitions", []):
                status = (c.get("status") or {}).get("type", {})
                if not status.get("completed"):
                    continue
                comps = c.get("competitors", [])
                if len(comps) != 2:
                    continue
                names: list[str] = []
                winner_idx: int | None = None
                for i, x in enumerate(comps):
                    ath = x.get("athlete") or {}
                    name = ath.get("displayName") or ath.get("fullName")
                    if not name:  # doubles / missing athlete -> not a singles match
                        names = []
                        break
                    names.append(name)
                    if x.get("winner"):
                        winner_idx = i
                if len(names) != 2 or winner_idx is None:
                    continue
                day = str(c.get("date", ""))[:10]
                if since and day < since:
                    continue
                # Orient home=winner so home_score>away_score; the winner is what
                # ratings and settlement need (no scoreline beyond win/loss).
                home, away = names[winner_idx], names[1 - winner_idx]
                out.append({"date": day, "home": home, "away": away,
                            "home_score": 1, "away_score": 0, "neutral": True,
                            "game_id": str(c.get("id", "")), "winner": home})
    return out


class ESPNTennisResultsProvider(ResultsProvider):
    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def fetch_results(self, league: str = "atp", days_back: int = 365) -> list[dict]:
        tour = tour_from_league(league)
        if tour is None:
            raise ProviderNotConfiguredError(
                f"Cannot derive an ESPN tennis tour (atp/wta) from league '{league}'.")
        # Anclado en UTC y con un dia de margen por lado: ver date_window.py.
        start, end = fetch_window(days_back)
        since = start.isoformat()
        by_id: dict[str, dict] = {}
        day = start
        while day <= end:
            for m in self._fetch(tour, f"{day:%Y%m%d}", since):
                by_id[m["game_id"]] = m  # dedupe matches seen across overlapping queries
            day += timedelta(days=_STEP_DAYS)
        return sorted(by_id.values(), key=lambda r: r["date"])

    def _fetch(self, tour: str, dates: str, since: str) -> list[dict]:
        url = f"{BASE}/{tour}/scoreboard"
        last_error: str | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                r = self.session.get(url, params={"dates": dates}, timeout=60)
                if r.status_code == 404:
                    return []
                if r.status_code in _RETRY_STATUS:
                    last_error = f"{r.status_code} {r.reason}"
                else:
                    r.raise_for_status()
                    return parse_tennis_scoreboard(r.json(), since=since)
            # `RequestException` y `ValueError` ademas de los dos de red: el
            # docstring promete SALTAR la ventana, pero un cuerpo no-JSON
            # (`r.json()` -> ValueError) o cualquier otra RequestException
            # subia y mataba el backfill entero de la liga, perdiendo
            # tambien las ventanas ya descargadas (N4-M-7).
            except (requests.RequestException, ValueError) as exc:
                last_error = f"{exc.__class__.__name__}: {exc}"
            if attempt < _MAX_ATTEMPTS:
                time.sleep(_BACKOFF_SECONDS * attempt)
        log.warning("[tennis/%s] ESPN window %s failed after %d attempts (%s); skipped.",
                    tour, dates, _MAX_ATTEMPTS, last_error)
        return []
