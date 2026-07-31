"""Dispersion de totals en baloncesto (auditoria 2026-07-31).

El marcador modelo-vs-mercado marco `wnba/totals` como el unico segmento donde el
mercado gana con claridad: Brier 0.336 frente a 0.250. Un Brier de 0.25 es lo que
da predecir siempre 0.5, asi que 0.336 significa equivocarse CON CONFIANZA, no por
ignorancia. La causa resulto ser la dispersion: el modelo asumia una desviacion
tipica del total muy inferior a la real, y una distribucion estrecha convierte una
diferencia pequena respecto a la linea en una probabilidad extrema.

Los valores de abajo son la desviacion tipica RESIDUAL medida walk-forward sobre
47.583 partidos historicos: desviacion de (total real - total esperado por el
modelo), prediciendo cada partido ANTES de incorporarlo. Es la cantidad correcta,
no la dispersion incondicional del total: el modelo ya varia su expectativa por
partido via `scoring.expected_total`, y usar la incondicional contaria esa
variacion dos veces.

    liga      antes   residual medido   fijado
    nba        19.0        21.6           22.0
    wnba       15.0        18.6           19.0
    ncaab      15.0        17.7           18.0
    wncaab     14.0        17.0           17.0

Si alguien cambia estos valores, este test salta: hay que volver a medir el
residual, no ajustarlo a ojo ni al resultado de una temporada.
"""
from __future__ import annotations

import pytest

from sqp.sports.registry import get_adapter

# (liga, residual medido walk-forward sobre el historico completo)
RESIDUAL_MEDIDO = {"nba": 21.6, "wnba": 18.6, "ncaab": 17.7, "wncaab": 17.0}
TOLERANCIA = 1.0  # redondeo al entero mas cercano


@pytest.mark.parametrize("liga,residual", sorted(RESIDUAL_MEDIDO.items()))
def test_total_sigma_matches_the_measured_residual(liga, residual):
    sigma = get_adapter(liga, "basketball", None).params["total_sigma"]
    assert abs(sigma - residual) <= TOLERANCIA, (
        f"{liga}: total_sigma={sigma} se aparta del residual medido {residual}. "
        "Volver a medirlo walk-forward antes de cambiarlo.")


@pytest.mark.parametrize("liga", sorted(RESIDUAL_MEDIDO))
def test_total_sigma_is_never_below_the_residual_by_more_than_rounding(liga):
    """Subestimar la dispersion produce sobreconfianza, que es el fallo concreto
    que se corrigio. Sobrestimarla solo resta discriminacion, que es mas benigno:
    el guard es asimetrico a proposito."""
    sigma = get_adapter(liga, "basketball", None).params["total_sigma"]
    assert sigma >= RESIDUAL_MEDIDO[liga] - 0.6, (
        f"{liga}: total_sigma={sigma} por debajo del residual "
        f"{RESIDUAL_MEDIDO[liga]} -> el modelo volveria a ser sobreconfiado.")


def test_a_wider_sigma_moves_probabilities_toward_one_half():
    """Comprobacion mecanica de la correccion: con la misma media y la misma
    linea, ensanchar la distribucion acerca la probabilidad a 0.5."""
    from sqp.models.distributions import normal_total_probs
    estrecha = normal_total_probs(171.0, 15.0, 178.0)["over"]
    ancha = normal_total_probs(171.0, 19.0, 178.0)["over"]
    assert estrecha < ancha < 0.5, "la mas ancha debe quedar mas cerca de 0.5"
