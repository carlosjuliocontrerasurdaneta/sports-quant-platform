"""Pruebas SINTETICAS de `scripts/research/measure_adjustment_battery.py`
(pre-registro `docs/research/2026-09-27-preregistro-bateria-ajustes.md` y su
Enmienda 1).

Ninguna prueba lee los historicos reales (`data/historical/`), ni ejecuta el
modo completo ni `--pre` contra los datos de produccion: eso es la medicion en
si. Todo se ejercita con partidos SINTETICOS pequenos (equipos A..F, marcadores
aleatorios con semilla fija), `warmup=0` y, cuando hace falta, un `data_root`
temporal. Los tests de `_league_meta` se fijan con `monkeypatch`, como en
`tests/test_measure_tilt_nhl.py`.
"""
from __future__ import annotations

import importlib.util
import json
import math

import numpy as np
import pandas as pd
import pytest

from sqp.config import ROOT
from sqp.features.rest_form import (
    h2h_p_adjustment,
    home_away_form_p_adjustment,
    margin_p_adjustment,
    rest_form_p_adjustment,
)
from sqp.sports.registry import get_adapter

SCRIPT = ROOT / "scripts" / "research" / "measure_adjustment_battery.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("measure_adjustment_battery", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_module()


TEAMS = ("A", "B", "C", "D", "E", "F")


def _games(kind: str, n_days: int = 70, start: str = "2014-10-01", per_day: int = 3,
           seed: int = 11) -> list[dict]:
    """Partidos SINTETICOS (no son datos reales de ninguna liga)."""
    rng = np.random.default_rng(seed)
    days = pd.date_range(start, periods=n_days, freq="D")
    rows, gid = [], 0
    for d in days:
        order = list(rng.permutation(TEAMS))
        for k in range(per_day):
            h, a = order[2 * k], order[2 * k + 1]
            if kind == "nba":
                hs, aws = int(rng.normal(112, 12)), int(rng.normal(108, 12))
            elif kind == "nfl":
                hs, aws = int(rng.normal(24, 8)), int(rng.normal(21, 8))
            elif kind == "mlb":
                hs, aws = int(rng.poisson(4.6)), int(rng.poisson(4.3))
            else:  # nhl
                hs, aws = int(rng.poisson(3.1)), int(rng.poisson(2.9))
            rows.append({"date": d.strftime("%Y-%m-%d"), "home": h, "away": a, "game_id": str(gid),
                         "home_score": hs, "away_score": aws, "neutral": False})
            gid += 1
    return rows


def _frame(mod, league: str, **kw):
    kind = league
    results = _games(kind)
    lp = dict(mod.EXPECTED_LEAGUE_PARAMS[league] or {}) or None
    return results, lp, mod.build_frame(results, league, mod.FAMILY[league], lp, warmup=0, **kw)


# ----------------------------------------------------------- parametros --
@pytest.mark.parametrize("league", ["nba", "nhl", "nfl", "mlb"])
def test_expected_params_match_real_adapters(mod, league):
    """Los literales del script (Enmienda 1(b)) son los que resuelve el codigo."""
    lp = mod.EXPECTED_LEAGUE_PARAMS[league]
    params = get_adapter(league, mod.FAMILY[league], lp).params
    assert dict(params) == mod.EXPECTED_ADAPTER_PARAMS[league]
    mod.assert_resolved_params(league, lp, dict(params))     # no aborta


def test_resolved_params_abort_on_tilt_09(mod):
    lp = {"elo_home_adv": 15.0, "tilt_scale": 0.9}
    params = dict(get_adapter("nhl", "hockey", lp).params)
    with pytest.raises(SystemExit, match="league_params"):
        mod.assert_resolved_params("nhl", lp, params)


def test_resolved_params_abort_when_adapter_params_change(mod):
    lp = mod.EXPECTED_LEAGUE_PARAMS["nhl"]
    params = dict(get_adapter("nhl", "hockey", lp).params)
    params["rest_elo_per_day"] = 0.0           # clave extra: debe abortar ("ninguna otra clave")
    with pytest.raises(SystemExit, match="adapter.params"):
        mod.assert_resolved_params("nhl", lp, params)
    params2 = dict(get_adapter("nhl", "hockey", lp).params)
    params2["avg_total"] = 6.2
    with pytest.raises(SystemExit, match="adapter.params"):
        mod.assert_resolved_params("nhl", lp, params2)


def test_resolved_params_nfl_must_be_none(mod):
    with pytest.raises(SystemExit):
        mod.assert_resolved_params("nfl", {"elo_k": 24}, dict(get_adapter("nfl", "football", None).params))
    mod.assert_resolved_params("nfl", None, dict(get_adapter("nfl", "football", None).params))


def test_load_league_aborts_when_meta_changes_and_applies_cutoff(mod, monkeypatch, tmp_path):
    hist = tmp_path / "data" / "historical"
    hist.mkdir(parents=True)
    rows = _games("nfl", n_days=4, start="2026-09-24")          # 24, 25, 26, 27
    pd.DataFrame(rows).assign(ingested_at="x").to_csv(hist / "results_nfl.csv", index=False)
    monkeypatch.setattr(mod, "_league_meta", lambda lg: {"family": "football"})
    results, lp, proc = mod.load_league("nfl", tmp_path)
    assert lp is None
    assert max(str(r["date"])[:10] for r in results) <= "2026-09-26"
    assert len(results) == 9 and proc["filas_leidas"] == 9 and len(proc["sha256"]) == 64
    monkeypatch.setattr(mod, "_league_meta", lambda lg: {"family": "football", "league_params": {"elo_k": 30}})
    with pytest.raises(SystemExit):
        mod.load_league("nfl", tmp_path)


# ------------------------------------------------ frame / L_i / identidades --
@pytest.mark.parametrize("league", ["nba", "nhl", "nfl", "mlb"])
def test_lines_are_floor_mu_plus_half(mod, league):
    _, _, fr = _frame(mod, league, with_outcomes=True)
    df = fr.df
    assert np.allclose(df["L"], np.floor(df["mu"]) + 0.5, atol=0, rtol=0)
    assert ((df["L"] - 0.5) % 1 == 0).all()
    if league in ("nba", "nfl"):                 # spread del local: -(floor(mu_margen)+0.5)
        assert ((df["s1"] + 0.5) % 1 == 0).all() and df["s2"].isna().all()
    else:                                        # puck/run line +-1,5
        assert (df["s1"] == -1.5).all() and (df["s2"] == 1.5).all()


