"""NHL goalie quality (save-percentage over league) and the lambda factor.

Implements section 4 and 5 of `docs/research/2026-09-26-preregistro-portero-nhl.md`
(and its amendments). The pattern is `models/starters.py` (MLB starting pitcher):
a bounded multiplicative factor on the OPPONENT'S scoring rate.

Quality (section 4), only from appearances with a date STRICTLY BEFORE the day
being estimated:

    e_g  = SV_g - SA_g * L_g              (excess saves of one appearance)
    q_i  = sum_g e_g / (sum_g SA_g + k)   (career rating, shrunk to 0 by k shots)

`L_g` is the league save percentage (shot-weighted) over all appearances of the
SAME season (1 August - 31 July) with date < the appearance's day; on the first
day of a season, where the season has no previous appearance, the whole previous
season is used. The reference is frozen per DATE: every appearance of day D uses
the same `L`, so the order of rows inside a day is irrelevant (the engine defers
a whole day, `engine.walk_forward_backtest`).

Factor (section 5):

    f(i) = clip(1 - beta * q_i / (1 - L_D), 1 - bound, 1 + bound)

The adapter multiplies the home lambda by f(away goalie) and the away lambda by
f(home goalie). `beta == 0.0` (the default) makes the adapter skip this class
altogether, so the output is byte-identical to the model without goalies.

Goalie identity: the announced goalie when the event carries one (M1 in the
backtest: the real starter; phase 2 in production), otherwise the LAST STARTER
OBSERVED for the team (the proxy, M2). A team whose last observed game has no
unambiguous starter (no goalie data, or 0 / 2+ starters flagged) has no proxy:
f = 1 for that side (section 13.3, "sin adivinar").
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Mapping


def season_of(date: str) -> int:
    """NHL season label for goalie purposes: 1 August - 31 July, named by the
    year in which it starts (2014-10-05 -> 2014, 2015-03-01 -> 2014)."""
    year, month = int(date[:4]), int(date[5:7])
    return year if month >= 8 else year - 1


@dataclass
class GoalieRatings:
    prior_shots: float = 0.0   # k: shrinkage, in shots against (derived per training)
    bound: float = 0.35        # max lambda adjustment per side (starters.py audit rule)
    # per goalie: sum of excess saves and sum of shots against
    excess: dict[str, float] = field(default_factory=dict)
    shots: dict[str, float] = field(default_factory=dict)
    # per season: [shots against, saves] over every appearance (league reference)
    league: dict[int, list[float]] = field(default_factory=dict)
    # per team key: last unambiguous starter of its last observed game (or None)
    last_starter: dict[str, str | None] = field(default_factory=dict)
    _day: str | None = None
    _day_ref: float | None = None

    # ------------------------------------------------------------ league ref --
    def league_ref(self, date: str) -> float | None:
        """Shot-weighted league save % for a day: same-season appearances seen so
        far, or the whole previous season if the season has none yet."""
        s = season_of(date)
        for key in (s, s - 1):
            tot = self.league.get(key)
            if tot is not None and tot[0] > 0:
                return tot[1] / tot[0]
        return None

    # --------------------------------------------------------------- observe --
    def observe_game(self, date: str, home_team: str, away_team: str,
                     home_apps: Iterable[Mapping] | None,
                     away_apps: Iterable[Mapping] | None) -> None:
        """Consume ONE finished game. Appearances are mappings with `id`,
        `shots_against`, `saves` (None/NaN when the goalie did not play) and
        `starter` (bool). Rows must arrive in non-decreasing date order."""
        date = str(date)[:10]
        if date != self._day:
            self._day = date
            self._day_ref = self.league_ref(date)   # frozen for the whole day
        for team, apps in ((home_team, home_apps), (away_team, away_apps)):
            apps = list(apps or [])
            starters = [a["id"] for a in apps if a.get("starter") and a.get("id")]
            self.last_starter[team] = starters[0] if len(starters) == 1 else None
            for a in apps:
                gid = a.get("id")
                sa, sv = _num(a.get("shots_against")), _num(a.get("saves"))
                if not gid or sa is None or sv is None:
                    continue                      # did not play / unidentified
                tot = self.league.setdefault(season_of(date), [0.0, 0.0])
                tot[0] += sa
                tot[1] += sv
                if self._day_ref is None:
                    continue                      # no reference yet (first ever day)
                self.excess[gid] = self.excess.get(gid, 0.0) + (sv - sa * self._day_ref)
                self.shots[gid] = self.shots.get(gid, 0.0) + sa

    # ----------------------------------------------------------------- query --
    def quality(self, goalie: str | None) -> float:
        """q: 0.0 for an unidentified goalie or one without prior shots."""
        if not goalie:
            return 0.0
        den = self.shots.get(goalie, 0.0) + self.prior_shots
        if den <= 0.0:
            return 0.0
        return self.excess.get(goalie, 0.0) / den

    def factor(self, goalie: str | None, date: str, beta: float) -> float:
        """Multiplier for the OPPOSING team's scoring rate (<1 = suppressor)."""
        if not goalie:
            return 1.0
        ref = self.league_ref(str(date)[:10])
        if ref is None or ref >= 1.0:
            return 1.0
        raw = 1.0 - beta * self.quality(goalie) / (1.0 - ref)
        return max(1.0 - self.bound, min(1.0 + self.bound, raw))

    def proxy(self, team: str) -> str | None:
        return self.last_starter.get(team)


def _num(v: object) -> float | None:
    if v is None:
        return None
    try:
        x = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) else x
