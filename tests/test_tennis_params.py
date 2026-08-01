"""Parametros del modelo de tenis (auditoria 2026-07-31).

El tenis tiene el modelo mas simple del sistema: Elo por jugador, dos parametros,
y solo el mercado de ganador. No hay handicap de juegos ni total de juegos.

elo_k MEDIDO walk-forward sobre 16.663 partidos (7.035 ATP + 9.628 WTA), con la
orientacion ALEATORIZADA en cada partido: el historico de tenis guarda
home = ganador, asi que evaluar tal cual daria 100% de acierto trivial y no
mediria nada.

    elo_k    log loss (arranque 50%)
      24       0.6597    <- valor anterior
      40       0.6563    <- optimo
      60       0.6585
      80       0.6649          (moneda = 0.6931)

La curva es claramente en U con minimo en 40, y el resultado se repite con
arranque del 20% y del 50%, y por separado en ATP y en WTA.

CONTEXTO HONESTO: 0.6563 frente a 0.6931 de una moneda es una mejora relativa de
apenas el 5%. El modelo de tenis explica muy poco, y no puede explicar mas
mientras ignore la SUPERFICIE -- probablemente el factor mas determinante del
tenis. El docstring del adaptador afirmaba "surface-aware" y no habia una sola
linea de codigo que manejase superficie (afirmacion corregida en esta auditoria).
"""
from __future__ import annotations

import pytest

from sqp.sports.registry import get_adapter


def _p(liga="tennis_atp_wimbledon"):
    return get_adapter(liga, "tennis", None).params


def test_elo_k_matches_the_measured_optimum():
    k = _p()["elo_k"]
    assert k == 40, (
        f"elo_k={k}; el optimo medido walk-forward sobre 16.663 partidos es 40 "
        "(log loss 0.6563 frente a 0.6597 con 24). Volver a medirlo antes de cambiarlo.")


def test_there_is_no_home_advantage_in_tennis():
    """Los torneos son en cancha neutral: cualquier ventaja de local seria un
    artefacto de que el historico guarda home = ganador."""
    assert _p()["elo_home_adv"] == 0


def test_tennis_only_estimates_the_match_winner():
    """Handicap de juegos y total de juegos exigen un modelo a nivel de juego que
    no existe. Este test evita que se afirme lo contrario sin implementarlo."""
    from sqp.domain.models import Event
    a = get_adapter("tennis_atp_wimbledon", "tennis", None)
    ev = Event(event_id="x", sport_key="tennis_atp_wimbledon", league="tennis_atp_wimbledon",
               home="A", away="B", start_time="2026-07-31T12:00:00Z")
    est = a.estimate(ev, spread_line=-2.5, total_line=22.5)
    assert est.home_win_estimated_probability is not None
    assert est.home_cover_estimated_probability is None, "no hay modelo de handicap de juegos"
    assert est.over_estimated_probability is None, "no hay modelo de total de juegos"


def test_the_docstring_does_not_claim_surface_awareness():
    """El adaptador afirmaba ser 'surface-aware' y no existe ninguna linea de
    codigo que maneje superficie. Afirmar una capacidad inexistente es peor que
    no tenerla: invita a confiar en el modelo para algo que no hace."""
    import inspect

    from sqp.sports.adapters import TennisAdapter
    doc = (inspect.getdoc(TennisAdapter) or "").lower()
    # No basta con buscar la cadena: el docstring la menciona a proposito para
    # explicar que la afirmacion se retiro. Lo que se exige es que declare
    # explicitamente la AUSENCIA.
    assert "no modela la superficie" in doc, (
        "el docstring debe declarar explicitamente que NO modela la superficie")
    afirma = any(f"{v} surface-aware" in doc for v in ("is", "es", ".", ","))
    assert not afirma, "el docstring vuelve a afirmar que maneja superficie"


def test_no_code_actually_handles_surface():
    """Guard del hecho, no del texto: si alguien implementa superficie de verdad,
    este test salta y hay que actualizar el docstring y volver a medir elo_k."""
    from pathlib import Path as _P

    import sqp
    raiz = _P(sqp.__file__).parent
    hits = [f.name for f in raiz.rglob("*.py")
            if any(t in f.read_text(encoding="utf-8").lower()
                   for t in ("surface_elo", "por_superficie", "surface_rating"))]
    assert hits == [], f"ya hay manejo de superficie en {hits}: actualizar el modelo de tenis"


@pytest.mark.parametrize("liga", ["tennis_atp_wimbledon", "tennis_wta_washington_open"])
def test_every_tournament_shares_the_tour_wide_parameters(liga):
    """El Elo es de tour completo: un torneo no debe llevar parametros propios
    mientras no haya evidencia por torneo para justificarlos."""
    assert _p(liga)["elo_k"] == 40
