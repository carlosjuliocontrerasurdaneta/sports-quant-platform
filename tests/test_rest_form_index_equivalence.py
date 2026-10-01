"""Equivalencia bit a bit del indice por equipo (`TeamHistoryIndex`,
`compute_pregame_features`, `over_rate_from_index`) frente a la
implementacion ORIGINAL de `sqp.features.rest_form` (2026-09-30, optimizacion
de coste de `build_adjustment_context` / `rest_form.py`, autorizada por el
operador; revision de Fable pendiente).

Este fichero conserva una COPIA DE REFERENCIA congelada de las funciones que
`build_adjustment_context` llamaba antes de la optimizacion (`_ref_*`,
copiadas literalmente de `rest_form.py` en el commit previo a este cambio).
Es deliberado NO importarlas del modulo de produccion: si alguien optimiza
mas adelante y las modifica o las retira, este test debe seguir comparando
contra el comportamiento HISTORICO, no contra si mismo.

Cuatro capas de evidencia:
  1. Propiedad sobre historiales sinteticos aleatorios (semilla fija), varias
     "ligas" (pools de equipos), con los casos limite pedidos: equipo sin
     historial, fechas repetidas, partidos del mismo dia, ventanas mayores
     que el historial, y entrada NO ordenada por fecha (camino de respaldo
     del indice).
  2. Igualdad EXACTA (`==` y `hash`) de las 16 features y de
     `adjust_model_probability` con coeficientes no nulos.
  3. Reutilizacion de un `TeamHistoryIndex` precalculado (parametro opcional)
     frente a reconstruirlo por defecto: mismo resultado.
  4. Fragmento de datos REALES (NFL y NBA) leido del arbol principal
     (`--data-root` de la bateria, aqui vía variable de entorno /
     ruta explicita); se salta si el fichero no existe (CI).
"""
from __future__ import annotations

import math
import random
from datetime import date
from pathlib import Path

import pytest

from sqp.config import RiskConfig
from sqp.features.rest_form import (StaleTeamIndexError, TeamHistoryIndex,
                                    compute_pregame_features,
                                    h2h_p_adjustment, home_away_form_p_adjustment,
                                    margin_p_adjustment, off_def_p_adjustment,
                                    over_rate_from_index, over_under_rate_p_adjustment,
                                    rest_form_p_adjustment, streak_p_adjustment,
                                    team_avg_conceded, team_avg_margin, team_avg_scored,
                                    team_avg_total, team_h2h_form, team_recent_form,
                                    team_recent_form_away, team_recent_form_home,
                                    team_rest_days, team_streak,
                                    totals_tendency_p_adjustment)
from sqp.pipeline.probabilities import AdjustmentContext, adjust_model_probability, \
    build_adjustment_context

# ===========================================================================
# Copia de referencia (congelada): el codigo de `rest_form.py` ANTES de esta
# optimizacion. Prefijo `_ref_` para no colisionar con nada del modulo real.
# ===========================================================================


def _ref_hasta(results: list[dict], reference_date: str | None) -> list[dict]:
    if reference_date is None:
        return results
    ref = str(reference_date)[:10]
    return [r for r in results if str(r.get("date", ""))[:10] < ref]


def _ref_team_rest_days(team, results, reference_date, normalize=None):
    norm = normalize or (lambda x: x)
    team_n = norm(team)
    ref = reference_date[:10]
    last = None
    for r in results:
        d = str(r.get("date", ""))[:10]
        if d >= ref:
            continue
        if norm(str(r.get("home", ""))) == team_n or norm(str(r.get("away", ""))) == team_n:
            if last is None or d > last:
                last = d
    if last is None:
        return None
    return (date.fromisoformat(ref) - date.fromisoformat(last)).days


def _ref_team_recent_form(team, results, n=5, normalize=None, reference_date=None):
    results = _ref_hasta(results, reference_date)
    norm = normalize or (lambda x: x)
    team_n = norm(team)
    team_games = [r for r in results
                 if norm(str(r.get("home", ""))) == team_n
                 or norm(str(r.get("away", ""))) == team_n]
    recent = team_games[-n:]
    if len(recent) < 2:
        return None
    total, graded = 0.0, 0
    for r in recent:
        try:
            hs = float(r["home_score"])
            aws = float(r["away_score"])
        except (KeyError, TypeError, ValueError):
            continue
        graded += 1
        is_home = norm(str(r.get("home", ""))) == team_n
        if hs > aws:
            total += 1.0 if is_home else 0.0
        elif aws > hs:
            total += 0.0 if is_home else 1.0
        else:
            total += 0.5
    return total / graded if graded >= 2 else None