def test_pre_frame_has_no_outcome_columns(mod):
    _, _, fr = _frame(mod, "nhl", with_outcomes=False)
    forbidden = {"home_score", "away_score", "margin", "total", "y_h2h", "p_h2h", "p_s1", "p_s2", "p_over"}
    assert forbidden.isdisjoint(fr.df.columns)
    assert {"L", "x2", "x3", "x4", "x8", "x9", "x10", "x6", "x7"} <= set(fr.df.columns)


def test_pre_features_do_not_depend_on_scores_of_the_game_itself(mod):
    """Cambiar los marcadores del ULTIMO dia no puede alterar ninguna feature ni
    L_i de ese dia: solo usan partidos con fecha estrictamente anterior."""
    res = _games("nhl")
    last = max(r["date"] for r in res)
    res2 = [dict(r, home_score=r["home_score"] + 7, away_score=r["away_score"] + 3) if r["date"] == last else dict(r)
            for r in res]
    lp = mod.EXPECTED_LEAGUE_PARAMS["nhl"]
    a = mod.build_frame(res, "nhl", "hockey", lp, with_outcomes=False, warmup=0).df
    b = mod.build_frame(res2, "nhl", "hockey", lp, with_outcomes=False, warmup=0).df
    pd.testing.assert_frame_equal(a, b)


def test_nhl_lambda_sum_independent_of_tilt(mod):
    """Enmienda 1(c).1: mu y L_i de los totales NHL no dependen de tilt_scale."""
    res = _games("nhl")
    f1 = mod.build_frame(res, "nhl", "hockey", {"elo_home_adv": 15.0, "tilt_scale": 0.439},
                         with_outcomes=False, warmup=0)
    f2 = mod.build_frame(res, "nhl", "hockey", {"elo_home_adv": 15.0, "tilt_scale": 0.9},
                         with_outcomes=False, warmup=0)
    assert f1.max_identity_dev is not None and f1.max_identity_dev <= 1e-12
    assert np.max(np.abs(f1.df["mu"].to_numpy() - f2.df["mu"].to_numpy())) <= 1e-12
    assert (f1.df["L"] == f2.df["L"]).all()


def test_x_values_match_hand_computation(mod):
    """Calendario determinista: A gana siempre por 10 (tot 190). En el partido
    final A (local) vs B: forma 1-0, margen +10 vs -10, H2H 100 %."""
    rows = []
    for i in range(8):
        rows.append({"date": f"2015-01-{i + 1:02d}", "home": "A" if i % 2 == 0 else "B",
                     "away": "B" if i % 2 == 0 else "A", "game_id": str(i),
                     "home_score": 100 if i % 2 == 0 else 90, "away_score": 90 if i % 2 == 0 else 100,
                     "neutral": False})
    rows.append({"date": "2015-01-09", "home": "A", "away": "B", "game_id": "8",
                 "home_score": 100, "away_score": 90, "neutral": False})
    fr = mod.build_frame(rows, "nba", "basketball", {"rest_points_per_day": 0.795},
                         with_outcomes=False, warmup=0)
    last = fr.df.iloc[-1]
    assert last["x2"] == pytest.approx(1.0)                   # form_h - form_a = 1 - 0
    assert last["x3"] == pytest.approx(0.5)                   # H2H 100 % - 0,5
    assert last["x9"] == pytest.approx(20.0)                  # +10 - (-10)
    assert last["x4"] == pytest.approx(190.0 - last["L"])     # (190 + 190)/2 - L
    assert last["x8"] == pytest.approx(1.0)                   # A en casa gana siempre, B fuera pierde siempre


def test_x_matches_layer_term_for_each_adjustment(mod):
    """El x del script es el termino de `adjust_model_probability` para coef = 1
    (recorte aparte): se contrasta contra las funciones de produccion."""
    results, lp, fr = _frame(mod, "nba", with_outcomes=True)
    df = fr.df
    pos = len(df) - 5
    r = fr.ordered[int(df["idx"].iloc[pos])]
    home, away, rd = r["home"], r["away"], str(df["date"].iloc[pos])
    risk0 = mod.risk_with()
    prior = mod._prior_games(fr.team_hist, fr.norm(home), fr.norm(away), rd)
    ctx = mod.build_adjustment_context(home, away, rd, prior, risk0, fr.norm)
    if None in (ctx.form_home, ctx.form_away, ctx.margin_home, ctx.margin_away, ctx.form_home_at_home,
                ctx.form_away_at_away, ctx.h2h_home):
        pytest.skip("muestra sintetica sin historia suficiente para este partido")
    assert df["x2"].iloc[pos] == pytest.approx(rest_form_p_adjustment(
        0.5, "h2h", home, home, away, None, None, ctx.form_home, ctx.form_away, 0.0, 1.0))
    assert df["x3"].iloc[pos] == pytest.approx(h2h_p_adjustment("h2h", home, home, away, ctx.h2h_home, 1.0))
    assert df["x8"].iloc[pos] == pytest.approx(home_away_form_p_adjustment(
        "h2h", home, home, away, ctx.form_home_at_home, ctx.form_away_at_away, 1.0))
    assert df["x9"].iloc[pos] == pytest.approx(margin_p_adjustment(
        "h2h", home, home, away, ctx.margin_home, ctx.margin_away, 1.0))


# --------------------------------------------------------------- paridad --
@pytest.mark.parametrize("league", ["nba", "nhl", "nfl", "mlb"])
def test_parity_1_engine_on_synthetic(mod, league):
    results, lp, fr = _frame(mod, league, with_outcomes=True, parity=True)
    info = mod.assert_parity_engine(fr, results, league, mod.FAMILY[league], lp, warmup=0)
    assert max(info["max_desviacion"].values()) <= 1e-12


def test_parity_1_detects_a_broken_base(mod):
    results, lp, fr = _frame(mod, "nhl", with_outcomes=True, parity=True)
    fr.df.loc[fr.df.index[10], "p_h2h"] += 1e-6
    with pytest.raises(SystemExit, match="PARIDAD 1"):
        mod.assert_parity_engine(fr, results, "nhl", "hockey", lp, warmup=0)


