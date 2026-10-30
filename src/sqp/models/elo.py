"""Generic Elo rating engine (teams or players).

Used as the baseline strength signal for every adapter. Margin-of-victory
multiplier optional. Ratings must be built ONLY from results prior to the
event being estimated (temporal correctness is the caller's responsibility;
`update` is sequential by design).
"""
from __future__ import annotations
import logging
import math
from datetime import date as _date
from dataclasses import dataclass, field
from typing import Callable, Optional

log = logging.getLogger(__name__)


@dataclass
class EloRatings:
    k: float = 20.0
    base: float = 1500.0
    home_advantage: float = 60.0       # Elo points added to home side pregame
    mov_scaling: bool = False           # margin-of-victory multiplier
    # When True, maintains separate home/away ratings per team alongside the
    # unified rating. expected_home_win and rating_diff then use
    # ratings_home[home] - ratings_away[away] (no fixed home_advantage offset;
    # the differential captures it dynamically). Falls back to unified + offset
    # for neutral-site games. Activate per league via elo_home_away_split: true
    # in configs/leagues/ratings.yaml after OOS validation.
    use_home_away_split: bool = False
    # Optional team-name canonicalizer. When set, every team string is reduced
    # to one identity before indexing, so ratings built from one vendor's names
    # bind to events quoted under another vendor's names (see sports.team_names).
    normalize: Optional[Callable[[str], str]] = field(default=None, repr=False, compare=False)
    ratings: dict[str, float] = field(default_factory=dict)
    # Role-specific ratings (populated only when use_home_away_split=True).
    ratings_home: dict[str, float] = field(default_factory=dict)
    ratings_away: dict[str, float] = field(default_factory=dict)
    games_played: dict[str, int] = field(default_factory=dict)
    # Season-boundary mean reversion (pre-registro 2026-10-29, §4 y §12.1).
    # 0.0 = disabled: identical behaviour to the engine without the feature.
    season_regression: float = 0.0
    season_gap_days: int = 30
    # Internal state: last observed UTC date (YYYY-MM-DD) and the first date of
    # the season already regressed (idempotence per boundary, Enmienda E3).
    _last_date: Optional[str] = field(default=None, repr=False, compare=False)
    _regressed_for: Optional[str] = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not 0.0 <= self.season_regression <= 1.0:
            raise ValueError(
                f"season_regression must be in [0, 1], got {self.season_regression}")

    def _key(self, team: str) -> str:
        return self.normalize(team) if self.normalize else team

    def get(self, team: str) -> float:
        return self.ratings.get(self._key(team), self.base)

    def get_home_rating(self, team: str) -> float:
        return self.ratings_home.get(self._key(team), self.base)

    def get_away_rating(self, team: str) -> float:
        return self.ratings_away.get(self._key(team), self.base)

    def expected_home_win(self, home: str, away: str, neutral: bool = False) -> float:
        if self.use_home_away_split and not neutral:
            diff = self.get_home_rating(home) - self.get_away_rating(away)
        else:
            ha = 0.0 if neutral else self.home_advantage
            diff = self.get(home) + ha - self.get(away)
        return 1.0 / (1.0 + 10 ** (-diff / 400.0))

    def rating_diff(self, home: str, away: str, neutral: bool = False) -> float:
        if self.use_home_away_split and not neutral:
            return self.get_home_rating(home) - self.get_away_rating(away)
        ha = 0.0 if neutral else self.home_advantage
        return self.get(home) + ha - self.get(away)

    def advance_to(self, date: object) -> bool:
        """Apply the season-boundary regression if `date` starts a new season.

        A boundary exists when `date` (UTC, first 10 chars) is >= season_gap_days
        after the last observed date. One regression per boundary (idempotent
        on the boundary date). Events on or before the last date never regress.
        No-op when season_regression == 0. Returns True if a regression ran.
        """
        if self.season_regression == 0.0:
            return False
        d = str(date)[:10]
        if self._last_date is None or self._regressed_for == d:
            return False
        # Boundary already regressed since the last observation: estimating
        # several unobserved post-boundary dates (the daily run's horizon) must
        # not regress once per date (revision Fable 2026-10-30).
        if self._regressed_for is not None and self._regressed_for > self._last_date:
            return False
        gap = (_date.fromisoformat(d) - _date.fromisoformat(self._last_date)).days
        if gap < self.season_gap_days:
            return False
        keep = 1.0 - self.season_regression
        for table in (self.ratings, self.ratings_home, self.ratings_away):
            for t, r in table.items():
                table[t] = self.base + keep * (r - self.base)
        self._regressed_for = d
        month = int(d[5:7])
        if not 6 <= month <= 10:
            log.warning("Elo season boundary detected on %s (month outside "
                        "June-October; gap %d days): check for an ingestion gap",
                        d, gap)
        return True

    def update(self, home: str, away: str, home_score: float, away_score: float,
               neutral: bool = False, date: object = None) -> None:
        if date is not None:
            self.advance_to(date)
        exp = self.expected_home_win(home, away, neutral)
        if home_score > away_score:
            actual = 1.0
        elif home_score < away_score:
            actual = 0.0
        else:
            actual = 0.5
        mult = 1.0
        if self.mov_scaling:
            margin = abs(home_score - away_score)
            elo_diff = abs(self.rating_diff(home, away, neutral))
            mult = math.log(margin + 1) * (2.2 / (elo_diff * 0.001 + 2.2))
        delta = self.k * mult * (actual - exp)
        hk, ak = self._key(home), self._key(away)
        self.ratings[hk] = self.get(home) + delta
        self.ratings[ak] = self.get(away) - delta
        if self.use_home_away_split and not neutral:
            self.ratings_home[hk] = self.get_home_rating(home) + delta
            self.ratings_away[ak] = self.get_away_rating(away) - delta
        self.games_played[hk] = self.games_played.get(hk, 0) + 1
        self.games_played[ak] = self.games_played.get(ak, 0) + 1
        if date is not None:
            d = str(date)[:10]
            if self._last_date is None or d > self._last_date:
                self._last_date = d

    def is_reliable(self, team: str, min_games: int = 10) -> bool:
        return self.games_played.get(self._key(team), 0) >= min_games
