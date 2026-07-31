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

from typing import Callable

from .adapters import (BasketballAdapter, FootballAdapter, BaseballAdapter,
                       HockeyAdapter, SoccerAdapter, TennisAdapter)
from .base import SportAdapter

FAMILY_PARAMS: dict[str, dict] = {
    # total_sigma = desviacion RESIDUAL medida walk-forward sobre el historico
    # (total real - total esperado por el modelo), no la dispersion
    # incondicional: el modelo ya varia mu por partido via scoring.expected_total.
    # Subida 19.0 -> 22.0 el 2026-07-31; el valor previo hacia el modelo
    # sobreconfiado en totals (ver tests/test_total_sigma_basketball.py).
    "basketball": {"points_per_elo": 0.028, "margin_sigma": 12.0,
                   "avg_total": 224.0, "total_sigma": 22.0,
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
    "tennis":     {"elo_k": 24, "elo_home_adv": 0},
}

LEAGUE_OVERRIDES: dict[str, dict] = {
    # avg_total 162 -> 171 (2026-07-04): el prior era de una era de menor
    # anotacion y sesgaba TODA la proyeccion al Under (p(Over) media del modelo
    # 0.302 sobre 35 partidos vs ~0.50 insesgado; est 0.597 vs obs 0.438 en 32
    # Unders liquidados). Evidencia: total observado 2026 = 170.9 (n=137),
    # ultimos 30 dias = 174.1, linea media de mercado = 175.1.
    # scoring_half_life_days 180 (2026-07-04): las tasas de anotacion decaen con
    # media vida de ~media temporada para seguir la era actual (el store 2023->
    # 2026 sin decaimiento proyectaba ~165 contra lineas 2026 de ~175 y volcaba
    # todos los totals al Under). Ver test_team_scoring y team_scoring.py.
    # 15.0 -> 19.0 (residual medido 18.6). Era la causa del peor segmento del
    # marcador: wnba/totals con Brier 0.336 frente a 0.250 del mercado.
    "wnba":   {"avg_total": 171.0, "total_sigma": 19.0, "points_per_elo": 0.024,
               "scoring_half_life_days": 180.0},
    "ncaab":  {"avg_total": 145.0, "total_sigma": 18.0, "margin_sigma": 10.5},  # residual 17.7
    "wncaab": {"avg_total": 132.0, "total_sigma": 17.0, "margin_sigma": 10.5},  # residual 17.0
    "ncaaf":  {"avg_total": 55.0, "total_sigma": 15.5, "margin_sigma": 15.5},
}

_FAMILY_ADAPTER: dict[str, Callable[..., SportAdapter]] = {
    "basketball": BasketballAdapter, "football": FootballAdapter,
    "baseball": BaseballAdapter, "hockey": HockeyAdapter,
    "soccer": SoccerAdapter, "tennis": TennisAdapter,
}


def get_adapter(league: str, family: str, league_params: dict | None = None):
    params = dict(FAMILY_PARAMS[family])
    params.update(LEAGUE_OVERRIDES.get(league, {}))
    params.update(league_params or {})
    return _FAMILY_ADAPTER[family](league, params)