def _ref_team_h2h_form(team_a, team_b, results, n=10, normalize=None, reference_date=None):
    results = _ref_hasta(results, reference_date)
    norm = normalize or (lambda x: x)
    a = norm(team_a)
    b = norm(team_b)
    matchups = [r for r in results
               if (norm(str(r.get("home", ""))) == a and norm(str(r.get("away", ""))) == b)
               or (norm(str(r.get("home", ""))) == b and norm(str(r.get("away", ""))) == a)]
    recent = matchups[-n:]
    if len(recent) < 2:
        return None
    total, graded = 0.0, 0
    for r in recent:
        try:
            hs = float(r["home_score"])
            aws = float(r["away_score"])
        except (KeyError, TypeError, ValueError):
            continue
        graded += 1
        home_is_a = norm(str(r.get("home", ""))) == a
        if hs > aws:
            total += 1.0 if home_is_a else 0.0
        elif aws > hs:
            total += 0.0 if home_is_a else 1.0
        else:
            total += 0.5
    return total / graded if graded >= 2 else None


def _ref_team_recent_form_home(team, results, n=5, normalize=None, reference_date=None):
    results = _ref_hasta(results, reference_date)
    norm = normalize or (lambda x: x)
    team_n = norm(team)
    home_games = [r for r in results if norm(str(r.get("home", ""))) == team_n]
    recent = home_games[-n:]
    if len(recent) < 2:
        return None
    total, graded = 0.0, 0
    for r in recent:
        try:
            hs, aws = float(r["home_score"]), float(r["away_score"])
        except (KeyError, TypeError, ValueError):
            continue
        graded += 1
        total += 1.0 if hs > aws else (0.5 if hs == aws else 0.0)
    return total / graded if graded >= 2 else None


def _ref_team_recent_form_away(team, results, n=5, normalize=None, reference_date=None):
    results = _ref_hasta(results, reference_date)
    norm = normalize or (lambda x: x)
    team_n = norm(team)
    away_games = [r for r in results if norm(str(r.get("away", ""))) == team_n]
    recent = away_games[-n:]
    if len(recent) < 2:
        return None
    total, graded = 0.0, 0
    for r in recent:
        try:
            hs, aws = float(r["home_score"]), float(r["away_score"])
        except (KeyError, TypeError, ValueError):
            continue
        graded += 1
        total += 1.0 if aws > hs else (0.5 if hs == aws else 0.0)
    return total / graded if graded >= 2 else None


def _ref_team_avg_margin(team, results, n=10, normalize=None, reference_date=None):
    results = _ref_hasta(results, reference_date)
    norm = normalize or (lambda x: x)
    team_n = norm(team)
    team_games = [r for r in results
                 if norm(str(r.get("home", ""))) == team_n
                 or norm(str(r.get("away", ""))) == team_n]
    recent = team_games[-n:]
    if len(recent) < 2:
        return None
    margins = []
    for r in recent:
        try:
            hs, aws = float(r["home_score"]), float(r["away_score"])
        except (KeyError, TypeError, ValueError):
            continue
        is_home = norm(str(r.get("home", ""))) == team_n
        margins.append(hs - aws if is_home else aws - hs)
    return sum(margins) / len(margins) if margins else None


def _ref_team_avg_scored(team, results, n=10, normalize=None, reference_date=None):
    results = _ref_hasta(results, reference_date)
    norm = normalize or (lambda x: x)
    team_n = norm(team)
    team_games = [r for r in results
                 if norm(str(r.get("home", ""))) == team_n
                 or norm(str(r.get("away", ""))) == team_n]
    recent = team_games[-n:]
    if len(recent) < 2:
        return None
    scored = []
    for r in recent:
        try:
            is_home = norm(str(r.get("home", ""))) == team_n
            scored.append(float(r["home_score"]) if is_home else float(r["away_score"]))
        except (KeyError, TypeError, ValueError):
            continue
    return sum(scored) / len(scored) if scored else None


def _ref_team_avg_conceded(team, results, n=10, normalize=None, reference_date=None):
    results = _ref_hasta(results, reference_date)
    norm = normalize or (lambda x: x)
    team_n = norm(team)
    team_games = [r for r in results
                 if norm(str(r.get("home", ""))) == team_n
                 or norm(str(r.get("away", ""))) == team_n]
    recent = team_games[-n:]
    if len(recent) < 2:
        return None
    conceded = []
    for r in recent:
        try:
            is_home = norm(str(r.get("home", ""))) == team_n
            conceded.append(float(r["away_score"]) if is_home else float(r["home_score"]))
        except (KeyError, TypeError, ValueError):
            continue
    return sum(conceded) / len(conceded) if conceded else None


def _ref_team_avg_total(team, results, n=10, normalize=None, reference_date=None):
    results = _ref_hasta(results, reference_date)
    norm = normalize or (lambda x: x)
    team_n = norm(team)
    team_games = [r for r in results
                 if norm(str(r.get("home", ""))) == team_n
                 or norm(str(r.get("away", ""))) == team_n]
    recent = team_games[-n:]
    if len(recent) < 2:
        return None
    totals_list = []
    for r in recent:
        try:
            totals_list.append(float(r["home_score"]) + float(r["away_score"]))
        except (KeyError, TypeError, ValueError):
            continue
    return sum(totals_list) / len(totals_list) if totals_list else None


