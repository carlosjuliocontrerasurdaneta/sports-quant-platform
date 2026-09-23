"""Monte Carlo engines. Outputs are empirical *estimated probabilities*.

Analytical formulas in models.distributions are preferred when exact; MC is
used for compound uncertainty (e.g. rating uncertainty propagation) and as a
cross-check in audits.
"""
from __future__ import annotations
import numpy as np

from sqp.markets.settlement_math import is_quarter_line, split_asian_line


def simulate_normal_game(mu_home: float, mu_away: float, sigma_team: float,
                         spread_line: float | None, total_line: float | None,
                         n_sims: int = 20000, seed: int | None = 42) -> dict:
    rng = np.random.default_rng(seed)
    hs = rng.normal(mu_home, sigma_team, n_sims)
    as_ = rng.normal(mu_away, sigma_team, n_sims)
    margin = hs - as_
    total = hs + as_
    out = {
        "home_win_estimated_probability": float(np.mean(margin > 0)),
        "away_win_estimated_probability": float(np.mean(margin < 0)),
    }
    if spread_line is not None:
        out["home_cover_estimated_probability"] = float(np.mean(margin > -spread_line))
        out["away_cover_estimated_probability"] = float(np.mean(margin < -spread_line))
    if total_line is not None:
        out["over_estimated_probability"] = float(np.mean(total > total_line))
        out["under_estimated_probability"] = float(np.mean(total < total_line))
    return out


def simulate_poisson_game(lam_home: float, lam_away: float,
                          spread_line: float | None, total_line: float | None,
                          three_way: bool = False, n_sims: int = 50000,
                          seed: int | None = 42) -> dict:
    rng = np.random.default_rng(seed)
    hs = rng.poisson(lam_home, n_sims)
    as_ = rng.poisson(lam_away, n_sims)
    margin = hs - as_
    total = hs + as_
    out: dict[str, float] = {}
    if three_way:
        out["home_win_estimated_probability"] = float(np.mean(margin > 0))
        out["draw_estimated_probability"] = float(np.mean(margin == 0))
        out["away_win_estimated_probability"] = float(np.mean(margin < 0))
    else:
        d = float(np.mean(margin == 0))
        out["home_win_estimated_probability"] = float(np.mean(margin > 0)) + 0.5 * d
        out["away_win_estimated_probability"] = float(np.mean(margin < 0)) + 0.5 * d
    if spread_line is not None:
        if is_quarter_line(spread_line):
            out["home_cover_estimated_probability"] = _quarter_decision(
                margin, [-s for s in split_asian_line(spread_line)])
        else:
            nz = margin != -spread_line
            out["home_cover_estimated_probability"] = float(np.mean(margin[nz] > -spread_line)) if nz.any() else 0.5
        out["away_cover_estimated_probability"] = 1 - out["home_cover_estimated_probability"]
    if total_line is not None:
        if is_quarter_line(total_line):
            out["over_estimated_probability"] = _quarter_decision(
                total, list(split_asian_line(total_line)))
        else:
            nz = total != total_line
            out["over_estimated_probability"] = float(np.mean(total[nz] > total_line)) if nz.any() else 0.5
        out["under_estimated_probability"] = 1 - out["over_estimated_probability"]
    return out


def _quarter_decision(x: np.ndarray, thresholds: list[float]) -> float:
    """Probabilidad de decision de una linea asiatica de CUARTO: media apuesta a
    cada una de las dos lineas adyacentes de medio punto, gana si ``x`` supera el
    umbral, push si lo iguala. Devuelve win_units / (win_units + loss_units),
    el contrato de `settlement_math` y de `distributions` (AUD-014, ronda
    audit-2026-09-23): comparar contra la linea fraccionaria tal cual trataba
    como binaria una apuesta que liquida a medias -- con marcadores enteros,
    `total != 2.25` se cumple siempre y las medias desaparecian."""
    win = 0.5 * sum(float(np.mean(x > t)) for t in thresholds)
    loss = 0.5 * sum(float(np.mean(x < t)) for t in thresholds)
    return win / (win + loss) if win + loss > 1e-12 else 0.5
