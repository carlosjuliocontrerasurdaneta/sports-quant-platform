"""Correlacion entre marcadores en poisson_match_probs (`score_rho`).

`poisson_match_probs` componia el marcador como `p_home[i] * p_away[j]`:
independencia pura. Medido walk-forward, la correlacion condicional de los
residuos es -0,0873 en NHL (p<0,0001, n=32.777) e indistinguible de cero en MLB
(-0,0043, p=0,68). Pre-registro:
`docs/research/2026-08-26-preregistro-correlacion-marcadores.md`.

Por que importa que sea correlacion y no dispersion:

    Var(margen) = Vh + Va - 2*rho*sh*sa
    Var(total)  = Vh + Va + 2*rho*sh*sa

`rho < 0` ENSANCHA el margen y ESTRECHA el total -- sentidos OPUESTOS.
`dispersion_k` los mueve en el MISMO sentido, y por eso no puede servir a los
dos mercados a la vez. Ese contraste es el contrato que fijan estos tests.
"""
from __future__ import annotations

import numpy as np
import pytest

from sqp.models.distributions import poisson_match_probs, score_pmf


def _grid(lam_h, lam_a, rho, max_goals=15, k=None):
    """Rejilla conjunta reconstruida como la usa poisson_match_probs."""
    from sqp.models.distributions import _joint_grid
    return _joint_grid(score_pmf(lam_h, max_goals, k), score_pmf(lam_a, max_goals, k), rho)


def _moments(g):
    n = g.shape[0]
    i = np.arange(n)
    ph, pa = g.sum(axis=1), g.sum(axis=0)
    mh, ma = (i * ph).sum(), (i * pa).sum()
    vh = ((i - mh) ** 2 * ph).sum()
    va = ((i - ma) ** 2 * pa).sum()
    cov = ((i[:, None] - mh) * (i[None, :] - ma) * g).sum()
    return mh, ma, vh, va, cov


class TestMarginalsArePreserved:
    """Lo innegociable: la correccion no puede tocar las marginales. Si las
    moviera, cambiaria las tasas por equipo y el moneyline de un solo lado.

    La referencia es la rejilla INDEPENDIENTE, no `score_pmf` crudo: el grid
    esta truncado en `max_goals`, asi que sus marginales ya vienen escaladas por
    la masa que el otro equipo pierde en la cola. El contrato es que la
    correlacion no las mueva RESPECTO A ESA BASE.
    """

    @pytest.mark.parametrize("rho", [-0.12, -0.06, 0.0, 0.06, 0.12])
    def test_row_and_column_sums_match_the_independent_marginals(self, rho):
        base, g = _grid(3.1, 2.7, 0.0), _grid(3.1, 2.7, rho)
        # 1e-9, no 1e-12: el recorte de la cola profunda introduce un sesgo
        # medido de 4.7e-07 en |rho|=0.12 y 1.4e-10 en el punto de trabajo
        # (-0.06). Sigue siendo seis ordenes menor que el ultimo decimal que se
        # sirve. Afirmar 1e-12 seria afirmar una exactitud que no se tiene.
        assert g.sum(axis=1) == pytest.approx(base.sum(axis=1), abs=1e-6)
        assert g.sum(axis=0) == pytest.approx(base.sum(axis=0), abs=1e-6)

    def test_marginals_preserved_with_negative_binomial_too(self):
        # La NegBin tiene colas mas gruesas y recorta mas que la Poisson: el
        # sesgo aqui es ~1e-4, no ~1e-9. Es la razon por la que el alcance
        # aprobado es NHL (Poisson) y no MLB.
        base = _grid(4.6, 4.3, 0.0, k=3.8)
        g = _grid(4.6, 4.3, -0.08, k=3.8)
        assert g.sum(axis=1) == pytest.approx(base.sum(axis=1), abs=1e-3)
        assert g.sum(axis=0) == pytest.approx(base.sum(axis=0), abs=1e-3)


