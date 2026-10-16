"""Pruebas sinteticas de `scripts/research/measure_tier_a_gap.py`
(pre-registro `docs/research/2026-10-02-preregistro-brecha-tier-a.md`).

Ninguna prueba ejecuta `--medir` ni `--contar` contra los datos reales de
produccion: eso es la medicion en si (prohibida fuera de la ejecucion unica
autorizada), y aqui todo se ejercita con filas sinteticas pequenas, igual que
`tests/test_measure_tilt_nhl.py` hace para su propio script hermano. Vive en
`tests/research/` porque el contrato del script (seccion 7 del pre-registro)
fija esa ruta para sus tests minimos.
"""
from __future__ import annotations

import importlib.util
import itertools
import json
import math
import sys

import numpy as np
import pandas as pd
import pytest

from sqp.config import ROOT

SCRIPT = ROOT / "scripts" / "research" / "measure_tier_a_gap.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("measure_tier_a_gap", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_module()


def test_script_exists():
    assert SCRIPT.exists()


# ------------------------------------------------------------------ pick_key --
def test_pick_key_normalizes_minus_zero_and_zero_as_the_same_line(mod):
    df = pd.DataFrame({"event_id": ["e1", "e1"], "market": ["spreads", "spreads"],
                       "selection": ["home", "home"], "line": [-0.0, 0.0]})
    claves = mod.pick_key(df)
    assert claves.iloc[0] == claves.iloc[1]


def test_pick_key_never_merges_h2h_rows_via_nan_concatenation(mod):
    """Dos h2h DISTINTOS (event_id distinto) con `line` NaN no deben fusionarse
    en la misma clave: celda a celda, NaN -> "" (ambas claves comparten solo
    el sufijo vacio de `line`, pero no el event_id)."""
    df = pd.DataFrame({"event_id": ["e1", "e2"], "market": ["h2h", "h2h"],
                       "selection": ["home", "home"], "line": [np.nan, np.nan]})
    claves = mod.pick_key(df)
    assert claves.iloc[0] != claves.iloc[1]
    assert claves.iloc[0].endswith("|") and claves.iloc[1].endswith("|")


def test_pick_key_same_h2h_event_collapses_to_one_key(mod):
    df = pd.DataFrame({"event_id": ["e1", "e1"], "market": ["h2h", "h2h"],
                       "selection": ["home", "home"], "line": [np.nan, np.nan]})
    claves = mod.pick_key(df)
    assert claves.iloc[0] == claves.iloc[1]


# ------------------------------------------------------------- first_serve_rows --
def _served_row(event_id="e1", market="h2h", selection="home", line=np.nan,
                generated_at="2026-10-05T12:00:00Z", start_time="2026-10-05T20:00:00Z",
                price_decimal=2.0, implied_probability_novig=0.48,
                estimated_probability=0.55, calibrated_probability=np.nan,
                books_count=25.0, data_label="real", league="nfl",
                home="HOME", away="AWAY") -> dict:
    return dict(event_id=event_id, market=market, selection=selection, line=line,
               generated_at=generated_at, start_time=start_time,
               price_decimal=price_decimal,
               implied_probability_novig=implied_probability_novig,
               estimated_probability=estimated_probability,
               calibrated_probability=calibrated_probability,
               books_count=books_count, data_label=data_label, league=league,
               home=home, away=away, game_date=generated_at[:10])


def test_first_serve_rows_keeps_earliest_and_excludes_incomplete_identity(mod):
    rows = [
        _served_row(generated_at="2026-10-05T12:00:00Z"),
        _served_row(generated_at="2026-10-04T08:00:00Z"),  # la mas temprana
        {**_served_row(), "event_id": np.nan},  # identidad incompleta
    ]
    df = pd.DataFrame(rows)
    primeras, counts = mod.first_serve_rows(df)
    assert len(primeras) == 1
    assert primeras.iloc[0]["generated_at"] == "2026-10-04T08:00:00Z"
    assert counts["identidad_incompleta"] == 1
    assert counts["claves_todas_ilegibles"] == 0


def test_first_serve_rows_excludes_and_counts_key_with_all_timestamps_illegible(mod):
    rows = [
        {**_served_row(event_id="e2"), "generated_at": "no-es-una-fecha"},
        {**_served_row(event_id="e2"), "generated_at": "tampoco"},
    ]
    df = pd.DataFrame(rows)
    primeras, counts = mod.first_serve_rows(df)
    assert len(primeras) == 0
    assert counts["claves_todas_ilegibles"] == 1


def test_first_serve_rows_never_picks_an_illegible_timestamp_over_a_legible_one(mod):
    rows = [
        {**_served_row(event_id="e3"), "generated_at": "no-es-una-fecha"},
        _served_row(event_id="e3", generated_at="2026-10-04T08:00:00Z"),
    ]
    df = pd.DataFrame(rows)
    primeras, counts = mod.first_serve_rows(df)
    assert len(primeras) == 1
    assert primeras.iloc[0]["generated_at"] == "2026-10-04T08:00:00Z"


def test_first_serve_rows_aborts_when_a_required_column_is_missing(mod):
    df = pd.DataFrame({"market": ["h2h"], "selection": ["home"]})
    with pytest.raises(SystemExit):
        mod.first_serve_rows(df)


def test_first_serve_rows_reports_duplicados_colapsados(mod):
    """Hallazgo M6: recuento que faltaba en la salida."""
    rows = [
        _served_row(event_id="e10", generated_at="2026-10-01T00:00:00Z"),
        _served_row(event_id="e10", generated_at="2026-10-02T00:00:00Z"),
        _served_row(event_id="e10", generated_at="2026-10-03T00:00:00Z"),
    ]
    _, counts = mod.first_serve_rows(pd.DataFrame(rows))
    assert counts["duplicados_colapsados"] == 2


# ------------------------------------------------------------ ventana (T0,T1] --
def test_pick_served_before_t0_and_reserved_after_stays_out_even_ungraded_before(mod):
    """Seccion 7, test minimo 2: un pick servido antes de T0 y re-servido
    despues queda fuera, tambien cuando la servida anterior a T0 no esta
    graduada (aqui no hay NINGUNA fila graduada en absoluto)."""
    rows = [
        _served_row(event_id="e4", generated_at="2026-09-01T00:00:00Z"),  # antes de T0
        _served_row(event_id="e4", generated_at="2026-10-10T00:00:00Z"),  # despues de T0
    ]
    served = pd.DataFrame(rows)
    primeras, _ = mod.first_serve_rows(served)
    assert len(primeras) == 1
    assert primeras.iloc[0]["generated_at"] == "2026-09-01T00:00:00Z"

    t0 = pd.Timestamp("2026-10-02T13:33:43Z")
    t1 = pd.Timestamp("2027-10-02T13:33:43Z")
    graded = pd.DataFrame(columns=["event_id", "market", "selection", "line", "result"])
    head = mod.git_rev_parse("HEAD", mod.DEFAULT_ROOT)
    labels_mod, tipster_mod = mod.load_frozen_classifier(mod.DEFAULT_ROOT, head, head)[:2]
    out = mod.build_primary_from_primeras(primeras, graded, labels_mod, tipster_mod,
                                          t0, t1, mod.DEFAULT_TZ_CLUSTER, mod.MAX_PLAUSIBLE_EV)
    assert len(out["frame"]) == 0
    assert out["counts"]["fuera_de_ventana"] == 1


def test_window_mask_is_exclusive_at_t0_and_inclusive_at_t1(mod):
    t0 = pd.Timestamp("2026-10-02T00:00:00Z")
    t1 = pd.Timestamp("2026-10-10T00:00:00Z")
    ts = pd.Series(pd.to_datetime(
        ["2026-10-02T00:00:00Z", "2026-10-02T00:00:01Z", "2026-10-10T00:00:00Z",
         "2026-10-10T00:00:01Z"], utc=True))
    mask = mod.window_mask(ts, t0, t1)
    assert list(mask) == [False, True, True, False]


def test_build_primary_reports_ventana_fechas(mod):
    """Hallazgo M6: primera/ultima servida de la ventana, solo fechas."""
    head = mod.git_rev_parse("HEAD", mod.DEFAULT_ROOT)
    labels_mod, tipster_mod = mod.load_frozen_classifier(mod.DEFAULT_ROOT, head, head)[:2]
    rows = [
        _served_row(event_id="e11", generated_at="2026-10-03T00:00:00Z"),
        _served_row(event_id="e12", generated_at="2026-10-07T00:00:00Z"),
    ]
    primeras, _ = mod.first_serve_rows(pd.DataFrame(rows))
    graded = pd.DataFrame(columns=["event_id", "market", "selection", "line", "result"])
    t0 = pd.Timestamp("2026-10-01T00:00:00Z")
    t1 = pd.Timestamp("2027-01-01T00:00:00Z")
    out = mod.build_primary_from_primeras(primeras, graded, labels_mod, tipster_mod,
                                          t0, t1, mod.DEFAULT_TZ_CLUSTER, mod.MAX_PLAUSIBLE_EV)
    assert out["ventana_fechas"]["primera"] == "2026-10-03"
    assert out["ventana_fechas"]["ultima"] == "2026-10-07"