def _ref_team_over_rate(team, results, reference_line, n=10, normalize=None,
                        reference_date=None):
    results = _ref_hasta(results, reference_date)
    if reference_line is None:
        return None
    norm = normalize or (lambda x: x)
    team_n = norm(team)
    team_games = [r for r in results
                 if norm(str(r.get("home", ""))) == team_n
                 or norm(str(r.get("away", ""))) == team_n]
    recent = team_games[-n:]
    if len(recent) < 2:
        return None
    overs = []
    for r in recent:
        try:
            overs.append(1.0 if float(r["home_score"]) + float(r["away_score"]) > reference_line
                        else 0.0)
        except (KeyError, TypeError, ValueError):
            continue
    return sum(overs) / len(overs) if overs else None


def _ref_team_streak(team, results, normalize=None, reference_date=None):
    results = _ref_hasta(results, reference_date)
    norm = normalize or (lambda x: x)
    team_n = norm(team)
    team_games = [r for r in results
                 if norm(str(r.get("home", ""))) == team_n
                 or norm(str(r.get("away", ""))) == team_n]
    streak = 0
    for r in reversed(team_games):
        try:
            hs = float(r["home_score"])
            aws = float(r["away_score"])
        except (KeyError, TypeError, ValueError):
            break
        is_home = norm(str(r.get("home", ""))) == team_n
        if hs > aws:
            outcome = 1 if is_home else -1
        elif aws > hs:
            outcome = -1 if is_home else 1
        else:
            break
        if streak == 0:
            streak = outcome
        elif (outcome > 0) == (streak > 0):
            streak += outcome
        else:
            break
    return streak


def ref_compute_features(home, away, ref_date, results, risk, normalize=None):
    """Espejo exacto del cuerpo ORIGINAL de `build_adjustment_context`."""
    return {
        "rest_home": _ref_team_rest_days(home, results, ref_date, normalize),
        "rest_away": _ref_team_rest_days(away, results, ref_date, normalize),
        "form_home": _ref_team_recent_form(home, results, risk.recent_form_n,
                                           normalize, ref_date),
        "form_away": _ref_team_recent_form(away, results, risk.recent_form_n,
                                           normalize, ref_date),
        "h2h_home": _ref_team_h2h_form(home, away, results, risk.h2h_n, normalize, ref_date),
        "avg_total_home": _ref_team_avg_total(home, results, risk.totals_tendency_n,
                                              normalize, ref_date),
        "avg_total_away": _ref_team_avg_total(away, results, risk.totals_tendency_n,
                                              normalize, ref_date),
        "streak_home": _ref_team_streak(home, results, normalize, ref_date),
        "streak_away": _ref_team_streak(away, results, normalize, ref_date),
        "avg_scored_home": _ref_team_avg_scored(home, results, risk.off_def_n,
                                                normalize, ref_date),
        "avg_conceded_home": _ref_team_avg_conceded(home, results, risk.off_def_n,
                                                    normalize, ref_date),
        "avg_scored_away": _ref_team_avg_scored(away, results, risk.off_def_n,
                                                normalize, ref_date),
        "avg_conceded_away": _ref_team_avg_conceded(away, results, risk.off_def_n,
                                                    normalize, ref_date),
        "form_home_at_home": _ref_team_recent_form_home(home, results, risk.home_away_form_n,
                                                        normalize, ref_date),
        "form_away_at_away": _ref_team_recent_form_away(away, results, risk.home_away_form_n,
                                                        normalize, ref_date),
        "margin_home": _ref_team_avg_margin(home, results, risk.margin_n, normalize, ref_date),
        "margin_away": _ref_team_avg_margin(away, results, risk.margin_n, normalize, ref_date),
    }


def ref_adjust_model_probability(p_model, market, selection, point, home, away,
                                 feats, results, risk, normalize=None,
                                 reference_date=None):
    """Espejo exacto del cuerpo ORIGINAL de `adjust_model_probability`,
    reconstruido sobre un dict de features `ref_compute_features` en vez de
    un `AdjustmentContext` (no depende de produccion para el termino
    over/under-rate: llama a la referencia congelada `_ref_team_over_rate`).
    `reference_date` debe ser el MISMO `ref_date` usado para construir
    `feats` (equivalente a `ctx.ref_date` en produccion)."""
    if market == "totals" and point is not None:
        over_rate_home = _ref_team_over_rate(home, results, point,
                                             risk.over_under_rate_n, normalize,
                                             reference_date)
        over_rate_away = _ref_team_over_rate(away, results, point,
                                             risk.over_under_rate_n, normalize,
                                             reference_date)
    else:
        over_rate_home = over_rate_away = None
    return max(0.01, min(0.99, p_model
               + rest_form_p_adjustment(
                   p_model, market, selection, home, away,
                   feats["rest_home"], feats["rest_away"], feats["form_home"],
                   feats["form_away"], risk.rest_days_coef, risk.recent_form_coef)
               + h2h_p_adjustment(
                   market, selection, home, away, feats["h2h_home"], risk.h2h_coef)
               + totals_tendency_p_adjustment(
                   market, selection, feats["avg_total_home"], feats["avg_total_away"],
                   point, risk.totals_tendency_coef)
               + streak_p_adjustment(
                   market, selection, home, away, feats["streak_home"],
                   feats["streak_away"], risk.streak_coef)
               + off_def_p_adjustment(
                   market, selection, home, away,
                   feats["avg_scored_home"], feats["avg_conceded_home"],
                   feats["avg_scored_away"], feats["avg_conceded_away"],
                   point, risk.off_def_h2h_coef, risk.off_def_totals_coef)
               + home_away_form_p_adjustment(
                   market, selection, home, away,
                   feats["form_home_at_home"], feats["form_away_at_away"],
                   risk.home_away_form_coef)
               + margin_p_adjustment(
                   market, selection, home, away, feats["margin_home"],
                   feats["margin_away"], risk.margin_coef)
               + over_under_rate_p_adjustment(
                   market, selection, over_rate_home, over_rate_away,
                   risk.over_under_rate_coef)))