@pytest.mark.parametrize("league", ["nba", "nhl", "nfl", "mlb"])
def test_parity_2_and_3_layer_on_synthetic(mod, league):
    """c = 0 -> clip(p_base); c arbitrario (incluido uno enorme que fuerza el
    recorte a [0,01; 0,99]) -> clip(p_base + c*x), con la funcion de produccion."""
    _, _, fr = _frame(mod, league, with_outcomes=True)
    pos = np.arange(len(fr.df))
    zero = mod.assert_parity_layer(fr, pos, {})
    assert zero["max_desviacion"] <= 1e-12
    probe = mod.assert_parity_layer(fr, pos, dict(mod.PROBE_C))
    assert probe["comprobaciones"] == len(pos) * 6 and probe["max_desviacion"] <= 1e-12
    huge = mod.assert_parity_layer(fr, pos, {k: 5.0 for k in mod.ADJ_IDS})
    assert huge["max_desviacion"] <= 1e-12


def test_parity_2_detects_a_broken_layer(mod, monkeypatch):
    _, _, fr = _frame(mod, "nhl", with_outcomes=True)
    real = mod.adjust_model_probability
    monkeypatch.setattr(mod, "adjust_model_probability",
                        lambda *a, **k: min(0.99, real(*a, **k) + 1e-3))
    with pytest.raises(SystemExit, match="PARIDAD 2/3"):
        mod.assert_parity_layer(fr, np.arange(len(fr.df)), {})


# ----------------------------------------------------------- bootstrap / Holm --
def test_bootstrap_reproducible_and_resamples_whole_days(mod):
    rng = np.random.default_rng(3)
    dates = np.repeat(np.array([f"2020-01-{d:02d}" for d in range(1, 21)]), 5)
    num = rng.normal(-0.01, 0.1, len(dates))
    st = {"a": (num, np.ones(len(dates)))}
    r1 = mod.bootstrap_dias(dates, st, n_boot=400, seed=42)
    r2 = mod.bootstrap_dias(dates, st, n_boot=400, seed=42)
    r3 = mod.bootstrap_dias(dates, st, n_boot=400, seed=7)
    assert r1 == r2 and r1 != r3
    assert r1["a"]["n_dias"] == 20 and r1["a"]["n_replicas"] == 400
    # dias completos: con num constante por dia, la replica es una media de medias diarias
    const = {"a": (np.repeat(np.arange(20, dtype=float), 5), np.ones(100))}
    out = mod.bootstrap_dias(dates, const, n_boot=200, seed=1)
    assert 0 <= out["a"]["ic95"][0] <= out["a"]["ic95"][1] <= 19


def test_bootstrap_default_seed_and_replicas(mod):
    assert mod.SEED == 42 and mod.N_BOOT == 10_000


def test_holm_order_stop_and_adjusted(mod):
    out = mod.holm({"a": 0.04, "b": 0.001, "c": 0.01, "d": 0.03}, alpha=0.05)
    assert [out[k]["rango"] for k in ("b", "c", "d", "a")] == [1, 2, 3, 4]
    assert out["b"]["rechaza"] and out["c"]["rechaza"]
    assert not out["d"]["rechaza"]          # 0,03 > 0,05/2 -> 0,025
    assert not out["a"]["rechaza"]          # paro al primer fallo aunque 0,04 <= 0,05
    assert out["b"]["umbral"] == pytest.approx(0.05 / 4)
    assert out["b"]["p_ajustado"] == pytest.approx(0.004)
    assert out["c"]["p_ajustado"] == pytest.approx(0.03)
    assert out["d"]["p_ajustado"] == pytest.approx(0.06)
    assert out["a"]["p_ajustado"] == pytest.approx(0.06)       # monotono


def test_p_value_is_normal_cdf(mod):
    assert mod.p_value(-0.002, 0.001) == pytest.approx(0.0227501, abs=1e-6)
    assert mod.p_value(0.001, 0.001) > 0.5
    assert mod.p_value(None, 0.001) == 1.0 and mod.p_value(-0.002, 0.0) == 1.0


# ----------------------------------------------------- criterios y la celda --
def _res(**kw):
    base = {"ajuste": 9, "c": [0.01, 0.02, 0.01], "delta_afectados": -0.003,
            "delta_por_particion": [-0.002, -0.004, -0.001], "ece_T": 0.01, "ece_base": 0.02,
            "delta_T_menos_C": -0.001, "delta_spread": -0.0005}
    base.update(kw)
    return base


def test_decide_accepts_and_each_criterion_rejects(mod):
    ok = mod.decide(_res(), True)
    assert ok["veredicto"] == "ACEPTA" and all(ok["criterios"].values())
    cases = {
        "1_delta_afectados_menor_igual_margen": dict(delta_afectados=-0.0019),
        "2_delta_negativo_en_cada_particion": dict(delta_por_particion=[-0.002, 0.0, -0.001]),
        "3_ece_T_no_peor_que_base": dict(ece_T=0.03),
        "4_c_positivo_en_todas": dict(c=[0.01, -0.02, 0.01]),
        "5_T_mejor_que_C": dict(delta_T_menos_C=0.0),
        "6_spreads_no_empeoran": dict(delta_spread=0.0001),
    }
    for name, kw in cases.items():
        d = mod.decide(_res(**kw), True)
        assert d["veredicto"] == "RECHAZA" and not d["criterios"][name], name
    assert mod.decide(_res(), False)["veredicto"] == "RECHAZA"
    # el criterio 6 solo aplica a los ajustes 2, 8 y 9
    assert mod.decide(_res(ajuste=4, delta_spread=0.5), True)["veredicto"] == "ACEPTA"
    # margen exacto: -0,002 acepta (<=)
    assert mod.decide(_res(delta_afectados=-0.002), True)["criterios"]["1_delta_afectados_menor_igual_margen"]


def _cell_df(n_per_day: int = 120, n_days: int = 120, signal: float = 0.06, seed: int = 5,
             start: str = "2000-01-01") -> pd.DataFrame:
    """Frame SINTETICO con la forma de la salida de `build_frame`: p_base ruidosa,
    x independiente del modelo y desenlace Bernoulli(p + signal*x)."""
    rng = np.random.default_rng(seed)
    days = pd.date_range(start, periods=n_days, freq="D").strftime("%Y-%m-%d").to_numpy()
    n = n_per_day * n_days
    date = np.repeat(days, n_per_day)
    p = rng.uniform(0.35, 0.65, n)
    x = rng.uniform(-1, 1, n)
    x[rng.random(n) < 0.1] = np.nan                       # sin historia
    x[rng.random(n) < 0.05] = 0.0                         # no afectado
    ptrue = np.clip(p + signal * np.nan_to_num(x), 0.02, 0.98)
    y = (rng.random(n) < ptrue).astype(float)
    margin = np.where(y == 1, 2.0, -2.0)                  # h2h y spread coherentes
    ps = np.clip(p - 0.02, 0.05, 0.95)
    ycov = (rng.random(n) < np.clip(ps + signal * np.nan_to_num(x), 0.02, 0.98)).astype(float)
    margin = np.where(ycov == 1, 3.0, 0.0)
    cols = {"idx": np.arange(n), "date": date, "home": "A", "away": "B", "neutral": False, "mu": 5.0,
            "L": 5.5, "s1": -1.5, "s2": 1.5, "y_h2h": y, "p_h2h": p, "margin": margin,
            "total": np.where(rng.random(n) < 0.5, 7.0, 4.0), "p_over": p, "p_s1": ps, "p_s2": ps}
    for k in (2, 3, 4, 8, 9, 10, 6, 7):
        cols[f"x{k}"] = x
    return pd.DataFrame(cols)


