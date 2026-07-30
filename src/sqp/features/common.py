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

from sqp.storage.atomic import atomic_write_csv


def default_team_state(pts_default: float = 4.0) -> dict:
    return {
        "games": 0, "wins": 0, "pts": 0.0, "pa": 0.0,
        "pts_history": [], "pa_history": [],
        "last_game_date": None,
        "_pts_default": pts_default,
    }


def rest_days(last_game_date, game_date, cap: int = 15) -> float:
    """Days since the team's last game, clamped to [1, cap]; 3.0 when unknown
    or unparseable (neutral mid-week rest)."""
    if last_game_date and game_date is not None:
        try:
            d1 = _date.fromisoformat(str(last_game_date)[:10])
            d2 = _date.fromisoformat(str(pd.Timestamp(game_date).date()))
            return float(max(1, min((d2 - d1).days, cap)))
        except Exception:
            return 3.0
    return 3.0


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

    feats["rest_days"] = rest_days(s.get("last_game_date"), game_date, cap=rest_cap)
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
        # Sin game_date el rest_days queda congelado en 3.0 y persistirlo
        # introduce skew train/serve (auditoria 2026-07-24, M-31): se omite del
        # estado; el consumidor debe recomputarlo desde last_game_date.
        f.pop("rest_days", None)
        rows.append({"team": team, **f, "last_game_date": state.get("last_game_date")})
    path = out_dir / f"{sport}_team_state.csv"
    # Atomico: es un artefacto de INFERENCIA; un truncado deja equipos sin
    # estado sin error visible (auditoria 2026-07-29, D-09).
    atomic_write_csv(pd.DataFrame(rows), path)
    return path
