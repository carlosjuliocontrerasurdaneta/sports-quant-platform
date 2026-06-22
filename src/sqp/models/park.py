"""Ballpark run-environment factors for baseball totals.

A park factor scales the expected total toward the home venue's scoring
environment: hitter parks (Coors) inflate totals, pitcher parks deflate them.
Estimated the classic way -- a team's total runs in its HOME games vs the same
team's total runs in its AWAY games -- so the team's own scoring level cancels
out and what remains is (mostly) the venue. The home venue is proxied by the
home team (one park per team per season).

Leakage-safe: ``update`` must be called only AFTER a game is estimated (the
adapters fold results in walk-forward), so a game's factor uses past games only.
Low-sample teams regress to a neutral 1.0; ``bound`` caps the multiplier. With
``bound == 0`` the factor is always 1.0 (a no-op), which is how the signal ships
OFF until an out-of-sample check justifies it.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Callable


class ParkFactors:
    def __init__(self, prior_games: float = 20.0, bound: float = 0.0,
                 normalize: Callable[[str | None], str] | None = None) -> None:
        self.prior_games = prior_games
        self.bound = bound
        self.nk = normalize or (lambda s: s)
        self._home_runs: dict[str, float] = defaultdict(float)
        self._home_n: dict[str, int] = defaultdict(int)
        self._away_runs: dict[str, float] = defaultdict(float)
        self._away_n: dict[str, int] = defaultdict(int)

    def update(self, home: str, away: str, total_runs: float) -> None:
        """Fold one completed game: the home team played a HOME game and the away
        team an AWAY game, both with the same observed total runs."""
        h, a = self.nk(home), self.nk(away)
        self._home_runs[h] += total_runs
        self._home_n[h] += 1
        self._away_runs[a] += total_runs
        self._away_n[a] += 1

    def factor(self, home: str | None) -> float:
        """Bounded park multiplier for ``home``'s venue (1.0 = neutral / unknown).

        raw = home_total_avg / away_total_avg for the home team; regressed toward
        1.0 by the smaller of the two sample sizes, then clamped to [1-bound,
        1+bound]."""
        h = self.nk(home)
        hn, an = self._home_n.get(h, 0), self._away_n.get(h, 0)
        if hn == 0 or an == 0:
            return 1.0
        away_avg = self._away_runs[h] / an
        if away_avg <= 0:
            return 1.0
        raw = (self._home_runs[h] / hn) / away_avg
        w = min(hn, an) / (min(hn, an) + self.prior_games)
        f = 1.0 + w * (raw - 1.0)
        return max(1.0 - self.bound, min(1.0 + self.bound, f))

    def is_known(self, home: str | None) -> bool:
        h = self.nk(home)
        return self._home_n.get(h, 0) > 0 and self._away_n.get(h, 0) > 0
