"""EV uncertainty penalty (ported from project 2). See sqp.markets.edge."""
import math

from sqp.markets.edge import adjusted_edge


def _raw(p, d):
    return p * d - 1.0


def test_no_op_when_coefficients_are_zero():
    # With all coefficients 0, the adjusted edge equals the raw edge and the
    # effective probability equals the input (this is the shipped default).
    r = adjusted_edge(0.60, 2.0, market_probability=0.50, books_count=1)
    assert r.penalty == 0.0
    assert math.isclose(r.adjusted_edge, _raw(0.60, 2.0))
    assert math.isclose(r.effective_probability, 0.60)


def test_uncertainty_penalty_scales_with_gap():
    # gap = |0.60 - 0.50| = 0.10 -> penalty = 0.10 * 0.35 = 0.035.
    r = adjusted_edge(0.60, 2.0, market_probability=0.50, books_count=5,
                      uncertainty_penalty=0.35)
    assert math.isclose(r.penalty, 0.035, abs_tol=1e-12)
    assert math.isclose(r.adjusted_edge, _raw(0.60, 2.0) - 0.035, abs_tol=1e-12)
    # p_eff yields exactly the adjusted edge at this price.
    assert math.isclose(r.effective_probability * 2.0 - 1.0, r.adjusted_edge, abs_tol=1e-12)
    assert r.effective_probability < 0.60          # penalty shrinks the staked prob


def test_anomaly_bump_applies_only_above_the_gap():
    common = dict(uncertainty_penalty=0.0, anomaly_edge_gap=0.06, anomaly_extra_penalty=0.02)
    below = adjusted_edge(0.55, 2.0, market_probability=0.50, books_count=5, **common)
    above = adjusted_edge(0.60, 2.0, market_probability=0.50, books_count=5, **common)
    assert below.penalty == 0.0                    # gap 0.05 <= 0.06
    assert math.isclose(above.penalty, 0.02)       # gap 0.10 > 0.06


def test_low_book_penalty_only_below_threshold():
    common = dict(low_book_penalty=0.015, min_books_for_consensus=2)
    thin = adjusted_edge(0.55, 2.0, market_probability=0.50, books_count=1, **common)
    thick = adjusted_edge(0.55, 2.0, market_probability=0.50, books_count=3, **common)
    assert math.isclose(thin.penalty, 0.015)
    assert thick.penalty == 0.0


def test_missing_market_or_books_skip_their_terms():
    # No market anchor -> no uncertainty/anomaly term; no book count -> no thin term.
    r = adjusted_edge(0.70, 1.8, market_probability=None, books_count=None,
                      uncertainty_penalty=0.35, low_book_penalty=0.015,
                      min_books_for_consensus=2)
    assert r.penalty == 0.0
    assert math.isclose(r.adjusted_edge, _raw(0.70, 1.8))


def test_penalty_never_negative():
    """Un modelo POR DEBAJO del mercado penaliza igual: el gap es |p - mercado|.

    AUD-MED-016 (auditoria integral 2026-09-10): antes se afirmaba
    `penalty >= 0.0` y `adjusted_edge <= raw`, y las dos son INVIOLABLES por
    construccion -- `edge.py` hace `penalty = max(0.0, penalty)` y
    `adj = raw - penalty`. El test no podia fallar.

    Peor: no cubria el defecto que su comentario dice vigilar. Si `edge.py:70`
    perdiera el `abs()` (`gap = probability - market_probability`), con p=0,40 y
    mercado=0,55 el gap seria -0,15, la penalizacion -0,0525 y el `max(0.0, ...)`
    la dejaria en 0,0: el modelo por debajo del mercado dejaria de penalizarse y
    el test seguiria VERDE. Ahora se fija el valor exacto, que si distingue los
    dos mundos."""
    r = adjusted_edge(0.40, 3.0, market_probability=0.55, books_count=5,
                      uncertainty_penalty=0.35)
    assert math.isclose(r.penalty, abs(0.40 - 0.55) * 0.35)   # 0.0525
    assert math.isclose(r.adjusted_edge, _raw(0.40, 3.0) - 0.0525)
    assert math.isclose(r.effective_probability, (r.adjusted_edge + 1.0) / 3.0)


# --- Ramas de penalizacion sin ninguna cobertura hasta el 2026-09-10 ----------
# AUD-MED-011 (auditoria integral): `grep` de `line_movement_pp`,
# `line_velocity_pp_per_h` y `books_spread` sobre `tests/` devolvia CERO
# coincidencias. Las tres ramas estan cableadas a produccion
# (`pipeline/daily.py` las alimenta desde `settings.risk.*`, y `config.py` las
# carga del yaml); hoy sus coeficientes son 0,0, asi que no se ejecutan, pero
# ACTIVARLAS por yaml no habria disparado ni un test. Cada rama se prueba
# cruzando y sin cruzar su umbral, que es lo que distingue "penaliza" de
# "penaliza cuando debe".


def test_adverse_line_movement_penalises_only_past_the_flat():
    comunes = dict(market_probability=None, books_count=None,
                   line_movement_penalty=0.02, line_movement_flat_pp=0.5)
    # Movimiento EN CONTRA de 3 pp: supera el umbral -> 3 * 0.02
    r = adjusted_edge(0.60, 2.0, line_movement_pp=-3.0, **comunes)
    assert math.isclose(r.penalty, 3.0 * 0.02)
    # Justo por debajo del umbral: no penaliza.
    assert adjusted_edge(0.60, 2.0, line_movement_pp=-0.4, **comunes).penalty == 0.0
    # Movimiento A FAVOR: nunca penaliza, y tampoco bonifica.
    assert adjusted_edge(0.60, 2.0, line_movement_pp=+5.0, **comunes).penalty == 0.0


def test_adverse_velocity_penalises_only_past_the_flat():
    comunes = dict(market_probability=None, books_count=None,
                   line_velocity_penalty=0.03, line_velocity_flat_pp_per_h=0.5)
    r = adjusted_edge(0.60, 2.0, line_velocity_pp_per_h=-2.0, **comunes)
    assert math.isclose(r.penalty, 2.0 * 0.03)
    assert adjusted_edge(0.60, 2.0, line_velocity_pp_per_h=-0.5,
                         **comunes).penalty == 0.0
    assert adjusted_edge(0.60, 2.0, line_velocity_pp_per_h=+9.0,
                         **comunes).penalty == 0.0


def test_books_spread_penalises_the_excess_over_the_threshold():
    comunes = dict(market_probability=None, books_count=None,
                   books_spread_penalty=0.5, books_spread_threshold=0.02)
    # Solo el EXCESO sobre el umbral, no la dispersion entera.
    r = adjusted_edge(0.60, 2.0, books_spread=0.05, **comunes)
    assert math.isclose(r.penalty, (0.05 - 0.02) * 0.5)
    assert adjusted_edge(0.60, 2.0, books_spread=0.02, **comunes).penalty == 0.0
    assert adjusted_edge(0.60, 2.0, books_spread=None, **comunes).penalty == 0.0


def test_las_tres_ramas_nuevas_siguen_siendo_no_op_con_los_coeficientes_a_cero():
    """Los defaults enviados (todos 0,0) no pueden cambiar ni un stake."""
    r = adjusted_edge(0.60, 2.0, market_probability=0.55, books_count=5,
                      line_movement_pp=-9.0, line_velocity_pp_per_h=-9.0,
                      books_spread=0.9)
    assert r.penalty == 0.0
    assert math.isclose(r.adjusted_edge, _raw(0.60, 2.0))
    assert math.isclose(r.effective_probability, 0.60)