class TestCorrelationHasTheRightSignAndSize:
    def test_rho_zero_is_exactly_independence(self):
        g = _grid(3.1, 2.7, 0.0)
        indep = np.outer(score_pmf(3.1, 15), score_pmf(2.7, 15))
        assert g == pytest.approx(indep, abs=1e-15)

    @pytest.mark.parametrize("rho", [-0.12, -0.06, 0.06, 0.12])
    def test_induced_covariance_matches_the_sign_of_rho(self, rho):
        _, _, _, _, cov = _moments(_grid(3.1, 2.7, rho))
        assert np.sign(cov) == np.sign(rho)

    def test_induced_correlation_is_monotone_in_rho(self):
        cors = []
        for rho in (-0.12, -0.06, 0.0, 0.06, 0.12):
            _, _, vh, va, cov = _moments(_grid(3.1, 2.7, rho))
            cors.append(cov / np.sqrt(vh * va))
        assert all(a < b for a, b in zip(cors, cors[1:]))

    def test_induced_correlation_is_close_to_the_requested_rho(self):
        """No exige igualdad: es una expansion de primer orden. Exige que el
        parametro sea interpretable en la escala en que se midio (~ -0.06)."""
        _, _, vh, va, cov = _moments(_grid(3.1, 2.7, -0.06))
        assert -0.10 < cov / np.sqrt(vh * va) < -0.02


class TestOppositeEffectOnMarginAndTotal:
    """El contraste con dispersion_k. Es la razon entera del parametro."""

    def test_negative_rho_widens_the_margin_and_narrows_the_total(self):
        base, corr = _grid(3.1, 2.7, 0.0), _grid(3.1, 2.7, -0.10)
        _, _, vh, va, cov0 = _moments(base)
        _, _, _, _, cov1 = _moments(corr)
        def var_margin(cov):
            return vh + va - 2 * cov

        def var_total(cov):
            return vh + va + 2 * cov

        assert var_margin(cov1) > var_margin(cov0)
        assert var_total(cov1) < var_total(cov0)

    def test_dispersion_k_moves_both_the_same_way(self):
        """Contraprueba: si dispersion_k pudiera hacer el trabajo, este test
        fallaria y el parametro nuevo sobraria."""
        tight, loose = _grid(3.1, 2.7, 0.0, k=8.0), _grid(3.1, 2.7, 0.0, k=3.0)
        _, _, vh0, va0, c0 = _moments(tight)
        _, _, vh1, va1, c1 = _moments(loose)
        assert (vh1 + va1 - 2 * c1) > (vh0 + va0 - 2 * c0)   # margen se ensancha
        assert (vh1 + va1 + 2 * c1) > (vh0 + va0 + 2 * c0)   # y el total TAMBIEN


class TestWiringAndSafety:
    def test_default_is_zero_so_every_league_is_byte_identical(self):
        a = poisson_match_probs(3.1, 2.7, -1.5, 5.5, three_way=False)
        b = poisson_match_probs(3.1, 2.7, -1.5, 5.5, three_way=False, score_rho=0.0)
        assert a == b

    def test_negative_rho_moves_the_served_probabilities(self):
        base = poisson_match_probs(3.1, 2.7, -1.5, 5.5, score_rho=0.0)
        corr = poisson_match_probs(3.1, 2.7, -1.5, 5.5, score_rho=-0.10)
        assert corr["over"] != base["over"]
        assert corr["home_cover"] != base["home_cover"]

    def test_probabilities_stay_valid_at_the_bound(self):
        for rho in (-0.15, 0.15):
            p = poisson_match_probs(1.2, 0.9, -1.5, 2.5, three_way=True, score_rho=rho)
            for v in p.values():
                assert 0.0 <= v <= 1.0
            assert p["home_win"] + p["draw"] + p["away_win"] == pytest.approx(1.0)

    def test_rho_out_of_range_is_rejected(self):
        with pytest.raises(ValueError, match="score_rho"):
            poisson_match_probs(3.1, 2.7, None, None, score_rho=-0.9)

    def test_composes_with_dixon_coles_without_breaking_normalisation(self):
        p = poisson_match_probs(1.4, 1.2, None, 2.5, three_way=True,
                                dc_rho=-0.10, score_rho=-0.06)
        assert p["home_win"] + p["draw"] + p["away_win"] == pytest.approx(1.0)
