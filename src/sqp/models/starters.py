"""Starting pitcher ratings from runs allowed in their starts.

v1 signal: full-game runs allowed by the starter's team in his starts
(bullpen innings included — documented limitation; per-start FIP from game
logs is the planned upgrade). Leak-free by construction: only starts strictly
prior to the estimated game feed the rating. The lambda factor is bounded
(audit rule: max +-35%) and regressed to the league mean.
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class StarterRatings:
    prior_starts: float = 5.0   # regression-to-mean weight (pseudo-starts at league mean)
    min_starts: int = 3         # below this the factor stays neutral
    bound: float = 0.35         # max lambda adjustment per side
    runs: dict[str, float] = field(default_factory=dict)
    starts: dict[str, int] = field(default_factory=dict)
    league_runs: float = 0.0
    league_starts: int = 0

    def update(self, pitcher: str | None, runs_allowed: float) -> None:
        if not pitcher:
            return
        self.runs[pitcher] = self.runs.get(pitcher, 0.0) + float(runs_allowed)
        self.starts[pitcher] = self.starts.get(pitcher, 0) + 1
        self.league_runs += float(runs_allowed)
        self.league_starts += 1

    def league_mean(self) -> float:
        return self.league_runs / self.league_starts if self.league_starts else 0.0

    def factor(self, pitcher: str | None) -> float:
        """Multiplier for the OPPOSING team's scoring rate (<1 = run suppressor)."""
        lg = self.league_mean()
        n = self.starts.get(pitcher or "", 0)
        if not pitcher or lg <= 0 or n < self.min_starts:
            return 1.0
        expected = (self.runs[pitcher] + self.prior_starts * lg) / (n + self.prior_starts)
        return max(1.0 - self.bound, min(1.0 + self.bound, expected / lg))

    def is_known(self, pitcher: str | None) -> bool:
        if not pitcher:
            return False
        return self.starts.get(pitcher, 0) >= self.min_starts
