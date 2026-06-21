"""Monte Carlo engines. Outputs are empirical *estimated probabilities*.

Analytical formulas in models.distributions are preferred when exact; MC is
used for compound uncertainty (e.g. rating uncertainty propagation) and as a
cross-check in audits.
"""
from __future__ import annotations
import numpy as np


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
        nz = margin != -spread_line
        out["home_cover_estimated_probability"] = float(np.mean(margin[nz] > -spread_line)) if nz.any() else 0.5
        out["away_cover_estimated_probability"] = 1 - out["home_cover_estimated_probability"]
    if total_line is not None:
        nz = total != total_line
        out["over_estimated_probability"] = float(np.mean(total[nz] > total_line)) if nz.any() else 0.5
        out["under_estimated_probability"] = 1 - out["over_estimated_probability"]
    return out