# ===========================================================================
# Generadores de historiales sinteticos
# ===========================================================================

LEAGUES = {
    "nba_like": [f"NBA{i}" for i in range(8)],
    "nfl_like": [f"NFL{i}" for i in range(4)],
    "soccer_like": [f"FC{i}" for i in range(6)],
}


def _gen_history(rng: random.Random, teams: list[str], n_games: int,
                 start_year: int = 2020, allow_same_day: bool = True,
                 allow_repeated_dates: bool = True, shuffle_order: bool = False) -> list[dict]:
    games = []
    day_counter = 0
    cur_date = date(start_year, 1, 1)
    for i in range(n_games):
        if allow_repeated_dates and rng.random() < 0.3:
            pass  # keep same date as previous game (repeated / same-day)
        else:
            cur_date = date.fromordinal(cur_date.toordinal() + rng.randint(1, 3))
        home, away = rng.sample(teams, 2)
        hs, aws = rng.randint(0, 6), rng.randint(0, 6)
        games.append({"date": cur_date.isoformat(), "home": home, "away": away,
                     "home_score": hs, "away_score": aws, "game_id": f"g{i}"})
        day_counter += 1
    if shuffle_order:
        rng.shuffle(games)
    else:
        games.sort(key=lambda r: r["date"])
    return games


def _assert_exact(a, b, label):
    assert a == b, f"{label}: {a!r} != {b!r}"
    if isinstance(a, float) and isinstance(b, float) and not (math.isnan(a) and math.isnan(b)):
        assert hash(a) == hash(b), f"{label} (hash): {a!r} vs {b!r}"


def _assert_exact_nan_ok(a, b, label):
    """Como `_assert_exact`, pero sin el chequeo de hash y tratando dos NaN
    como iguales (`nan == nan` es `False` en Python, asi que `_assert_exact`
    no sirve aqui): las features de historiales con marcador NaN pueden
    llegar a dar NaN de forma LEGITIMA (p.ej. `margin`/`avg_total` sobre una
    ventana con algun marcador NaN sin filtrar), y lo que importa es que la
    produccion y la referencia den NaN EN LOS MISMOS CASOS, no que sean
    bit a bit iguales como floats normales."""
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return
    assert a == b, f"{label}: {a!r} != {b!r}"


ALL_RISK_WINDOWS = dict(recent_form_n=5, h2h_n=10, totals_tendency_n=10,
                        off_def_n=10, home_away_form_n=5, margin_n=10)
FEATURE_KEYS = ["rest_home", "rest_away", "form_home", "form_away", "h2h_home",
               "avg_total_home", "avg_total_away", "streak_home", "streak_away",
               "avg_scored_home", "avg_conceded_home", "avg_scored_away",
               "avg_conceded_away", "form_home_at_home", "form_away_at_away",
               "margin_home", "margin_away"]


@pytest.mark.parametrize("league_name,teams", LEAGUES.items())
@pytest.mark.parametrize("shuffle_order", [False, True], ids=["ordenado", "desordenado"])
def test_compute_pregame_features_matches_reference(league_name, teams, shuffle_order):
    rng = random.Random(f"features-{league_name}-{shuffle_order}-20260930")
    results = _gen_history(rng, teams, n_games=180, shuffle_order=shuffle_order)
    risk = RiskConfig(**ALL_RISK_WINDOWS)
    # Varias fechas de referencia, incluyendo una anterior a TODO el historial
    # (equipo "sin historial" efectivo) y una posterior a todo.
    ref_dates = ["2020-01-01", "2020-06-15", "2099-01-01"]
    for ref_date in ref_dates:
        for _ in range(15):
            home, away = rng.sample(teams, 2)
            got = compute_pregame_features(
                home, away, ref_date, results, **ALL_RISK_WINDOWS, normalize=None)
            expected = ref_compute_features(home, away, ref_date, results, risk, None)
            for key in FEATURE_KEYS:
                _assert_exact(got[key], expected[key], f"{league_name}/{key}@{ref_date}")


def test_team_with_no_history_is_none_or_zero():
    results = _gen_history(random.Random(1), ["A", "B", "C"], n_games=40)
    got = compute_pregame_features("GHOST", "A", "2021-01-01", results, **ALL_RISK_WINDOWS)
    expected = ref_compute_features("GHOST", "A", "2021-01-01", results, RiskConfig())
    for key in FEATURE_KEYS:
        _assert_exact(got[key], expected[key], f"ghost/{key}")
    assert got["rest_home"] is None
    assert got["streak_home"] == 0