_FOLDS3 = {"A": {"train_end": "2000-01-30", "test_start": "2000-01-31", "test_end": "2000-02-29"},
           "B": {"train_end": "2000-02-29", "test_start": "2000-03-01", "test_end": "2000-03-31"},
           "C": {"train_end": "2000-03-31", "test_start": "2000-04-01", "test_end": "2000-04-30"}}


def test_evaluate_cell_recovers_signal_and_c_is_positive(mod):
    L = mod.LeagueData(_cell_df(signal=0.1), "nhl", _FOLDS3)
    res = mod.evaluate_cell(L, 9)
    assert all(c > 0 for c in res["c"]) and 0.04 < np.mean(res["c"]) < 0.16
    assert res["delta_afectados"] < -0.002 and all(d < 0 for d in res["delta_por_particion"])
    assert res["delta_T_menos_C"] < 0
    assert res["n_afectados"] < res["n_test"]            # NaN y ceros no son afectados
    assert res["delta_spread"] is not None and res["delta_spread"] < 0
    assert len(res["delta_spread_por_linea"]) == 2
    assert res["delta_spread"] == pytest.approx(np.mean(res["delta_spread_por_linea"]), rel=1e-9)


def test_evaluate_cell_without_signal_does_not_improve(mod):
    L = mod.LeagueData(_cell_df(signal=0.0), "nhl", _FOLDS3)
    res = mod.evaluate_cell(L, 2)
    assert abs(res["delta_afectados"]) < 0.002
    assert mod.decide(res, True)["veredicto"] == "RECHAZA"


def test_run_league_cells_end_to_end_with_small_bootstrap(mod, monkeypatch):
    monkeypatch.setattr(mod, "N_BOOT", 200)
    orig = mod.bootstrap_dias
    monkeypatch.setattr(mod, "bootstrap_dias", lambda d, s, n_boot=200, seed=42, chunk=250: orig(d, s, n_boot, seed, chunk))
    L = mod.LeagueData(_cell_df(signal=0.1), "nhl", _FOLDS3)
    cells = mod.run_league_cells(L)
    assert set(cells) == set(mod.ADJ_IDS)
    c9 = cells[9]
    assert c9["se_delta"] > 0 and c9["p"] < 0.01
    assert set(c9["bootstrap"]) == {"delta_afectados", "T_menos_C", "delta_spread"}
    assert "delta_spread" not in cells[4]["bootstrap"]      # criterio 6 solo en 2, 8, 9
    # secundarios sobre los mismos datos
    assert mod._tercile_report(c9["_w"], c9["_w"]["x_raw"])["x_positivo"]["n"] > 0
    assert mod._profile_grid(L, 9, 0.05)["particiones"]["A"]["argmin_c"] is not None
    assert "a" in mod._joint_report(L, 9)["A"]
    assert mod._bias_report(L)["h2h"]["A"]["n"] > 0
    assert mod._coverage_report(L)["adj9"]["none_por_falta_de_historia"] > 0


def test_totals_cell_uses_over_outcome_and_excludes_pushes(mod):
    df = _cell_df()
    df["total"] = df["L"]            # todos empujan: ninguna fila valida
    L = mod.LeagueData(df, "nhl", _FOLDS3)
    p, y, valid = L.decision(4)
    assert not valid.any()
    df2 = _cell_df()
    df2["total"] = 7.0
    p, y, valid = mod.LeagueData(df2, "nhl", _FOLDS3).decision(4)
    assert valid.all() and (y == 1.0).all()


# --------------------------------------------------------------- abortos --
def test_abort_when_optimizer_does_not_converge(mod, monkeypatch):
    class _Res:
        success = False
        message = "maxiter"
        x = np.array([0.0])

    monkeypatch.setattr(mod, "minimize", lambda *a, **k: _Res())
    with pytest.raises(SystemExit, match="NO CONVERGIO"):
        mod.fit_c(np.full(10, 0.5), np.ones(10), np.ones(10))
    with pytest.raises(SystemExit, match="NO CONVERGIO"):
        mod.fit_a(np.full(10, 0.5), np.ones(10))


def test_optimizer_settings_are_preregistered(mod):
    assert mod.NM_OPTS == {"xatol": 1e-7, "fatol": 1e-10, "maxiter": 2000}


def _pre(**kw):
    base = {"git_head": "abc", "manifiesto": {"data/historical/results_nba.csv": {"sha256": "h1", "filas": 5}},
            "config_sha256": {"configs/default.yaml": "c1"}, "parametros_resueltos": {"nba": {"x": 1}}}
    base.update(kw)
    return base


def test_abort_on_different_head(mod):
    pre = _pre()
    mod._check_pre_provenance(pre, "abc", pre["manifiesto"], pre["config_sha256"], pre["parametros_resueltos"])
    with pytest.raises(SystemExit, match="HEAD"):
        mod._check_pre_provenance(pre, "def", pre["manifiesto"], pre["config_sha256"], pre["parametros_resueltos"])
    with pytest.raises(SystemExit):
        mod._check_pre_provenance(pre, None, pre["manifiesto"], pre["config_sha256"], pre["parametros_resueltos"])


