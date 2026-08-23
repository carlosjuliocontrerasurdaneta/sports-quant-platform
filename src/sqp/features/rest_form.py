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


def team_avg_scored(
    team: str,
    results: list[dict],
    n: int = 10,
    normalize: Callable[[str], str] | None = None,
) -> float | None:
    """Average goals/runs scored per game in the team's last n games.

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
    scored = []
    for r in recent:
        try:
            is_home = norm(str(r.get("home", ""))) == team_n
            scored.append(float(r["home_score"]) if is_home else float(r["away_score"]))
        except (KeyError, TypeError, ValueError):
            continue
    return sum(scored) / len(scored) if scored else None


def team_avg_conceded(
    team: str,
    results: list[dict],
    n: int = 10,
    normalize: Callable[[str], str] | None = None,
) -> float | None:
    """Average goals/runs conceded per game in the team's last n games.

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
    conceded = []
    for r in recent:
        try:
            is_home = norm(str(r.get("home", ""))) == team_n
            conceded.append(float(r["away_score"]) if is_home else float(r["home_score"]))
        except (KeyError, TypeError, ValueError):
            continue
    return sum(conceded) / len(conceded) if conceded else None


def off_def_p_adjustment(
    market: str,
    selection: str,
    home: str,
    away: str,
    avg_scored_home: float | None,
    avg_conceded_home: float | None,
    avg_scored_away: float | None,
    avg_conceded_away: float | None,
    point: float | None,
    off_def_h2h_coef: float,
    off_def_totals_coef: float,
) -> float:
    """Additive adjustment based on offensive and defensive strength.

    Totals: expected_total = (scored_home + conceded_away + scored_away + conceded_home) / 2
            adj = (expected_total - point) * off_def_totals_coef
            Over gets +adj, Under gets -adj.

    H2H/spreads: expected_margin = (scored_home + conceded_away - scored_away - conceded_home) / 2
                 adj = sign * expected_margin * off_def_h2h_coef
                 Home selection gets sign=+1, away gets -1.

    Returns 0 when any required input is None or both coefs are 0.
    """
    have_all = all(x is not None for x in
                   [avg_scored_home, avg_conceded_home, avg_scored_away, avg_conceded_away])
    if market == "totals" and off_def_totals_coef != 0.0 and have_all and point is not None:
        expected_total = (avg_scored_home + avg_conceded_away  # type: ignore[operator]
                          + avg_scored_away + avg_conceded_home) / 2.0  # type: ignore[operator]
        adj = (expected_total - point) * off_def_totals_coef
        if selection == "Over":
            return adj
        if selection == "Under":
            return -adj
        return 0.0
    if market in ("h2h", "spreads") and off_def_h2h_coef != 0.0 and have_all:
        expected_margin = (avg_scored_home + avg_conceded_away  # type: ignore[operator]
                           - avg_scored_away - avg_conceded_home) / 2.0  # type: ignore[operator]
        if selection == home:
            return expected_margin * off_def_h2h_coef
        if selection == away:
            return -expected_margin * off_def_h2h_coef
    return 0.0


def team_streak(
    team: str,
    results: list[dict],
    normalize: Callable[[str], str] | None = None,
) -> int:
    """Current consecutive win (+) or loss (-) streak for the team.

    Iterates from the most recent game backward. A draw or a missing score
    resets to 0 and stops. Returns 0 when no games are available.
    e.g. W W W → +3; L L → -2; W L W → +1 (only the last win counts).
    """
    norm = normalize or (lambda x: x)
    team_n = norm(team)
    team_games = [
        r for r in results
        if norm(str(r.get("home", ""))) == team_n
        or norm(str(r.get("away", ""))) == team_n
    ]
    streak = 0
    for r in reversed(team_games):
        try:
            hs = float(r["home_score"])
            aws = float(r["away_score"])
        except (KeyError, TypeError, ValueError):
            break
        is_home = norm(str(r.get("home", ""))) == team_n
        if hs > aws:
            outcome = 1 if is_home else -1
        elif aws > hs:
            outcome = -1 if is_home else 1
        else:
            break  # draw breaks streak
        if streak == 0:
            streak = outcome
        elif (outcome > 0) == (streak > 0):
            streak += outcome
        else:
            break
    return streak


def streak_p_adjustment(
    market: str,
    selection: str,
    home: str,
    away: str,
    streak_home: int,
    streak_away: int,
    streak_coef: float,
) -> float:
    """Additive adjustment for h2h and spreads based on win/loss streak differential.

    adj = sign * (streak_home - streak_away) * streak_coef.
    Home selection gets sign=+1, away gets -1. Totals and draws return 0.
    streak_coef defaults to 0 (no-op); activate only after OOS validation.
    """
    if streak_coef == 0.0 or market == "totals":
        return 0.0
    if selection == home:
        sign = 1.0
    elif selection == away:
        sign = -1.0
    else:
        return 0.0
    return sign * (streak_home - streak_away) * streak_coef


def team_avg_total(
    team: str,
    results: list[dict],
    n: int = 10,
    normalize: Callable[[str], str] | None = None,
) -> float | None:
    """Average total score (home_score + away_score) per game in the team's last n games.

    Captures scoring environment tendency: high-scoring teams inflate totals,
    low-scoring ones deflate them. Returns None when fewer than 2 games available.
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
    totals_list = []
    for r in recent:
        try:
            totals_list.append(float(r["home_score"]) + float(r["away_score"]))
        except (KeyError, TypeError, ValueError):
            continue
    return sum(totals_list) / len(totals_list) if totals_list else None


def totals_tendency_p_adjustment(
    market: str,
    selection: str,
    avg_total_home: float | None,
    avg_total_away: float | None,
    point: float | None,
    totals_tendency_coef: float,
) -> float:
    """Additive adjustment to p_model for totals markets based on team scoring tendency.

    combined_avg = mean of both teams' avg total per game.
    adj = (combined_avg - point) * coef.
    Over gets +adj (teams tend to score more than the line → favor Over).
    Under gets -adj. Returns 0 for h2h/spreads, or when any input is missing.
    coef defaults to 0 (no-op); activate only with OOS evidence.
    """
    if totals_tendency_coef == 0.0 or market != "totals":
        return 0.0
    if avg_total_home is None or avg_total_away is None or point is None:
        return 0.0
    combined_avg = (avg_total_home + avg_total_away) / 2.0
    adj = (combined_avg - point) * totals_tendency_coef
    if selection == "Over":
        return adj
    if selection == "Under":
        return -adj
    return 0.0


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
