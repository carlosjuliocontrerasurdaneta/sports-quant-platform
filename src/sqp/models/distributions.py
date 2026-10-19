"""Score/margin/total distribution models shared by adapters.

- Normal margin/total: basketball, american football (continuous approx).
- Poisson per-team scoring: hockey, soccer, baseball (count processes).

Every function returns *estimated probabilities*.
"""
from __future__ import annotations
import math
import warnings
from numbers import Integral

import numpy as np
from scipy.stats import nbinom, norm, poisson

from sqp.markets.settlement_math import (combine_adjacent_lines, is_quarter_line,
                                         split_asian_line)


def _finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value}")


def _normal_parameters(mean: float, sigma: float) -> None:
    _finite("mean", mean)
    _finite("sigma", sigma)
    if sigma <= 0:
        raise ValueError(f"sigma must be positive, got {sigma}")


def normal_margin_probs(mu_margin: float, sigma: float, spread_line: float | None):
    """P(home wins) and P(home covers `spread_line`) under margin ~ N(mu, sigma).

    spread_line is the HOME handicap (e.g. -5.5 means home must win by 6+).
    Continuity-corrected at 0.5 around pushes is intentionally omitted for
    half-point lines; integer lines return push-excluded probabilities.
    """
    _normal_parameters(mu_margin, sigma)
    if spread_line is not None:
        _finite("spread_line", spread_line)
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
    _normal_parameters(mu_total, sigma)
    _finite("total_line", total_line)
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
    _finite("lam", lam)
    if lam < 0:
        raise ValueError(f"lam must be non-negative, got {lam}")
    if isinstance(max_goals, bool) or not isinstance(max_goals, Integral) or max_goals < 0:
        raise ValueError("max_goals must be a non-negative integer")
    if k is not None:
        _finite("k", k)
    # One vectorized SciPy call instead of one dispatch per score. Keep the
    # list return type and the existing k<=0 Poisson fallback for compatibility.
    scores = np.arange(max_goals + 1)
    if k is None or k <= 0:
        return poisson.pmf(scores, lam).tolist()
    return nbinom.pmf(scores, k, k / (k + lam)).tolist()


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
                        score_rho: float = 0.0, tie_adds_goal: bool = False):
    """Exact probabilities from per-team scoring over a joint score grid.

    Returns home/away win (+draw if three_way), spread cover and total O/U.
    For 2-way sports (NHL regulation+OT), the draw mass is reallocated 50/50
    unless the adapter overrides with an OT model. dc_rho != 0 applies the
    Dixon-Coles low-score adjustment (the grid is renormalized afterwards).
    ``score_rho`` correlates the two teams' scores across the WHOLE grid, unlike
    dc_rho which only touches the i,j<=1 corner; see `_joint_grid`. Default 0.0
    reproduces independence byte for byte.

    ``tie_adds_goal`` (audit-2026-10-18, AUD-001): in the NHL a regulation tie
    ALWAYS ends with one more goal (OT or the shootout winner's goal), so the
    tie cell (k,k) is not a final score: it becomes (k+1,k) and (k,k+1) with
    half the mass each. The draw split for h2h stays 50/50; totals count
    that mass as 2k+1, not 2k -- before, P(Over) was biased 2-5 pp
    with a sign that alternated with the line's parity (n=4.658 NHL games since
    2023-10, 0 ties). Spreads see the one-goal margin. Only for 2-way leagues.

    The rates passed in are fit on FINAL scores, which already include that
    extra goal; using them as regulation rates and then adding it would push
    the expected final total up by P(tie) (~0.17 goals in the NHL). So the two
    rates are scaled by one common factor (the home/away split is kept) until
    the grid's expected FINAL total equals ``lam_home + lam_away``. Measured on
    the NHL history at its mean total (6.158): P(Over) 4.5/5.5/6.5/7.5 =
    0.764/0.553/0.442/0.255 against 0.781/0.558/0.444/0.244 observed (before:
    0.736/0.579/0.419/0.278; adding the goal WITHOUT rescaling: 0.783/0.579/
    0.469/0.278). The rescaling DOES move h2h and spreads slightly: smaller
    rates mean fewer goals of separation (Fable review 2026-10-18: h2h up to
    -0.22 pp, puck line -1.5 -0.3 to -0.6 pp). And the final total now depends a
    little on the split: balanced teams tie more often.
    """
    _finite("dc_rho", dc_rho)
    if tie_adds_goal and three_way:
        raise ValueError("tie_adds_goal only applies to 2-way leagues (three_way=False)")
    if spread_line is not None:
        _finite("spread_line", spread_line)
    if total_line is not None:
        _finite("total_line", total_line)
    if tie_adds_goal:
        lam_home, lam_away = _regulation_rates(lam_home, lam_away, max_goals,
                                               dispersion_k, score_rho, dc_rho)
    p_home = score_pmf(lam_home, max_goals, dispersion_k)
    p_away = score_pmf(lam_away, max_goals, dispersion_k)
    joint = _joint_grid(p_home, p_away, score_rho)
    # LINEAS ASIATICAS DE CUARTO (auditoria integral 2026-09-17, AUD-001).
    # Una linea +-x.25 / +-x.75 liquida la mitad del stake en cada una de las
    # dos lineas de medio punto adyacentes (`settle._grade`, AUD-MED-002).
    # Este pricing la trataba como una linea entera -- con margen entero el
    # push era siempre 0 --, asi que la probabilidad servida se desviaba
    # 7-13 pp de la coherente con la liquidacion (reproducido: Under 2.25
    # 0.544 frente a 0.477) e invertia el signo del EV. Se acumulan las masas
    # de cada linea adyacente y se combinan con `combine_adjacent_lines`; la
    # probabilidad servida es la de DECISION (win_units / (win_units +
    # loss_units)), la misma convencion que ya elimina la masa push en las
    # lineas de medio punto y enteras, para las que el calculo no cambia.
    spread_lines = _adjacent_lines(spread_line)
    total_lines = _adjacent_lines(total_line)
    win = draw = loss = 0.0
    cover = [0.0] * len(spread_lines)
    push = [0.0] * len(spread_lines)
    over = [0.0] * len(total_lines)
    total_push = [0.0] * len(total_lines)
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
            # Final (margin, total, mass) cells this grid cell settles as.
            cells: tuple[tuple[int, int, float], ...]
            if tie_adds_goal and m == 0:
                cells = ((1, t + 1, p / 2.0), (-1, t + 1, p / 2.0))
            else:
                cells = ((m, t, p),)
            for mf, tf, pf in cells:
                for k, line in enumerate(spread_lines):
                    if mf > -line: cover[k] += pf
                    elif mf == -line: push[k] += pf
                for k, line in enumerate(total_lines):
                    if tf > line: over[k] += pf
                    elif tf == line: total_push[k] += pf
    mass = win + draw + loss  # normalize truncated grid mass
    if not math.isfinite(mass) or mass <= 0:
        raise ValueError("score grid has no finite positive mass; check rates and max_goals")
    win, draw, loss = win / mass, draw / mass, loss / mass
    out: dict[str, float] = {}
    if three_way:
        out.update({"home_win": win, "draw": draw, "away_win": loss})
    else:
        out.update({"home_win": win + draw * 0.5, "away_win": loss + draw * 0.5})
    if spread_line is not None:
        out["home_cover"] = _decision_probability(cover, push, mass)
        out["away_cover"] = 1.0 - out["home_cover"]
    if total_line is not None:
        out["over"] = _decision_probability(over, total_push, mass)
        out["under"] = 1.0 - out["over"]
    return out


