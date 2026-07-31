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


# --- margin_sigma: gobierna los spreads ---------------------------------------
#
# Medido con el camino REAL del modelo (elo.rating_diff -> elo_diff_to_margin +
# ajuste por descanso), walk-forward sobre el historico completo. La NFL salio
# exacta (13.5 = 13.5), lo que confirma el metodo; las tres ligas universitarias
# heredaban los sigmas de las profesionales y estan muy por debajo: el deporte
# universitario tiene mucha mas varianza (palizas, disparidad de talento, sin
# draft igualador).
MARGIN_RESIDUAL = {"nba": 13.1, "wnba": 13.6, "ncaab": 15.6,
                   "wncaab": 18.2, "nfl": 13.5, "ncaaf": 20.2}
_FAMILIA = {"nba": "basketball", "wnba": "basketball", "ncaab": "basketball",
            "wncaab": "basketball", "nfl": "football", "ncaaf": "football"}


@pytest.mark.parametrize("liga,residual", sorted(MARGIN_RESIDUAL.items()))
def test_margin_sigma_matches_the_measured_residual(liga, residual):
    from sqp.config import CONFIG_DIR, load_yaml
    lp = (load_yaml(CONFIG_DIR / "leagues" / "ratings.yaml").get("leagues") or {}).get(liga)
    sigma = get_adapter(liga, _FAMILIA[liga], lp).params["margin_sigma"]
    assert abs(sigma - residual) <= TOLERANCIA, (
        f"{liga}: margin_sigma={sigma} se aparta del residual medido {residual}. "
        "Volver a medirlo walk-forward antes de cambiarlo.")


def test_college_leagues_are_wider_than_their_pro_counterparts():
    """Guard conceptual: el deporte universitario tiene mas varianza que el
    profesional. Si alguien vuelve a igualarlos, este test lo detiene."""
    from sqp.config import CONFIG_DIR, load_yaml
    rt = load_yaml(CONFIG_DIR / "leagues" / "ratings.yaml").get("leagues") or {}
    def g(lg):
        return get_adapter(lg, _FAMILIA[lg], rt.get(lg)).params["margin_sigma"]

    assert g("ncaab") > g("nba"), "NCAAB debe ser mas disperso que la NBA"
    assert g("wncaab") > g("wnba"), "WNCAAB debe ser mas disperso que la WNBA"
    assert g("ncaaf") > g("nfl"), "NCAAF debe ser mas disperso que la NFL"
