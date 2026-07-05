"""The Odds API client (primary odds provider). https://the-odds-api.com

- API key from env only (never hardcoded).
- Featured markets: h2h, spreads, totals.
- Soccer h2h is 3-way (1X2). Tennis sport keys are per-tournament and carry
  NO scores in this API: tennis settlement requires a secondary results source.
- /scores endpoint feeds ratings and settlement for leagues marked has_scores.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import cast

import requests
from sqp.exceptions import ProviderNotConfiguredError
from sqp.domain.models import Event, EventOdds, MarketLine
from sqp.providers.odds_cache import FileCache

BASE = "https://api.the-odds-api.com/v4"

_TRUTHY = ("1", "true", "yes", "on")


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in _TRUTHY

# Verified against the official sports list (the-odds-api.com), 2026-06.
SPORT_KEYS: dict[str, dict] = {
    # league_id: {sport_key, family, three_way, has_scores}
    "mlb":    {"sport_key": "baseball_mlb",          "family": "baseball",   "three_way": False, "has_scores": True},
    "nba":    {"sport_key": "basketball_nba",        "family": "basketball", "three_way": False, "has_scores": True},
    "wnba":   {"sport_key": "basketball_wnba",       "family": "basketball", "three_way": False, "has_scores": True},
    "ncaab":  {"sport_key": "basketball_ncaab",      "family": "basketball", "three_way": False, "has_scores": True},
    "wncaab": {"sport_key": "basketball_wncaab",     "family": "basketball", "three_way": False, "has_scores": True},
    "nfl":    {"sport_key": "americanfootball_nfl",  "family": "football",   "three_way": False, "has_scores": True},
    "ncaaf":  {"sport_key": "americanfootball_ncaaf","family": "football",   "three_way": False, "has_scores": True},
    "nhl":    {"sport_key": "icehockey_nhl",         "family": "hockey",     "three_way": False, "has_scores": True},
    # soccer leagues are loaded dynamically from configs/leagues/soccer.yaml (family=soccer, three_way=True)
    # tennis tournaments are discovered dynamically via /sports (family=tennis, has_scores=False)
}


class OddsAPIClient:
    def __init__(self, api_key: str | None, regions: str = "us,eu", odds_format: str = "decimal",
                 session: requests.Session | None = None, *,
                 cache_ttl: float | None = None, force_refresh: bool | None = None,
                 offline_mode: bool | None = None, cache_dir: Path | None = None):
        if odds_format != "decimal":
            # Prices are persisted as price_decimal; american prices would be
            # stored in a decimal field and silently corrupt every probability.
            raise ValueError(
                f"OddsAPIClient stores prices as decimal; odds_format must be "
                f"'decimal', got '{odds_format}'. Set ODDS_API_ODDS_FORMAT=decimal.")
        self.api_key = api_key
        self.regions = regions
        self.odds_format = odds_format
        self.session = session or requests.Session()
        self._sports_cache: dict[str, dict] | None = None
        # Live quota, refreshed from response headers on every call (None until
        # the first request). Used by the budget guard in the daily orchestrator.
        self.requests_remaining: int | None = None
        self.requests_used: int | None = None
        self.requests_last: int | None = None  # credit cost of the most recent call
        # True when the most recent _get was served from the on-disk cache (no
        # network call, no credit spent). Lets callers skip side effects that must
        # happen once per real fetch (e.g. persisting an odds snapshot).
        self.last_response_cached: bool = False
        # On-disk TTL cache for paid endpoints: re-running within the TTL costs no
        # credits. Wired to .env (ODDS_CACHE_TTL_SECONDS / FORCE_REFRESH /
        # OFFLINE_MODE); the free /sports list is never cached.
        self.cache_ttl = float(cache_ttl if cache_ttl is not None else os.getenv(
            "ODDS_CACHE_TTL_SECONDS", os.getenv("CACHE_TTL_SECONDS", "21600")))
        self.force_refresh = _env_flag("FORCE_REFRESH") if force_refresh is None else force_refresh
        self.offline_mode = _env_flag("OFFLINE_MODE") if offline_mode is None else offline_mode
        if cache_dir is None:
            from sqp.config import ROOT
            cache_dir = ROOT / "data" / "cache" / "odds"
        self._cache = FileCache(cache_dir)

    def _require_key(self):
        if not self.api_key:
            raise ProviderNotConfiguredError(
                "ODDS_API_KEY is missing. Set it in .env or run with SQP_MODE=demo.")

    def _get(self, path: str, *, cache: bool = False, **params) -> list | dict:
        self.last_response_cached = False
        ckey = self._cache.key(path, params) if cache else None
        if ckey is not None and not self.force_refresh:
            ttl = float("inf") if self.offline_mode else self.cache_ttl
            hit = self._cache.get(ckey, ttl)
            if hit is not None:
                self.last_response_cached = True
                return hit
        if cache and self.offline_mode:
            raise ProviderNotConfiguredError(
                f"OFFLINE_MODE active and no cached response for {path}.")
        self._require_key()
        params["apiKey"] = self.api_key
        r = self.session.get(f"{BASE}{path}", params=params, timeout=30)
        r.raise_for_status()
        self._capture_quota(getattr(r, "headers", {}) or {})
        data = r.json()
        if ckey is not None:
            self._cache.put(ckey, data)
        return data

    def _capture_quota(self, headers) -> None:
        for attr, key in (("requests_remaining", "x-requests-remaining"),
                          ("requests_used", "x-requests-used"),
                          ("requests_last", "x-requests-last")):
            val = headers.get(key)
            if val is not None:
                try:
                    setattr(self, attr, int(val))
                except (TypeError, ValueError):
                    pass

    def list_sports(self, all_sports: bool = True) -> list[dict]:
        return cast("list[dict]", self._get("/sports", all="true" if all_sports else "false"))

    def is_sport_active(self, sport_key: str) -> bool | None:
        """Whether the sport is currently in season per /sports (cached per client).

        Returns None when the key is unknown to the API. /sports does not
        consume request quota.
        """
        if self._sports_cache is None:
            self._sports_cache = {s["key"]: s for s in self.list_sports(all_sports=True)}
        sport = self._sports_cache.get(sport_key)
        return None if sport is None else bool(sport.get("active", False))

    def _parse_events(self, raw: list, sport_key: str, league_id: str) -> list[EventOdds]:
        """Shared parser for live and historical odds payloads (same event shape)."""
        out: list[EventOdds] = []
        for ev in raw:
            event = Event(event_id=ev["id"], sport_key=sport_key, league=league_id,
                          home=ev["home_team"], away=ev["away_team"],
                          start_time=ev["commence_time"], data_label="real")
            lines: list[MarketLine] = []
            for bm in ev.get("bookmakers", []):
                for mk in bm.get("markets", []):
                    for oc in mk.get("outcomes", []):
                        lines.append(MarketLine(
                            market=mk["key"], bookmaker=bm["key"], outcome=oc["name"],
                            price_decimal=float(oc["price"]), point=oc.get("point")))
            out.append(EventOdds(event=event, lines=lines))
        return out

    def fetch_odds(self, league_id: str, sport_key: str, markets: str = "h2h,spreads,totals") -> list[EventOdds]:
        raw = self._get(f"/sports/{sport_key}/odds", cache=True, regions=self.regions,
                        markets=markets, oddsFormat=self.odds_format)
        return self._parse_events(cast(list, raw), sport_key, league_id)

    def fetch_historical_odds(self, sport_key: str, date_iso: str, league_id: str | None = None,
                              markets: str = "h2h,spreads,totals") -> dict:
        """Odds snapshot as it stood at an ISO-8601 UTC timestamp (paid plans only).

        The /historical endpoint costs ~10x a live call (markets x regions x 10);
        read ``requests_last`` after calling to see the real credit cost. Returns
        the snapshot's timestamp, the adjacent snapshot timestamps (for paging),
        and the parsed events.
        """
        raw = self._get(f"/historical/sports/{sport_key}/odds", cache=True, regions=self.regions,
                        markets=markets, oddsFormat=self.odds_format, date=date_iso)
        snap = raw if isinstance(raw, dict) else {}
        events = self._parse_events(snap.get("data", []) or [], sport_key, league_id or sport_key)
        return {"timestamp": snap.get("timestamp"),
                "previous_timestamp": snap.get("previous_timestamp"),
                "next_timestamp": snap.get("next_timestamp"),
                "events": events}

    def fetch_scores(self, sport_key: str, days_from: int = 3) -> list[dict]:
        """Completed games for settlement / rating updates (where supported).
        Not cached: settlement needs fresh final scores; a stale cache could grade
        not-yet-final games. Scores are cheap; correctness outweighs the saving."""
        return cast("list[dict]", self._get(f"/sports/{sport_key}/scores", daysFrom=days_from))