def test_window_larger_than_history():
    results = _gen_history(random.Random(2), ["A", "B", "C"], n_games=6)
    huge = dict(recent_form_n=500, h2h_n=500, totals_tendency_n=500,
               off_def_n=500, home_away_form_n=500, margin_n=500)
    got = compute_pregame_features("A", "B", "2099-01-01", results, **huge)
    expected = ref_compute_features("A", "B", "2099-01-01", results, RiskConfig(**huge))
    for key in FEATURE_KEYS:
        _assert_exact(got[key], expected[key], f"window-grande/{key}")


def test_same_day_and_repeated_dates_edge_case():
    results = [
        {"date": "2024-05-01", "home": "A", "away": "B", "home_score": 3, "away_score": 1},
        {"date": "2024-05-01", "home": "B", "away": "A", "home_score": 0, "away_score": 0},
        {"date": "2024-05-01", "home": "A", "away": "C", "home_score": 2, "away_score": 2},
        {"date": "2024-05-03", "home": "C", "away": "A", "home_score": 1, "away_score": 4},
    ]
    for ref_date in ("2024-05-01", "2024-05-02", "2024-05-04"):
        got = compute_pregame_features("A", "B", ref_date, results, **ALL_RISK_WINDOWS)
        expected = ref_compute_features("A", "B", ref_date, results, RiskConfig())
        for key in FEATURE_KEYS:
            _assert_exact(got[key], expected[key], f"mismodia/{key}@{ref_date}")


def test_unsorted_input_falls_back_correctly():
    """El indice asume orden ascendente por fecha (precondicion documentada);
    con entrada DESORDENADA cae a un filtro lineal que debe seguir
    produciendo el mismo resultado que la referencia."""
    rng = random.Random(3)
    results = _gen_history(rng, ["A", "B", "C", "D"], n_games=60, shuffle_order=True)
    for ref_date in ("2020-03-01", "2020-08-01"):
        got = compute_pregame_features("A", "C", ref_date, results, **ALL_RISK_WINDOWS)
        expected = ref_compute_features("A", "C", ref_date, results, RiskConfig())
        for key in FEATURE_KEYS:
            _assert_exact(got[key], expected[key], f"desordenado/{key}@{ref_date}")


def test_precomputed_index_matches_default_construction():
    rng = random.Random(4)
    teams = ["A", "B", "C", "D", "E"]
    results = _gen_history(rng, teams, n_games=100)
    idx = TeamHistoryIndex.build(results, None)
    for _ in range(10):
        home, away = rng.sample(teams, 2)
        with_idx = compute_pregame_features(
            home, away, "2020-06-01", results, **ALL_RISK_WINDOWS, team_index=idx)
        without_idx = compute_pregame_features(
            home, away, "2020-06-01", results, **ALL_RISK_WINDOWS)
        for key in FEATURE_KEYS:
            _assert_exact(with_idx[key], without_idx[key], f"reuso-indice/{key}")


def test_over_rate_from_index_matches_reference():
    rng = random.Random(5)
    teams = ["A", "B", "C", "D"]
    results = _gen_history(rng, teams, n_games=80)
    idx = TeamHistoryIndex.build(results, None)
    for ref_date in ("2020-02-01", "2020-09-01", "2099-01-01"):
        for line in (5.5, 8.0, None):
            for team in teams:
                got = over_rate_from_index(idx, team, line, 10, None, ref_date)
                expected = _ref_team_over_rate(team, results, line, 10, None, ref_date)
                _assert_exact(got, expected, f"over_rate/{team}@{ref_date}/{line}")


def test_adjust_model_probability_matches_reference_with_nonzero_coefficients():
    """`build_adjustment_context` + `adjust_model_probability` (produccion,
    ya optimizados) frente al chain reconstruido a mano sobre la referencia
    congelada, con TODOS los coeficientes activos a la vez."""
    rng = random.Random(6)
    teams = ["A", "B", "C", "D", "E", "F"]
    results = _gen_history(rng, teams, n_games=200)
    risk = RiskConfig(rest_days_coef=0.003, recent_form_coef=0.04, h2h_coef=0.05,
                      totals_tendency_coef=0.004, streak_coef=0.01,
                      off_def_h2h_coef=0.002, off_def_totals_coef=0.003,
                      home_away_form_coef=0.03, margin_coef=0.01,
                      over_under_rate_coef=0.02)
    ref_date = "2020-07-01"
    for _ in range(20):
        home, away = rng.sample(teams, 2)
        ctx = build_adjustment_context(home, away, ref_date, results, risk)
        feats = ref_compute_features(home, away, ref_date, results, risk)
        for market, selection, point in (
            ("h2h", home, None), ("h2h", away, None),
            ("spreads", home, -3.5), ("spreads", away, 3.5),
            ("totals", "Over", 7.5), ("totals", "Under", 7.5),
        ):
            for p_model in (0.2, 0.5, 0.83):
                got = adjust_model_probability(p_model, market, selection, point,
                                               home, away, ctx, risk)
                expected = ref_adjust_model_probability(
                    p_model, market, selection, point, home, away, feats, results, risk,
                    reference_date=ref_date)
                assert got == expected, (
                    f"{home} vs {away} {market}/{selection}@{point} p={p_model}: "
                    f"{got!r} != {expected!r}")


