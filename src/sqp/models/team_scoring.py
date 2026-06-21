"""Per-team scoring rates for Normal-margin sports (basketball, american football).

Elo measures relative STRENGTH (win probability), not the scoring ENVIRONMENT of
a specific matchup. Using one league-average total for every game makes the
totals model fire spurious Over/Under edges whenever the market total differs
from the league mean (the audit found every WNBA totals pick landing on Under).

These offense/defense rates, regressed to the league mean and updated strictly
on prior games (leak-free), give a matchup-specific expected total while leaving
the Elo-based side (moneyline/spread) model untouched. Team identity is
canonicalized with the same normalizer as Elo so ratings bind across vendors.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class TeamScoringRates:
    prior_games: float = 6.0   # regression-to-mean weight (pseudo-games at league mean)
    normalize: Optional[Callable[[str], str]] = field(default=None, repr=False, compare=False)
    points_for: dict[str, float] = field(default_factory=dict)
    points_against: dict[str, float] = field(default_factory=dict)
    games: dict[str, int] = field(default_factory=dict)
    league_points: float = 0.0     # total points scored across all team-games
    league_team_games: int = 0     # team-games seen (2 per match)

    def _key(self, team: str) -> str:
        return self.normalize(team) if self.normalize else team

    def update(self, home: str, away: str, home_score: float, away_score: float) -> None:
        hk, ak = self._key(home), self._key(away)
        self.points_for[hk] = self.points_for.get(hk, 0.0) + float(home_score)
        self.points_against[hk] = self.points_against.get(hk, 0.0) + float(away_score)
        self.games[hk] = self.games.get(hk, 0) + 1
        self.points_for[ak] = self.points_for.get(ak, 0.0) + float(away_score)
        self.points_against[ak] = self.points_against.get(ak, 0.0) + float(home_score)
        self.games[ak] = self.games.get(ak, 0) + 1
        self.league_points += float(home_score) + float(away_score)
        self.league_team_games += 2

    def league_mean(self) -> float:
        """Average points scored per team per game (0 before any data)."""
        return self.league_points / self.league_team_games if self.league_team_games else 0.0

    def _regressed(self, totals: dict[str, float], team: str, lg: float) -> float:
        k = self._key(team)
        n = self.games.get(k, 0)
        return (totals.get(k, 0.0) + self.prior_games * lg) / (n + self.prior_games)

    def offense(self, team: str, lg: float) -> float:
        return self._regressed(self.points_for, team, lg)

    def defense(self, team: str, lg: float) -> float:
        return self._regressed(self.points_against, team, lg)

    def expected_total(self, home: str, away: str, fallback_total: float) -> float:
        """Matchup expected total. Falls back to the league constant before any
        results are observed (identical to the old behavior on a cold start)."""
        lg = self.league_mean()
        if lg <= 0:
            return fallback_total
        # each side's expected points = blend of its offense and the opponent's defense
        home_pts = 0.5 * (self.offense(home, lg) + self.defense(away, lg))
        away_pts = 0.5 * (self.offense(away, lg) + self.defense(home, lg))
        return home_pts + away_pts
