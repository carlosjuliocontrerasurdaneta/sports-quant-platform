"""Pregame team-level features: rest days and recent form.

Both features are computed from the chronologically-sorted results list that
the adapter already uses for Elo fitting, so there is no extra data source.

Rest days: days since a team's last game strictly before the event date.
A larger differential (home more rested than away) is a weak positive signal.

Recent form: win rate (win=1, draw=0.5, loss=0) over the last n completed
games. Draws count as 0.5 regardless of sport; for two-outcome sports all
results are 0 or 1, so the metric is equivalent to plain win rate.

Both return None when there is insufficient data (< 1 prior game for rest,
< 2 for form) — callers treat None as "no adjustment".

Scaling guide for the coefficients in RiskConfig:
  rest_days_coef: probability points added per extra rest day of advantage.
    e.g. 0.002 → 3-day advantage gives home +0.6 pp.
  recent_form_coef: probability points added per unit of form differential
    (range −1 to +1).  e.g. 0.05 → perfect vs winless gives +5 pp.
  Both default to 0.0 (no-op) until validated on OOS data.
"""
from __future__ import annotations

from datetime import date
from typing import Callable


def team_rest_days(
    team: str,
    results: list[dict],
    reference_date: str,
    normalize: Callable[[str], str] | None = None,
) -> int | None:
    """Days since the team's last game strictly before reference_date (YYYY-MM-DD).

    Returns None when no prior game is found.
    """
    norm = normalize or (lambda x: x)
    team_n = norm(team)
    ref = reference_date[:10]
    last: str | None = None
    for r in results:
        d = str(r.get("date", ""))[:10]
        if d >= ref:
            continue
        if norm(str(r.get("home", ""))) == team_n or norm(str(r.get("away", ""))) == team_n:
            if last is None or d > last:
                last = d
    if last is None:
        return None
    return (date.fromisoformat(ref) - date.fromisoformat(last)).days


def team_recent_form(
    team: str,
    results: list[dict],
    n: int = 5,
    normalize: Callable[[str], str] | None = None,
) -> float | None:
    """Win rate (win=1, draw=0.5, loss=0) over the last n completed games.

    Results must be in chronological order (ascending date).
    Returns None when fewer than 2 games are available.
    """
    norm = normalize or (lambda x: x)
    team_n = norm(team)
    team_games = [
        r for r in results
        if norm(str(r.get("home", ""))) == team_n
        or norm(str(r.get("away", ""))) == team_n
    ]
    recent = team_games[-n:]
    if len(recent) < 2:
        return None
    total = 0.0
    for r in recent:
        try:
            hs = float(r["home_score"])
            aws = float(r["away_score"])
        except (KeyError, TypeError, ValueError):
            continue
        is_home = norm(str(r.get("home", ""))) == team_n
        if hs > aws:
            total += 1.0 if is_home else 0.0
        elif aws > hs:
            total += 0.0 if is_home else 1.0
        else:
            total += 0.5
    return total / len(recent)


def rest_form_p_adjustment(
    p_model: float,
    market: str,
    selection: str,
    home: str,
    away: str,
    rest_home: int | None,
    rest_away: int | None,
    form_home: float | None,
    form_away: float | None,
    rest_days_coef: float,
    recent_form_coef: float,
) -> float:
    """Return an additive adjustment to p_model for (market, selection).

    Only adjusts h2h and spreads where the selection is a team name.
    Totals ("Over"/"Under") and three-way draws return 0.
    The result is NOT clamped here; callers clip to [0.01, 0.99].
    """
    if rest_days_coef == 0.0 and recent_form_coef == 0.0:
        return 0.0
    if market == "totals":
        return 0.0
    if selection == home:
        sign = 1.0
    elif selection == away:
        sign = -1.0
    else:
        return 0.0  # Draw or unknown
    adj = 0.0
    if rest_days_coef != 0.0 and rest_home is not None and rest_away is not None:
        adj += sign * (rest_home - rest_away) * rest_days_coef
    if recent_form_coef != 0.0 and form_home is not None and form_away is not None:
        adj += sign * (form_home - form_away) * recent_form_coef
    return adj


def team_h2h_form(
    team_a: str,
    team_b: str,
    results: list[dict],
    n: int = 10,
    normalize: Callable[[str], str] | None = None,
) -> float | None:
    """Win rate of team_a vs team_b in their last n direct matchups.

    win=1, draw=0.5, loss=0. Returns None when fewer than 2 matchups found.
    Results must be in chronological order (ascending date).
    """
    norm = normalize or (lambda x: x)
    a = norm(team_a)
    b = norm(team_b)
    matchups = [
        r for r in results
        if (norm(str(r.get("home", ""))) == a and norm(str(r.get("away", ""))) == b)
        or (norm(str(r.get("home", ""))) == b and norm(str(r.get("away", ""))) == a)
    ]
    recent = matchups[-n:]
    if len(recent) < 2:
        return None
    total = 0.0
    for r in recent:
        try:
            hs = float(r["home_score"])
            aws = float(r["away_score"])
        except (KeyError, TypeError, ValueError):
            continue
        home_is_a = norm(str(r.get("home", ""))) == a
        if hs > aws:
            total += 1.0 if home_is_a else 0.0
        elif aws > hs:
            total += 0.0 if home_is_a else 1.0
        else:
            total += 0.5
    return total / len(recent)


def h2h_p_adjustment(
    market: str,
    selection: str,
    home: str,
    away: str,
    h2h_home: float | None,
    h2h_coef: float,
) -> float:
    """Additive h2h adjustment to p_model for h2h markets only.

    h2h_home is the home team's win rate in past direct matchups vs the away
    team (from team_h2h_form). Centered at 0.5 (equal record):
      adj = sign * (h2h_home - 0.5) * h2h_coef
    Returns 0 for spreads, totals, draws, or when h2h_home is None / coef is 0.
    """
    if h2h_home is None or h2h_coef == 0.0 or market != "h2h":
        return 0.0
    if selection == home:
        return (h2h_home - 0.5) * h2h_coef
    if selection == away:
        return -(h2h_home - 0.5) * h2h_coef
    return 0.0
