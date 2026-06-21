"""Shared rolling-feature logic (ported from the ML project; decoupled from its
pydantic config so it depends only on the data passed in). Used by the generic
team-sport feature builder for NBA, NFL and NHL.

All features are PREGAME: they summarise a team's PAST games only, so there is
no lookahead into the game being predicted.
"""
from __future__ import annotations

from datetime import date as _date
from pathlib import Path

import numpy as np
import pandas as pd


def default_team_state(pts_default: float = 4.0) -> dict:
    return {
        "games": 0, "wins": 0, "pts": 0.0, "pa": 0.0,
        "pts_history": [], "pa_history": [],
        "last_game_date": None,
        "_pts_default": pts_default,
    }


def get_team_features(team: str, stats: dict, windows: list[int], ewm_span: int,
                      pts_default: float, game_date=None, rest_cap: int = 15) -> dict:
    s = stats.get(team, default_team_state(pts_default))
    games = max(s["games"], 1)
    hist_pts = s["pts_history"]
    hist_pa = s["pa_history"]

    feats: dict = {"games": s["games"], "win_rate": s["wins"] / games}

    for w in windows:
        feats[f"pts_l{w}"] = np.mean(hist_pts[-w:]) if hist_pts else pts_default
        feats[f"pa_l{w}"] = np.mean(hist_pa[-w:]) if hist_pa else pts_default
        feats[f"diff_l{w}"] = feats[f"pts_l{w}"] - feats[f"pa_l{w}"]

    feats["pts_ewm"] = (float(pd.Series(hist_pts).ewm(span=ewm_span).mean().iloc[-1])
                        if hist_pts else pts_default)
    feats["pa_ewm"] = (float(pd.Series(hist_pa).ewm(span=ewm_span).mean().iloc[-1])
                       if hist_pa else pts_default)
    feats["diff_ewm"] = feats["pts_ewm"] - feats["pa_ewm"]

    last = s.get("last_game_date")
    if last and game_date is not None:
        try:
            d1 = _date.fromisoformat(str(last)[:10])
            d2 = _date.fromisoformat(str(pd.Timestamp(game_date).date()))
            feats["rest_days"] = float(max(1, min((d2 - d1).days, rest_cap)))
        except Exception:
            feats["rest_days"] = 3.0
    else:
        feats["rest_days"] = 3.0
    return feats


def update_team_stats(team: str, pts: float, pa: float, won: bool, stats: dict,
                      pts_default: float = 4.0, game_date=None) -> None:
    if team not in stats:
        stats[team] = default_team_state(pts_default)
    s = stats[team]
    s["games"] += 1
    s["wins"] += int(won)
    s["pts"] += pts
    s["pa"] += pa
    s["pts_history"].append(pts)
    s["pa_history"].append(pa)
    if game_date is not None:
        s["last_game_date"] = str(pd.Timestamp(game_date).date())


def write_state_csv(sport: str, team_stats: dict, windows: list[int], ewm_span: int,
                    pts_default: float, out_dir: Path) -> Path:
    """Persist the final per-team state (latest rolling features) for daily
    inference. Takes an explicit out_dir (no hidden global config)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for team, state in team_stats.items():
        f = get_team_features(team, team_stats, windows, ewm_span, pts_default)
        rows.append({"team": team, **f, "last_game_date": state.get("last_game_date")})
    path = out_dir / f"{sport}_team_state.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path
