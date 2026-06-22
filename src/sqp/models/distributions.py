"""Score/margin/total distribution models shared by adapters.

- Normal margin/total: basketball, american football (continuous approx).
- Poisson per-team scoring: hockey, soccer, baseball (count processes).

Every function returns *estimated probabilities*.
"""
from __future__ import annotations
from scipy.stats import norm, poisson


def normal_margin_probs(mu_margin: float, sigma: float, spread_line: float | None):
    """P(home wins) and P(home covers `spread_line`) under margin ~ N(mu, sigma).

    spread_line is the HOME handicap (e.g. -5.5 means home must win by 6+).
    Continuity-corrected at 0.5 around pushes is intentionally omitted for
    half-point lines; integer lines return push-excluded probabilities.
    """
    p_home_win = 1.0 - norm.cdf(0.0, loc=mu_margin, scale=sigma)
    out = {"home_win": p_home_win, "away_win": 1.0 - p_home_win}
    if spread_line is not None:
        thr = -spread_line  # home covers if margin > -line
        if float(thr).is_integer():
            p_cover = 1.0 - norm.cdf(thr + 0.5, mu_margin, sigma)
            p_push = norm.cdf(thr + 0.5, mu_margin, sigma) - norm.cdf(thr - 0.5, mu_margin, sigma)
            denom = max(1e-12, 1.0 - p_push)
            out["home_cover"] = p_cover / denom
        else:
            out["home_cover"] = 1.0 - norm.cdf(thr, mu_margin, sigma)
        out["away_cover"] = 1.0 - out["home_cover"]
    return out


def normal_total_probs(mu_total: float, sigma: float, total_line: float | None):
    if total_line is None:
        return {}
    if float(total_line).is_integer():
        p_over = 1.0 - norm.cdf(total_line + 0.5, mu_total, sigma)
        p_push = norm.cdf(total_line + 0.5, mu_total, sigma) - norm.cdf(total_line - 0.5, mu_total, sigma)
        denom = max(1e-12, 1.0 - p_push)
        return {"over": p_over / denom, "under": 1.0 - p_over / denom}
    p_over = 1.0 - norm.cdf(total_line, mu_total, sigma)
    return {"over": p_over, "under": 1.0 - p_over}


def _dixon_coles_tau(i: int, j: int, lam_home: float, lam_away: float, rho: float) -> float:
    """Dixon-Coles (1997) low-score correction. rho < 0 boosts 0-0 and 1-1
    (more draws) and trims 1-0/0-1, fixing the independent-Poisson draw
    underpricing in low-scoring leagues."""
    if i == 0 and j == 0:
        return 1.0 - lam_home * lam_away * rho
    if i == 0 and j == 1:
        return 1.0 + lam_home * rho
    if i == 1 and j == 0:
        return 1.0 + lam_away * rho
    if i == 1 and j == 1:
        return 1.0 - rho
    return 1.0


def poisson_match_probs(lam_home: float, lam_away: float, spread_line: float | None,
                        total_line: float | None, three_way: bool = False,
                        max_goals: int = 15, dc_rho: float = 0.0):
    """Exact probabilities from independent Poisson scoring (hockey/soccer base).

    Returns home/away win (+draw if three_way), spread cover and total O/U.
    For 2-way sports (NHL regulation+OT), the draw mass is reallocated 50/50
    unless the adapter overrides with an OT model. dc_rho != 0 applies the
    Dixon-Coles low-score adjustment (the grid is renormalized afterwards).
    """
    p_home = [poisson.pmf(i, lam_home) for i in range(max_goals + 1)]
    p_away = [poisson.pmf(j, lam_away) for j in range(max_goals + 1)]
    win = draw = loss = 0.0
    cover = push = 0.0
    over = total_push = 0.0
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            p = p_home[i] * p_away[j]
            if dc_rho:
                p *= max(0.0, _dixon_coles_tau(i, j, lam_home, lam_away, dc_rho))
            m = i - j
            t = i + j
            if m > 0: win += p
            elif m == 0: draw += p
            else: loss += p
            if spread_line is not None:
                if m > -spread_line: cover += p
                elif m == -spread_line: push += p
            if total_line is not None:
                if t > total_line: over += p
                elif t == total_line: total_push += p
    mass = win + draw + loss  # normalize truncated grid mass
    win, draw, loss = win / mass, draw / mass, loss / mass
    cover, push = cover / mass, push / mass
    over, total_push = over / mass, total_push / mass
    out: dict[str, float] = {}
    if three_way:
        out.update({"home_win": win, "draw": draw, "away_win": loss})
    else:
        out.update({"home_win": win + draw * 0.5, "away_win": loss + draw * 0.5})
    if spread_line is not None:
        denom = max(1e-12, 1.0 - push)
        out["home_cover"] = cover / denom
        out["away_cover"] = 1.0 - out["home_cover"]
    if total_line is not None:
        denom = max(1e-12, 1.0 - total_push)
        out["over"] = over / denom
        out["under"] = 1.0 - out["over"]
    return out


def elo_diff_to_margin(elo_diff: float, points_per_elo: float) -> float:
    """Map an Elo difference to an expected scoring margin (sport-calibrated)."""
    return elo_diff * points_per_elo
