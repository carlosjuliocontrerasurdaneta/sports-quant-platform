"""MLB public Stats API abstraction (statsapi.mlb.com).

Used for: schedule, probable pitchers, historical results. This is the only
stats vendor assumed by default (it is public). Other leagues need configured
vendors or demo mode.
"""
from __future__ import annotations
import requests
from .base import ResultsProvider

BASE = "https://statsapi.mlb.com/api/v1"


class MLBStatsProvider(ResultsProvider):
    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def fetch_results(self, league: str = "mlb", days_back: int = 365) -> list[dict]:
        from datetime import date, timedelta
        end = date.today()
        start = end - timedelta(days=days_back)
        r = self.session.get(f"{BASE}/schedule", params={
            "sportId": 1, "startDate": start.isoformat(), "endDate": end.isoformat(),
            "gameType": "R"}, timeout=60)
        r.raise_for_status()
        out = []
        for d in r.json().get("dates", []):
            for g in d.get("games", []):
                status = g.get("status", {})
                if status.get("abstractGameState") != "Final":
                    continue
                # Postponed/cancelled games also report abstractGameState=Final,
                # with no score keys: defaulting them to 0-0 fabricates ties.
                if status.get("detailedState", "").startswith(("Postponed", "Cancelled", "Suspended")):
                    continue
                teams = g["teams"]
                if "score" not in teams["home"] or "score" not in teams["away"]:
                    continue
                out.append({
                    "date": d["date"],
                    "home": teams["home"]["team"]["name"],
                    "away": teams["away"]["team"]["name"],
                    "home_score": teams["home"]["score"],
                    "away_score": teams["away"]["score"],
                    "neutral": False,
                    "game_id": str(g.get("gamePk", "")),  # distinguishes doubleheaders
                })
        return out

    def fetch_starters(self, days_back: int = 365) -> list[dict]:
        """Starter map per game keyed by gamePk. Uses probablePitcher hydration:
        for past games it reflects the announced starter (per-game boxscore
        confirmation is the planned upgrade)."""
        from datetime import date, timedelta
        end = date.today()
        start = end - timedelta(days=days_back)
        r = self.session.get(f"{BASE}/schedule", params={
            "sportId": 1, "startDate": start.isoformat(), "endDate": end.isoformat(),
            "gameType": "R", "hydrate": "probablePitcher"}, timeout=120)
        r.raise_for_status()
        out = []
        for d in r.json().get("dates", []):
            for g in d.get("games", []):
                t = g["teams"]
                out.append({
                    "game_id": str(g.get("gamePk", "")),
                    "date": d["date"],
                    "home_starter": t["home"].get("probablePitcher", {}).get("fullName"),
                    "away_starter": t["away"].get("probablePitcher", {}).get("fullName"),
                })
        return out

    def fetch_starter_fip(self, days_back: int = 365, log=None) -> list[dict]:
        """Per-start FIP for both starters of every completed game (v2 signal).

        One boxscore request PER GAME (~2,400 for a season); free but slow, so
        this is a one-off backfill, not a per-run fetch. Returns rows:
        {game_id, date, home_starter, home_starter_fip, away_starter,
        away_starter_fip}; a side with no identifiable start or IP=0 gets None."""
        from datetime import date, timedelta
        from sqp.models.fip import fip_from_line
        end = date.today()
        start = end - timedelta(days=days_back)
        r = self.session.get(f"{BASE}/schedule", params={
            "sportId": 1, "startDate": start.isoformat(), "endDate": end.isoformat(),
            "gameType": "R"}, timeout=120)
        r.raise_for_status()
        games = [(g.get("gamePk"), d["date"]) for d in r.json().get("dates", [])
                 for g in d.get("games", [])
                 if g.get("status", {}).get("abstractGameState") == "Final"
                 and not g.get("status", {}).get("detailedState", "").startswith(
                     ("Postponed", "Cancelled", "Suspended"))]
        out = []
        for i, (gpk, day) in enumerate(games):
            try:
                box = self.session.get(f"{BASE}/game/{gpk}/boxscore", timeout=60).json()
            except Exception as exc:  # one bad game must not abort the backfill
                if log:
                    log.warning("boxscore %s failed: %s", gpk, exc)
                continue
            row = {"game_id": str(gpk), "date": day}
            for side in ("home", "away"):
                name, fip = self._starter_fip(box, side, fip_from_line)
                row[f"{side}_starter"] = name
                row[f"{side}_starter_fip"] = fip
            out.append(row)
            if log and (i + 1) % 250 == 0:
                log.info("FIP backfill progress: %d/%d games", i + 1, len(games))
        return out

    @staticmethod
    def _starter_fip(box: dict, side: str, fip_fn) -> tuple[str | None, float | None]:
        """Starter name and per-start FIP for one side; the starter is the first
        listed pitcher (confirmed via gamesStarted==1)."""
        team = box.get("teams", {}).get(side, {})
        pitchers = team.get("pitchers") or []
        if not pitchers:
            return None, None
        pl = team.get("players", {}).get(f"ID{pitchers[0]}", {})
        pit = pl.get("stats", {}).get("pitching", {})
        if str(pit.get("gamesStarted", "0")) != "1":
            return pl.get("person", {}).get("fullName"), None
        fip = fip_fn(int(pit.get("homeRuns", 0)), int(pit.get("baseOnBalls", 0)),
                     int(pit.get("hitByPitch", 0)), int(pit.get("strikeOuts", 0)),
                     pit.get("inningsPitched", "0.0"))
        return pl.get("person", {}).get("fullName"), fip

    def fetch_probable_pitchers(self, date_iso: str) -> list[dict]:
        r = self.session.get(f"{BASE}/schedule", params={
            "sportId": 1, "date": date_iso, "hydrate": "probablePitcher"}, timeout=60)
        r.raise_for_status()
        out = []
        for d in r.json().get("dates", []):
            for g in d.get("games", []):
                t = g["teams"]
                out.append({
                    "date": d["date"],          # official MLB game date
                    "commence": g.get("gameDate"),  # UTC start; disambiguates a series
                    "home": t["home"]["team"]["name"], "away": t["away"]["team"]["name"],
                    "home_pitcher": t["home"].get("probablePitcher", {}).get("fullName"),
                    "away_pitcher": t["away"].get("probablePitcher", {}).get("fullName"),
                })
        return out
