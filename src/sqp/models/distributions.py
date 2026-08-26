"""Score/margin/total distribution models shared by adapters.

- Normal margin/total: basketball, american football (continuous approx).
- Poisson per-team scoring: hockey, soccer, baseball (count processes).

Every function returns *estimated probabilities*.
"""
from __future__ import annotations
import math

import numpy as np
from scipy.stats import nbinom, norm, poisson


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


def score_pmf(lam: float, max_goals: int = 15, k: float | None = None) -> list[float]:
    """Distribucion del marcador de un equipo: Poisson, o binomial negativa si `k`.

    Poisson exige Var(y|lambda) = lambda. Medido walk-forward sobre el historico,
    eso se cumple en hockey (dispersion 1.01 sobre 52.540 equipos-partido) pero NO
    en beisbol (2.21 sobre 14.223): el beisbol anota a rachas y su varianza dobla
    la que Poisson admite, asi que el modelo subestimaba las colas y se volvia
    sobreconfiado en totals y runline (auditoria 2026-07-31).

    La binomial negativa anade dispersion manteniendo la media:
        Var = mu + mu^2/k        (k -> infinito recupera Poisson exacto)
    Se parametriza con n=k, p=k/(k+mu), que es la forma de scipy.

    `k=None` devuelve Poisson puro: hockey y futbol quedan byte-identicos.
    """
    if k is None or k <= 0:
        return [poisson.pmf(i, lam) for i in range(max_goals + 1)]
    return [nbinom.pmf(i, k, k / (k + lam)) for i in range(max_goals + 1)]


SCORE_RHO_MAX = 0.15