def _tie_mass_and_mean(lam_home: float, lam_away: float, max_goals: int,
                       dispersion_k: float | None, score_rho: float,
                       dc_rho: float) -> tuple[float, float]:
    """(P(tie), E[total]) of the normalized regulation grid, with the same
    pmf, correlation and Dixon-Coles terms `poisson_match_probs` uses."""
    joint = _joint_grid(score_pmf(lam_home, max_goals, dispersion_k),
                        score_pmf(lam_away, max_goals, dispersion_k), score_rho)
    n = max_goals + 1
    if dc_rho:
        joint = joint.copy()
        for i in range(min(2, n)):
            for j in range(min(2, n)):
                joint[i, j] *= max(0.0, _dixon_coles_tau(i, j, lam_home, lam_away, dc_rho))
    mass = float(joint.sum())
    if not math.isfinite(mass) or mass <= 0:
        raise ValueError("score grid has no finite positive mass; check rates and max_goals")
    totals = np.add.outer(np.arange(n), np.arange(n))
    return float(np.trace(joint)) / mass, float((joint * totals).sum()) / mass


_REGULATION_C_MIN = 1e-6


def _regulation_rates(lam_home: float, lam_away: float, max_goals: int,
                      dispersion_k: float | None, score_rho: float,
                      dc_rho: float) -> tuple[float, float]:
    """Rates c*lam_home, c*lam_away whose grid, with the tie goal added,
    has expected FINAL total lam_home + lam_away (AUD-001). Bisection on c in
    (0, 1]: the final mean c*L + P(tie) grows with c, tends to 1 (a sure 0-0
    tie plus its goal) as c -> 0, and c=1 already overshoots. So a solution
    exists for any total above 1 goal, the minimum possible final total."""
    target = lam_home + lam_away
    lo, hi = _REGULATION_C_MIN, 1.0
    for _ in range(50):
        mid = (lo + hi) / 2.0
        tie, mean = _tie_mass_and_mean(mid * lam_home, mid * lam_away, max_goals,
                                       dispersion_k, score_rho, dc_rho)
        if mean + tie < target:
            lo = mid
        else:
            hi = mid
    c = (lo + hi) / 2.0
    # Saturated at a bracket end: no factor reproduces the target, which only
    # happens for a total of 1 goal or less, impossible when every tie adds one
    # (Fable review 2026-10-18 asked for a loud signal). A first bracket of
    # [0.5, 1] saturated on an ordinary low-scoring input (total 1.1 in
    # `tests/test_market_tuning.py`), so the bracket is (0, 1]. The signal is
    # a warning, not an exception: an impossible input must not take down the
    # daily run of every league; the rates are used as given.
    if c - _REGULATION_C_MIN < 1e-9 or 1.0 - c < 1e-9:
        warnings.warn(
            f"tie_adds_goal: no regulation rates reproduce a final total of "
            f"{target:.3f} (factor saturated at {c:.6g}); rates used unscaled",
            RuntimeWarning, stacklevel=3)
        return lam_home, lam_away
    return c * lam_home, c * lam_away


def _adjacent_lines(line: float | None) -> list[float]:
    """[line] para lineas enteras/medias; las dos adyacentes para las de cuarto."""
    if line is None:
        return []
    if is_quarter_line(line):
        return list(split_asian_line(line))
    return [line]


def _decision_probability(win_mass: list[float], push_mass: list[float], mass: float) -> float:
    """P(gana | no push) sobre una linea, o su equivalente ponderado por stake
    sobre dos lineas adyacentes de medio punto (medias victorias/derrotas)."""
    if len(win_mass) == 1:
        w, p = win_mass[0] / mass, push_mass[0] / mass
        return w / max(1e-12, 1.0 - p)
    lines = []
    for w, p in zip(win_mass, push_mass):
        w, p = w / mass, p / mass
        lines.append((w, p, max(0.0, 1.0 - w - p)))
    sp = combine_adjacent_lines(lines[0], lines[1])
    resolved = sp.win_units + sp.loss_units
    return sp.win_units / resolved if resolved > 1e-12 else 0.5


def elo_diff_to_margin(elo_diff: float, points_per_elo: float) -> float:
    """Map an Elo difference to an expected scoring margin (sport-calibrated)."""
    return elo_diff * points_per_elo
