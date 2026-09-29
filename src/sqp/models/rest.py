"""Rest / back-to-back margin adjustment for basketball (NBA/WNBA).

A team playing on short rest (a back-to-back) underperforms its expected scoring
margin; a well-rested team overperforms. This shifts the expected HOME margin by
``points_per_day * (home_rest - away_rest)`` (rest days capped), so it moves the
moneyline/spread but not the total.

Leakage-safe: ``observe`` records each team's game dates and must be called
only AFTER a game is estimated (the adapters fold results in walk-forward), so a
game's rest uses past games only. Rest is unknown for a team's first game -> no
adjustment. With ``points_per_day == 0`` the adjustment is always 0 (a no-op),
which is how the signal ships OFF until an out-of-sample check justifies it.

``rest_days``/``margin_adjustment`` use the team's most recent game date
STRICTLY BEFORE ``game_date`` (KI-070). At generation time (~12:00 local),
``results`` can already contain a game the SAME UTC day as the event being
estimated (e.g. a 02:00Z West Coast game and a 23:30Z game later that day):
naively using "the last observed date" would then see that earlier same-day
game and compute rest = 0 for the later one, a value the walk-forward engine
never produces (the engine defers a day's ``observe`` calls until that whole
UTC day is done, so it always estimates a day's games from the PREVIOUS day's
closing state -- see ``backtesting.engine.walk_forward_backtest``'s ``pending``
buffer). Keeping the last two distinct dates per team and skipping any stored
date equal to ``game_date`` makes ``RestModel`` reproduce that engine
semantics regardless of the order rows are fed to it, so the correction is
inert for the engine's own walk-forward (which never stores a same-day date
before estimating that day) and fixes the production gap instead of requiring
a separate change to the day-batching of ``SportAdapter.fit_results``.
"""
from __future__ import annotations

from datetime import date as _date
from typing import Callable


class RestModel:
    def __init__(self, points_per_day: float = 0.0, max_rest: int = 4,
                 normalize: Callable[[str | None], str] | None = None) -> None:
        self.points_per_day = points_per_day
        self.max_rest = max_rest
        self.nk = normalize or (lambda s: s or "")
        # Last two DISTINCT game dates per team (most recent last). Two, not
        # one, so `rest_days` can skip a stored date equal to `game_date`
        # itself and fall back to the true previous date -- see KI-070 above.
        self._dates: dict[str, list[str]] = {}

    def observe(self, home: str, away: str, game_date: str | None) -> None:
        if not game_date:
            return
        day = str(game_date)[:10]
        for team in (self.nk(home), self.nk(away)):
            hist = self._dates.setdefault(team, [])
            if hist and hist[-1] == day:
                continue  # already recorded for this team today
            hist.append(day)
            if len(hist) > 2:
                del hist[0]

    def rest_days(self, team: str, game_date: str | None) -> int | None:
        """Capped days since the team's most recent game STRICTLY BEFORE
        `game_date`, or None if unknown (KI-070: a stored date equal to
        `game_date` -- an already-observed same-UTC-day game -- is skipped,
        not treated as "yesterday")."""
        if not game_date:
            return None
        day = str(game_date)[:10]
        last = next((d for d in reversed(self._dates.get(self.nk(team), ())) if d < day), None)
        if last is None:
            return None
        try:
            d = (_date.fromisoformat(day) - _date.fromisoformat(last)).days
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
