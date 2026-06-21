"""Synthetic demo provider. ALL outputs are labeled demo_synthetic.

Purpose: make the platform runnable end-to-end with zero credentials so the
pipeline, math and reports can be validated. Never mix with real data.
"""
from __future__ import annotations
import numpy as np
from datetime import datetime, timedelta, timezone
from sqp.domain.models import Event, EventOdds, MarketLine
from .base import ResultsProvider

_TEAMS = {
    "baseball":   [f"Demo BB Team {c}" for c in "ABCDEFGH"],
    "basketball": [f"Demo BK Team {c}" for c in "ABCDEFGH"],
    "football":   [f"Demo FB Team {c}" for c in "ABCDEFGH"],
    "hockey":     [f"Demo HK Team {c}" for c in "ABCDEFGH"],
    "soccer":     [f"Demo SC Team {c}" for c in "ABCDEFGH"],
}
_PARAMS = {  # (avg_team_score, score_sd_for_results)
    "baseball": (4.5, 3.0), "basketball": (112, 12), "football": (22, 10),
    "hockey": (3.0, 1.8), "soccer": (1.4, 1.2),
}


class SyntheticProvider(ResultsProvider):
    def __init__(self, family: str, seed: int = 7):
        self.family = family
        self.rng = np.random.default_rng(seed)

    def fetch_results(self, league: str, days_back: int = 365) -> list[dict]:
        teams = _TEAMS[self.family]
        mu, sd = _PARAMS[self.family]
        strength = {t: self.rng.normal(0, 0.5) for t in teams}
        out = []
        for d in range(200):
            h, a = self.rng.choice(teams, 2, replace=False)
            hs = max(0, round(self.rng.normal(mu * (1 + 0.08 * strength[h]) + 0.05 * mu, sd)))
            as_ = max(0, round(self.rng.normal(mu * (1 + 0.08 * strength[a]), sd)))
            out.append({"date": f"demo-{d}", "home": h, "away": a,
                        "home_score": int(hs), "away_score": int(as_), "neutral": False})
        return out

    def fetch_odds(self, league_id: str, three_way: bool = False,
                   avg_total: float | None = None) -> list[EventOdds]:
        teams = _TEAMS[self.family]
        mu, _ = _PARAMS[self.family]
        if avg_total is not None:
            mu = avg_total / 2.0  # respect the league scoring environment
        out = []
        start = datetime.now(timezone.utc) + timedelta(hours=6)
        for i in range(3):
            h, a = teams[2 * i], teams[2 * i + 1]
            ev = Event(event_id=f"demo-{league_id}-{i}", sport_key=f"demo_{self.family}",
                       league=league_id, home=h, away=a,
                       start_time=start.isoformat(), data_label="demo_synthetic")
            ph = float(np.clip(self.rng.normal(0.55, 0.08), 0.30, 0.75))
            overround = 1.045
            lines = []
            if three_way:
                pd_ = 0.26
                pa = max(0.05, 1 - ph * (1 - pd_) - pd_)
                ph3 = max(0.05, 1 - pd_ - pa)
                s = ph3 + pd_ + pa
                ph3, pd_, pa = ph3 / s, pd_ / s, pa / s
                for name, p in [(h, ph3), ("Draw", pd_), (a, pa)]:
                    lines.append(MarketLine("h2h", "demo_book", name, round(1 / (p * overround), 3)))
            else:
                for name, p in [(h, ph), (a, 1 - ph)]:
                    lines.append(MarketLine("h2h", "demo_book", name, round(1 / (p * overround), 3)))
            spread = round((ph - 0.5) * 0.3 * mu * 2) / 2 or 0.5
            total = round(mu * 2 * 2) / 2 + 0.5
            for name, point, price in [(h, -spread, 1.91), (a, spread, 1.91)]:
                lines.append(MarketLine("spreads", "demo_book", name, price, point))
            for name, price in [("Over", 1.91), ("Under", 1.91)]:
                lines.append(MarketLine("totals", "demo_book", name, price, total))
            ev_odds = EventOdds(event=ev, lines=lines)
            out.append(ev_odds)
        return out