# ------------------------------------------------------- filtros de validez --
def test_first_serve_failing_2_4_stays_out_even_if_a_later_serve_would_pass(mod):
    """Seccion 7, test minimo 3: la fila de decision (primera servida) EN
    VIVO (generated_at >= start_time) excluye el pick entero, aunque una
    servida posterior sea claramente pregame."""
    rows = [
        _served_row(event_id="e5", generated_at="2026-10-05T21:00:00Z",
                   start_time="2026-10-05T20:00:00Z"),  # en vivo: generated_at >= start_time
        _served_row(event_id="e5", generated_at="2026-10-06T21:00:00Z",
                   start_time="2026-10-07T20:00:00Z"),  # esta SI seria pregame
    ]
    served = pd.DataFrame(rows)
    primeras, _ = mod.first_serve_rows(served)
    assert len(primeras) == 1
    assert primeras.iloc[0]["generated_at"] == "2026-10-05T21:00:00Z"

    t0 = pd.Timestamp("2026-10-01T00:00:00Z")
    t1 = pd.Timestamp("2027-10-01T00:00:00Z")
    graded = pd.DataFrame(columns=["event_id", "market", "selection", "line", "result"])
    head = mod.git_rev_parse("HEAD", mod.DEFAULT_ROOT)
    labels_mod, tipster_mod = mod.load_frozen_classifier(mod.DEFAULT_ROOT, head, head)[:2]
    out = mod.build_primary_from_primeras(primeras, graded, labels_mod, tipster_mod,
                                          t0, t1, mod.DEFAULT_TZ_CLUSTER, mod.MAX_PLAUSIBLE_EV)
    assert len(out["frame"]) == 0
    assert out["counts"]["generado_en_vivo_o_despues"] == 1


def test_pregame_mask_excludes_and_counts_illegible_start_time(mod):
    head = mod.git_rev_parse("HEAD", mod.DEFAULT_ROOT)
    labels_mod, _ = mod.load_frozen_classifier(mod.DEFAULT_ROOT, head, head)[:2]
    df = pd.DataFrame([_served_row(event_id="e6", start_time="no-es-fecha")])
    valido, counts = mod.pregame_mask(df, labels_mod)
    assert not valido.iloc[0]
    assert counts["start_time_ilegible"] == 1
    assert counts["generado_en_vivo_o_despues"] == 0


def test_pyp_mask_flags_each_reason_mutually_exclusively(mod):
    head = mod.git_rev_parse("HEAD", mod.DEFAULT_ROOT)
    labels_mod, _ = mod.load_frozen_classifier(mod.DEFAULT_ROOT, head, head)[:2]
    rows = [
        _served_row(event_id="sin_p", estimated_probability=np.nan,
                   calibrated_probability=np.nan),
        _served_row(event_id="sin_cuota", price_decimal=0.5),
        _served_row(event_id="sin_novig", implied_probability_novig=np.nan),
        _served_row(event_id="valida"),
    ]
    df = pd.DataFrame(rows)
    valido, counts = mod.pyp_mask(df, labels_mod)
    assert list(valido) == [False, False, False, True]
    assert counts["sin_p_finita"] == 1
    assert counts["sin_cuota_valida"] == 1
    assert counts["sin_novig"] == 1


def test_pyp_mask_scoped_to_pregame_ok_avoids_double_counting(mod):
    """Hallazgo L1: una fila que falla pregame Y p/cuota/novig a la vez debe
    contarse SOLO en pregame si `pyp_mask` se restringe a lo que ya paso
    pregame (como hace `build_primary_from_primeras`)."""
    head = mod.git_rev_parse("HEAD", mod.DEFAULT_ROOT)
    labels_mod, tipster_mod = mod.load_frozen_classifier(mod.DEFAULT_ROOT, head, head)[:2]
    rows = [
        _served_row(event_id="e_doble", start_time="no-es-fecha",
                   estimated_probability=np.nan, calibrated_probability=np.nan),
    ]
    ventana = pd.DataFrame(rows)
    valido_pre, c_pre = mod.pregame_mask(ventana, labels_mod)
    assert c_pre["start_time_ilegible"] == 1
    ventana_pre_ok = ventana[valido_pre]
    assert ventana_pre_ok.empty
    _, c_pyp = mod.pyp_mask(ventana_pre_ok, labels_mod)
    assert c_pyp["sin_p_finita"] == 0  # restringido: no vuelve a contar la fila


# -------------------------------------------------------------- clasificador --
def test_classify_rows_matches_live_classify_function(mod):
    head = mod.git_rev_parse("HEAD", mod.DEFAULT_ROOT)
    labels_mod, tipster_mod = mod.load_frozen_classifier(mod.DEFAULT_ROOT, head, head)[:2]
    df = pd.DataFrame([_served_row(event_id="e7", estimated_probability=0.55,
                                   price_decimal=1.9, implied_probability_novig=0.48,
                                   books_count=25.0)])
    out = mod.classify_rows(df, labels_mod, tipster_mod, mod.MAX_PLAUSIBLE_EV)
    assert out["_tier"].iloc[0] == "A"
    ev_esperado = 0.55 * 1.9 - 1.0
    assert out["_ev"].iloc[0] == pytest.approx(ev_esperado)
    assert out["_edge_pp"].iloc[0] == pytest.approx(0.55 - 0.48)


def test_classify_rows_on_empty_frame_returns_expected_columns(mod):
    head = mod.git_rev_parse("HEAD", mod.DEFAULT_ROOT)
    labels_mod, tipster_mod = mod.load_frozen_classifier(mod.DEFAULT_ROOT, head, head)[:2]
    out = mod.classify_rows(pd.DataFrame(columns=["event_id"]), labels_mod, tipster_mod, 0.075)
    assert out.empty
    for col in ("_p", "_price", "_novig", "_casas", "_ev", "_edge_pp", "_tier", "_motivo"):
        assert col in out.columns


def test_count_live_classifier_disagreement_zero_when_identical(mod):
    head = mod.git_rev_parse("HEAD", mod.DEFAULT_ROOT)
    labels_mod, tipster_mod = mod.load_frozen_classifier(mod.DEFAULT_ROOT, head, head)[:2]
    df = pd.DataFrame([_served_row(event_id="e9", estimated_probability=0.55,
                                   price_decimal=1.9, implied_probability_novig=0.48,
                                   books_count=25.0)])
    clasif = mod.classify_rows(df, labels_mod, tipster_mod, mod.MAX_PLAUSIBLE_EV)
    n = mod.count_live_classifier_disagreement(clasif)
    assert n == 0  # el clasificador vivo HOY coincide con H


def test_count_live_classifier_disagreement_empty_frame(mod):
    assert mod.count_live_classifier_disagreement(pd.DataFrame()) == 0


# ---------------------------------------------------------- join_result_by_key --
def test_join_result_by_key_returns_none_when_graded_is_empty(mod):
    claves = pd.Series(["e1|h2h|home|"])
    resultado, counts = mod.join_result_by_key(claves, pd.DataFrame())
    assert resultado.iloc[0] is None
    assert counts["resultados_discrepantes"] == 0


def test_join_result_by_key_marks_discrepant_with_sentinel_not_none(mod):
    """Hallazgo L5: discrepante != sin_graduar -- usa `_DISCREPANTE`, no `None`."""
    claves = pd.Series(["e1|h2h|home|"])
    graded = pd.DataFrame({"event_id": ["e1", "e1"], "market": ["h2h", "h2h"],
                           "selection": ["home", "home"], "line": [np.nan, np.nan],
                           "result": ["win", "loss"]})
    resultado, counts = mod.join_result_by_key(claves, graded)
    assert resultado.iloc[0] == mod._DISCREPANTE
    assert resultado.iloc[0] is not None
    assert counts["resultados_discrepantes"] == 1


def test_join_result_by_key_uses_any_matching_graded_row(mod):
    claves = pd.Series(["e1|h2h|home|"])
    graded = pd.DataFrame({"event_id": ["e1", "e1"], "market": ["h2h", "h2h"],
                           "selection": ["home", "home"], "line": [np.nan, np.nan],
                           "result": ["win", "win"]})
    resultado, counts = mod.join_result_by_key(claves, graded)
    assert resultado.iloc[0] == "win"
    assert counts["resultados_discrepantes"] == 0