def test_abort_on_different_hash_or_config_or_params(mod):
    pre = _pre()
    changed = {"data/historical/results_nba.csv": {"sha256": "h2", "filas": 5}}
    with pytest.raises(SystemExit, match="HASH DE ENTRADA"):
        mod._check_pre_provenance(pre, "abc", changed, pre["config_sha256"], pre["parametros_resueltos"])
    rows = {"data/historical/results_nba.csv": {"sha256": "h1", "filas": 6}}
    with pytest.raises(SystemExit, match="HASH DE ENTRADA"):
        mod._check_pre_provenance(pre, "abc", rows, pre["config_sha256"], pre["parametros_resueltos"])
    with pytest.raises(SystemExit, match="ratings.yaml"):
        mod._check_pre_provenance(pre, "abc", pre["manifiesto"], {"configs/default.yaml": "c2"},
                                  pre["parametros_resueltos"])
    with pytest.raises(SystemExit, match="Parametros"):
        mod._check_pre_provenance(pre, "abc", pre["manifiesto"], pre["config_sha256"], {"nba": {"x": 2}})
    with pytest.raises(SystemExit, match="conjunto de ficheros"):
        mod._check_pre_provenance(pre, "abc", {}, pre["config_sha256"], pre["parametros_resueltos"])


def test_abort_on_dirty_porcelain(mod):
    mod.check_git_clean("", "x")
    with pytest.raises(SystemExit, match="NO esta vacio"):
        mod.check_git_clean(" M src/sqp/x.py\n", "x")
    with pytest.raises(SystemExit):
        mod.check_git_clean(None, "x")


def test_full_mode_aborts_before_measuring_when_tree_dirty(mod, monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "git_status_porcelain", lambda cwd, paths=None: " M configs/default.yaml\n")
    monkeypatch.setattr(mod, "run_full", lambda root: pytest.fail("no debe medir con el arbol sucio"))
    pre_json = tmp_path / "pre.json"
    pre_json.write_text(json.dumps(_pre()), encoding="utf-8")
    with pytest.raises(SystemExit, match="NO esta vacio"):
        mod.main(["--data-root", str(tmp_path), "--pre-json", str(pre_json), "--out", str(tmp_path / "o.json")])


def test_pre_mode_aborts_on_dirty_repo(mod, monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "git_head", lambda cwd: "abc")
    monkeypatch.setattr(mod, "git_status_porcelain", lambda cwd, paths=None: "?? algo\n")
    with pytest.raises(SystemExit, match="NO esta vacio"):
        mod.main(["--pre", "--data-root", str(tmp_path), "--out", str(tmp_path / "o.json")])


def test_cli_argument_validation(mod, tmp_path):
    with pytest.raises(SystemExit):
        mod.main(["--pre", "--parity-only", "--out", str(tmp_path / "o")])
    with pytest.raises(SystemExit):
        mod.main(["--data-root", str(tmp_path), "--out", str(tmp_path / "o")])          # falta --pre-json
    with pytest.raises(SystemExit):
        mod.main(["--leagues", "nba", "--data-root", str(tmp_path), "--out", str(tmp_path / "o")])


# -------------------------------------------------------------------- --pre --
def test_pre_league_computes_no_loss_and_pairs_no_features_with_outcomes(mod, monkeypatch, tmp_path):
    """`--pre` no puede calcular ninguna perdida ni estimar nada: las funciones
    de perdida, el optimizador, el bootstrap, ECE y `adapter.estimate` explotan."""
    hist = tmp_path / "data" / "historical"
    hist.mkdir(parents=True)
    pd.DataFrame(_games("nhl", n_days=120, start="2014-09-01")).assign(ingested_at="x").to_csv(
        hist / "results_nhl.csv", index=False)
    monkeypatch.setattr(mod, "_league_meta", lambda lg: {"family": "hockey", "league_params":
                                                         dict(mod.EXPECTED_LEAGUE_PARAMS["nhl"])})

    def boom(*a, **k):
        raise AssertionError("--pre no debe calcular perdidas ni estimar")

    for name in ("ll_vec", "fit", "minimize", "bootstrap_dias", "expected_calibration_error",
                 "walk_forward_backtest", "evaluate_cell", "decide"):
        monkeypatch.setattr(mod, name, boom)
    from sqp.sports.adapters import PoissonAdapter
    monkeypatch.setattr(PoissonAdapter, "estimate", boom)
    out = mod.pre_league("nhl", tmp_path)
    assert set(out["test_combinado"]) == {f"adj{k}" for k in mod.ADJ_IDS}
    assert out["procedencia"]["filas_leidas"] == 360 and len(out["procedencia"]["sha256"]) == 64
    assert out["nhl_identidad_lambda_max_desviacion"] <= 1e-12
    assert set(out["correlaciones"]) == set(mod.CORR_NAMES)
    assert out["identidades"]["max_abs_x4_menos_x7"] <= 1e-12


def test_pre_identities_x6_and_x7(mod):
    """Secciones 2.3 y 2.4: x7 == x4 y x6 == x9/2 con las ventanas vigentes (10)."""
    _, _, fr = _frame(mod, "nba", with_outcomes=False)
    df = fr.df.dropna(subset=["x4", "x7"])
    assert len(df) > 0 and np.max(np.abs(df["x4"] - df["x7"])) <= 1e-12
    df = fr.df.dropna(subset=["x9", "x6"])
    assert len(df) > 0 and np.max(np.abs(df["x9"] / 2 - df["x6"])) <= 1e-12


def test_manifest_hashes_files_and_marks_missing(mod, tmp_path):
    hist = tmp_path / "data" / "historical"
    hist.mkdir(parents=True)
    (hist / "results_nba.csv").write_text("date,home\n2020-01-01,A\n2020-01-02,B\n", encoding="utf-8")
    m = mod.input_manifest(tmp_path)
    e = m["data/historical/results_nba.csv"]
    assert e["filas"] == 2 and len(e["sha256"]) == 64
    assert m["data/historical/results_nhl.csv"] == {"sha256": None, "filas": None}


def test_battery_never_computes_old_tilt_base(mod):
    """Enmienda 1(b): sin base alternativa. El script no contiene el literal 0.9
    de tilt ni reutiliza `measure_tilt_nhl.load_league`."""
    src = SCRIPT.read_text(encoding="utf-8")
    assert "import measure_tilt_nhl" not in src and "from measure_tilt_nhl" not in src
    assert '"tilt_scale": 0.9' not in src and "tilt_scale=0.9" not in src
    assert mod.EXPECTED_LEAGUE_PARAMS["nhl"]["tilt_scale"] == 0.439


def test_windows_are_the_configured_ones(mod):
    assert mod.risk_windows() == mod.WINDOW_DEFAULTS
    r = mod.risk_with(margin_coef=0.01)
    assert r.margin_coef == 0.01 and r.recent_form_coef == 0.0 and r.h2h_coef == 0.0
    assert (r.recent_form_n, r.h2h_n, r.totals_tendency_n, r.home_away_form_n, r.margin_n,
            r.over_under_rate_n) == (5, 10, 10, 5, 10, 10)