def test_adjustment_context_field_values_match_reference():
    """Comprueba tambien el objeto `AdjustmentContext` devuelto por
    `build_adjustment_context`, campo a campo, contra la referencia."""
    rng = random.Random(7)
    teams = ["A", "B", "C", "D"]
    results = _gen_history(rng, teams, n_games=120)
    risk = RiskConfig()
    ref_date = "2020-05-01"
    home, away = "A", "B"
    ctx = build_adjustment_context(home, away, ref_date, results, risk)
    assert isinstance(ctx, AdjustmentContext)
    expected = ref_compute_features(home, away, ref_date, results, risk)
    for key in FEATURE_KEYS:
        _assert_exact(getattr(ctx, key), expected[key], f"ctx.{key}")
    assert ctx.results is results
    assert ctx.ref_date == ref_date
    assert ctx.team_index is not None


# ===========================================================================
# NaN en el marcador (revision de Fable, 2026-09-30): el indice reutilizaba
# `_win_rate_from_window` (patron if/elif/else, NaN -> 0.5) tambien para
# `form_home_at_home`/`form_away_at_away`, que en el original usaban la
# expresion `1.0 if hs > aws else (0.5 if hs == aws else 0.0)` de
# `team_recent_form_home`/`team_recent_form_away` (NaN -> 0.0). Estos tests
# cubren ese patron -- y el resto de las 16 features, por si comparte algo
# parecido -- con marcadores NaN en varias posiciones, incluida la PRIMERA
# fila de la lista.
# ===========================================================================


def _inject_nans(results: list[dict], nan_specs: list[tuple]) -> list[dict]:
    """Copia `results` sustituyendo `home_score`/`away_score` por NaN en las
    filas de `nan_specs`: lista de `(posicion, which)` con `which` en
    {"home", "away", "both"}. No muta `results` in-place."""
    out = list(results)
    for pos, which in nan_specs:
        g = dict(out[pos])
        if which in ("home", "both"):
            g["home_score"] = float("nan")
        if which in ("away", "both"):
            g["away_score"] = float("nan")
        out[pos] = g
    return out


NONZERO_RISK = dict(rest_days_coef=0.003, recent_form_coef=0.04, h2h_coef=0.05,
                    totals_tendency_coef=0.004, streak_coef=0.01,
                    off_def_h2h_coef=0.002, off_def_totals_coef=0.003,
                    home_away_form_coef=0.03, margin_coef=0.01,
                    over_under_rate_coef=0.02, **ALL_RISK_WINDOWS)


@pytest.mark.parametrize("shuffle_order", [False, True], ids=["ordenado", "desordenado"])
def test_nan_scores_match_reference_for_all_features(shuffle_order):
    """Las 16 features con marcadores NaN en varias posiciones -- incluida la
    posicion 0 de la lista -- comparadas con la copia congelada del
    original."""
    teams = ["A", "B", "C", "D", "E"]
    rng = random.Random(f"nan-features-{shuffle_order}-20260930")
    base = _gen_history(rng, teams, n_games=130, shuffle_order=shuffle_order)
    results = _inject_nans(base, [
        (0, "home"),                  # primer partido de la lista
        (7, "away"),
        (23, "both"),
        (55, "home"),
        (len(base) - 1, "away"),      # ultimo partido de la lista
    ])
    risk = RiskConfig(**ALL_RISK_WINDOWS)
    for ref_date in ("2020-01-01", "2020-06-15", "2099-01-01"):
        for _ in range(20):
            home, away = rng.sample(teams, 2)
            got = compute_pregame_features(
                home, away, ref_date, results, **ALL_RISK_WINDOWS, normalize=None)
            expected = ref_compute_features(home, away, ref_date, results, risk, None)
            for key in FEATURE_KEYS:
                _assert_exact_nan_ok(got[key], expected[key], f"nan/{key}@{ref_date}")


def test_nan_scores_match_reference_including_first_game():
    """Caso limite explicito: NaN precisamente en la fila 0 de `results`,
    para las 16 features y para varias fechas de referencia (incluida una
    que deja la fila 0 como UNICO partido disponible)."""
    teams = ["A", "B", "C"]
    rng = random.Random("nan-first-game-20260930")
    base = _gen_history(rng, teams, n_games=25)
    results = _inject_nans(base, [(0, "both")])
    risk = RiskConfig(**ALL_RISK_WINDOWS)
    for ref_date in (base[1]["date"], base[5]["date"], "2099-01-01"):
        for home, away in (("A", "B"), ("B", "C"), ("A", "C")):
            got = compute_pregame_features(
                home, away, ref_date, results, **ALL_RISK_WINDOWS)
            expected = ref_compute_features(home, away, ref_date, results, risk)
            for key in FEATURE_KEYS:
                _assert_exact_nan_ok(got[key], expected[key],
                                     f"nan-primer-partido/{key}@{ref_date}")