def test_discrepant_result_is_not_double_counted_as_sin_graduar(mod):
    """Hallazgo L5, extremo a extremo: una clave discrepante no debe sumar a
    'sin_graduar' en `build_primary_from_primeras`."""
    head = mod.git_rev_parse("HEAD", mod.DEFAULT_ROOT)
    labels_mod, tipster_mod = mod.load_frozen_classifier(mod.DEFAULT_ROOT, head, head)[:2]
    served = pd.DataFrame([_served_row(event_id="e_disc", generated_at="2026-10-05T00:00:00Z")])
    primeras, _ = mod.first_serve_rows(served)
    graded = pd.DataFrame({"event_id": ["e_disc", "e_disc"], "market": ["h2h", "h2h"],
                           "selection": ["home", "home"], "line": [np.nan, np.nan],
                           "result": ["win", "loss"]})
    t0 = pd.Timestamp("2026-10-01T00:00:00Z")
    t1 = pd.Timestamp("2027-01-01T00:00:00Z")
    out = mod.build_primary_from_primeras(primeras, graded, labels_mod, tipster_mod,
                                          t0, t1, mod.DEFAULT_TZ_CLUSTER, mod.MAX_PLAUSIBLE_EV)
    assert out["counts"]["resultados_discrepantes"] == 1
    assert out["counts"]["sin_graduar"] == 0


# ------------------------------------------------------------- cluster de dia --
def test_day_cluster_uses_the_passed_timezone_not_the_machine_timezone(mod):
    """Seccion 7, test minimo 4 (parte 1): un partido a las 01:00 UTC del
    dia 6 cae el dia 5 en America/New_York (UTC-4 en octubre) pero seguiria
    siendo dia 6 en UTC -- si el cluster usara la zona de la maquina (en vez
    de la pasada), este caso no lo distinguiria de forma fiable."""
    head = mod.git_rev_parse("HEAD", mod.DEFAULT_ROOT)
    labels_mod, _ = mod.load_frozen_classifier(mod.DEFAULT_ROOT, head, head)[:2]
    s = pd.Series(["2026-10-06T01:00:00Z"])
    dia_ny = mod.day_cluster(s, "America/New_York", labels_mod, s.index)
    dia_utc = mod.day_cluster(s, "UTC", labels_mod, s.index)
    assert dia_ny.iloc[0] == "2026-10-05"
    assert dia_utc.iloc[0] == "2026-10-06"
    assert dia_ny.iloc[0] != dia_utc.iloc[0]


def test_cluster_mean_se_matches_hand_computed_value_for_three_days(mod):
    """Seccion 7, test minimo 4 (parte 2): reproduce el SE a mano, en un caso
    de 3 dias con 2 picks cada uno (seccion 3.1: SE^2 = G/(G-1) *
    sum_g(sum_i(r_i-D))^2 / n^2)."""
    r = np.array([0.2, -0.1, 0.3, 0.0, -0.4, 0.1])
    day = np.array(["d1", "d1", "d2", "d2", "d3", "d3"])
    out = mod.cluster_mean_se(r, day)
    n = 6
    d_hat = r.mean()
    sums = []
    for d in ("d1", "d2", "d3"):
        sums.append(float(np.sum((r[day == d] - d_hat))))
    g = 3
    se2_manual = (g / (g - 1)) * sum(s ** 2 for s in sums) / (n ** 2)
    se_manual = math.sqrt(se2_manual)
    assert out["d_hat"] == pytest.approx(d_hat)
    assert out["se"] == pytest.approx(se_manual)
    assert out["z"] == pytest.approx(d_hat / se_manual)
    assert out["g"] == 3


def test_cluster_mean_se_returns_none_se_with_a_single_cluster(mod):
    out = mod.cluster_mean_se(np.array([0.1, -0.2]), np.array(["d1", "d1"]))
    assert out["se"] is None and out["z"] is None


def test_cluster_mean_se_empty_input(mod):
    out = mod.cluster_mean_se(np.array([]), np.array([]))
    assert out["n"] == 0 and out["d_hat"] is None


def test_cluster_mean_se_with_weights_recovers_half_weighted_mean(mod):
    r = np.array([1.0, 1.0, 0.0])
    w = np.array([1.0, 0.5, 0.5])
    day = np.array(["d1", "d2", "d3"])
    out = mod.cluster_mean_se(r, day, weights=w)
    assert out["d_hat"] == pytest.approx((1.0 + 0.5 + 0.0) / 2.0)


def test_cluster_diff_se_matches_hand_computation(mod):
    r_a = np.array([0.2, -0.1, 0.3, 0.0])
    day_a = np.array(["d1", "d1", "d2", "d2"])
    r_b = np.array([0.1, 0.1, -0.2, -0.3])
    day_b = np.array(["d1", "d2", "d2", "d3"])
    out = mod.cluster_diff_se(r_a, day_a, r_b, day_b)
    d_a, d_b = r_a.mean(), r_b.mean()
    dias = sorted(set(day_a) | set(day_b))

    def per_day(r, day, d):
        return {dd: float(np.sum(r[day == dd] - d)) if (day == dd).any() else 0.0
               for dd in dias}

    sa, sb = per_day(r_a, day_a, d_a), per_day(r_b, day_b, d_b)
    n_a, n_b = len(r_a), len(r_b)
    terms = [sa[dd] / n_a - sb[dd] / n_b for dd in dias]
    g = len(dias)
    se_manual = math.sqrt((g / (g - 1)) * sum(t ** 2 for t in terms))
    assert out["d_hat_a"] == pytest.approx(d_a)
    assert out["d_hat_b"] == pytest.approx(d_b)
    assert out["diff"] == pytest.approx(d_a - d_b)
    assert out["se"] == pytest.approx(se_manual)
    assert out["g"] == g


def test_cluster_diff_se_empty_and_single_cluster(mod):
    out = mod.cluster_diff_se(np.array([]), np.array([]), np.array([0.1]), np.array(["d1"]))
    assert out["se"] is None
    out2 = mod.cluster_diff_se(np.array([0.1]), np.array(["d1"]),
                               np.array([0.2]), np.array(["d1"]))
    assert out2["se"] is None and out2["g"] == 1


# --------------------------------------------------------------- bootstrap --
def test_bootstrap_by_cluster_is_deterministic_with_fixed_seed(mod):
    r = np.array([0.1, -0.2, 0.3, -0.1, 0.05, -0.05])
    day = np.array(["d1", "d1", "d2", "d2", "d3", "d3"])
    out1 = mod.bootstrap_by_cluster(r, day, seed=mod.SEED, n_boot=500)
    out2 = mod.bootstrap_by_cluster(r, day, seed=mod.SEED, n_boot=500)
    assert out1 == out2


def test_bootstrap_by_cluster_empty_input(mod):
    out = mod.bootstrap_by_cluster(np.array([]), np.array([]), seed=1, n_boot=10)
    assert out["n_dias"] == 0 and out["p05"] is None


def test_bootstrap_by_cluster_quantiles_are_exact_when_all_days_are_identical(mod):
    """Cuantiles del bootstrap con un valor conocido y verificable a mano:
    si todos los dias tienen el MISMO residuo medio, cualquier remuestreo
    (con reemplazo, por dias) da exactamente ese valor -- p05 == p95 ==
    0.1, sin depender de la semilla."""
    r = np.array([0.1, 0.1, 0.1, 0.1])
    day = np.array(["d1", "d1", "d2", "d2"])
    out = mod.bootstrap_by_cluster(r, day, seed=123, n_boot=500)
    assert out["p05"] == pytest.approx(0.1)
    assert out["p95"] == pytest.approx(0.1)
    assert out["n_dias"] == 2
    assert out["n_replicas_validas"] == 500


# ----------------------------------------------------------- etiquetas 6/5 --
def test_decision_label_confirma_when_z_crosses_threshold(mod):
    assert mod.decision_label(-0.05, 0.02, -2.5) == "CONFIRMA"


def test_decision_label_descarta_when_lower_bound_above_minus_delta(mod):
    assert mod.decision_label(0.01, 0.01, 1.0) == "DESCARTA"


def test_decision_label_inconcluso_otherwise(mod):
    assert mod.decision_label(-0.02, 0.02, -1.0) == "INCONCLUSO"


def test_decision_label_missing_inputs_is_inconcluso(mod):
    assert mod.decision_label(None, None, None) == "INCONCLUSO"


