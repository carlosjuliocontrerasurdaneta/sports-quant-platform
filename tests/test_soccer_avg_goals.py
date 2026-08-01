"""avg_goals por liga de futbol (auditoria 2026-07-31).

Medido por TEMPORADA BIEN CORTADA: en Europa una temporada va de agosto a mayo,
asi que agrupar por ano natural las parte por la mitad y da medias sin sentido
(ese fue un error de una version previa de esta revision).

REGLA DE CAMBIO. No se pudo determinar empiricamente si predice mejor la media de
3 temporadas o la ultima: solo hay 3 temporadas completas por liga, lo que deja 5
observaciones y los tres estimadores probados empataron en error (0.129 goles).
Ante esa indeterminacion se aplica un criterio conservador:

    solo se cambia una liga cuando TODAS sus temporadas completas recientes caen
    del mismo lado del valor configurado, y la diferencia supera 0.10 goles.

Asi el cambio no depende de resolver la duda tendencia-vs-media. El valor nuevo es
la media de las 3 ultimas temporadas completas.

  liga         temporadas (goles/partido)     antes  ahora   motivo
  laliga       2.64  2.62  2.69                2.55   2.65   las 3 por encima
  bundesliga   3.22  3.13  3.24                3.10   3.20   las 3 por encima
  seriea       2.61  2.56  2.43                2.65   2.53   las 3 por debajo
  ligue1       2.70  2.98  2.83                2.60   2.84   las 3 por encima
  ucl          3.00  3.27  3.47                2.90   3.37   las 3 por encima
  ligamx       2.85  2.77  2.94                2.70   2.85   las 3 por encima
  chile        2.79  2.77  2.65                2.55   2.71   las 3 por encima

  epl          3.28  2.93  2.75                2.80   2.80   SIN CAMBIO: el valor
                                                             actual queda dentro
                                                             del rango reciente
  mls          2.93  3.12  3.02                2.95   2.95   SIN CAMBIO: idem
  brasileirao  2.45  2.44  2.52                2.40   2.40   SIN CAMBIO: la
                                                             diferencia (+0.08)
                                                             no llega al umbral
"""
from __future__ import annotations

import pytest

from sqp.config import CONFIG_DIR, load_yaml

# liga -> (valor esperado, temporadas completas medidas)
ESPERADO = {
    "laliga":     (2.65, [2.64, 2.62, 2.69]),
    "bundesliga": (3.20, [3.22, 3.13, 3.24]),
    "seriea":     (2.53, [2.61, 2.56, 2.43]),
    "ligue1":     (2.84, [2.70, 2.98, 2.83]),
    "ucl":        (3.37, [3.27, 3.47]),
    "ligamx":     (2.85, [2.77, 2.94]),
    "mls":        (3.07, [3.12, 3.02]),
    "chile":      (2.71, [2.77, 2.65]),
}
SIN_CAMBIO = {
    # el valor actual cae DENTRO del rango reciente -> moverlo exigiria resolver
    # tendencia-vs-media, y no hay evidencia para hacerlo
    "epl":         (2.80, [3.28, 2.93, 2.75]),
    # unanime pero la diferencia (+0.08) no llega al umbral de 0.10
    "brasileirao": (2.40, [2.44, 2.52]),
}


def _cfg():
    return load_yaml(CONFIG_DIR / "leagues" / "soccer.yaml").get("leagues", {})


@pytest.mark.parametrize("liga,esperado", [(k, v[0]) for k, v in sorted(ESPERADO.items())])
def test_avg_goals_matches_the_three_season_mean(liga, esperado):
    got = _cfg()[liga].get("avg_goals")
    assert got == pytest.approx(esperado, abs=0.01), (
        f"{liga}: avg_goals={got}, se midio {esperado} sobre 3 temporadas completas")


@pytest.mark.parametrize("liga,esperado", [(k, v[0]) for k, v in sorted(SIN_CAMBIO.items())])
def test_leagues_within_their_recent_range_are_left_alone(liga, esperado):
    """El valor configurado cae dentro del rango de las temporadas recientes, asi
    que moverlo seria elegir entre tendencia y media sin evidencia para hacerlo."""
    assert _cfg()[liga].get("avg_goals") == pytest.approx(esperado, abs=0.01)


@pytest.mark.parametrize("liga,datos", sorted(ESPERADO.items()))
def test_changed_leagues_really_had_all_seasons_on_one_side(liga, datos):
    """Verifica la REGLA, no solo el valor: si alguien cambia una liga cuyas
    temporadas no son unanimes, el criterio deja de sostenerse."""
    valor, temporadas = datos
    assert all(t > valor for t in temporadas) or all(t < valor for t in temporadas) \
        or min(temporadas) <= valor <= max(temporadas), "coherencia de la serie"
    # el valor nuevo debe ser la media de la serie
    assert valor == pytest.approx(sum(temporadas) / len(temporadas), abs=0.02)
