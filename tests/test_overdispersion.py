"""Sobredispersion en el marcador de beisbol (auditoria 2026-07-31).

Poisson exige Var(y|lambda) = lambda. Medido walk-forward sobre el historico:

    MLB   14.223 equipos-partido   dispersion 2.21   <- Poisson muy mal
    NHL   52.540 equipos-partido   dispersion 1.01   <- Poisson exacto

El beisbol anota a rachas (una entrada grande de 7 carreras y ocho en blanco),
asi que la varianza real dobla la que Poisson admite. Consecuencia: el modelo
subestima las colas y se vuelve sobreconfiado en totals y runline -- el mismo
fallo que los sigmas estrechos, en forma distributiva.

La correccion es una binomial negativa, que anade un parametro de dispersion k y
tiende a Poisson cuando k -> infinito. Se implementa como opcional para que
hockey y futbol (donde Poisson SI encaja) queden byte-identicos.

    Var = mu + mu^2/k    ->    k = mu^2/(Var - mu)    ->    k(MLB) ~ 3.8
"""
from __future__ import annotations

import numpy as np
import pytest

from sqp.models.distributions import poisson_match_probs, score_pmf


# --- la pmf: Poisson por defecto, binomial negativa con k --------------------

def test_without_k_the_pmf_is_poisson():
    from scipy.stats import poisson
    got = score_pmf(3.5, max_goals=15, k=None)
    exp = [poisson.pmf(i, 3.5) for i in range(16)]
    assert np.allclose(got, exp)


def test_with_k_the_variance_matches_the_negative_binomial_formula():
    mu, k = 4.57, 3.8
    p = np.array(score_pmf(mu, max_goals=60, k=k))
    x = np.arange(len(p))
    m = float((p * x).sum())
    v = float((p * (x - m) ** 2).sum())
    assert m == pytest.approx(mu, rel=0.01)
    assert v == pytest.approx(mu + mu * mu / k, rel=0.03)


def test_a_smaller_k_means_more_dispersion():
    def var(k):
        p = np.array(score_pmf(4.5, 60, k))
        x = np.arange(61)
        return float((p * (x - (p * x).sum()) ** 2).sum())

    assert var(2.0) > var(8.0) > var(None)


def test_the_pmf_sums_to_one_on_a_generous_grid():
    for k in (None, 3.8, 1.0, 50.0):
        assert sum(score_pmf(4.5, 200, k)) == pytest.approx(1.0, abs=1e-9)


def test_truncation_loss_is_negligible_with_the_production_grid():
    """max_score=25 y k=3.8 (beisbol) sobre los lambdas reales de una MLB: la
    cola de la binomial negativa es mas larga que la de Poisson, asi que la
    rejilla pierde algo de masa. Se comprueba que es despreciable; ademas
    poisson_match_probs renormaliza despues."""
    for lam in (3.5, 4.5, 6.0):
        perdida = 1.0 - sum(score_pmf(lam, 25, 3.8))
        assert perdida < 1e-3, f"lambda={lam}: se pierde {perdida:.2e} de masa"


# --- integracion con el motor de probabilidades ------------------------------

def test_dispersion_none_is_byte_identical_to_the_current_behaviour():
    """Guard de no-regresion para hockey y futbol, donde Poisson SI encaja."""
    base = poisson_match_probs(3.1, 2.6, -1.5, 6.5)
    same = poisson_match_probs(3.1, 2.6, -1.5, 6.5, dispersion_k=None)
    assert base == same


def test_overdispersion_fattens_the_tails_of_the_total():
    """Con la misma media, mas dispersion sube la probabilidad de superar una
    linea alta: es exactamente la sobreconfianza que se corrige."""
    linea_alta = 12.5
    poi = poisson_match_probs(4.6, 4.4, None, linea_alta)["over"]
    nb = poisson_match_probs(4.6, 4.4, None, linea_alta, dispersion_k=3.8)["over"]
    assert nb > poi


def test_overdispersion_moves_a_central_line_toward_one_half():
    poi = poisson_match_probs(5.2, 4.0, None, 8.5)["over"]
    nb = poisson_match_probs(5.2, 4.0, None, 8.5, dispersion_k=3.8)["over"]
    assert abs(nb - 0.5) < abs(poi - 0.5)


def test_probabilities_stay_normalised_with_dispersion():
    out = poisson_match_probs(4.6, 4.4, -1.5, 8.5, dispersion_k=3.8)
    assert out["home_win"] + out["away_win"] == pytest.approx(1.0, abs=1e-6)
    assert out["over"] + out["under"] == pytest.approx(1.0, abs=1e-6)
    assert out["home_cover"] + out["away_cover"] == pytest.approx(1.0, abs=1e-6)


# --- configuracion por familia -----------------------------------------------

def test_baseball_declares_the_measured_dispersion_and_hockey_does_not():
    from sqp.sports.registry import get_adapter
    mlb = get_adapter("mlb", "baseball", None).params.get("dispersion_k")
    nhl = get_adapter("nhl", "hockey", None).params.get("dispersion_k")
    assert mlb is not None and 3.0 <= mlb <= 5.0, (
        f"beisbol: dispersion_k={mlb}, se midio 3.8 sobre 14.223 equipos-partido")
    assert nhl is None, (
        f"hockey: dispersion medida 1.01 (Poisson exacto), no debe llevar k; got {nhl}")
