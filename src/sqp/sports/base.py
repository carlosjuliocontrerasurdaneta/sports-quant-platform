"""SportAdapter: the extension point. Two modeling families:

- TeamSportAdapter: head-to-head between TEAMS (basketball, football,
  baseball, hockey, soccer). Strength = Elo; scoring distribution per family.
- HeadToHeadAdapter: individuals (tennis). Same Elo machinery keyed by player
  and surface.

Adding a sport = implementing an adapter. The core pipeline never changes.
"""
from __future__ import annotations
import functools
from abc import ABC, abstractmethod
from sqp.domain.models import Event, EstimatedProbabilities
from sqp.models.elo import EloRatings
from sqp.sports.team_names import get_team_normalizer


def _advance_before(fn):
    @functools.wraps(fn)
    def wrapper(self, event, *args, **kwargs):
        elo = getattr(self, "elo", None)
        if elo is not None and elo.season_regression > 0.0:
            elo.advance_to(event.start_time)
        return fn(self, event, *args, **kwargs)
    wrapper._sqp_advance_wrapped = True  # type: ignore[attr-defined]
    return wrapper


class SportAdapter(ABC):
    family: str = "abstract"
    three_way: bool = False

    def __init_subclass__(cls, **kwargs):
        """Wrap estimate/estimate_f5 so the Elo season-boundary regression is
        applied BEFORE estimating (the first day of a season is estimated before
        it is observed; pre-registro Elo regresion §12.1). With
        season_regression == 0 `advance_to` is a no-op."""
        super().__init_subclass__(**kwargs)
        for name in ("estimate", "estimate_f5"):
            fn = cls.__dict__.get(name)
            if fn is None or getattr(fn, "_sqp_advance_wrapped", False):
                continue
            setattr(cls, name, _advance_before(fn))

    def __init__(self, league: str, params: dict):
        self.league = league
        self.params = params
        # One canonical identity per team across vendors (results vs live odds).
        self.normalize = get_team_normalizer(league)
        self.elo = EloRatings(
            k=params.get("elo_k", 20.0),
            home_advantage=params.get("elo_home_adv", 60.0),
            mov_scaling=params.get("elo_mov", False),
            use_home_away_split=bool(params.get("elo_home_away_split", False)),
            normalize=self.normalize,
            season_regression=float(params.get("elo_season_regression", 0.0)),
        )

    def observe(self, r: dict) -> None:
        """Consume ONE chronological result. Elo by default; adapters may
        learn more from the same row (e.g. starter ratings in baseball)."""
        self.elo.update(r["home"], r["away"], r["home_score"], r["away_score"],
                        r.get("neutral", False), date=r.get("date"))

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