def _joint_grid(p_home: list[float], p_away: list[float],
                score_rho: float = 0.0) -> np.ndarray:
    """Rejilla conjunta del marcador. `score_rho=0` es independencia exacta.

    El motor componia `p(i,j) = p_home[i] * p_away[j]`, es decir independencia
    pura, y la correlacion residual medida walk-forward NO es cero: -0.0873 en
    NHL (p<0.0001, n=32.777). En MLB si lo es (-0.0043, p=0.68), asi que esto es
    una correccion de hockey, no una general (pre-registro 2026-08-26).

    Importa que sea correlacion y no dispersion porque

        Var(margen) = Vh + Va - 2*rho*sh*sa
        Var(total)  = Vh + Va + 2*rho*sh*sa

    y `rho < 0` los mueve en sentidos OPUESTOS, que es lo que los datos piden en
    NHL (el margen se queda corto un 2.8%, el total se pasa un 3.3%).
    `dispersion_k` los mueve en el MISMO sentido y por eso no puede servir a los
    dos mercados a la vez -- la tension abierta desde 2026-08-17.

    Forma: termino de primer orden de la copula gaussiana,

        p(i,j) = p_h(i)*p_a(j) + rho * dphi_h(i) * dphi_a(j)
        dphi(i) = phi(z(i)) - phi(z(i-1)),  z(i) = Phi^-1(F(i))

    Se elige frente a una copula exacta porque (a) PRESERVA LAS MARGINALES --
    sumando en j, la correccion telescopa a phi(+inf)-phi(-inf)=0, asi que las
    tasas por equipo y el moneyline de un lado quedan intactos; y (b) cuesta dos
    vectores de 16 entradas y un producto externo, frente a ~289 evaluaciones de
    la normal bivariante por evento. Es una expansion de primer orden: valida en
    el regimen medido (|rho| ~ 0.06), por eso el bound.

    La preservacion es exacta en aritmetica real pero NO en punto flotante: el
    recorte de celdas negativas en la cola introduce un sesgo, medido y acotado
    en la tabla del cuerpo de la funcion (1e-10 en el punto de trabajo de NHL).
    """
    ph = np.asarray(p_home, dtype=float)
    pa = np.asarray(p_away, dtype=float)
    if not score_rho:
        return np.outer(ph, pa)
    if not math.isfinite(score_rho) or abs(score_rho) > SCORE_RHO_MAX:
        raise ValueError(
            f"score_rho must be finite and |score_rho| <= {SCORE_RHO_MAX}, "
            f"got {score_rho}: the first-order expansion degrades beyond that")

    def _dphi(p: np.ndarray) -> np.ndarray:
        # phi(z) en los cortes de la acumulada; el borde superior se fuerza a 0
        # para que la correccion sume exactamente cero sobre el grid truncado.
        cdf = np.clip(np.cumsum(p), 0.0, 1.0)
        phi = norm.pdf(norm.ppf(np.clip(cdf, 1e-12, 1 - 1e-12)))
        phi[-1] = 0.0
        return np.diff(np.concatenate(([0.0], phi)))

    indep = np.outer(ph, pa)
    grid = indep + score_rho * np.outer(_dphi(ph), _dphi(pa))
    # En la cola profunda el termino independiente cae a ~1e-12 y la correccion
    # puede superarlo, dejando una celda negativa. Se recorta.
    #
    # Se probo amortiguar la correccion ENTERA por un escalar en vez de recortar
    # (preservaria las marginales de forma exacta) y NO SIRVE: el factor sale
    # proporcional a 1/rho, asi que el resultado queda identico para todo rho --
    # el parametro deja de tener efecto. Queda registrado para no reintentarlo.
    #
    # El recorte sesga las marginales. Error maximo MEDIDO (2026-08-26):
    #
    #   rho      NHL (Poisson 2.9/2.8)   MLB (NegBin 4.6/4.3, k=3.8)
    #   -0.06         1.4e-10                   2.0e-05
    #   -0.09         1.6e-08                   7.9e-05
    #   -0.12         4.7e-07                   2.1e-04
    #   -0.20         2.9e-05                   7.5e-04
    #
    # En NHL, que es el unico alcance aprobado, el sesgo en el punto de trabajo
    # (-0.06) es 1e-10: seis ordenes por debajo del ultimo decimal servido. La
    # NegBin tiene colas mas gruesas y recorta mas, por eso el bound se fijo en
    # 0.15 y no mas arriba: pasado ahi el error crece a 1e-3.
    #
    # El parametro es ademas casi 1:1 con la correlacion inducida
    # (rho=-0.06 -> -0.0568 en NHL), asi que se interpreta en la misma escala en
    # que se midio el defecto.
    #
    # NO se renormaliza aqui: `poisson_match_probs` ya divide por la masa del
    # grid truncado, y renormalizar solo en la rama rho!=0 rompia la
    # continuidad con rho=0.
    return np.clip(grid, 0.0, None)


def poisson_match_probs(lam_home: float, lam_away: float, spread_line: float | None,
                        total_line: float | None, three_way: bool = False,
                        max_goals: int = 15, dc_rho: float = 0.0,
                        dispersion_k: float | None = None,
                        score_rho: float = 0.0):
    """Exact probabilities from per-team scoring over a joint score grid.

    Returns home/away win (+draw if three_way), spread cover and total O/U.
    For 2-way sports (NHL regulation+OT), the draw mass is reallocated 50/50
    unless the adapter overrides with an OT model. dc_rho != 0 applies the
    Dixon-Coles low-score adjustment (the grid is renormalized afterwards).
    ``score_rho`` correlates the two teams' scores across the WHOLE grid, unlike
    dc_rho which only touches the i,j<=1 corner; see `_joint_grid`. Default 0.0
    reproduces independence byte for byte.
    """
    p_home = score_pmf(lam_home, max_goals, dispersion_k)
    p_away = score_pmf(lam_away, max_goals, dispersion_k)
    joint = _joint_grid(p_home, p_away, score_rho)
    win = draw = loss = 0.0
    cover = push = 0.0
    over = total_push = 0.0
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            p = float(joint[i, j])
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