def test_bootstrap_label_confirma_descarta_inconcluso(mod):
    assert mod.bootstrap_label(-0.05, -0.01) == "CONFIRMA"
    assert mod.bootstrap_label(-0.02, 0.0) == "DESCARTA"
    assert mod.bootstrap_label(-0.05, 0.01) == "INCONCLUSO"


# ------------------------------------------------------- grupos de deporte 2.5 --
def test_sport_group_maps_direct_codes_and_families(mod):
    assert mod.sport_group("mlb") == "MLB"
    assert mod.sport_group("nfl") == "NFL"
    assert mod.sport_group("ncaaf") == "NCAAF"
    assert mod.sport_group("nba") == "NBA"
    assert mod.sport_group("wnba") == "WNBA"
    assert mod.sport_group("nhl") == "NHL"
    assert mod.sport_group("epl") == "futbol"  # liga real de configs/leagues/soccer.yaml
    assert mod.sport_group("atp") == "tenis"


def test_sport_group_unknown_league_is_marked_otro(mod):
    assert mod.sport_group("liga-inventada-xyz").startswith("otro:")


def test_parse_max_plausible_edge_from_tag_message(mod):
    msg = ("Pre-registro brecha tier A: H y T0.\n"
          "max_plausible_edge efectivo de Settings en H: 0.075 (medido hoy)\n")
    assert mod.parse_max_plausible_edge_from_tag_message(msg) == pytest.approx(0.075)
    assert mod.parse_max_plausible_edge_from_tag_message(None) is None
    assert mod.parse_max_plausible_edge_from_tag_message("sin el patron") is None


def test_git_tag_message_reads_the_real_tag(mod):
    """Verificacion de INTEGRACION del ancla real (seccion 2.5). Un checkout sin
    el tag -- CI con `actions/checkout` mientras el tag no este publicado -- no
    puede verificarla: se SALTA con el motivo explicito en vez de fallar o de
    pasar en falso. `git tag -l` sale 0 y devuelve "" con un tag inexistente,
    asi que `is not None` no distinguia ausencia de presencia (auditoria
    2026-10-15, AUD-002)."""
    if mod.git_rev_parse(f"refs/tags/{mod.TAG_NAME}", mod.DEFAULT_ROOT) is None:
        pytest.skip(f"tag {mod.TAG_NAME} ausente en este checkout: el ancla real del "
                    "pre-registro NO se verifica aqui (AUD-002)")
    msg = mod.git_tag_message(mod.TAG_NAME, mod.DEFAULT_ROOT)
    assert msg, f"el tag {mod.TAG_NAME} existe pero su mensaje esta vacio"
    assert mod.parse_max_plausible_edge_from_tag_message(msg) == pytest.approx(0.075)


# --------------------------------------------------- assemble_stats (M6, M3) --
def test_assemble_stats_end_to_end_with_known_d_hat_and_se(mod):
    """Test extremo a extremo de `assemble_stats` con D_hat y SE conocidos a
    mano: dos dias de 2 picks tier A cada uno, residuos simetricos que dan
    D_hat = 0 exactamente, y SE calculado con la formula de la seccion 3.1."""
    pf = pd.DataFrame({
        "_tier": ["A", "A", "A", "A"],
        "_resultado": ["win", "loss", "win", "loss"],
        "_p": [0.5, 0.6, 0.4, 0.5],
        "_dia": ["2026-10-01", "2026-10-01", "2026-10-02", "2026-10-02"],
        "event_id": ["e1", "e2", "e3", "e4"],
        "_edge_pp": [0.04, 0.04, 0.04, 0.04],
        "_novig": [0.46, 0.56, 0.36, 0.46],
        "_price": [2.0, 2.0, 2.0, 2.0],
        "_ev": [0.0, 0.0, 0.0, 0.0],
        "league": ["nfl", "nfl", "nfl", "nfl"],
    })
    primary = {"frame": pf, "counts": {}}
    ledger_vacio = {"frame": pd.DataFrame(), "counts": {}}
    out = mod.assemble_stats(primary, ledger_vacio, seed=mod.SEED, n_boot=200)
    primario = out["primario"]
    assert primario["n"] == 4
    assert primario["d_hat"] == pytest.approx(0.0, abs=1e-12)
    assert primario["se"] == pytest.approx(0.05, abs=1e-9)
    assert primario["z"] == pytest.approx(0.0, abs=1e-9)
    assert primario["etiqueta"] == "INCONCLUSO"
    assert primario["cota_inferior_95"] == pytest.approx(-mod.ALPHA_Z * 0.05, abs=1e-9)
    assert "S2_tier_B" in out and "S4_bandas" in out and "S6_metricas_apuesta" in out


def test_build_ledger_population_excludes_key_served_before_t0(mod):
    """Test extremo a extremo del ledger con una clave cuya primera SERVIDA
    es anterior a T0, aunque la fila del ledger (settled) sea posterior:
    debe quedar fuera (seccion 2.2)."""
    head = mod.git_rev_parse("HEAD", mod.DEFAULT_ROOT)
    labels_mod, tipster_mod = mod.load_frozen_classifier(mod.DEFAULT_ROOT, head, head)[:2]

    served_primeras = pd.DataFrame([_served_row(event_id="e8", generated_at="2026-09-01T00:00:00Z")])
    settled = pd.DataFrame([{
        **_served_row(event_id="e8", generated_at="2026-10-05T00:00:00Z"),
        "result": "win", "stake": 0.0,
    }])
    t0 = pd.Timestamp("2026-10-02T00:00:00Z")
    t1 = pd.Timestamp("2027-01-01T00:00:00Z")
    out = mod.build_ledger_population(served_primeras, settled, labels_mod, tipster_mod,
                                      t0, t1, mod.DEFAULT_TZ_CLUSTER, mod.MAX_PLAUSIBLE_EV)
    assert len(out["frame"]) == 0
    assert out["counts"]["fuera_de_ventana"] == 1


def test_build_ledger_population_reports_ventana_keys_before_validity(mod):
    """Hallazgo L2: `ventana_keys` se calcula ANTES de los filtros de 2.4, y
    es el conjunto que debe usar la verificacion cruzada de 2.3."""
    head = mod.git_rev_parse("HEAD", mod.DEFAULT_ROOT)
    labels_mod, tipster_mod = mod.load_frozen_classifier(mod.DEFAULT_ROOT, head, head)[:2]
    # El start_time del LEDGER sale del stream SERVIDO (ambiguedad 1): hay
    # que ensuciar el de `served_primeras`, no el de `settled`, para que la
    # fila falle el filtro pregame de 2.4.
    served_primeras = pd.DataFrame([_served_row(event_id="e13", generated_at="2026-10-05T00:00:00Z",
                                               start_time="no-es-fecha")])
    settled = pd.DataFrame([{
        **_served_row(event_id="e13", generated_at="2026-10-05T00:00:00Z"),
        "result": "win", "stake": 0.0,
    }])
    t0 = pd.Timestamp("2026-10-01T00:00:00Z")
    t1 = pd.Timestamp("2027-01-01T00:00:00Z")
    out = mod.build_ledger_population(served_primeras, settled, labels_mod, tipster_mod,
                                      t0, t1, mod.DEFAULT_TZ_CLUSTER, mod.MAX_PLAUSIBLE_EV)
    assert len(out["frame"]) == 0  # excluida por 2.4 (start_time ilegible)
    assert out["ventana_keys"] == {"e13|h2h|home|"}  # pero SI entro en la ventana


def test_build_ledger_population_counts_incomplete_identity_in_window(mod):
    """Hallazgo L2 (segunda parte): filas sin identidad con `generated_at`
    propio en la ventana, contadas aparte."""
    head = mod.git_rev_parse("HEAD", mod.DEFAULT_ROOT)
    labels_mod, tipster_mod = mod.load_frozen_classifier(mod.DEFAULT_ROOT, head, head)[:2]
    settled = pd.DataFrame([{**_served_row(event_id=np.nan, generated_at="2026-10-05T00:00:00Z"),
                            "result": "win", "stake": 0.0}])
    t0 = pd.Timestamp("2026-10-01T00:00:00Z")
    t1 = pd.Timestamp("2027-01-01T00:00:00Z")
    out = mod.build_ledger_population(pd.DataFrame(), settled, labels_mod, tipster_mod,
                                      t0, t1, mod.DEFAULT_TZ_CLUSTER, mod.MAX_PLAUSIBLE_EV)
    assert out["counts"]["identidad_incompleta_con_generated_at_en_ventana"] == 1