def test_clean_drops_working_keys_and_nan(mod):
    d = mod._clean({"a": float("nan"), "_w": np.arange(3), "b": np.float64(1.5), "c": [np.int64(2)]})
    assert d == {"a": None, "b": 1.5, "c": [2]}
    json.dumps(d)
    assert math.isfinite(0.0)


def test_feature_stride_marks_rows_and_layer_parity_holds_on_them(mod):
    results = _games("nhl")
    lp = mod.EXPECTED_LEAGUE_PARAMS["nhl"]
    fr = mod.build_frame(results, "nhl", "hockey", lp, with_outcomes=True, feature_stride=4, warmup=0)
    feat = fr.df["feat"].to_numpy(bool)
    assert feat.sum() == math.ceil(len(fr.df) / 4) and not fr.df.loc[~feat, "x9"].notna().any()
    info = mod.assert_parity_layer(fr, np.flatnonzero(feat), dict(mod.PROBE_C))
    assert info["partidos"] == feat.sum() and info["max_desviacion"] <= 1e-12


def test_parity_only_end_to_end_on_synthetic_root(mod, monkeypatch, tmp_path):
    """`--parity-only` completo (paridad 1, 2 y 3) sobre una raiz de datos
    SINTETICA y una `_league_meta` fijada; no toca los historicos reales."""
    hist = tmp_path / "data" / "historical"
    hist.mkdir(parents=True)
    pd.DataFrame(_games("nhl", n_days=150, start="2014-09-01")).assign(ingested_at="x").to_csv(
        hist / "results_nhl.csv", index=False)
    monkeypatch.setattr(mod, "_league_meta", lambda lg: {"family": "hockey", "league_params":
                                                         dict(mod.EXPECTED_LEAGUE_PARAMS["nhl"])})
    out = mod.parity_only(tmp_path, ("nhl",), stride=1)
    r = out["ligas"]["nhl"]
    assert r["resultado"] == "PARIDAD OK" and r["partidos_test"] > 0
    assert max(r["paridad1"]["max_desviacion"].values()) <= 1e-12
    assert r["paridad2_y_3_c_arbitrario_y_c0"]["comprobaciones_c0"] == 3 * r["partidos_test"]


def _synthetic_root(mod, tmp_path, monkeypatch):
    hist = tmp_path / "data" / "historical"
    hist.mkdir(parents=True)
    for lg in mod.LEAGUES:
        pd.DataFrame(_games(lg, n_days=150, start="2014-09-01")).assign(ingested_at="x").to_csv(
            hist / f"results_{lg}.csv", index=False)
    for lg, kind in (("wnba", "nba"), ("ncaab", "nba"), ("wncaab", "nba"), ("ncaaf", "nfl")):
        pd.DataFrame(_games(kind, n_days=150, start="2014-09-01", seed=3)).assign(ingested_at="x").to_csv(
            hist / f"results_{lg}.csv", index=False)
    fam = dict(mod.FAMILY, wnba="basketball", ncaab="basketball", wncaab="basketball", ncaaf="football")
    monkeypatch.setattr(mod, "TRANSFER_EVAL_FROM", {"wnba": "2014-12-01"})
    monkeypatch.setattr(mod, "_league_meta", lambda lg: {
        "family": fam.get(lg, "basketball"),
        "league_params": (dict(mod.EXPECTED_LEAGUE_PARAMS[lg]) if mod.EXPECTED_LEAGUE_PARAMS.get(lg) else None)})
    folds = {"A": {"train_end": "2014-12-15", "test_start": "2014-12-16", "test_end": "2015-01-05"},
             "B": {"train_end": "2015-01-05", "test_start": "2015-01-06", "test_end": "2015-01-31"}}
    monkeypatch.setattr(mod, "FOLDS", {lg: folds for lg in mod.LEAGUES})
    orig = mod.bootstrap_dias
    monkeypatch.setattr(mod, "bootstrap_dias",
                        lambda d, s, n_boot=60, seed=42, chunk=250: orig(d, s, n_boot, seed, chunk))


def test_run_full_end_to_end_on_synthetic_data(mod, monkeypatch, tmp_path):
    """Recorrido COMPLETO (paridades, 24 celdas, bootstrap, Holm, criterios e
    informes secundarios) sobre datos SINTETICOS y particiones sinteticas. No es
    la medicion: es la prueba de que el cableado no revienta y es serializable."""
    _synthetic_root(mod, tmp_path, monkeypatch)
    real_cap = mod.captured_lines

    def cap(results, league, root):
        if league == "nfl":
            raise ValueError("cuotas rotas (sintetico)")
        return real_cap(results, league, root)

    monkeypatch.setattr(mod, "captured_lines", cap)
    out = mod.run_full(tmp_path)
    # cambio 2: el error de captured_lines se conserva (tipo + traceback), no n=0 aparente
    e7 = out["secundarios"]["nfl"]["7_linea_capturada"]
    assert e7["tipo"] == "ValueError" and "cuotas rotas" in e7["error"] and "Traceback" in e7["traceback"]
    assert "error" not in out["secundarios"]["nba"]["7_linea_capturada"]
    # cambio 1 y 11a: futbol retirado; informe 9 de punta a punta en las cuatro secundarias
    assert out["secundarios"]["9_futbol_agrupado"] == {"retirado": "Enmienda 2 (2026-10-08)"}
    tr = out["secundarios"]["9_transferencia"]
    assert set(tr) == {"wnba", "ncaab", "wncaab", "ncaaf"}
    for name, rep9 in tr.items():
        assert "error" not in rep9, (name, rep9)
        assert rep9["evaluados"] > 0 and set(f"adj{a}" for a in mod.ADJ_IDS) <= set(rep9)
    assert tr["wnba"]["evaluar_desde"] == "2014-12-01" and tr["ncaab"]["evaluar_desde"] == "0000-00-00"
    assert tr["wnba"]["evaluados"] < tr["ncaab"]["evaluados"]          # WNBA recortada por fecha
    # cambio 7: informe 8 con frame alternativo
    h8 = out["secundarios"]["nba"]["8_ajuste4_vs_adaptador"]
    assert h8["aplica"] and h8["n_afectados_adj4"] > 0 and h8["delta_con_menos_sin_half_life_test"] is not None
    assert len(out["holm"]) == 24 and len(out["veredictos"]) == 24
    assert set(out["veredictos"].values()) <= {"ACEPTA", "RECHAZA"}
    for lg in mod.LEAGUES:
        assert out["paridad"][lg]["motor"]["n_h2h"] > 0
        assert out["paridad"][lg]["capa_c_ultima_particion_y_c0"]["max_desviacion"] <= 1e-12
        for adj in mod.ADJ_IDS:
            cell = out["ligas"][lg][str(adj)]
            assert set(cell["decision"]["criterios"]) == {
                "1_delta_afectados_menor_igual_margen", "2_delta_negativo_en_cada_particion",
                "3_ece_T_no_peor_que_base", "4_c_positivo_en_todas", "5_T_mejor_que_C",
                "6_spreads_no_empeoran", "7_holm_rechaza"}
    sec = out["secundarios"]
    for lg in mod.LEAGUES:
        if lg == "nfl":
            continue
        for name in ("1_bias_base", "2_estimacion_conjunta", "3_perfil_rejilla_c", "4_terciles_y_signo",
                     "5_por_temporada", "6_colinealidad", "7_linea_capturada", "8_ajuste4_vs_adaptador",
                     "10_cobertura"):
            val = sec[lg][name]
            assert not (isinstance(val, dict) and "error" in val), (lg, name, val)
    assert "error" not in sec["nfl"]["10_cobertura"] and sec["nfl"]["10_cobertura"]["exhibicion"] == \
        "no disponible en ResultsStore"
    assert sec["nba"]["8_ajuste4_vs_adaptador"]["aplica"] is True
    assert sec["nhl"]["8_ajuste4_vs_adaptador"]["aplica"] is False
    json.dumps(mod._clean(out))