@pytest.mark.parametrize("shuffle_order", [False, True], ids=["ordenado", "desordenado"])
def test_nan_scores_match_reference_for_adjust_model_probability(shuffle_order):
    """`adjust_model_probability` con TODOS los coeficientes activos, sobre
    un historial con marcadores NaN, frente a la referencia congelada
    reconstruida a mano."""
    teams = ["A", "B", "C", "D", "E", "F"]
    rng = random.Random(f"nan-adjust-{shuffle_order}-20260930")
    base = _gen_history(rng, teams, n_games=180, shuffle_order=shuffle_order)
    results = _inject_nans(base, [
        (0, "home"), (12, "away"), (48, "both"), (len(base) - 2, "home"),
    ])
    risk = RiskConfig(**NONZERO_RISK)
    ref_date = "2020-07-01"
    for _ in range(15):
        home, away = rng.sample(teams, 2)
        ctx = build_adjustment_context(home, away, ref_date, results, risk)
        feats = ref_compute_features(home, away, ref_date, results, risk)
        for market, selection, point in (
            ("h2h", home, None), ("h2h", away, None),
            ("spreads", home, -3.5), ("spreads", away, 3.5),
            ("totals", "Over", 7.5), ("totals", "Under", 7.5),
        ):
            for p_model in (0.2, 0.5, 0.83):
                got = adjust_model_probability(p_model, market, selection, point,
                                               home, away, ctx, risk)
                expected = ref_adjust_model_probability(
                    p_model, market, selection, point, home, away, feats, results, risk,
                    reference_date=ref_date)
                _assert_exact_nan_ok(
                    got, expected,
                    f"nan-adjust/{home} vs {away} {market}/{selection}@{point} p={p_model}")


# ===========================================================================
# Contra las funciones VIVAS (no la copia congelada): si alguien cambia
# `team_recent_form`, `team_recent_form_home`, etc. sin actualizar
# `compute_pregame_features` -- o al reves -- este test debe fallar. A
# diferencia de `ref_compute_features`, que congela a proposito el
# comportamiento HISTORICO y nunca debe tocarse, esto vigila que no queden
# dos implementaciones vivas divergiendo en silencio.
# ===========================================================================


def live_compute_features(home, away, ref_date, results, risk, normalize=None):
    """Espejo de `ref_compute_features`, pero llamando a las funciones vivas
    de `sqp.features.rest_form` en vez de a la copia congelada."""
    return {
        "rest_home": team_rest_days(home, results, ref_date, normalize),
        "rest_away": team_rest_days(away, results, ref_date, normalize),
        "form_home": team_recent_form(home, results, risk.recent_form_n, normalize, ref_date),
        "form_away": team_recent_form(away, results, risk.recent_form_n, normalize, ref_date),
        "h2h_home": team_h2h_form(home, away, results, risk.h2h_n, normalize, ref_date),
        "avg_total_home": team_avg_total(home, results, risk.totals_tendency_n,
                                         normalize, ref_date),
        "avg_total_away": team_avg_total(away, results, risk.totals_tendency_n,
                                         normalize, ref_date),
        "streak_home": team_streak(home, results, normalize, ref_date),
        "streak_away": team_streak(away, results, normalize, ref_date),
        "avg_scored_home": team_avg_scored(home, results, risk.off_def_n, normalize, ref_date),
        "avg_conceded_home": team_avg_conceded(home, results, risk.off_def_n,
                                               normalize, ref_date),
        "avg_scored_away": team_avg_scored(away, results, risk.off_def_n, normalize, ref_date),
        "avg_conceded_away": team_avg_conceded(away, results, risk.off_def_n,
                                               normalize, ref_date),
        "form_home_at_home": team_recent_form_home(home, results, risk.home_away_form_n,
                                                    normalize, ref_date),
        "form_away_at_away": team_recent_form_away(away, results, risk.home_away_form_n,
                                                    normalize, ref_date),
        "margin_home": team_avg_margin(home, results, risk.margin_n, normalize, ref_date),
        "margin_away": team_avg_margin(away, results, risk.margin_n, normalize, ref_date),
    }


@pytest.mark.parametrize("with_nans", [False, True], ids=["sin-nan", "con-nan"])
def test_compute_pregame_features_matches_live_functions(with_nans):
    """`compute_pregame_features` frente a las funciones VIVAS del modulo
    (team_recent_form, team_recent_form_home/_away, team_h2h_form,
    team_rest_days, team_avg_total, team_streak, team_avg_scored/_conceded,
    team_avg_margin), no la copia congelada."""
    teams = ["A", "B", "C", "D", "E"]
    rng = random.Random(f"live-{with_nans}-20260930")
    results = _gen_history(rng, teams, n_games=140)
    if with_nans:
        results = _inject_nans(results, [
            (0, "home"), (10, "away"), (30, "both"), (len(results) - 1, "home"),
        ])
    risk = RiskConfig(**ALL_RISK_WINDOWS)
    for ref_date in ("2020-01-15", "2020-07-01", "2099-01-01"):
        for _ in range(15):
            home, away = rng.sample(teams, 2)
            got = compute_pregame_features(
                home, away, ref_date, results, **ALL_RISK_WINDOWS, normalize=None)
            expected = live_compute_features(home, away, ref_date, results, risk, None)
            for key in FEATURE_KEYS:
                _assert_exact_nan_ok(got[key], expected[key], f"live/{key}@{ref_date}")


