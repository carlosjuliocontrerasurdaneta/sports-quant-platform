"""Corte temporal de las features pregame de `sqp.features.rest_form` (AUD-LOW-005).

`team_rest_days` era la UNICA que recibia fecha de corte y la aplicaba; las
otras diez tomaban "las ultimas n" de la lista que les dieran, asi que la
proteccion contra look-ahead vivia entera en el llamador. No habia fuga -- los
dos consumidores recortan antes --, pero un tercero que pasara el historial
completo la introducia en diez features a la vez, sin error ni aviso.

Estos tests fijan las dos mitades del contrato: que el recorte OCURRE, y que
sobre una lista ya recortada es un no-op EXACTO (que es lo que hace seguro
haberlo anadido a un pipeline en produccion).
"""
from __future__ import annotations

import pytest

from sqp.features.rest_form import (team_avg_conceded, team_avg_margin,
                                    team_avg_scored, team_avg_total,
                                    team_h2h_form, team_over_rate,
                                    team_recent_form, team_recent_form_away,
                                    team_recent_form_home, team_streak)

REF = "2026-06-10"


def _g(date: str, home: str, away: str, hs: int, aws: int) -> dict:
    return {"date": date, "home": home, "away": away,
            "home_score": hs, "away_score": aws}


# A pierde SIEMPRE antes del corte y gana SIEMPRE despues. Cualquier feature que
# mire el futuro se delata con el signo.
PASADO = [_g("2026-06-01", "A", "B", 0, 3), _g("2026-06-03", "B", "A", 3, 0),
          _g("2026-06-05", "A", "B", 0, 3), _g("2026-06-07", "B", "A", 3, 0)]
FUTURO = [_g("2026-06-11", "A", "B", 9, 0), _g("2026-06-13", "B", "A", 0, 9),
          _g("2026-06-15", "A", "B", 9, 0), _g("2026-06-17", "B", "A", 0, 9)]
TODO = PASADO + FUTURO

# (funcion, args extra). Se excluye `team_rest_days`: ya recortaba.
CASOS = [
    (team_recent_form, ("A", TODO, 5)),
    (team_recent_form_home, ("A", TODO, 5)),
    (team_recent_form_away, ("A", TODO, 5)),
    (team_avg_margin, ("A", TODO, 10)),
    (team_avg_scored, ("A", TODO, 10)),
    (team_avg_conceded, ("A", TODO, 10)),
    (team_avg_total, ("A", TODO, 10)),
    (team_streak, ("A", TODO)),
]


@pytest.mark.parametrize("fn,args", CASOS, ids=lambda v: getattr(v, "__name__", ""))
def test_reference_date_excludes_the_future(fn, args):
    """Con el historial COMPLETO y fecha de corte, el resultado debe ser el
    mismo que con el pasado a secas -- y distinto del que sale sin corte."""
    *cabeza, _ = args
    con_corte = fn(*args, None, REF)
    solo_pasado = fn(*[PASADO if a is TODO else a for a in args])
    sin_corte = fn(*args)
    assert con_corte == solo_pasado, "el corte debe dejar exactamente el pasado"
    assert con_corte != sin_corte, "sin corte se cuela el futuro (el test seria mudo)"


@pytest.mark.parametrize("fn,args", CASOS, ids=lambda v: getattr(v, "__name__", ""))
def test_cutoff_is_a_no_op_on_an_already_trimmed_list(fn, args):
    """La razon por la que anadirlo a produccion es seguro: los dos consumidores
    ya recortan (`roi_engine._prior_games` con `d < rd`; daily con el historico
    liquidado), asi que sobre esas listas el filtro no cambia NADA."""
    recortado = [PASADO if a is TODO else a for a in args]
    assert fn(*recortado, None, REF) == fn(*recortado)


def test_h2h_and_over_rate_also_cut():
    """Las dos de firma distinta, aparte del parametrize."""
    assert team_h2h_form("A", "B", TODO, 10, None, REF) == team_h2h_form("A", "B", PASADO, 10)
    assert team_h2h_form("A", "B", TODO, 10) != team_h2h_form("A", "B", PASADO, 10)
    assert (team_over_rate("A", TODO, 5.0, 10, None, REF)
            == team_over_rate("A", PASADO, 5.0, 10))
    assert team_over_rate("A", TODO, 5.0, 10) != team_over_rate("A", PASADO, 5.0, 10)


def test_the_reference_day_itself_is_excluded():
    """Mismo criterio que `team_rest_days` (`d >= ref` fuera): un partido del
    propio dia del evento puede no haberse jugado cuando se estima."""
    mismo_dia = PASADO + [_g(REF, "A", "B", 9, 0)]
    assert team_recent_form("A", mismo_dia, 5, None, REF) == team_recent_form("A", PASADO, 5)


def test_unreadable_scores_leave_the_denominator(recwarn):
    """El divisor era `len(recent)`, asi que una fila con marcador ilegible se
    saltaba con `continue` pero seguia contando -- como DERROTA. Con pleno de
    victorias y una fila rota, el equipo salia 0,75 en vez de 1,0."""
    gana_siempre = [_g("2026-06-01", "A", "B", 3, 0), _g("2026-06-02", "A", "B", 3, 0),
                    _g("2026-06-03", "A", "B", 3, 0)]
    rota = dict(gana_siempre[0], date="2026-06-04", home_score=None)
    assert team_recent_form("A", gana_siempre, 5) == 1.0
    assert team_recent_form("A", gana_siempre + [rota], 5) == 1.0


def test_too_few_readable_games_is_none():
    """Un partido que no se puede graduar no es un partido disponible: el umbral
    de 2 se aplica a lo LEIDO, no a lo listado."""
    uno_bueno = [_g("2026-06-01", "A", "B", 3, 0),
                 dict(_g("2026-06-02", "A", "B", 3, 0), home_score="n/d")]
    assert team_recent_form("A", uno_bueno, 5) is None
