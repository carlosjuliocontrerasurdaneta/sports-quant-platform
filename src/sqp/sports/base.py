"""SportAdapter: the extension point. Two modeling families:

- TeamSportAdapter: head-to-head between TEAMS (basketball, football,
  baseball, hockey, soccer). Strength = Elo; scoring distribution per family.
- HeadToHeadAdapter: individuals (tennis). Same Elo machinery keyed by player
  and surface.

Adding a sport = implementing an adapter. The core pipeline never changes.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from sqp.domain.models import Event, EstimatedProbabilities
from sqp.models.elo import EloRatings
from sqp.sports.team_names import get_team_normalizer


class SportAdapter(ABC):
    family: str = "abstract"
    three_way: bool = False

    def __init__(self, league: str, params: dict):
        self.league = league
        self.params = params
        # One canonical identity per team across vendors (results vs live odds).
        self.normalize = get_team_normalizer(league)
        self.elo = EloRatings(
            k=params.get("elo_k", 20.0),
            home_advantage=params.get("elo_home_adv", 60.0),
            mov_scaling=params.get("elo_mov", False),
            normalize=self.normalize,
        )

    def observe(self, r: dict) -> None:
        """Consume ONE chronological result. Elo by default; adapters may
        learn more from the same row (e.g. starter ratings in baseball)."""
        self.elo.update(r["home"], r["away"], r["home_score"], r["away_score"],
                        r.get("neutral", False))

    def fit_results(self, results: list[dict]) -> None:
        """Sequential update. Results MUST be in chronological order and
        strictly prior to the events being estimated (no lookahead)."""
        for r in results:
            self.observe(r)

    @abstractmethod
    def estimate(self, event: Event, spread_line: float | None,
                 total_line: float | None) -> EstimatedProbabilities:
        ...

    def reliability_warning(self, event: Event, min_games: int = 10) -> str | None:
        weak = [t for t in (event.home, event.away) if not self.elo.is_reliable(t, min_games)]
        if weak:
            return f"Low-sample ratings for: {', '.join(weak)} (<{min_games} games). Estimates unreliable."
        return None