# ------------------------------------------------------- verificacion cruzada 2.3 --
def test_cross_check_unique_settled_detects_stake_and_identity_classes(mod):
    settled = pd.DataFrame({
        "event_id": ["e1", "e1", "e2", None],
        "market": ["h2h", "h2h", "h2h", "h2h"],
        "selection": ["home", "home", "home", "home"],
        "line": [np.nan, np.nan, np.nan, np.nan],
        "stake": [5.0, 3.0, 0.0, 0.0],
        "generated_at": ["2026-10-05T00:00:00Z", "2026-10-06T00:00:00Z",
                         "2026-10-05T00:00:00Z", "2026-10-05T00:00:00Z"],
    })
    window_keys = set(mod.pick_key(settled))  # incluye la clave vacia ("|h2h|home|")
    out = mod.cross_check_unique_settled(settled, window_keys)
    assert out["clases"]["fila_con_stake"] == 1
    assert out["clases"]["identidad_incompleta_nan"] == 1


def test_cross_check_unique_settled_empty_settled(mod):
    out = mod.cross_check_unique_settled(pd.DataFrame(), set())
    assert out["n_diferencias"] == 0


# ---------------------------------------------------------- join_result_by_key --
def test_join_result_by_key_abort_free_on_missing_result_column(mod):
    claves = pd.Series(["e1|h2h|home|"])
    graded = pd.DataFrame({"event_id": ["e1"], "market": ["h2h"], "selection": ["home"]})
    resultado, counts = mod.join_result_by_key(claves, graded)
    assert resultado.iloc[0] is None
    assert counts["resultados_discrepantes"] == 0


# ------------------------------------------------------------ --contar / jsonl --
def test_contar_mode_emits_no_result_fields_and_appends_exactly_one_line(
        mod, tmp_path, monkeypatch):
    """Seccion 7, test minimo 5."""
    data_root = tmp_path / "repo"
    (data_root / "data" / "calibration").mkdir(parents=True)
    (data_root / "data" / "bets").mkdir(parents=True)
    pd.DataFrame([_served_row()]).to_csv(
        data_root / "data" / "calibration" / "served_nfl.csv", index=False)

    preregistro = tmp_path / "pre.md"
    preregistro.write_text("# pre-registro de prueba\n", encoding="utf-8")

    head = mod.git_rev_parse("HEAD", mod.DEFAULT_ROOT)
    monkeypatch.setattr(mod, "resolve_h_t0",
                        lambda *a, **k: {"h": head, "t0_iso": "2020-01-01T00:00:00Z",
                                        "via": "tag"})
    monkeypatch.setattr(mod, "git_rev_parse", lambda ref, cwd: head)

    class _Args:
        pass
    args = _Args()
    args.data_root = data_root
    args.preregistro = preregistro
    args.tz_cluster = mod.DEFAULT_TZ_CLUSTER
    args.no_log = False

    out = mod.run_contar(args)
    texto = json.dumps(out)
    for campo_prohibido in ('"d_hat"', '"D_hat"', '"brecha"', '"p_valor', '"z":'):
        assert campo_prohibido not in texto
    assert out["modo"] == "contar"
    # La procedencia pesada (sha256/ligas) vive FUERA de "registro" (M6).
    assert "sha256_csv" in out["procedencia"]

    log_path = mod.contar_log_path(preregistro)
    assert log_path.exists()
    lineas = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lineas) == 1
    registro = json.loads(lineas[0])
    assert set(registro) == {
        "instante_ejecucion_utc", "head", "h", "t0", "t1_candidato", "n_primario",
        "g_primario", "n_ledger_informativo", "picks_ventana_sin_graduar",
        "via_resolucion_h_t0", "primera_servida_ventana", "ultima_servida_ventana",
        "tz_cluster_primario", "tz_cluster_solicitada"}
    assert "sha256_csv" not in registro

    # segunda ejecucion: anade una SEGUNDA linea (append-only), nunca reescribe.
    mod.run_contar(args)
    lineas2 = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lineas2) == 2


def test_contar_mode_with_no_log_does_not_touch_the_registry(mod, tmp_path, monkeypatch):
    data_root = tmp_path / "repo2"
    (data_root / "data" / "calibration").mkdir(parents=True)
    (data_root / "data" / "bets").mkdir(parents=True)
    pd.DataFrame([_served_row()]).to_csv(
        data_root / "data" / "calibration" / "served_nfl.csv", index=False)
    preregistro = tmp_path / "pre2.md"
    preregistro.write_text("# pre-registro de prueba\n", encoding="utf-8")

    head = mod.git_rev_parse("HEAD", mod.DEFAULT_ROOT)
    monkeypatch.setattr(mod, "resolve_h_t0",
                        lambda *a, **k: {"h": head, "t0_iso": "2020-01-01T00:00:00Z",
                                        "via": "tag"})
    monkeypatch.setattr(mod, "git_rev_parse", lambda ref, cwd: head)

    class _Args:
        pass
    args = _Args()
    args.data_root = data_root
    args.preregistro = preregistro
    args.tz_cluster = mod.DEFAULT_TZ_CLUSTER
    args.no_log = True

    out = mod.run_contar(args)
    assert "no se escribio" in out["aviso"].lower()
    log_path = mod.contar_log_path(preregistro)
    assert not log_path.exists()


def test_contar_mode_reports_ligas_faltantes_without_aborting(mod, tmp_path, monkeypatch):
    """Hallazgo M5: --contar solo INFORMA una liga listada pero no cargada
    (fichero vacio), nunca aborta."""
    data_root = tmp_path / "repo_m5"
    (data_root / "data" / "calibration").mkdir(parents=True)
    (data_root / "data" / "bets").mkdir(parents=True)
    pd.DataFrame([_served_row()]).to_csv(
        data_root / "data" / "calibration" / "served_nfl.csv", index=False)
    (data_root / "data" / "calibration" / "served_mlb.csv").write_text("", encoding="utf-8")
    preregistro = tmp_path / "pre_m5.md"
    preregistro.write_text("# pre-registro de prueba\n", encoding="utf-8")

    head = mod.git_rev_parse("HEAD", mod.DEFAULT_ROOT)
    monkeypatch.setattr(mod, "resolve_h_t0",
                        lambda *a, **k: {"h": head, "t0_iso": "2020-01-01T00:00:00Z",
                                        "via": "tag"})
    monkeypatch.setattr(mod, "git_rev_parse", lambda ref, cwd: head)

    class _Args:
        pass
    args = _Args()
    args.data_root = data_root
    args.preregistro = preregistro
    args.tz_cluster = mod.DEFAULT_TZ_CLUSTER
    args.no_log = True

    out = mod.run_contar(args)  # NO debe abortar
    assert "mlb" in out["procedencia"]["ligas"]["served"]["faltantes"]


# --------------------------------------------------------------- carga segura M5 --
def test_read_csv_glob_safe_skips_corrupt_files_without_mutating_them(mod, tmp_path):
    good = tmp_path / "good.csv"
    pd.DataFrame({"league": ["nfl"], "a": [1]}).to_csv(good, index=False)
    bad = tmp_path / "bad.csv"
    bad.write_text('a,b\n"1,2\n3,4', encoding="utf-8")  # comilla sin cerrar -> ParserError
    original_bytes = bad.read_bytes()
    df, errores = mod._read_csv_glob_safe([good, bad])
    assert "league" in df.columns and list(df["league"]) == ["nfl"]
    assert len(errores) == 1
    assert bad.exists()  # NUNCA se renombra/mueve (M5)
    assert bad.read_bytes() == original_bytes  # contenido intacto


def test_ligas_provenance_reports_missing_leagues(mod, tmp_path):
    p1 = tmp_path / "served_nfl.csv"
    p1.write_text("league\nnfl\n", encoding="utf-8")
    p2 = tmp_path / "served_mlb.csv"
    p2.write_text("", encoding="utf-8")  # vacio -> no se carga ninguna fila
    df, errores = mod._read_csv_glob_safe([p1, p2])
    prov = mod._ligas_provenance([p1, p2], df, "served_", errores)
    assert prov["listadas"] == ["mlb", "nfl"]
    assert prov["faltantes"] == ["mlb"]
    assert prov["cargadas"] == ["nfl"]


# --------------------------------------------------------------- --medir --
def _fake_show_builder(mapping: dict[str, str]):
    """`git_show_text` falso para pruebas de `--medir`: devuelve el texto de
    `mapping` para cualquier `relpath` conocido (ignora `ref`, salvo que el
    propio test necesite distinguirlo), y lanza si se pide algo inesperado
    -- asi un cambio futuro que anada una lectura de git sin cubrir aqui
    rompe la prueba en vez de pasar en silencio."""
    def fake(ref, relpath, cwd):
        if relpath in mapping:
            return mapping[relpath]
        raise AssertionError(f"git_show_text con relpath inesperado: {relpath!r} (ref={ref!r})")
    return fake


