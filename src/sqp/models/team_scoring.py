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
    # Exponential recency decay half-life in days; 0 = off (legacy cumulative
    # averages). Without it, rates blend every stored season equally, so a
    # league whose scoring environment drifts (WNBA 2023->2026: ~165 -> ~175)
    # projects the multi-season mean against a current-era market line and
    # fires a systematic Under bias (2026-07-04 finding: model mean p(Over)
    # 0.302 across 35 games). Decay only uses PAST dates: leak-free and
    # incremental, so walk-forward backtests stay valid.
    half_life_days: float = 0.0
    normalize: Optional[Callable[[str], str]] = field(default=None, repr=False, compare=False)
    points_for: dict[str, float] = field(default_factory=dict)
    points_against: dict[str, float] = field(default_factory=dict)
    games: dict[str, float] = field(default_factory=dict)
    league_points: float = 0.0     # total points scored across all team-games
    league_team_games: float = 0.0  # team-games seen (2 per match)
    _last_day: Optional[str] = field(default=None, repr=False, compare=False)

    def _key(self, team: str) -> str:
        return self.normalize(team) if self.normalize else team

    def _decay(self, date: Optional[str]) -> None:
        """Age every accumulated sum by the days elapsed since the last update.
        No-op when half_life_days is 0, the date is missing/unparsable, or the
        row arrives out of order (results are merged chronologically upstream)."""
        if self.half_life_days <= 0 or not date:
            return
        day = str(date)[:10]
        if self._last_day is not None and day > self._last_day:
            try:
                from datetime import date as _date
                delta = (_date.fromisoformat(day)
                         - _date.fromisoformat(self._last_day)).days
            except ValueError:
                delta = 0
            if delta > 0:
                f = 0.5 ** (delta / self.half_life_days)
                for sums in (self.points_for, self.points_against, self.games):
                    for k in sums:
                        sums[k] *= f
                self.league_points *= f
                self.league_team_games *= f
        if self._last_day is None or day > self._last_day:
            self._last_day = day

    def update(self, home: str, away: str, home_score: float, away_score: float,
               date: Optional[str] = None) -> None:
        self._decay(date)
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
