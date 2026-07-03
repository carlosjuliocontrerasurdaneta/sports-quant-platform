"""League registry: maps league_id -> (adapter class, parameters).

Family defaults below; leagues override. margin_sigma values are standard
published magnitudes for each sport and MUST be re-estimated from your own
historical data during calibration (run_calibration_report).

Per-league param precedence (later wins): FAMILY_PARAMS -> LEAGUE_OVERRIDES ->
league_params (ratings.yaml / soccer.yaml) -> adapter __init__ code default.
This chain is independent of env vars and default.yaml (those feed Settings,
not league_params). Full map: docs/CONFIG-PRECEDENCE.md.
"""
from __future__ import annotations
from .adapters import (BasketballAdapter, FootballAdapter, BaseballAdapter,
                       HockeyAdapter, SoccerAdapter)

FAMILY_PARAMS: dict[str, dict] = {
    "basketball": {"points_per_elo": 0.028, "margin_sigma": 12.0,
                   "avg_total": 224.0, "total_sigma": 19.0,
                   "elo_k": 20, "elo_home_adv": 70, "elo_mov": True},
    "football":   {"points_per_elo": 0.025, "margin_sigma": 13.5,
                   "avg_total": 44.0, "total_sigma": 13.5,
                   "elo_k": 24, "elo_home_adv": 55, "elo_mov": True},
    "baseball":   {"avg_total": 8.7, "tilt_scale": 0.8, "max_score": 25,
                   "home_scoring_bonus": 0.10, "elo_k": 6, "elo_home_adv": 25},
    "hockey":     {"avg_total": 6.1, "tilt_scale": 0.9, "max_score": 15,
                   "home_scoring_bonus": 0.10, "elo_k": 10, "elo_home_adv": 33},
    "soccer":     {"avg_total": 2.7, "tilt_scale": 1.0, "max_score": 10,
                   "home_scoring_bonus": 0.15, "elo_k": 18, "elo_home_adv": 48,
                   "dc_rho": 0.0},  # Dixon-Coles: tune per league (scripts/tune_ratings.py)
}

LEAGUE_OVERRIDES: dict[str, dict] = {
    "wnba":   {"avg_total": 162.0, "total_sigma": 15.0, "points_per_elo": 0.024},
    "ncaab":  {"avg_total": 145.0, "total_sigma": 15.0, "margin_sigma": 10.5},
    "wncaab": {"avg_total": 132.0, "total_sigma": 14.0, "margin_sigma": 10.5},
    "ncaaf":  {"avg_total": 55.0, "total_sigma": 15.5, "margin_sigma": 15.5},
}

_FAMILY_ADAPTER = {
    "basketball": BasketballAdapter, "football": FootballAdapter,
    "baseball": BaseballAdapter, "hockey": HockeyAdapter,
    "soccer": SoccerAdapter,
}


def get_adapter(league: str, family: str, league_params: dict | None = None):
    params = dict(FAMILY_PARAMS[family])
    params.update(LEAGUE_OVERRIDES.get(league, {}))
    params.update(league_params or {})
    return _FAMILY_ADAPTER[family](league, params)