def test_medir_mode_aborts_without_an_addendum(mod, monkeypatch):
    """Seccion 7, test minimo 6 (parte 1): sin addendum, --medir aborta."""
    preregistro = mod._WORKTREE_ROOT / "docs" / "research" / "_test_fake_preregistro_1.md"
    rel_pre = "docs/research/_test_fake_preregistro_1.md"
    head = mod.git_rev_parse("HEAD", mod.DEFAULT_ROOT)

    monkeypatch.setattr(mod, "resolve_h_t0",
                        lambda *a, **k: {"h": head, "t0_iso": "2020-01-01T00:00:00Z", "via": "tag"})
    monkeypatch.setattr(mod, "git_rev_parse", lambda ref, cwd: head)
    monkeypatch.setattr(mod, "git_status_porcelain", lambda cwd, *a, **k: "")
    monkeypatch.setattr(mod, "git_show_text",
                        _fake_show_builder({rel_pre: "# pre-registro sin addendum\n"}))

    class _Args:
        pass
    args = _Args()
    args.data_root = mod.DEFAULT_ROOT
    args.preregistro = preregistro
    args.tz_cluster = mod.DEFAULT_TZ_CLUSTER
    args.t1 = "2027-05-01T00:00:00Z"
    args.seed = mod.SEED
    args.n_boot = 10

    with pytest.raises(SystemExit, match="No hay addendum"):
        mod.run_medir(args)


def test_medir_mode_aborts_with_a_t1_different_from_the_addendum(mod, monkeypatch):
    """Seccion 7, test minimo 6 (parte 2): T1 distinto del registrado."""
    preregistro = mod._WORKTREE_ROOT / "docs" / "research" / "_test_fake_preregistro_2.md"
    rel_pre = "docs/research/_test_fake_preregistro_2.md"
    head = mod.git_rev_parse("HEAD", mod.DEFAULT_ROOT)
    doc_text = ("## Addenda\nT1 fijado = 2027-05-01T00:00:00Z\n"
               "commit del registro = 0123456789abcdef0123456789abcdef01234567\n")

    monkeypatch.setattr(mod, "resolve_h_t0",
                        lambda *a, **k: {"h": head, "t0_iso": "2020-01-01T00:00:00Z", "via": "tag"})
    monkeypatch.setattr(mod, "git_rev_parse", lambda ref, cwd: head)
    monkeypatch.setattr(mod, "git_status_porcelain", lambda cwd, *a, **k: "")
    monkeypatch.setattr(mod, "git_show_text", _fake_show_builder({rel_pre: doc_text}))

    class _Args:
        pass
    args = _Args()
    args.data_root = mod.DEFAULT_ROOT
    args.preregistro = preregistro
    args.tz_cluster = mod.DEFAULT_TZ_CLUSTER
    args.t1 = "2027-06-01T00:00:00Z"  # distinto del addendum
    args.seed = mod.SEED
    args.n_boot = 10

    with pytest.raises(SystemExit, match="no coincide"):
        mod.run_medir(args)


def test_medir_mode_accepts_t1_in_a_different_iso_representation_of_the_same_instant(
        mod, monkeypatch):
    """Hallazgo M1: compara POR INSTANTE, no por texto -- 'Z' y '+00:00' del
    mismo instante no deben abortar aqui (abortara mas adelante, al no
    haber registro .jsonl, pero NO por esta comprobacion)."""
    preregistro = mod._WORKTREE_ROOT / "docs" / "research" / "_test_fake_preregistro_2b.md"
    rel_pre = "docs/research/_test_fake_preregistro_2b.md"
    rel_jsonl = "docs/research/_test_fake_preregistro_2b.contar.jsonl"
    head = mod.git_rev_parse("HEAD", mod.DEFAULT_ROOT)
    doc_text = ("## Addenda\nT1 fijado = 2027-05-01T00:00:00Z\n"
               "commit del registro = 0123456789abcdef0123456789abcdef01234567\n")

    monkeypatch.setattr(mod, "resolve_h_t0",
                        lambda *a, **k: {"h": head, "t0_iso": "2020-01-01T00:00:00Z", "via": "tag"})
    monkeypatch.setattr(mod, "git_rev_parse", lambda ref, cwd: head)
    monkeypatch.setattr(mod, "git_status_porcelain", lambda cwd, *a, **k: "")
    monkeypatch.setattr(mod, "git_show_text", _fake_show_builder({rel_pre: doc_text}))

    class _Args:
        pass
    args = _Args()
    args.data_root = mod.DEFAULT_ROOT
    args.preregistro = preregistro
    args.tz_cluster = mod.DEFAULT_TZ_CLUSTER
    args.t1 = "2027-05-01T00:00:00+00:00"  # MISMO instante, otra representacion
    args.seed = mod.SEED
    args.n_boot = 10

    # Pasa la comprobacion de T1 y aborta mas adelante (sin registro .jsonl
    # cubierto por el fake), nunca por "no coincide".
    with pytest.raises(AssertionError, match=rel_jsonl):
        mod.run_medir(args)


def test_medir_mode_aborts_when_n_at_t1_is_below_the_threshold(mod, tmp_path, monkeypatch):
    """Seccion 7, test minimo 6 (parte 3): addendum y registro consistentes
    -- INCLUYENDO el respaldo del commit citado (hallazgo M1) -- pero
    `n(T1)` recalculado hoy no llega a 2100 (datos sinteticos, muy por
    debajo del umbral): debe abortar en la comprobacion final, no antes."""
    data_root = tmp_path / "repo3"
    (data_root / "data" / "calibration").mkdir(parents=True)
    (data_root / "data" / "bets").mkdir(parents=True)
    pd.DataFrame([_served_row()]).to_csv(
        data_root / "data" / "calibration" / "served_nfl.csv", index=False)

    preregistro = mod._WORKTREE_ROOT / "docs" / "research" / "_test_fake_preregistro_3.md"
    rel_pre = "docs/research/_test_fake_preregistro_3.md"
    rel_jsonl = "docs/research/_test_fake_preregistro_3.contar.jsonl"
    t1 = "2027-05-01T00:00:00Z"
    commit_registro = "0123456789abcdef0123456789abcdef01234567"
    doc_text = (f"## Addenda\nT1 fijado = {t1}\n"
               f"commit del registro = {commit_registro}\n")
    jsonl_line = json.dumps({"n_primario": 2100, "t1_candidato": t1}) + "\n"

    head = mod.git_rev_parse("HEAD", mod.DEFAULT_ROOT)
    monkeypatch.setattr(mod, "resolve_h_t0",
                        lambda *a, **k: {"h": head, "t0_iso": "2020-01-01T00:00:00Z", "via": "tag"})
    monkeypatch.setattr(mod, "git_rev_parse", lambda ref, cwd: head)
    monkeypatch.setattr(mod, "git_status_porcelain", lambda cwd, *a, **k: "")
    monkeypatch.setattr(mod, "git_show_text",
                        _fake_show_builder({rel_pre: doc_text, rel_jsonl: jsonl_line}))

    class _Args:
        pass
    args = _Args()
    args.data_root = data_root
    args.preregistro = preregistro
    args.tz_cluster = mod.DEFAULT_TZ_CLUSTER
    args.t1 = t1
    args.seed = mod.SEED
    args.n_boot = 10

    with pytest.raises(SystemExit, match=r"n\(T1\)"):
        mod.run_medir(args)