def test_main_pre_then_full_and_abort_on_changed_input(mod, monkeypatch, tmp_path):
    """`--pre` -> `--pre-json` -> modo completo sobre datos SINTETICOS: el modo
    completo acepta su `--pre`, y aborta si despues cambia un fichero de entrada."""
    _synthetic_root(mod, tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "git_head", lambda cwd: "deadbeef")
    monkeypatch.setattr(mod, "git_status_porcelain", lambda cwd, paths=None: "")
    pre_path, out_path = tmp_path / "pre.json", tmp_path / "res.json"
    monkeypatch.setattr(mod, "captured_lines", lambda results, league, root: {})
    assert mod.main(["--pre", "--data-root", str(tmp_path), "--out", str(pre_path)]) == 0
    pre = json.loads(pre_path.read_text(encoding="utf-8"))
    assert pre["git_head"] == "deadbeef" and pre["git_status_porcelain"] == ""
    assert set(pre["ligas"]) == set(mod.LEAGUES) and "ventanas" in pre and pre["config_sha256"]
    assert pre["parametros_resueltos"]["nhl"]["league_params"] == {"elo_home_adv": 15.0, "tilt_scale": 0.439}
    assert mod.main(["--data-root", str(tmp_path), "--pre-json", str(pre_path), "--out", str(out_path)]) == 0
    res = json.loads(out_path.read_text(encoding="utf-8"))
    assert res["modo"] == "completo" and res["git_head"] == "deadbeef" and len(res["veredictos"]) == 24
    # cambio 3: el JSON completo registra la procedencia
    assert res["parametros_resueltos"] == pre["parametros_resueltos"] and res["manifiesto"] == pre["manifiesto"]
    assert res["config_sha256"] == pre["config_sha256"]
    assert res["git_status_porcelain_src_configs_scripts_research"] == ""
    assert res["pre_json_sha256"] == mod.sha256_of(pre_path)
    assert pre["ligas"]["nhl"]["ingesta"]["A"]["filas"] > 0
    f = tmp_path / "data" / "historical" / "results_nfl.csv"
    f.write_text(f.read_text(encoding="utf-8") + "2014-09-05,A,B,zz,1,0,False,x\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="HASH DE ENTRADA"):
        mod.main(["--data-root", str(tmp_path), "--pre-json", str(pre_path), "--out", str(out_path)])
    monkeypatch.setattr(mod, "git_head", lambda cwd: "other")
    with pytest.raises(SystemExit, match="HEAD DE GIT CAMBIO"):
        mod.main(["--data-root", str(tmp_path), "--pre-json", str(pre_path), "--out", str(out_path)])


def test_data_root_required_and_live_tree_rejected(mod, monkeypatch, tmp_path):
    """Cambio 4: --pre y el modo completo exigen --data-root explicito y abortan si es el arbol vivo."""
    monkeypatch.setattr(mod, "git_status_porcelain", lambda cwd, paths=None: "")
    with pytest.raises(SystemExit):
        mod.main(["--pre", "--out", str(tmp_path / "o.json")])
    with pytest.raises(SystemExit):
        mod.main(["--pre-json", str(tmp_path / "p.json"), "--out", str(tmp_path / "o.json")])
    with pytest.raises(SystemExit, match="arbol vivo"):
        mod.main(["--pre", "--data-root", str(mod.DEFAULT_ROOT), "--out", str(tmp_path / "o.json")])
    with pytest.raises(SystemExit, match="arbol vivo"):
        mod.main(["--data-root", str(mod.DEFAULT_ROOT / "."), "--pre-json", str(tmp_path / "p.json"),
                  "--out", str(tmp_path / "o.json")])
    # Enmienda 1(g): la instantanea debe quedar FUERA de data/ (ignorado por git, el porcelain no lo ve)
    inside = mod.DEFAULT_ROOT / "data" / "snapshot_bateria"
    with pytest.raises(SystemExit, match="dentro de data"):
        mod.main(["--pre", "--data-root", str(inside), "--out", str(tmp_path / "o.json")])
    with pytest.raises(SystemExit, match="dentro de data"):
        mod.main(["--data-root", str(inside), "--pre-json", str(tmp_path / "p.json"),
                  "--out", str(tmp_path / "o.json")])


def test_captured_lines_uses_roi_engine_sort_key_on_doubleheader(mod, monkeypatch, tmp_path):
    """Hallazgo 1 (ronda 2): en una doble jornada (mismo dia, mismos equipos) el consumo de
    `used` depende del orden; captured_lines debe recorrer los resultados con la clave de
    roi_engine.backtest_league (date, home, away, game_id, home_score, away_score), no solo
    por fecha. Datos SINTETICOS."""
    seen: list[str] = []
    monkeypatch.setattr(mod, "load_closing_odds", lambda root, league: ["sentinela"])
    monkeypatch.setattr(mod, "get_team_normalizer", lambda league: (lambda s: s))
    monkeypatch.setattr(mod, "_match_index", lambda odds, order_insensitive, norm: {})
    monkeypatch.setattr(mod, "_match_result",
                        lambda r, idx, used, order_insensitive, norm: seen.append(r["game_id"]))
    rows = [{"date": "2025-06-01", "home": "NYY", "away": "BOS", "game_id": "g2", "home_score": 3, "away_score": 1},
            {"date": "2025-06-01", "home": "NYY", "away": "BOS", "game_id": "g1", "home_score": 5, "away_score": 2},
            {"date": "2025-05-31", "home": "TOR", "away": "BAL", "game_id": "g0", "home_score": 1, "away_score": 0}]
    assert mod.captured_lines(rows, "mlb", tmp_path) == {}
    key = lambda r: (str(r.get("date", "")), str(r.get("home", "")), str(r.get("away", "")),  # noqa: E731
                     str(r.get("game_id", "")), str(r.get("home_score", "")), str(r.get("away_score", "")))
    assert seen == [r["game_id"] for r in sorted(rows, key=key)] == ["g0", "g1", "g2"]


def test_parity_only_may_default_to_live_tree(mod, monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(mod, "parity_only", lambda root, leagues, stride=1: seen.update(root=root) or {"ligas": {}})
    assert mod.main(["--parity-only"]) == 0
    assert seen["root"] == mod.DEFAULT_ROOT


def test_ingestion_report_counts_only(mod, tmp_path):
    """Cambio 5: recuentos de ingested_at > 2026-09-27 y duplicados; nunca marcadores."""
    hist = tmp_path / "data" / "historical"
    hist.mkdir(parents=True)
    rows = [("2020-01-01", "A", "B", "1", "2026-09-28T00:00:00"), ("2020-01-02", "A", "B", "2", "2026-09-27T23:00:00"),
            ("2020-01-02", "A", "B", "3", "2026-10-01T00:00:00"), ("2020-01-03", "C", "D", "3", "2020-01-04"),
            ("2027-01-01", "C", "D", "9", "2026-10-01")]            # fuera del corte
    pd.DataFrame(rows, columns=["date", "home", "away", "game_id", "ingested_at"]).assign(
        home_score=1, away_score=0).to_csv(hist / "results_nhl.csv", index=False)
    folds = {"A": {"train_end": "2019-12-31", "test_start": "2020-01-01", "test_end": "2020-01-31"}}
    rep = mod.ingestion_report("nhl", tmp_path, folds)
    a = rep["A"]
    assert rep["ingested_at"] == "disponible" and a["filas"] == 4
    assert a["ingestadas_despues_2026_09_27"] == 2
    assert a["ingestadas_el_2026_09_27"] == 1        # las del propio 27 se informan aparte (ambiguas)
    assert a["duplicados_date_home_away"] == 1 and a["duplicados_game_id"] == 1
    assert "home_score" not in json.dumps(rep)
    pd.DataFrame(rows, columns=["date", "home", "away", "game_id", "ingested_at"]).drop(columns="ingested_at").to_csv(
        hist / "results_nhl.csv", index=False)
    rep2 = mod.ingestion_report("nhl", tmp_path, folds)
    assert rep2["ingested_at"] == "no disponible" and rep2["A"]["ingestadas_despues_2026_09_27"] == "no disponible"
    assert rep2["A"]["ingestadas_el_2026_09_27"] == "no disponible"


def test_safe_informe_keeps_traceback(mod):
    out = mod._safe_informe("x", lambda: 1 / 0)
    assert out["tipo"] == "ZeroDivisionError" and "Traceback" in out["traceback"] and mod._is_error(out)
    assert mod._safe_informe("y", lambda: {"ok": 1}) == {"ok": 1}


def test_joint_report_records_non_convergence_per_fold(mod, monkeypatch):
    L = mod.LeagueData(_cell_df(), "nhl", _FOLDS3)
    calls = {"n": 0}
    real = mod.fit_ac

    def flaky(p, x, y):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("no convergio (sintetico)")
        return real(p, x, y)

    monkeypatch.setattr(mod, "fit_ac", flaky)
    out = mod._joint_report(L, 9)
    assert "no_converge" in out["B"] and "c_con_intercepto_controlado" in out["A"] and "c_con_intercepto_controlado" in out["C"]


def test_ll_vec_equals_binary_nll_series(mod):
    from sqp.backtesting.tuning import _binary_nll_series
    rng = np.random.default_rng(0)
    p = np.concatenate([rng.uniform(0, 1, 500), [0.0, 1.0, 1e-15]])
    y = (rng.random(len(p)) < 0.5).astype(float)
    assert np.allclose(mod.ll_vec(p, y), _binary_nll_series(list(p), list(y)), rtol=0, atol=1e-12)


def test_mlb_folds_and_cutoff_are_the_preregistered_ones(mod):
    f = mod.FOLDS["mlb"]
    assert f["A"] == {"train_end": "2024-12-31", "test_start": "2025-01-01", "test_end": "2025-12-31"}
    assert f["B"] == {"train_end": "2025-12-31", "test_start": "2026-01-01", "test_end": "2026-09-26"}
    assert mod.CUTOFF == "2026-09-26"
    dates = np.array(["2024-12-31", "2025-01-01", "2025-12-31", "2026-01-01", "2026-09-26", "2026-09-27"])
    assert list(mod.fold_index(dates, f)) == [-1, 0, 0, 1, 1, -1]


def test_nfl_ties_leave_h2h_but_stay_in_spreads(mod):
    results = _games("nfl")
    results[40]["home_score"] = results[40]["away_score"] = 20           # empate
    lp = mod.EXPECTED_LEAGUE_PARAMS["nfl"]
    fr = mod.build_frame(results, "nfl", "football", lp, with_outcomes=True, warmup=0)
    ordered_pos = int(np.flatnonzero(fr.df["margin"].to_numpy() == 0)[0])
    L = mod.LeagueData(fr.df, "nfl", {"A": {"train_end": "2014-09-30", "test_start": "2014-10-01",
                                           "test_end": "2015-12-31"}})
    _, _, valid_h2h = L.decision(2)
    assert not valid_h2h[ordered_pos]
    (p, y, valid_s), = L.spread_lines()
    assert valid_s[ordered_pos]
    _, _, valid_t = L.decision(4)
    assert valid_t[ordered_pos]