# ===========================================================================
# `TeamHistoryIndex`: igualdad de `AdjustmentContext` y contrato de
# procedencia (`StaleTeamIndexError`) -- revision de Fable, 2026-09-30.
# ===========================================================================


def test_adjustment_context_equal_despite_different_team_index_instances():
    """Dos `AdjustmentContext` con las mismas entradas, pero construidos por
    separado (dos instancias DISTINTAS de `TeamHistoryIndex`), deben seguir
    siendo iguales: `team_index` es `compare=False` precisamente para que la
    igualdad dependa solo de las 16 features, no de compartir instancia de
    indice."""
    teams = ["A", "B", "C", "D"]
    results = _gen_history(random.Random(42), teams, n_games=90)
    risk = RiskConfig()
    ctx1 = build_adjustment_context("A", "B", "2020-05-01", results, risk)
    ctx2 = build_adjustment_context("A", "B", "2020-05-01", results, risk)
    assert ctx1.team_index is not ctx2.team_index
    assert ctx1 == ctx2


def test_build_adjustment_context_rejects_mismatched_team_index():
    """Un `team_index` construido sobre un `results` DISTINTO debe
    rechazarse con una excepcion explicita -- nunca devolver features de otro
    historial en silencio."""
    teams = ["A", "B", "C"]
    results_a = _gen_history(random.Random(1), teams, n_games=50)
    results_b = _gen_history(random.Random(2), teams, n_games=70)
    idx_b = TeamHistoryIndex.build(results_b, None)
    risk = RiskConfig()
    with pytest.raises(StaleTeamIndexError):
        build_adjustment_context("A", "B", "2020-03-01", results_a, risk, team_index=idx_b)


def test_build_adjustment_context_accepts_matching_team_index():
    """El mismo `results` (la MISMA lista) si es aceptado, con el mismo
    resultado que sin pasar `team_index`."""
    teams = ["A", "B", "C"]
    results = _gen_history(random.Random(3), teams, n_games=60)
    idx = TeamHistoryIndex.build(results, None)
    risk = RiskConfig()
    ctx_with = build_adjustment_context("A", "B", "2020-03-01", results, risk,
                                        team_index=idx)
    ctx_without = build_adjustment_context("A", "B", "2020-03-01", results, risk)
    assert ctx_with == ctx_without


# ===========================================================================
# Fragmento de datos REALES (se salta si no existe -- CI sin `data/historical`)
# ===========================================================================

MAIN_TREE = Path(r"C:\dev\3\sports-quant-platform")


def _load_real_slice(league: str, n_rows: int) -> list[dict]:
    from sqp.storage.results_store import ResultsStore
    p = ResultsStore(MAIN_TREE).path(league)
    if not p.exists():
        pytest.skip(f"{p} no existe en este entorno (CI sin data/historical)")
    results = ResultsStore(MAIN_TREE).load(league)
    return results[:n_rows]


@pytest.mark.parametrize("league", ["nfl", "nba"])
def test_real_data_slice_matches_reference(league):
    results = _load_real_slice(league, 400)
    if len(results) < 60:
        pytest.skip(f"muy pocas filas reales de {league} en este entorno para el test")
    risk = RiskConfig(**ALL_RISK_WINDOWS)
    rng = random.Random(f"real-{league}")
    # Fechas de referencia repartidas por el fragmento cargado (no solo la
    # ultima), para ejercitar corte temporal en varios puntos.
    sample_positions = sorted(rng.sample(range(30, len(results)), min(15, len(results) - 30)))
    for pos in sample_positions:
        ref_date = str(results[pos].get("date", ""))[:10]
        home = str(results[pos].get("home", ""))
        away = str(results[pos].get("away", ""))
        got = compute_pregame_features(home, away, ref_date, results, **ALL_RISK_WINDOWS)
        expected = ref_compute_features(home, away, ref_date, results, risk)
        for key in FEATURE_KEYS:
            _assert_exact(got[key], expected[key], f"{league}/{key}@{ref_date}")
        # Tambien la cadena completa de ajustes, con coeficientes no nulos.
        big_risk = RiskConfig(rest_days_coef=0.002, recent_form_coef=0.05, h2h_coef=0.05,
                              margin_coef=0.01, streak_coef=0.01, home_away_form_coef=0.02,
                              **ALL_RISK_WINDOWS)
        ctx = build_adjustment_context(home, away, ref_date, results, big_risk)
        feats_big = ref_compute_features(home, away, ref_date, results, big_risk)
        got_p = adjust_model_probability(0.55, "h2h", home, None, home, away, ctx, big_risk)
        expected_p = ref_adjust_model_probability(
            0.55, "h2h", home, None, home, away, feats_big, results, big_risk,
            reference_date=ref_date)
        assert got_p == expected_p