def test_medir_mode_aborts_when_the_cited_commit_jsonl_lacks_the_backing_line(
        mod, tmp_path, monkeypatch):
    """Hallazgo M1: el commit citado en el addendum debe contener, EN ESA
    version de .contar.jsonl, la linea con n>=2100 -- si HEAD la tiene pero
    el commit citado no, --medir aborta por falta de respaldo."""
    preregistro = mod._WORKTREE_ROOT / "docs" / "research" / "_test_fake_preregistro_4.md"
    rel_pre = "docs/research/_test_fake_preregistro_4.md"
    rel_jsonl = "docs/research/_test_fake_preregistro_4.contar.jsonl"
    t1 = "2027-05-01T00:00:00Z"
    commit_registro = "0123456789abcdef0123456789abcdef01234567"
    doc_text = (f"## Addenda\nT1 fijado = {t1}\n"
               f"commit del registro = {commit_registro}\n")

    head = mod.git_rev_parse("HEAD", mod.DEFAULT_ROOT)

    def fake_show(ref, relpath, cwd):
        if relpath == rel_pre:
            return doc_text
        if relpath == rel_jsonl:
            if ref == commit_registro:
                return json.dumps({"n_primario": 500, "t1_candidato": t1}) + "\n"
            return json.dumps({"n_primario": 2100, "t1_candidato": t1}) + "\n"
        raise AssertionError(f"relpath inesperado: {relpath}")

    monkeypatch.setattr(mod, "resolve_h_t0",
                        lambda *a, **k: {"h": head, "t0_iso": "2020-01-01T00:00:00Z", "via": "tag"})
    monkeypatch.setattr(mod, "git_rev_parse", lambda ref, cwd: head)
    monkeypatch.setattr(mod, "git_status_porcelain", lambda cwd, *a, **k: "")
    monkeypatch.setattr(mod, "git_show_text", fake_show)

    class _Args:
        pass
    args = _Args()
    args.data_root = mod.DEFAULT_ROOT
    args.preregistro = preregistro
    args.tz_cluster = mod.DEFAULT_TZ_CLUSTER
    args.t1 = t1
    args.seed = mod.SEED
    args.n_boot = 10

    with pytest.raises(SystemExit, match="sin respaldo verificable"):
        mod.run_medir(args)


def test_medir_mode_aborts_when_a_league_csv_is_missing_from_the_loaded_set(
        mod, tmp_path, monkeypatch):
    """Hallazgo M5: --medir ABORTA (no solo informa) si una liga listada no
    se cargo (CSV vacio/corrupto)."""
    data_root = tmp_path / "repo_m5_medir"
    (data_root / "data" / "calibration").mkdir(parents=True)
    (data_root / "data" / "bets").mkdir(parents=True)
    pd.DataFrame([_served_row()]).to_csv(
        data_root / "data" / "calibration" / "served_nfl.csv", index=False)
    (data_root / "data" / "calibration" / "served_mlb.csv").write_text("", encoding="utf-8")

    preregistro = mod._WORKTREE_ROOT / "docs" / "research" / "_test_fake_preregistro_5.md"
    rel_pre = "docs/research/_test_fake_preregistro_5.md"
    rel_jsonl = "docs/research/_test_fake_preregistro_5.contar.jsonl"
    t1 = "2027-05-01T00:00:00Z"
    commit_registro = "0123456789abcdef0123456789abcdef01234567"
    doc_text = (f"## Addenda\nT1 fijado = {t1}\ncommit del registro = {commit_registro}\n")
    jsonl_line = json.dumps({"n_primario": 2100, "t1_candidato": t1}) + "\n"

    head = mod.git_rev_parse("HEAD", mod.DEFAULT_ROOT)
    monkeypatch.setattr(mod, "resolve_h_t0",
                        lambda *a, **k: {"h": head, "t0_iso": "2020-01-01T00:00:00Z", "via": "tag"})
    monkeypatch.setattr(mod, "git_rev_parse", lambda ref, cwd: head)
    monkeypatch.setattr(mod, "git_status_porcelain", lambda cwd, *a, **k: "")
    monkeypatch.setattr(mod, "git_show_text",
                        _fake_show_builder({rel_pre: doc_text, rel_jsonl: jsonl_line}))

    class _Args:
        pass
    args = _Args()
    args.data_root = data_root
    args.preregistro = preregistro
    args.tz_cluster = mod.DEFAULT_TZ_CLUSTER
    args.t1 = t1
    args.seed = mod.SEED
    args.n_boot = 10

    with pytest.raises(SystemExit, match="mlb"):
        mod.run_medir(args)


