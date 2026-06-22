"""Rest / back-to-back margin adjustment for basketball (NBA/WNBA).

A team playing on short rest (a back-to-back) underperforms its expected scoring
margin; a well-rested team overperforms. This shifts the expected HOME margin by
``points_per_day * (home_rest - away_rest)`` (rest days capped), so it moves the
moneyline/spread but not the total.

Leakage-safe: ``observe`` records each team's last game date and must be called
only AFTER a game is estimated (the adapters fold results in walk-forward), so a
game's rest uses past games only. Rest is unknown for a team's first game -> no
adjustment. With ``points_per_day == 0`` the adjustment is always 0 (a no-op),
which is how the signal ships OFF until an out-of-sample check justifies it.
"""
from __future__ import annotations

from datetime import date as _date
from typing import Callable


class RestModel:
    def __init__(self, points_per_day: float = 0.0, max_rest: int = 4,
                 normalize: Callable[[str | None], str] | None = None) -> None:
        self.points_per_day = points_per_day
        self.max_rest = max_rest
        self.nk = normalize or (lambda s: s)
        self._last_date: dict[str, str] = {}

    def observe(self, home: str, away: str, game_date: str | None) -> None:
        if not game_date:
            return
        day = str(game_date)[:10]
        self._last_date[self.nk(home)] = day
        self._last_date[self.nk(away)] = day

    def rest_days(self, team: str, game_date: str | None) -> int | None:
        """Capped days since the team's last game, or None if unknown."""
        last = self._last_date.get(self.nk(team))
        if not last or not game_date:
            return None
        try:
            d = (_date.fromisoformat(str(game_date)[:10]) - _date.fromisoformat(last)).days
        except ValueError:
            return None
        return max(0, min(d, self.max_rest))

    def margin_adjustment(self, home: str, away: str, game_date: str | None) -> float:
        """Points to add to the expected HOME margin from the rest differential.
        0 when disabled, on a first game, or with unparseable dates."""
        if self.points_per_day == 0.0:
            return 0.0
        hr = self.rest_days(home, game_date)
        ar = self.rest_days(away, game_date)
        if hr is None or ar is None:
            return 0.0
        return self.points_per_day * (hr - ar)
