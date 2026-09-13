"""El id de liga compone RUTAS DE FICHERO y llega de una respuesta remota.

AUD-MED-002 (auditoria integral 2026-09-10). `scripts/run_all.py:_active_tennis`
descubre los torneos de tenis dinamicamente y devuelve `s["key"]` de la respuesta
de /sports **literal**; `daily._league_meta` aceptaba cualquier cosa que empezara
por `tennis_` sin lista blanca -- a diferencia de las ramas de SPORT_KEYS y de
futbol, que exigen pertenencia y lanzan KeyError. Ese id se interpola en
`predictions_{league}.csv`, `candidates_{league}.csv`, `odds_{league}_{mes}.csv`
y en el nombre del `.joblib` del calibrador (que se abre con joblib.load, es
decir deserializacion de pickle).

Reproducido antes del arreglo: `_league_meta("tennis_../../../configs/x")` NO
lanzaba, y la ruta resuelta caia fuera de `data/predictions`.
"""
from __future__ import annotations

import pytest

from sqp.pipeline.daily import _league_meta

BARRA = chr(47)
CONTRABARRA = chr(92)


@pytest.mark.parametrize("league", [
    "tennis_" + BARRA.join(["..", "..", "..", "configs", "x"]),
    "tennis_a" + CONTRABARRA + "b",
    "tennis_a" + BARRA + "b",
    "tennis_atp" + BARRA,
    "TENNIS_ATP",          # el alfabeto es minuscula: una clave rara no pasa
    "tennis_a b",
    "nba;rm",
    "..",
    "",
])
def test_un_id_que_puede_componer_una_ruta_se_rechaza(league):
    with pytest.raises(KeyError):
        _league_meta(league)


@pytest.mark.parametrize("league,sport_key", [
    ("nba", "basketball_nba"),
    ("mlb", "baseball_mlb"),
    ("epl", "soccer_epl"),
    ("atp", "atp"),
    ("wta", "wta"),
    ("tennis_atp_wimbledon", "tennis_atp_wimbledon"),
])
def test_las_ligas_legitimas_siguen_resolviendo(league, sport_key):
    """Contraprueba obligatoria: un guard que rechaza de mas es una liga perdida,
    y los torneos de tenis SI llevan guiones bajos."""
    assert _league_meta(league)["sport_key"] == sport_key