def test_medir_mode_full_success_with_tz_sensitivity(mod, tmp_path, monkeypatch):
    """Extremo a extremo: >= 2100 picks A win/loss sinteticos, addendum y
    registro respaldados correctamente, --tz-cluster distinto del congelado
    (hallazgo M2: debe aparecer como sensibilidad MARCADA, nunca sustituir
    al primario, que siempre usa America/New_York)."""
    n = 2110
    rng = np.random.default_rng(777)
    dates = pd.date_range("2026-10-05", periods=max(60, n // 30), freq="D")
    served_rows, graded_rows = [], []
    for i in range(n):
        day = dates[i % len(dates)]
        gen_at = (day - pd.Timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        start_at = day.strftime("%Y-%m-%dT%H:%M:%SZ")
        row = _served_row(event_id=f"ev{i}", generated_at=gen_at, start_time=start_at,
                          price_decimal=1.9, implied_probability_novig=0.48,
                          estimated_probability=0.55, calibrated_probability=np.nan,
                          books_count=25.0, league="nfl")
        served_rows.append(row)
        graded_rows.append({**row, "result": "win" if rng.random() < 0.5 else "loss"})

    data_root = tmp_path / "repo_full"
    (data_root / "data" / "calibration").mkdir(parents=True)
    (data_root / "data" / "bets").mkdir(parents=True)
    pd.DataFrame(served_rows).to_csv(
        data_root / "data" / "calibration" / "served_nfl.csv", index=False)
    pd.DataFrame(graded_rows).to_csv(
        data_root / "data" / "calibration" / "graded_nfl.csv", index=False)

    preregistro = mod._WORKTREE_ROOT / "docs" / "research" / "_test_fake_preregistro_full.md"
    rel_pre = "docs/research/_test_fake_preregistro_full.md"
    rel_jsonl = "docs/research/_test_fake_preregistro_full.contar.jsonl"
    t1 = "2027-05-01T00:00:00Z"
    commit_registro = "0123456789abcdef0123456789abcdef01234567"
    doc_text = (f"## Addenda\nT1 fijado = {t1}\ncommit del registro = {commit_registro}\n")
    jsonl_line = json.dumps({"n_primario": 2100, "t1_candidato": t1}) + "\n"

    head = mod.git_rev_parse("HEAD", mod.DEFAULT_ROOT)
    monkeypatch.setattr(mod, "resolve_h_t0",
                        lambda *a, **k: {"h": head, "t0_iso": "2020-01-01T00:00:00Z", "via": "tag"})
    monkeypatch.setattr(mod, "git_rev_parse", lambda ref, cwd: head)
    monkeypatch.setattr(mod, "git_status_porcelain", lambda cwd, *a, **k: "")
    monkeypatch.setattr(mod, "git_show_text",
                        _fake_show_builder({rel_pre: doc_text, rel_jsonl: jsonl_line}))
    # Test sintetico: el mensaje del tag tambien es un doble, como el resto de
    # git arriba. La lectura del tag REAL la cubre
    # `test_git_tag_message_reads_the_real_tag` (auditoria 2026-10-15, AUD-002).
    monkeypatch.setattr(mod, "git_tag_message", lambda tag, cwd: (
        "max_plausible_edge efectivo de Settings en H: 0.075 (doble del test)\n"))

    class _Args:
        pass
    args = _Args()
    args.data_root = data_root
    args.preregistro = preregistro
    args.tz_cluster = "UTC"  # distinto del congelado -> sensibilidad aparte
    args.t1 = t1
    args.seed = mod.SEED
    args.n_boot = 50

    out = mod.run_medir(args)
    assert out["modo"] == "medir"
    assert out["primario"]["n"] >= N_REQUIRED if (N_REQUIRED := mod.N_REQUIRED) else True
    assert out["procedencia"]["tz_cluster_primario"] == mod.DEFAULT_TZ_CLUSTER
    assert out["procedencia"]["tz_cluster_solicitada"] == "UTC"
    assert "S5_sensibilidad_tz_cluster_alternativa" in out
    assert out["S5_sensibilidad_tz_cluster_alternativa"]["zona"] == "UTC"
    assert out["procedencia"]["max_plausible_edge"]["registrado_en_tag"] == pytest.approx(0.075)
    assert out["procedencia"]["picks_que_el_clasificador_vivo_clasificaria_distinto"] == 0
    assert out["procedencia"]["seed_n_boot"]["difiere_de_lo_congelado"] is True


# ----------------------------------------------- recuentos adicionales 2.3 --
def test_count_keys_with_multiple_stake_rows(mod):
    settled = pd.DataFrame({
        "event_id": ["e1", "e1", "e2"], "market": ["h2h", "h2h", "h2h"],
        "selection": ["home", "home", "home"], "line": [np.nan, np.nan, np.nan],
        "stake": [5.0, 3.0, 0.0]})
    assert mod.count_keys_with_multiple_stake_rows(settled) == 1


def test_count_keys_with_multiple_stake_rows_empty_or_no_stake_column(mod):
    assert mod.count_keys_with_multiple_stake_rows(pd.DataFrame()) == 0
    settled = pd.DataFrame({"event_id": ["e1"], "market": ["h2h"], "selection": ["home"]})
    assert mod.count_keys_with_multiple_stake_rows(settled) == 0


def test_parse_t1_addendum_returns_none_without_the_expected_format(mod):
    assert mod.parse_t1_addendum("texto cualquiera sin addendum") is None


def test_parse_t1_addendum_extracts_t1_and_commit(mod):
    texto = ("## Addenda\nT1 fijado = 2027-05-01T00:00:00Z\n"
            "commit del registro = abcdef0123456789abcdef0123456789abcdef01\n")
    t1, commit = mod.parse_t1_addendum(texto)
    assert t1 == "2027-05-01T00:00:00Z"
    assert commit == "abcdef0123456789abcdef0123456789abcdef01"


# -------------------------------------------------------- resolucion de H/T0 --
def test_resolve_h_t0_aborts_when_tag_and_fallback_disagree(mod, monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "git_rev_parse", lambda ref, cwd: "aaaa")
    monkeypatch.setattr(mod, "git_committer_date_iso", lambda ref, cwd: "2026-01-01T00:00:00Z")
    monkeypatch.setattr(mod, "git_log_added", lambda rel, cwd: ("bbbb", "2026-02-01T00:00:00Z"))
    with pytest.raises(SystemExit):
        mod.resolve_h_t0(tmp_path / "pre.md", tmp_path)


def test_resolve_h_t0_uses_fallback_when_tag_is_absent(mod, monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "git_rev_parse", lambda ref, cwd: None)
    monkeypatch.setattr(mod, "git_committer_date_iso", lambda ref, cwd: None)
    monkeypatch.setattr(mod, "git_log_added", lambda rel, cwd: ("bbbb", "2026-02-01T00:00:00Z"))
    out = mod.resolve_h_t0(tmp_path / "pre.md", tmp_path)
    assert out == {"h": "bbbb", "t0_iso": "2026-02-01T00:00:00Z", "via": "fallback"}


def test_resolve_h_t0_aborts_when_neither_mechanism_resolves(mod, monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "git_rev_parse", lambda ref, cwd: None)
    monkeypatch.setattr(mod, "git_committer_date_iso", lambda ref, cwd: None)
    monkeypatch.setattr(mod, "git_log_added", lambda rel, cwd: None)
    with pytest.raises(SystemExit):
        mod.resolve_h_t0(tmp_path / "pre.md", tmp_path)


# ------------------------------------------------------------------- _parse_ts --
def test_parse_ts_treats_different_iso_representations_as_equal(mod):
    a = mod._parse_ts("2027-05-01T00:00:00Z")
    b = mod._parse_ts("2027-05-01T00:00:00+00:00")
    assert a == b


def test_parse_ts_returns_none_for_garbage(mod):
    assert mod._parse_ts("no-es-fecha") is None
    assert mod._parse_ts(None) is None


# ------------------------------------------------------- clasificador congelado --
def test_load_frozen_classifier_uses_live_modules_when_hashes_match(mod):
    head = mod.git_rev_parse("HEAD", mod.DEFAULT_ROOT)
    labels_mod, tipster_mod, hashes = mod.load_frozen_classifier(mod.DEFAULT_ROOT, head, head)
    import sqp.evaluation.labels as live_labels
    import sqp.evaluation.tipster as live_tipster
    assert labels_mod is live_labels
    assert tipster_mod is live_tipster
    assert not hashes["labels"]["diverge"]
    assert not hashes["tipster"]["diverge"]
    assert hashes["labels"]["hash_disco"] == hashes["labels"]["hash_h"]


def test_load_frozen_classifier_isolates_sources_when_hashes_diverge(mod, monkeypatch):
    """Simula divergencia: fuerza `hash_h` != `hash_head` (con un contador,
    para no depender de que exista otro commit real con otro contenido) y
    comprueba que se cargan modulos AISLADOS (no los objetos live), que
    clasifican igual, y que `sys.modules['sqp.evaluation.labels']` queda
    intacto despues. `h` sigue siendo HEAD (una ref real y valida) para que
    `git show` pueda leer las fuentes."""
    import sqp.evaluation.labels as live_labels
    head = mod.git_rev_parse("HEAD", mod.DEFAULT_ROOT)
    contador = itertools.count()

    def fake_blob_hash(ref, relpath, cwd):
        return f"hash-{next(contador)}"  # siempre distinto -> diverge=True

    monkeypatch.setattr(mod, "git_blob_hash", fake_blob_hash)
    labels_mod, tipster_mod, hashes = mod.load_frozen_classifier(mod.DEFAULT_ROOT, head, head)
    assert hashes["labels"]["diverge"] is True
    assert labels_mod is not live_labels
    assert labels_mod.__name__ == "_frozen_labels_at_h"
    assert tipster_mod.classify(0.05, 0.03, 20, 0.55, 0.075) == ("A", "edge solido con consenso profundo")
    # el modulo real no quedo sustituido para el resto del proceso.
    assert sys.modules["sqp.evaluation.labels"] is live_labels


def test_load_frozen_classifier_forces_isolation_when_disk_differs_from_h_even_if_head_matches(
        mod, monkeypatch):
    """Hallazgo M4: `hash_h == hash_head` pero `hash_disco` distinto
    (cambios sin commitear) debe forzar la carga aislada, NUNCA el import
    vivo (que leeria el fichero en disco, no H)."""
    import sqp.evaluation.labels as live_labels
    head = mod.git_rev_parse("HEAD", mod.DEFAULT_ROOT)

    monkeypatch.setattr(mod, "git_blob_hash", lambda ref, relpath, cwd: "same-hash")
    monkeypatch.setattr(mod, "git_hash_object", lambda relpath, cwd: "disco-distinto")
    labels_mod, tipster_mod, hashes = mod.load_frozen_classifier(mod.DEFAULT_ROOT, head, head)
    assert hashes["labels"]["diverge"] is True
    assert labels_mod is not live_labels


def test_git_hash_object_matches_git_blob_hash_of_head_when_clean(mod):
    head = mod.git_rev_parse("HEAD", mod.DEFAULT_ROOT)
    disco = mod.git_hash_object(mod._LABELS_REL, mod.DEFAULT_ROOT)
    blob_head = mod.git_blob_hash(head, mod._LABELS_REL, mod.DEFAULT_ROOT)
    assert disco == blob_head


# --------------------------------------------------------------- argparse --
def test_contar_and_medir_are_mutually_exclusive(mod, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["measure_tier_a_gap.py", "--contar", "--medir",
                                      "--t1", "2027-01-01T00:00:00Z"])
    with pytest.raises(SystemExit):
        mod.main()


def test_one_of_contar_or_medir_is_required(mod, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["measure_tier_a_gap.py"])
    with pytest.raises(SystemExit):
        mod.main()


def test_medir_requires_t1(mod, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["measure_tier_a_gap.py", "--medir"])
    with pytest.raises(SystemExit):
        mod.main()


def test_no_log_rejected_outside_contar(mod, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["measure_tier_a_gap.py", "--medir",
                                      "--t1", "2027-01-01T00:00:00Z", "--no-log"])
    with pytest.raises(SystemExit):
        mod.main()


def test_t1_rejected_with_contar(mod, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["measure_tier_a_gap.py", "--contar",
                                      "--t1", "2027-01-01T00:00:00Z"])
    with pytest.raises(SystemExit):
        mod.main()


def test_liga_solo_cabecera_no_es_faltante(tmp_path):
    """Revision Fable 2026-10-03: un CSV que se lee sin error pero solo trae
    cabecera va a `vacias`, no a `faltantes` (no debe abortar --medir)."""
    mod = _load_module()
    p1 = tmp_path / "served_mlb.csv"
    p2 = tmp_path / "served_nba.csv"
    pd.DataFrame([{"league": "mlb", "event_id": "e"}]).to_csv(p1, index=False)
    p2.write_text("league,event_id\n", encoding="utf-8")
    df, errores = mod._read_csv_glob_safe([p1, p2])
    prov = mod._ligas_provenance([p1, p2], df, "served_", errores)
    assert prov["faltantes"] == [] and prov["vacias"] == ["nba"]


def test_tz_cluster_invalida_falla_antes_de_medir(monkeypatch):
    mod = _load_module()
    llamado = []
    monkeypatch.setattr(mod, "run_contar", lambda a: llamado.append(a) or {})
    monkeypatch.setattr(sys, "argv", ["x", "--contar", "--no-log",
                                      "--tz-cluster", "Marte/Olympus"])
    with pytest.raises(SystemExit):
        mod.main()
    assert llamado == []
