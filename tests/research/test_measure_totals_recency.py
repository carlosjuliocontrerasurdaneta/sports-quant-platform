"""Pruebas SINTETICAS de `scripts/research/measure_totals_recency.py` (pre-registro
`docs/research/2026-10-09-preregistro-recencia-totales.md`).

Ninguna prueba lee los historicos reales (`data/historical/`), ni ejecuta `--pre`,
`--fase H` o `--fase M` contra ellos: eso es la medicion en si. Todo se ejercita con
partidos SINTETICOS pequenos (equipos A..F, marcadores aleatorios con semilla fija)
y raices de datos temporales. Los metadatos de liga se fijan con `monkeypatch`.
"""
from __future__ import annotations

import importlib.util
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.optimize import minimize
from scipy.stats import norm

from sqp.config import ROOT
from sqp.models import distributions as dist
from sqp.sports.registry import get_adapter

SCRIPT = ROOT / "scripts" / "research" / "measure_totals_recency.py"
TEAMS = ("A", "B", "C", "D", "E", "F")


def _load_module():
    spec = importlib.util.spec_from_file_location("measure_totals_recency", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_module()


def _games(kind: str, n_days: int = 100, start: str = "2014-09-01", per_day: int = 3, seed: int = 11,
           drift: float = 0.0) -> list[dict]:
    """Partidos SINTETICOS. `drift` desplaza el nivel de anotacion a lo largo del tiempo."""
    rng = np.random.default_rng(seed)
    rows, gid = [], 0
    for k, d in enumerate(pd.date_range(start, periods=n_days, freq="D")):
        order = list(rng.permutation(TEAMS))
        for j in range(per_day):
            h, a = order[2 * j], order[2 * j + 1]
            lvl = drift * k
            if kind == "nba":
                hs, aws = int(rng.normal(112 + lvl, 12)), int(rng.normal(108 + lvl, 12))
            elif kind == "nfl":
                hs, aws = int(rng.normal(24 + lvl / 10, 8)), int(rng.normal(21 + lvl / 10, 8))
            else:
                hs, aws = int(rng.poisson(3.1 + lvl / 40)), int(rng.poisson(2.9 + lvl / 40))
            rows.append({"date": d.strftime("%Y-%m-%d"), "home": h, "away": a, "game_id": str(gid),
                         "home_score": hs, "away_score": aws, "neutral": False})
            gid += 1
    return rows


SYN_FOLDS = {"A": {"train_end": "2014-10-31", "test_start": "2014-11-01", "test_end": "2014-11-15"},
             "B": {"train_end": "2014-11-15", "test_start": "2014-11-16", "test_end": "2014-11-30"},
             "C": {"train_end": "2014-11-30", "test_start": "2014-12-01", "test_end": "2014-12-31"}}


def _expected_lp(mod, lg):
    return dict(mod.bat.EXPECTED_LEAGUE_PARAMS[lg]) if mod.bat.EXPECTED_LEAGUE_PARAMS[lg] else None


def _patch_meta(mod, monkeypatch):
    monkeypatch.setattr(mod, "_league_meta", lambda lg: {"family": mod.FAMILY[lg], "league_params": _expected_lp(mod, lg)})
    monkeypatch.setattr(mod, "FOLDS", {lg: SYN_FOLDS for lg in mod.LEAGUES})
    monkeypatch.setattr(mod, "DOC_TABLE_9_1", {lg: {} for lg in mod.LEAGUES})   # la tabla real no aplica a datos sinteticos


def _write_root(tmp_path, n_days: int = 100, drift: float = 0.0):
    hist = tmp_path / "data" / "historical"
    hist.mkdir(parents=True, exist_ok=True)
    for lg in ("nba", "nfl", "nhl"):
        pd.DataFrame(_games(lg, n_days=n_days, start="2014-09-01", drift=drift)).assign(ingested_at="x").to_csv(
            hist / f"results_{lg}.csv", index=False)
    return tmp_path


@pytest.fixture()
def runs(mod, monkeypatch, tmp_path):
    _patch_meta(mod, monkeypatch)
    root = _write_root(tmp_path)
    return {lg: mod.LeagueRun(lg, root) for lg in mod.LEAGUES}


# ------------------------------------------------------------ rejilla y reglas --
def test_grid_is_the_preregistered_eleven_values(mod):
    assert mod.GRID == (0.0, 30.0, 45.0, 60.0, 90.0, 120.0, 180.0, 270.0, 365.0, 540.0, 730.0)
    mod.assert_vigente_matches_params()      # 180 / 0 / 0 contra los parametros resueltos reales
    assert mod.H_VIGENTE == {"nba": 180.0, "nfl": 0.0, "nhl": 0.0}
    assert mod.K_HOLM == 3 and mod.N_BOOT == 10_000 and mod.SEED == 42 and mod.H1_MARGIN == 0.002
    assert mod.TOL == 1e-12 and mod.M_MIN_N == {"nba": 800, "nhl": 800, "nfl": 250}
    assert (mod.M_CUTOFF, mod.M_CUTOFF_EXT, mod.MARKET_START) == ("2027-01-31", "2027-04-20", "2026-03-01")


def test_select_h_argmin_and_tie_rules(mod):
    prof = {0.0: 0.9, 30.0: 0.8, 90.0: 0.7, 180.0: 0.75}
    assert mod.select_h(prof, 180.0) == 90.0
    # empate exacto: el mas cercano al vigente
    assert mod.select_h({0.0: 0.5, 90.0: 0.5, 365.0: 0.5, 30.0: 0.9}, 180.0) == 90.0
    assert mod.select_h({0.0: 0.5, 90.0: 0.5, 365.0: 0.5}, 0.0) == 0.0
    # persiste el empate (equidistantes del vigente): el mayor
    assert mod.select_h({60.0: 0.5, 120.0: 0.5, 30.0: 0.6}, 90.0) == 120.0
    with pytest.raises(SystemExit):
        mod.select_h({0.0: float("nan"), 30.0: 0.5}, 0.0)
    with pytest.raises(SystemExit):
        mod.select_h({}, 0.0)


def test_candidate_params_is_league_params_union_h_and_keeps_tilt(mod):
    lp = {"elo_home_adv": 15.0, "tilt_scale": 0.439}
    cand = mod.candidate_params(lp, 90.0)
    assert cand == {"elo_home_adv": 15.0, "tilt_scale": 0.439, mod.HALF_LIFE_KEY: 90.0} and lp == {
        "elo_home_adv": 15.0, "tilt_scale": 0.439}
    ad = get_adapter("nhl", "hockey", cand)
    assert ad.params["tilt_scale"] == 0.439 and ad.params[mod.HALF_LIFE_KEY] == 90.0
    # NBA con h = 0 reemplaza el 180 de LEAGUE_OVERRIDES
    assert get_adapter("nba", "basketball", mod.candidate_params({"rest_points_per_day": 0.795}, 0.0)).params[
        mod.HALF_LIFE_KEY] == 0.0


# ------------------------------------------------------------- distribuciones --
def test_normal_nll_equals_minus_logpdf(mod):
    mu, t = np.array([215.0, 230.5, 224.0]), np.array([201.0, 244.0, 224.0])
    np.testing.assert_allclose(mod.normal_nll(mu, t, 22.0), -norm.logpdf(t, mu, 22.0), atol=1e-12)


@pytest.mark.parametrize("line", [43.5, 44.0, 44.25, 220.5, 221.0])
def test_normal_over_matches_production_including_integer_lines(mod, line):
    mu = np.array([40.0, 44.0, 47.3, 224.0])
    got = mod.normal_over(mu, 13.5, line)
    want = [dist.normal_total_probs(float(m), 13.5, line)["over"] for m in mu]
    np.testing.assert_allclose(got, want, atol=1e-12)


def test_hockey_grid_matches_poisson_match_probs(mod):
    lam_h, lam_a = np.array([2.9, 3.4, 3.1, 4.0]), np.array([2.7, 3.0, 3.6, 2.2])
    pt = mod.hockey_pt(lam_h, lam_a)
    np.testing.assert_allclose(pt.sum(axis=1), 1.0, atol=1e-12)
    for line in (4.5, 5.5, 6.5, 7.5, 6.0, 5.0):
        want = [dist.poisson_match_probs(a, b, None, line, three_way=False, max_goals=15)["over"]
                for a, b in zip(lam_h, lam_a)]
        np.testing.assert_allclose(mod.hockey_over(pt, line), want, atol=1e-12)
    # P(T = k) = P(Over k - 0,5) - P(Over k + 0,5), la identidad de la seccion 7.3
    for k in (2, 5, 8):
        a = [dist.poisson_match_probs(x, y, None, k - 0.5, max_goals=15)["over"] for x, y in zip(lam_h, lam_a)]
        b = [dist.poisson_match_probs(x, y, None, k + 0.5, max_goals=15)["over"] for x, y in zip(lam_h, lam_a)]
        np.testing.assert_allclose(pt[:, k], np.array(a) - np.array(b), atol=1e-12)
    mm = mod.hockey_margin(lam_h, lam_a, (-1.5, 1.5))
    for i, (x, y) in enumerate(zip(lam_h, lam_a)):
        p = dist.poisson_match_probs(x, y, -1.5, None, three_way=False, max_goals=15)
        q = dist.poisson_match_probs(x, y, 1.5, None, three_way=False, max_goals=15)
        assert abs(mm["home_win"][i] - p["home_win"]) <= 1e-12
        assert abs(mm["cover@-1.5"][i] - p["home_cover"]) <= 1e-12 and abs(mm["cover@1.5"][i] - q["home_cover"]) <= 1e-12
    with pytest.raises(ValueError):
        mod.hockey_margin(lam_h, lam_a, (-1.0,))


def test_hockey_nll_excludes_out_of_grid_and_non_integer(mod):
    lh, la = np.array([3.0, 3.0, 3.0]), np.array([3.0, 3.0, 3.0])
    nll, valid = mod.hockey_nll(lh, la, np.array([6.0, 31.0, 5.5]))
    assert valid.tolist() == [True, False, False] and np.isnan(nll[1:]).all() and np.isfinite(nll[0])
    pt = mod.hockey_pt(lh[:1], la[:1])
    assert nll[0] == pytest.approx(-np.log(pt[0, 6]))


def test_hockey_lambdas_reproduce_adapter_rates_at_zero_shift(mod, runs):
    r = runs["nhl"]
    lh, la = mod.hockey_lambdas(r.base["avg"], r.base["tilt"], r.spec.bonus)
    np.testing.assert_allclose(lh, r.base["lam_h"], atol=1e-12)
    np.testing.assert_allclose(la, r.base["lam_a"], atol=1e-12)
    np.testing.assert_allclose(r.base["lam_h"] + r.base["lam_a"], r.base["avg"] + r.spec.bonus, atol=1e-12)


# ---------------------------------------------------------------- recorrido --
@pytest.mark.parametrize("lg", ["nba", "nfl", "nhl"])
def test_base_walk_equals_grid_walk_at_vigente_and_h_changes_mu(mod, runs, lg):
    r = runs[lg]
    for k in r.base:
        np.testing.assert_array_equal(r.base[k], r.grid[r.h_vig][k])
    assert not np.array_equal(r.grid[30.0]["mu"], r.grid[730.0]["mu"]) or lg == "nfl"
    assert len(r.base["mu"]) == len(r.dates) == 300 - mod.WARMUP


def test_walk_does_not_see_the_game_it_estimates_nor_same_day_games(mod, runs):
    r = runs["nba"]
    rows = [dict(x) for x in r.results]
    day = "2014-10-20"
    idx = [i for i, x in enumerate(sorted(rows, key=lambda x: x["date"])) if x["date"] == day]
    ordered = sorted(rows, key=lambda x: x["date"])
    for i in idx:                                   # cambia todos los marcadores de ese dia
        ordered[i]["home_score"], ordered[i]["away_score"] = 300, 0
    new = mod.walk_mu(ordered, "nba", "basketball", r.league_params)
    old = r.base
    day_mask = old["date"] <= day
    np.testing.assert_array_equal(new["mu"][day_mask], old["mu"][day_mask])       # hasta ese dia incluido: igual
    assert not np.array_equal(new["mu"][~day_mask], old["mu"][~day_mask])        # despues: cambia


def test_decay_uses_only_past_dates_and_matches_production_scoring(mod, runs):
    """mu(h) = TeamScoringRates con ese h, incremental y con dias estrictamente previos."""
    r = runs["nba"]
    lp = mod.candidate_params(r.league_params, 60.0)
    ad = get_adapter("nba", "basketball", lp)
    ordered = sorted(r.results, key=lambda x: x["date"])
    pending, mus = [], []
    for i, g in enumerate(ordered):
        if pending and g["date"] != pending[0]["date"]:
            for c in pending:
                ad.observe(c)
            pending.clear()
        if i >= mod.WARMUP:
            mus.append(ad.scoring.expected_total(g["home"], g["away"], ad.params["avg_total"]))
        pending.append(g)
    np.testing.assert_allclose(r.grid[60.0]["mu"], mus, atol=1e-12)


def test_lines_are_floor_mu_plus_half_and_hash_is_stable(mod, runs):
    r = runs["nhl"]
    line = mod.l_base(r.base["mu"])
    assert np.all(line == np.floor(r.base["mu"]) + 0.5)
    assert mod.l_hash(line) == mod.l_hash(line.copy()) and len(mod.l_hash(line)) == 64


def test_outcomes_are_aligned_with_the_walk(mod, runs):
    r = runs["nhl"]
    out = mod.read_outcomes(r.results)
    assert len(out["total"]) == len(r.dates) and np.all(out["total"] == out["home"] + out["away"])
    ordered = sorted(r.results, key=lambda x: x["date"])
    assert out["total"][0] == ordered[mod.WARMUP]["home_score"] + ordered[mod.WARMUP]["away_score"]


# ------------------------------------------------------------- control C --
def test_level_shift_normal_is_the_exact_minimizer(mod, runs):
    r = runs["nba"]
    out = mod.read_outcomes(r.results)
    train = r.masks["B"]["train"]
    a = mod.fit_level_shift(r.spec, r.base, out["total"], train)
    f = lambda v: float(np.mean(mod.total_loss(r.spec, r.base, out["total"], float(v[0]))[0][train]))  # noqa: E731
    res = minimize(f, [0.0], method="Nelder-Mead", options={"xatol": 1e-9, "fatol": 1e-12})
    assert a == pytest.approx(res.x[0], abs=1e-4)
    assert a == pytest.approx(float(np.mean((out["total"] - r.base["mu"])[train])))


def test_level_shift_nhl_recovers_a_known_offset(mod, runs):
    r = runs["nhl"]
    out = mod.read_outcomes(r.results)
    total = out["total"] + np.where(r.masks["C"]["train"], 2.0, 0.0)           # nivel mas alto en entrenamiento C
    a_hi = mod.fit_level_shift(r.spec, r.base, total, r.masks["C"]["train"])
    a_lo = mod.fit_level_shift(r.spec, r.base, out["total"], r.masks["C"]["train"])
    assert a_hi > a_lo + 1.0


# ---------------------------------------------------------------- fase H --
@pytest.mark.parametrize("lg", ["nba", "nfl", "nhl"])
def test_evaluate_league_H_wiring_and_manual_recomputation(mod, runs, lg):
    r = runs[lg]
    out = mod.read_outcomes(r.results)
    res = mod.evaluate_league_H(r, out, n_boot=40)
    assert set(res["h_por_particion"]) == {"A", "B", "C"} and set(res["a_por_particion"]) == {"A", "B", "C"}
    assert all(h in mod.GRID for h in res["h_por_particion"].values())
    assert set(res["criterios"]) == {"H1", "H2", "H3", "H4", "H5"} and set(res["perdidas"]) == {"A", "B", "C", "combinado"}
    assert set(res["bootstrap"]) >= {"delta_H1", "T_menos_C", "delta_H4", "particion_A", "particion_B", "particion_C"}
    assert (("delta_H5_h2h" in res["bootstrap"]) == (lg == "nhl")) and ((res["delta_H5"] is not None) == (lg == "nhl"))
    assert res["bootstrap"]["delta_H1"]["n_replicas"] == 40
    # recomputo a mano de Delta H1 y del brazo T
    w = res["_w"]
    tv = w["tv"]
    manual_t = np.concatenate([w["loss_h"][res["h_por_particion"][n]][r.masks[n]["test"] & w["valid"]] for n in "ABC"])
    manual_b = np.concatenate([w["loss_b"][r.masks[n]["test"] & w["valid"]] for n in "ABC"])
    assert res["delta_H1"] == pytest.approx(float(np.mean(manual_t - manual_b)), abs=1e-12)
    assert res["n_test"] == int(tv.sum()) == len(manual_t)
    # el entrenamiento NO incluye el test: perfil calculado solo con fechas <= train_end
    for n, f in SYN_FOLDS.items():
        tr = r.masks[n]["train"] & w["valid"]
        assert max(r.dates[tr].tolist()) <= f["train_end"]
        for h in r.grid_hs:
            assert res["_w"]["train_profile"][n][mod.hkey(h)] == pytest.approx(float(np.mean(w["loss_h"][h][tr])))
    # el argmin del perfil de entrenamiento es h_P
    for n in "ABC":
        prof = {float(k): v for k, v in w["train_profile"][n].items()}
        assert res["h_por_particion"][n] == mod.select_h(prof, r.h_vig)


def test_h_equal_to_vigente_gives_zero_delta_and_fails_h2(mod, runs, monkeypatch):
    """Seccion 4: si h_P coincide con el vigente, T == base, Delta = 0 exacto y H2 falla."""
    r = runs["nba"]
    monkeypatch.setattr(mod, "select_h", lambda prof, h_vig: h_vig)
    res = mod.evaluate_league_H(r, mod.read_outcomes(r.results), n_boot=20)
    assert res["delta_H1"] == 0.0 and all(v == 0.0 for v in res["delta_por_particion"].values())
    assert res["criterios"]["H2"] is False and res["criterios"]["H1"] is False


def test_recency_signal_is_found_by_the_training_selection(mod, monkeypatch, tmp_path):
    """Con un nivel de anotacion que deriva, el argmin de entrenamiento no es el mas largo."""
    _patch_meta(mod, monkeypatch)
    root = _write_root(tmp_path, n_days=100, drift=0.9)
    r = mod.LeagueRun("nba", root)
    res = mod.evaluate_league_H(r, mod.read_outcomes(r.results), n_boot=20)
    assert res["h_por_particion"]["C"] < 730.0
    assert res["delta_H1"] < 0 and res["T_menos_C"] is not None


def test_criteria_each_one_can_fail(mod, runs, monkeypatch):
    r = runs["nhl"]
    out = mod.read_outcomes(r.results)
    res = mod.evaluate_league_H(r, out, n_boot=20)
    h1 = res["delta_H1"] <= -mod.H1_MARGIN
    assert res["criterios"]["H1"] == h1
    assert res["criterios"]["H3"] == (res["T_menos_C"] < 0)
    assert res["criterios"]["H4"] == (res["delta_H4"] <= 0)
    assert res["criterios"]["H5"] == (res["delta_H5"]["h2h"] <= 0 and res["delta_H5"]["spreads"] <= 0)


def test_nhl_out_of_grid_totals_are_counted_and_excluded(mod, runs):
    r = runs["nhl"]
    out = mod.read_outcomes(r.results)
    out["total"] = out["total"].copy()
    out["total"][5] = 40.0
    res = mod.evaluate_league_H(r, out, n_boot=10)
    assert np.isfinite(res["delta_H1"]) and not res["_w"]["valid"][5]


def test_holm_k3_and_h6(mod):
    h = mod.apply_holm({"nba": {"p": 1e-6}, "nfl": {"p": 0.03}, "nhl": {"p": 0.004}})
    assert h["K"] == 3 and h["orden"] == ["nba", "nhl", "nfl"]
    assert h["umbrales"] == pytest.approx({"nba": 0.05 / 3, "nhl": 0.05 / 2, "nfl": 0.05})
    assert h["rechazadas"] == ["nba", "nhl", "nfl"]
    h2 = mod.apply_holm({"nba": {"p": 0.04}, "nfl": {"p": 0.5}, "nhl": {"p": 0.02}})
    assert h2["rechazadas"] == []                 # 0,02 > 0,05/3: se detiene en el primer escalon
    with pytest.raises(SystemExit):
        mod.apply_holm({"nba": {"p": 0.1}})


def test_bootstrap_is_shared_by_blocks_of_days(mod, runs, monkeypatch):
    seen = {}
    orig = mod.bootstrap_dias

    def spy(dates, stats, **kw):
        seen["days"] = len(np.unique(dates))
        seen["stats"] = set(stats)
        seen["n"] = len(dates)
        return orig(dates, stats, n_boot=30)

    monkeypatch.setattr(mod, "bootstrap_dias", spy)
    r = runs["nhl"]
    mod.evaluate_league_H(r, mod.read_outcomes(r.results))
    assert seen["days"] == len(np.unique(r.dates[r.in_test])) and seen["n"] == int(r.in_test.sum())
    assert {"delta_H1", "delta_H5_h2h", "delta_H5_spreads"} <= seen["stats"]


def test_informes_H_are_produced_and_isolated(mod, runs):
    r = runs["nba"]
    res = mod.evaluate_league_H(r, mod.read_outcomes(r.results), n_boot=10)
    inf = mod.informes_H(r, res)
    assert set(inf) == {"1", "2", "3", "4"} and not any(mod.bat._is_error(v) for v in inf.values())
    assert set(inf["4"]) == {mod.hkey(h) for h in r.grid_hs}
    assert inf["2"]["combinado"]["base"]["de_residuo"] > 0 and "h_C_en_extremo_de_la_rejilla" in inf["1"]


# ---------------------------------------------------------------- paridad --
@pytest.mark.parametrize("lg", ["nba", "nfl", "nhl"])
def test_parity_1_2_3_pass_on_synthetic(mod, runs, lg):
    r = runs[lg]
    par = mod.run_parity(r, mod.read_outcomes(r.results), r.grid_hs)
    assert par["aserto1_motor"]["desviacion_max"] <= 1e-12 and par["aserto2_mu"]["desviacion_max"] <= 1e-12
    assert set(par["aserto1_motor"]["por_brazo"]) == {"base", *(mod.hkey(h) for h in r.grid_hs)}
    assert par["aserto3_distribucion"]["aplica"] is (lg == "nhl")
    if lg == "nhl":
        assert par["aserto3_distribucion"]["desviacion_max"] <= 1e-12
        assert set(par["aserto1_motor"]["por_brazo"]["base"]) == {"h2h", "spreads@-1.5", "spreads@1.5", "totals@5.5"}


def test_parity_1_detects_a_broken_arm(mod, runs):
    r = runs["nba"]
    r.grid[90.0]["mu"] = r.grid[90.0]["mu"] + 1e-6
    with pytest.raises(SystemExit, match="PARIDAD 1 ROTA"):
        mod.parity_engine(r, mod.read_outcomes(r.results), (90.0,))


def test_parity_2_detects_a_broken_mu_and_3_a_broken_lambda(mod, runs):
    r = runs["nhl"]
    r.base["lam_h"] = r.base["lam_h"] + 1e-6
    with pytest.raises(SystemExit, match="PARIDAD 2 ROTA"):
        mod.parity_mu(r)
    r2 = runs["nba"]
    r2.base["mu"] = r2.base["mu"] + 1e-6
    with pytest.raises(SystemExit, match="PARIDAD 2 ROTA"):
        mod.parity_mu(r2)


def test_parity_3_detects_broken_normalization(mod, runs, monkeypatch):
    r = runs["nhl"]
    monkeypatch.setattr(mod, "hockey_pt", lambda a, b, mg=15: mod.hockey_pt.__wrapped__(a, b, mg) * 1.001
                        if hasattr(mod.hockey_pt, "__wrapped__") else np.full((len(a), 31), 0.0333))
    with pytest.raises(SystemExit, match="PARIDAD 3 ROTA"):
        mod.parity_distribution(r)


def test_parity_only_end_to_end_with_subset(mod, monkeypatch, tmp_path):
    _patch_meta(mod, monkeypatch)
    root = _write_root(tmp_path)
    out = mod.parity_only(root, ("nhl", "nba"), (0.0, 90.0))
    assert out["ligas"]["nhl"]["resultado"] == "PARIDAD OK" and out["rejilla_comprobada"] == [0.0, 90.0]
    assert set(out["ligas"]["nba"]["aserto1_motor"]["por_brazo"]) == {"base", "0.0", "90.0"}


# ------------------------------------------------------------- aserto 5 / pre --
def _battery_for(mod, runs):
    ligas = {}
    for lg, r in runs.items():
        counts = {n: {"partidos": int(m["test"].sum()), "dias": int(len(np.unique(r.dates[m["test"]])))}
                  for n, m in r.masks.items()}
        ligas[lg] = {"evaluados": int(len(r.dates)), "lineas_L": {"sha256_vector": mod.l_hash(mod.l_base(r.base["mu"]))},
                     "particiones": counts}
    return {"ligas": ligas}


def test_assertion_5_against_battery_pre(mod, runs):
    bat_pre = _battery_for(mod, runs)
    r = runs["nba"]
    counts = {n: {"partidos": int(m["test"].sum()), "dias": int(len(np.unique(r.dates[m["test"]])))}
              for n, m in r.masks.items()}
    h = mod.l_hash(mod.l_base(r.base["mu"]))
    assert mod.check_against_battery("nba", counts, h, len(r.dates), bat_pre)["coincide"]
    with pytest.raises(SystemExit, match="aserto 5"):
        mod.check_against_battery("nba", counts, "0" * 64, len(r.dates), bat_pre)
    bad = {**counts, "A": {"partidos": counts["A"]["partidos"] + 1, "dias": counts["A"]["dias"]}}
    with pytest.raises(SystemExit, match="aserto 5"):
        mod.check_against_battery("nba", bad, h, len(r.dates), bat_pre)


def test_battery_pre_file_is_verified_by_sha256(mod, tmp_path):
    with pytest.raises(SystemExit, match="Falta"):
        mod.load_battery_pre(tmp_path)
    (tmp_path / mod.BATTERY_PRE_NAME).write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit, match="SHA-256"):
        mod.load_battery_pre(tmp_path)


def test_doc_table_comparison(mod):
    ok = {mod.hkey(h): {"media": m, "rms": s, "n": 1} for h, (m, s) in mod.DOC_TABLE_9_1["nba"].items()}
    assert mod.compare_doc_table("nba", ok)["coincide"]
    ok["0.0"]["media"] += 0.5
    out = mod.compare_doc_table("nba", ok)
    assert not out["coincide"] and out["no_coinciden"] == ["0.0"]


def test_pre_league_computes_no_loss_and_never_reads_outcomes(mod, runs, monkeypatch, tmp_path):
    def boom(*a, **k):
        raise AssertionError("--pre no debe leer desenlaces ni calcular perdidas")

    for name in ("read_outcomes", "total_loss", "ll_vec", "fit", "bootstrap_dias", "walk_forward_backtest",
                 "hockey_nll", "normal_nll", "evaluate_league_H", "fit_level_shift", "run_parity", "over_prob"):
        monkeypatch.setattr(mod, name, boom)
    from sqp.sports.adapters import NormalMarginAdapter, PoissonAdapter
    monkeypatch.setattr(PoissonAdapter, "estimate", boom)
    monkeypatch.setattr(NormalMarginAdapter, "estimate", boom)
    battery = _battery_for_nologic(mod, runs)
    for lg, r in runs.items():
        out = mod.pre_league(r, battery, tmp_path)
        assert out["aserto5_bateria"]["coincide"] and set(out["tabla_9_1"]) == {mod.hkey(h) for h in r.grid_hs}
        assert out["tabla_9_1"][mod.hkey(r.h_vig)]["rms"] == 0.0 and out["evaluados"] == 300 - mod.WARMUP


def _battery_for_nologic(mod, runs):
    """Como `_battery_for` pero sin llamar a nada que el test haya sustituido."""
    ligas = {}
    for lg, r in runs.items():
        counts = {n: {"partidos": int(m["test"].sum()), "dias": int(len(np.unique(r.dates[m["test"]])))}
                  for n, m in r.masks.items()}
        ligas[lg] = {"evaluados": int(len(r.dates)), "particiones": counts,
                     "lineas_L": {"sha256_vector": mod.l_hash(np.floor(r.base["mu"]) + 0.5)}}
    return {"ligas": ligas}


def test_table_9_1_is_rms_and_mean_of_mu_difference_in_test_c(mod, runs):
    r = runs["nfl"]
    t = mod.table_9_1(r.base, r.grid, r.masks["C"]["test"])
    d = (r.grid[90.0]["mu"] - r.base["mu"])[r.masks["C"]["test"]]
    assert t["90.0"]["media"] == pytest.approx(d.mean()) and t["90.0"]["rms"] == pytest.approx(np.sqrt((d ** 2).mean()))
    assert t["0.0"]["rms"] == 0.0     # NFL: h = 0 es la base


# ------------------------------------------------------ procedencia y abortos --
def test_check_provenance_aborts(mod):
    pre = {"git_head": "abc", "manifiesto": {"f": {"sha256": "1", "filas": 2}}, "config_sha256": {"c": "x"},
           "parametros_resueltos": {"nba": {"league_params": None, "adapter_params": {"a": 1}}},
           "codigo_sha256": mod.code_hashes()}
    mod.check_provenance(pre, "abc", pre["manifiesto"], pre["config_sha256"], pre["parametros_resueltos"], "pre")
    with pytest.raises(SystemExit, match="HEAD DE GIT CAMBIO"):
        mod.check_provenance(pre, "zzz", pre["manifiesto"], pre["config_sha256"], pre["parametros_resueltos"], "pre")
    with pytest.raises(SystemExit, match="HASH DE ENTRADA CAMBIO"):
        mod.check_provenance(pre, "abc", {"f": {"sha256": "9", "filas": 2}}, pre["config_sha256"],
                             pre["parametros_resueltos"], "pre")
    with pytest.raises(SystemExit, match="conjunto de ficheros"):
        mod.check_provenance(pre, "abc", {}, pre["config_sha256"], pre["parametros_resueltos"], "pre")
    with pytest.raises(SystemExit, match="ratings.yaml"):
        mod.check_provenance(pre, "abc", pre["manifiesto"], {"c": "y"}, pre["parametros_resueltos"], "pre")
    with pytest.raises(SystemExit, match="Parametros resueltos"):
        mod.check_provenance(pre, "abc", pre["manifiesto"], pre["config_sha256"], {"nba": {}}, "pre")
    with pytest.raises(SystemExit):
        mod.check_provenance({**pre, "git_head": None}, "abc", pre["manifiesto"], pre["config_sha256"],
                             pre["parametros_resueltos"], "pre")


def test_check_pre_tables_aborts_on_difference(mod):
    tab = {lg: {"0.0": {"media": 1.0, "rms": 2.0, "n": 3}} for lg in mod.LEAGUES}
    counts = {lg: {"A": (10, 5)} for lg in mod.LEAGUES}
    pre = {"tabla_9_1": tab, "recuentos": {lg: {"A": [10, 5]} for lg in mod.LEAGUES}}
    mod.check_pre_tables(pre, tab, counts)
    bad = {lg: {"0.0": {"media": 1.0 + 1e-6, "rms": 2.0, "n": 3}} for lg in mod.LEAGUES}
    with pytest.raises(SystemExit, match="tabla 9.1"):
        mod.check_pre_tables(pre, bad, counts)
    with pytest.raises(SystemExit, match="recuentos"):
        mod.check_pre_tables(pre, tab, {lg: {"A": (11, 5)} for lg in mod.LEAGUES})


def test_load_league_cut_applies_cutoff_and_game_id_assertion(mod, monkeypatch, tmp_path):
    _patch_meta(mod, monkeypatch)
    hist = tmp_path / "data" / "historical"
    hist.mkdir(parents=True)
    rows = _games("nfl", n_days=4, start="2026-09-24")
    pd.DataFrame(rows).assign(ingested_at="x").to_csv(hist / "results_nfl.csv", index=False)
    got, lp, proc = mod.load_league_cut("nfl", tmp_path, "2026-09-26")
    assert len(got) == 9 and lp is None and proc["filas_antes_dedupe_game_id"] == 9 and len(proc["sha256"]) == 64
    got2, _, _ = mod.load_league_cut("nfl", tmp_path, "2026-09-27")
    assert len(got2) == 12
    dup = rows + [dict(rows[0], date="2026-09-25")]
    pd.DataFrame(dup).assign(ingested_at="x").to_csv(hist / "results_nfl.csv", index=False)
    with pytest.raises(SystemExit, match="descartes por game_id"):
        mod.load_league_cut("nfl", tmp_path, "2026-09-27")
    pd.DataFrame(rows).assign(ingested_at="x").to_csv(hist / "results_nfl.csv", index=False)
    monkeypatch.setattr(mod, "_league_meta", lambda lg: {"family": "football", "league_params": {"elo_k": 24}})
    with pytest.raises(SystemExit, match="league_params"):
        mod.load_league_cut("nfl", tmp_path, "2026-09-27")


def test_manifest_hashes_results_and_odds(mod, tmp_path):
    hist, odds = tmp_path / "data" / "historical", tmp_path / "data" / "odds"
    hist.mkdir(parents=True)
    odds.mkdir(parents=True)
    (hist / "results_nba.csv").write_text("date,home\n2020-01-01,A\n", encoding="utf-8")
    (odds / "odds_nba_202603.csv").write_text("a\n1\n2\n", encoding="utf-8")
    h = mod.manifest(tmp_path, odds=False)
    assert set(h) == {f"data/historical/results_{lg}.csv" for lg in mod.LEAGUES}
    m = mod.manifest(tmp_path, odds=True)
    assert m["data/odds/odds_nba_202603.csv"]["filas"] == 2 and m["data/historical/results_nhl.csv"]["sha256"] is None


def test_assert_vigente_aborts_if_params_change(mod, monkeypatch):
    monkeypatch.setitem(mod.H_VIGENTE, "nba", 90.0)
    with pytest.raises(SystemExit, match="h vigente"):
        mod.assert_vigente_matches_params()


# --------------------------------------------------------------------- CLI --
def test_cli_argument_validation(mod, tmp_path, monkeypatch):
    p = str(tmp_path / "o.json")
    for argv in (["--pre", "--parity-only"], [], ["--fase", "H", "--data-root", str(tmp_path), "--out", p],
                 ["--pre", "--out", p], ["--fase", "M", "--pre", "--data-root", str(tmp_path), "--out", p],
                 ["--fase", "M", "--data-root", str(tmp_path), "--pre-json", p, "--out", p],
                 ["--pre", "--data-root", str(tmp_path), "--out", p, "--leagues", "nba"],
                 ["--pre", "--data-root", str(tmp_path), "--out", p, "--pre-json", p],
                 ["--fase", "M", "--pre", "--h-json", p, "--data-root", str(tmp_path), "--out", p]):
        with pytest.raises(SystemExit):
            mod.main(argv)
    with pytest.raises(SystemExit):
        mod.main(["--parity-only", "--data-root", str(tmp_path), "--leagues", "mlb"])
    with pytest.raises(SystemExit):
        mod.main(["--parity-only", "--data-root", str(tmp_path), "--h-subset", "17"])


def test_live_tree_and_data_subtree_are_rejected(mod, monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "git_status_porcelain", lambda cwd, paths=None: "")
    p = str(tmp_path / "o.json")
    with pytest.raises(SystemExit, match="arbol vivo"):
        mod.main(["--pre", "--data-root", str(mod.DEFAULT_ROOT), "--out", p])
    with pytest.raises(SystemExit, match="dentro de data"):
        mod.main(["--fase", "H", "--data-root", str(mod.DEFAULT_ROOT / "data" / "snap"), "--pre-json", p, "--out", p])


def test_pre_and_full_abort_on_dirty_tree(mod, monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "git_status_porcelain", lambda cwd, paths=None: " M configs/default.yaml\n")
    monkeypatch.setattr(mod, "git_head", lambda cwd: "abc")
    pre_json = tmp_path / "pre.json"
    pre_json.write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit, match="NO esta vacio"):
        mod.main(["--pre", "--data-root", str(tmp_path), "--out", str(tmp_path / "o.json")])
    monkeypatch.setattr(mod, "run_H", lambda *a, **k: pytest.fail("no debe medir con el arbol sucio"))
    with pytest.raises(SystemExit, match="NO esta vacio"):
        mod.main(["--fase", "H", "--data-root", str(tmp_path), "--pre-json", str(pre_json), "--out", str(tmp_path / "o.json")])


def test_main_pre_then_fase_H_end_to_end_and_aborts_on_changed_input(mod, monkeypatch, tmp_path):
    _patch_meta(mod, monkeypatch)
    root = _write_root(tmp_path)
    monkeypatch.setattr(mod, "git_head", lambda cwd: "deadbeef")
    monkeypatch.setattr(mod, "git_status_porcelain", lambda cwd, paths=None: "")
    orig = mod.bootstrap_dias
    monkeypatch.setattr(mod, "bootstrap_dias", lambda d, s, n_boot=30, seed=42, chunk=250: orig(d, s, n_boot, seed, chunk))
    runs_ = {lg: mod.LeagueRun(lg, root) for lg in mod.LEAGUES}
    bat_pre = _battery_for_nologic(mod, runs_)
    manifest_now = mod.manifest(root, odds=False)
    bat_pre["manifiesto"] = manifest_now
    bat_pre["config_sha256"] = mod.bat.config_hashes()
    monkeypatch.setattr(mod, "load_battery_pre", lambda data_root: bat_pre)
    pre_path, out_path = tmp_path / "pre_H.json", tmp_path / "H.json"
    assert mod.main(["--pre", "--data-root", str(root), "--out", str(pre_path)]) == 0
    pre = json.loads(pre_path.read_text(encoding="utf-8"))
    assert pre["git_head"] == "deadbeef" and pre["git_status_porcelain"] == "" and set(pre["ligas"]) == set(mod.LEAGUES)
    assert set(pre["tabla_9_1"]["nba"]) == {mod.hkey(h) for h in mod.GRID}
    assert pre["parametros_resueltos"]["nhl"]["league_params"] == {"elo_home_adv": 15.0, "tilt_scale": 0.439}
    assert mod.main(["--fase", "H", "--data-root", str(root), "--pre-json", str(pre_path), "--out", str(out_path)]) == 0
    res = json.loads(out_path.read_text(encoding="utf-8"))
    assert res["modo"] == "fase H" and set(res["por_liga"]) == set(mod.LEAGUES) and res["rejilla"] == list(mod.GRID)
    for lg in mod.LEAGUES:
        r = res["por_liga"][lg]
        assert {"h_por_particion", "a_por_particion", "perdidas", "delta_H1", "delta_por_particion", "T_menos_C",
                "delta_H4", "delta_H5", "bootstrap", "p", "criterios", "veredicto_H"} <= set(r)
        assert set(r["criterios"]) == {"H1", "H2", "H3", "H4", "H5", "H6"} and r["veredicto_H"] in ("ACEPTA", "RECHAZA")
        assert res["paridad"][lg]["aserto1_motor"]["desviacion_max"] <= 1e-12
    assert set(res["holm"]) >= {"orden", "umbrales", "p_ajustados", "rechazadas"} and set(res["informes"]) == {"1", "2", "3", "4"}
    assert res["pre_json_sha256"] == mod.sha256_of(pre_path)
    # un fichero de entrada cambia -> aborta antes de medir
    f = root / "data" / "historical" / "results_nfl.csv"
    f.write_text(f.read_text(encoding="utf-8") + "2014-09-05,A,B,zz,1,0,False,x\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="HASH DE ENTRADA"):
        mod.main(["--fase", "H", "--data-root", str(root), "--pre-json", str(pre_path), "--out", str(tmp_path / "H2.json")])


# --------------------------------------------------------------------- fase M --
def _odds_root(tmp_path, results, league, *, line=224.5, skip_novig_every=0):
    """Raiz con resultados y cuotas SINTETICAS: un evento por partido, dos libros."""
    odds_rows = []
    for k, g in enumerate(results):
        eid = f"e{k}"
        for book in ("b1", "b2"):
            for out_, price in (("Over", 1.91), ("Under", 1.91)):
                if skip_novig_every and k % skip_novig_every == 0 and out_ == "Under":
                    continue
                odds_rows.append({"captured_at": f"{g['date']}T18:00:00Z", "event_id": eid,
                                  "commence_time": f"{g['date']}T23:00:00Z", "home": g["home"], "away": g["away"],
                                  "market": "totals", "outcome": out_, "point": line, "price_decimal": price,
                                  "bookmaker": book})
            odds_rows.append({"captured_at": f"{g['date']}T18:00:00Z", "event_id": eid,
                              "commence_time": f"{g['date']}T23:00:00Z", "home": g["home"], "away": g["away"],
                              "market": "h2h", "outcome": g["home"], "point": None, "price_decimal": 1.8,
                              "bookmaker": book})
    od = tmp_path / "data" / "odds"
    od.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(odds_rows).to_csv(od / f"odds_{league}_201411.csv", index=False)
    return tmp_path


def _m_setup(mod, monkeypatch, tmp_path, league="nba", line=224.5, **kw):
    _patch_meta(mod, monkeypatch)
    monkeypatch.setattr(mod, "MARKET_START", "2014-11-15")
    root = _write_root(tmp_path)
    rows = [r for r in _games(league, n_days=100, start="2014-09-01")]
    root = _odds_root(root, rows, league, line=line, **kw)
    return root


def test_m_pre_counting_never_reads_scores_and_estimates_nothing(mod, monkeypatch, tmp_path):
    root = _m_setup(mod, monkeypatch, tmp_path)
    rows = [{k: v for k, v in r.items() if k not in ("home_score", "away_score")} for r in _games("nba")]
    odds = mod.load_closing_odds(root, "nba")

    def boom(*a, **k):
        raise AssertionError("el conteo previo no estima nada")

    monkeypatch.setattr(mod, "get_adapter", boom)
    monkeypatch.setattr(mod, "_m_estimate", boom)
    m = mod.m_matches("nba", rows, odds, None, start="2014-11-15", h_c=None, estimate=False)
    assert len(m["recs"]) > 0 and set(m["recs"][0]) == {"date", "mes", "event_id", "L", "spread", "p_fair"}
    assert m["conteo"]["sin_emparejar"] >= 0 and "n_ambiguos_omitidos" in m["conteo"]
    assert all(abs(r["p_fair"] - 0.5) < 1e-9 for r in m["recs"])
    assert set(mod.month_table(m["recs"])) == {"2014-11", "2014-12"}


def test_m_decision_rules(mod):
    assert mod.decide_m_league(800, mod.M_CUTOFF, "nba") == "medir"
    assert mod.decide_m_league(799, mod.M_CUTOFF, "nba") == "prorroga"
    assert mod.decide_m_league(799, mod.M_CUTOFF_EXT, "nba") == "no_concluyente"
    assert mod.decide_m_league(250, mod.M_CUTOFF, "nfl") == "medir" and mod.decide_m_league(249, mod.M_CUTOFF, "nfl") == "prorroga"
    assert mod.decide_m_league(800, mod.M_CUTOFF_EXT, "nhl") == "medir"
    assert mod.decide_m_league(799, mod.M_CUTOFF, "nba", "RECHAZA") == "no_medida_descriptivo"
    assert mod.decide_m_league(800, mod.M_CUTOFF, "nba", "RECHAZA") == "medir"
    assert mod.decide_m_league(10, mod.M_CUTOFF_EXT, "nhl", "RECHAZA") == "no_medida_descriptivo"


def test_m_events_without_complete_novig_are_not_counted(mod, monkeypatch, tmp_path):
    root = _m_setup(mod, monkeypatch, tmp_path, skip_novig_every=2)
    rows = _games("nba")
    odds = mod.load_closing_odds(root, "nba")
    m = mod.m_matches("nba", rows, odds, None, start="2014-11-15", h_c=None, estimate=False)
    assert m["conteo"]["sin_novig"] > 0 and len(m["recs"]) > 0


def test_m_ambiguous_doubleheader_is_omitted_and_counted(mod, monkeypatch, tmp_path):
    _patch_meta(mod, monkeypatch)
    root = tmp_path
    rows = [dict(date="2014-11-20", home="A", away="B", game_id=str(i), home_score=100, away_score=90, neutral=False)
            for i in range(1, 3)]
    pad = [dict(date=f"2014-09-{d:02d}", home="C", away="D", game_id=f"p{d}", home_score=100, away_score=90,
                neutral=False) for d in range(1, 29)] * 3
    pad = [dict(r, game_id=f"p{i}") for i, r in enumerate(pad)]
    allrows = pad + rows
    odds_rows = []
    for k, t in enumerate(("T10:00:00Z", "T18:00:00Z")):
        for out_ in ("Over", "Under"):
            odds_rows.append({"captured_at": f"2014-11-20T0{k}:00:00Z", "event_id": f"d{k}",
                              "commence_time": f"2014-11-20{t}", "home": "A", "away": "B", "market": "totals",
                              "outcome": out_, "point": 220.5, "price_decimal": 1.9, "bookmaker": "b"})
    od = root / "data" / "odds"
    od.mkdir(parents=True)
    pd.DataFrame(odds_rows).to_csv(od / "odds_nba_201411.csv", index=False)
    odds = mod.load_closing_odds(root, "nba")
    m = mod.m_matches("nba", allrows, odds, None, start="2014-11-01", h_c=None, estimate=False)
    assert m["conteo"]["n_ambiguos_omitidos"] == 2 and len(m["recs"]) == 0


def test_measure_m_league_normal_and_parity_4(mod, monkeypatch, tmp_path):
    root = _m_setup(mod, monkeypatch, tmp_path, league="nba", line=224.0)         # linea entera: hay empujes posibles
    rows, lp, _ = mod.load_league_cut("nba", root, "2014-12-31")
    odds = mod.load_closing_odds(root, "nba")
    res = mod.measure_m_league("nba", rows, odds, lp, 90.0, set(odds), n_boot=40)
    assert res["n"] > 0 and res["n_evaluados"] + res["n_empujes"] == res["n"]
    assert res["paridad_M"]["desviacion_max"] <= 1e-12 and res["h_C"] == 90.0
    assert set(res["criterios"]) == {"M1", "M2", "M3"} and res["criterios"]["M1"] is False      # n << 800
    assert res["veredicto_M"] == "NO CONCLUYENTE" and res["delta_M3"] is None
    assert res["bootstrap"]["delta_M"]["n_replicas"] == 40
    assert not mod.bat._is_error(res["informes"]["5"]) and not mod.bat._is_error(res["informes"]["6"])
    assert res["informes"]["5"]["log_loss_novig"] == pytest.approx(np.log(2.0), abs=1e-9)
    # M2 es un signo sobre la estimacion puntual
    assert res["criterios"]["M2"] == (res["delta_M"] <= 0)


def test_measure_m_league_hockey_has_m3_and_spreads_report(mod, monkeypatch, tmp_path):
    root = _m_setup(mod, monkeypatch, tmp_path, league="nhl", line=5.5)
    rows, lp, _ = mod.load_league_cut("nhl", root, "2014-12-31")
    odds = mod.load_closing_odds(root, "nhl")
    res = mod.measure_m_league("nhl", rows, odds, lp, 60.0, set(), n_boot=30)
    assert res["delta_M3"] is not None and "delta_M3" in res["bootstrap"]
    assert res["criterios"]["M3"] == (res["delta_M3"] <= 0)
    assert res["paridad_M"]["desviacion_max"] <= 1e-12
    assert "regular_vs_playoffs" not in res["informes"]["6"] and res["n_lineas_cuarto_sin_paridad4"] == 0
    assert res["informes"]["6"]["submuestra_cierre"]["n"] == 0


def test_script_total_probability_matches_production_on_integer_and_quarter_lines(mod, runs):
    ev = mod.Event(event_id="x", sport_key="bt", league="nhl", home="A", away="B", start_time="2014-12-01")
    ad = get_adapter("nhl", "hockey", _expected_lp(mod, "nhl"))
    for r in sorted(runs["nhl"].results, key=lambda x: x["date"])[:80]:
        ad.observe(r)
    spec = mod.LeagueSpec("nhl", dict(ad.params))
    for line in (5.5, 6.0, 5.0):
        mine = mod.script_total_probability(ad, ev, line, spec)
        assert abs(mine - ad.estimate(ev, None, line).over_estimated_probability) <= 1e-12
    assert mod.script_total_probability(ad, ev, 5.25, spec) is None


def test_run_M_end_to_end_via_main(mod, monkeypatch, tmp_path):
    root = _m_setup(mod, monkeypatch, tmp_path, league="nba", line=224.5)
    monkeypatch.setattr(mod, "git_head", lambda cwd: "deadbeef")
    monkeypatch.setattr(mod, "git_status_porcelain", lambda cwd, paths=None: "")
    monkeypatch.setattr(mod, "M_MIN_N", {"nba": 5, "nhl": 5, "nfl": 5})
    orig = mod.bootstrap_dias
    monkeypatch.setattr(mod, "bootstrap_dias", lambda d, s, n_boot=30, seed=42, chunk=250: orig(d, s, n_boot, seed, chunk))
    h_json = {"parametros_resueltos": mod.resolved_report(mod.LEAGUES), "codigo_sha256": mod.code_hashes(),
              "por_liga": {lg: {"h_por_particion": {"A": 30.0, "B": 60.0, "C": 90.0},
                                "veredicto_H": "RECHAZA" if lg == "nba" else "ACEPTA"} for lg in mod.LEAGUES}}
    hp = tmp_path / "H.json"
    hp.write_text(json.dumps(h_json), encoding="utf-8")
    sha = mod.sha256_of(hp)
    pre_p, out_p = tmp_path / "pre_M.json", tmp_path / "M.json"
    with pytest.raises(SystemExit, match="SHA-256"):
        mod.main(["--fase", "M", "--pre", "--data-root", str(root), "--h-json", str(hp), "--h-sha256", "0" * 64,
                  "--out", str(pre_p)])
    assert mod.main(["--fase", "M", "--pre", "--data-root", str(root), "--h-json", str(hp), "--h-sha256", sha,
                     "--out", str(pre_p), "--m-cutoff", "2027-01-31"]) == 0
    pre = json.loads(pre_p.read_text(encoding="utf-8"))
    assert pre["h_C"] == {"nba": 90.0, "nfl": 90.0, "nhl": 90.0} and pre["h_json_sha256"] == sha
    assert pre["ligas"]["nba"]["decision"] == "medir" and pre["ligas"]["nfl"]["n_emparejados_con_linea_y_novig"] == 0
    assert pre["ligas"]["nfl"]["decision"] == "prorroga"
    assert mod.main(["--fase", "M", "--data-root", str(root), "--h-json", str(hp), "--pre-json", str(pre_p),
                     "--out", str(out_p)]) == 0
    res = json.loads(out_p.read_text(encoding="utf-8"))
    nba = res["por_liga"]["nba"]
    assert nba["valor"] == "descriptivo" and nba["h_veredicto"] == "RECHAZA" and nba["veredicto_M"] in ("NO VETA", "VETA")
    assert res["por_liga"]["nfl"]["veredicto_M"] == "PRORROGA" and set(res["informes"]) == {"5", "6"}
    assert "nba" in res["paridad_M"] and res["h_C"]["nba"] == 90.0
    # H.json distinto del commiteado -> aborta
    hp.write_text(json.dumps({**h_json, "x": 1}), encoding="utf-8")
    with pytest.raises(SystemExit, match="SHA-256"):
        mod.main(["--fase", "M", "--data-root", str(root), "--h-json", str(hp), "--pre-json", str(pre_p),
                  "--out", str(tmp_path / "M2.json")])


def test_h_c_must_be_in_grid(mod):
    with pytest.raises(SystemExit):
        mod.h_c_of({"por_liga": {"nba": {"h_por_particion": {"C": 17.0}}}}, "nba")
    with pytest.raises(SystemExit):
        mod.h_c_of({}, "nba")
    assert mod.h_c_of({"por_liga": {"nba": {"h_por_particion": {"C": 90.0}}}}, "nba") == 90.0


def test_ambiguity_counter_counts_only_ambiguity_warnings(mod):
    lg = logging.getLogger("sqp.roi_engine")
    with mod.count_ambiguous() as c:
        lg.warning("emparejamiento AMBIGUO omitido: x")
        lg.warning("otra cosa")
    assert c.n == 1
    lg.warning("emparejamiento AMBIGUO omitido: fuera del contexto")
    assert c.n == 1


def test_roi_key_is_the_roi_engine_sort_key(mod):
    rows = [{"date": "2025-06-01", "home": "N", "away": "B", "game_id": "g2", "home_score": 3, "away_score": 1},
            {"date": "2025-06-01", "home": "N", "away": "B", "game_id": "g1", "home_score": 5, "away_score": 2}]
    assert [r["game_id"] for r in sorted(rows, key=mod.roi_key)] == ["g1", "g2"]


# ------------------------------------------------- correcciones F1-F6 (Enmienda 1) --
def _m_files(mod, monkeypatch, tmp_path, h_over=None):
    root = _m_setup(mod, monkeypatch, tmp_path, league="nba", line=224.5)
    monkeypatch.setattr(mod, "git_head", lambda cwd: "deadbeef")
    monkeypatch.setattr(mod, "git_status_porcelain", lambda cwd, paths=None: "")
    monkeypatch.setattr(mod, "M_MIN_N", {"nba": 5, "nhl": 5, "nfl": 5})
    h_json = {"parametros_resueltos": mod.resolved_report(mod.LEAGUES), "codigo_sha256": mod.code_hashes(),
              "por_liga": {lg: {"h_por_particion": {"A": 30.0, "B": 60.0, "C": 90.0}, "veredicto_H": "ACEPTA"}
                           for lg in mod.LEAGUES}}
    h_json.update(h_over or {})
    hp = tmp_path / "H.json"
    hp.write_text(json.dumps(h_json), encoding="utf-8")
    return root, hp, mod.sha256_of(hp)


def test_f1_prorroga_only_measures_prorroga_leagues_and_requires_prev(mod, monkeypatch, tmp_path):
    root, hp, sha = _m_files(mod, monkeypatch, tmp_path)
    pre_d = tmp_path / "pre_D.json"
    base = ["--fase", "M", "--pre", "--data-root", str(root), "--h-json", str(hp), "--h-sha256", sha]
    assert mod.main(base + ["--out", str(pre_d)]) == 0
    d = json.loads(pre_d.read_text(encoding="utf-8"))
    assert d["ligas"]["nba"]["decision"] == "medir" and d["ligas"]["nfl"]["decision"] == "prorroga"
    with pytest.raises(SystemExit, match="obligatorio"):
        mod.main(base + ["--out", str(tmp_path / "x1.json"), "--m-cutoff", "2027-04-20"])
    with pytest.raises(SystemExit, match="solo aplica"):
        mod.main(base + ["--out", str(tmp_path / "x2.json"), "--prev-pre-m", str(pre_d)])
    out_e = tmp_path / "pre_E.json"
    assert mod.main(base + ["--out", str(out_e), "--m-cutoff", "2027-04-20", "--prev-pre-m", str(pre_d)]) == 0
    e = json.loads(out_e.read_text(encoding="utf-8"))
    assert e["ligas"]["nba"]["decision"] == "ya_medida_en_D" and e["ligas"]["nba"]["decision_en_D"] == "medir"
    assert e["ligas"]["nfl"]["decision"] == "no_concluyente"
    assert e["prev_pre_m_sha256"] == mod.sha256_of(pre_d)          # G3: SHA-256 del fichero
    bad = tmp_path / "pre_bad.json"
    bad.write_text(json.dumps({**d, "h_json_sha256": "0" * 64}), encoding="utf-8")
    with pytest.raises(SystemExit, match="no es el pre_M de D"):
        mod.main(base + ["--out", str(tmp_path / "x3.json"), "--m-cutoff", "2027-04-20", "--prev-pre-m", str(bad)])
    res = mod.run_M(root, json.loads(hp.read_text(encoding="utf-8")), e, n_boot=10)
    assert res["por_liga"]["nba"]["veredicto_M"] == "YA MEDIDA EN D"


def test_f1_league_with_h_rejected_gets_no_extension(mod, monkeypatch, tmp_path):
    h_over = {"por_liga": {lg: {"h_por_particion": {"C": 90.0}, "veredicto_H": "RECHAZA"} for lg in mod.LEAGUES}}
    root, hp, sha = _m_files(mod, monkeypatch, tmp_path, h_over)
    out = tmp_path / "pre.json"
    mod.main(["--fase", "M", "--pre", "--data-root", str(root), "--h-json", str(hp), "--h-sha256", sha, "--out", str(out)])
    d = json.loads(out.read_text(encoding="utf-8"))
    assert d["ligas"]["nfl"]["decision"] == "no_medida_descriptivo" and d["ligas"]["nba"]["decision"] == "medir"


def test_f2_existing_out_aborts_in_every_measuring_mode(mod, monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "git_status_porcelain", lambda cwd, paths=None: "")
    o = tmp_path / "o.json"
    o.write_text("{}", encoding="utf-8")
    j = tmp_path / "j.json"
    j.write_text("{}", encoding="utf-8")
    for argv in (["--pre"], ["--fase", "H", "--pre-json", str(j)],
                 ["--fase", "M", "--pre", "--h-json", str(j), "--h-sha256", "1"],
                 ["--fase", "M", "--pre-json", str(j), "--h-json", str(j)]):
        with pytest.raises(SystemExit, match="ya existe"):
            mod.main(argv + ["--data-root", str(tmp_path), "--out", str(o)])
    assert o.read_text(encoding="utf-8") == "{}"


def test_f3_fase_M_aborts_if_n_or_monthly_counts_differ_from_pre(mod, monkeypatch, tmp_path):
    root = _m_setup(mod, monkeypatch, tmp_path, league="nba", line=224.5)
    rows, lp, _ = mod.load_league_cut("nba", root, "2014-12-31")
    odds = mod.load_closing_odds(root, "nba")
    m = mod.m_matches("nba", rows, odds, lp, start=mod.MARKET_START, h_c=None, estimate=False)
    n = len(m["recs"])
    ok = {"n_emparejados_con_linea_y_novig": n, "por_mes": mod.month_table(m["recs"])}
    assert mod.measure_m_league("nba", rows, odds, lp, 90.0, set(), n_boot=10, expect=ok)["n"] == n
    with pytest.raises(SystemExit, match="difieren del --pre"):
        mod.measure_m_league("nba", rows, odds, lp, 90.0, set(), n_boot=10,
                             expect={**ok, "n_emparejados_con_linea_y_novig": n + 1})
    bad_m = dict(ok["por_mes"])
    bad_m["2014-11"] = bad_m.get("2014-11", 0) + 1
    with pytest.raises(SystemExit, match="difieren del --pre"):
        mod.measure_m_league("nba", rows, odds, lp, 90.0, set(), n_boot=10, expect={**ok, "por_mes": bad_m})


def test_f4_code_hashes_recorded_and_pre_M_aborts_if_code_differs(mod, monkeypatch, tmp_path):
    ch = mod.code_hashes()
    assert set(ch) == {"measure_totals_recency.py", "measure_adjustment_battery.py"}
    assert all(len(v) == 64 for v in ch.values())
    root, hp, sha = _m_files(mod, monkeypatch, tmp_path,
                             {"codigo_sha256": {**ch, "measure_totals_recency.py": "0" * 64}})
    with pytest.raises(SystemExit, match="codigo"):
        mod.main(["--fase", "M", "--pre", "--data-root", str(root), "--h-json", str(hp), "--h-sha256", sha,
                  "--out", str(tmp_path / "p.json")])
    man = {"f": {"sha256": "1", "filas": 1}}
    pre = {"git_head": "a", "manifiesto": man, "config_sha256": {}, "parametros_resueltos": {},
           "codigo_sha256": {"x": "1"}}
    with pytest.raises(SystemExit, match="codigo"):
        mod.check_provenance(pre, "a", man, {}, {}, "pre")


def test_g1_code_hashes_ignore_line_endings(mod, monkeypatch, tmp_path):
    src = Path(mod.__file__).resolve().parent
    for crlf in (False, True):
        d = tmp_path / ("crlf" if crlf else "lf")
        d.mkdir()
        for n in ("measure_totals_recency.py", "measure_adjustment_battery.py"):
            b = (src / n).read_bytes().replace(b"\r\n", b"\n")
            (d / n).write_bytes(b.replace(b"\n", b"\r\n") if crlf else b)
    hashes = []
    for sub in ("lf", "crlf"):
        monkeypatch.setattr(mod, "__file__", str(tmp_path / sub / "measure_totals_recency.py"))
        hashes.append(mod.code_hashes())
    assert hashes[0] == hashes[1]


def test_g2_check_provenance_requires_codigo_sha256(mod):
    man = {"f": {"sha256": "1", "filas": 1}}
    pre = {"git_head": "a", "manifiesto": man, "config_sha256": {}, "parametros_resueltos": {}}
    with pytest.raises(SystemExit, match="codigo_sha256"):
        mod.check_provenance(pre, "a", man, {}, {}, "pre")


def test_f4_codigo_sha256_in_pre_H(mod, monkeypatch, tmp_path):
    _patch_meta(mod, monkeypatch)
    root = _write_root(tmp_path)
    runs_ = {lg: mod.LeagueRun(lg, root) for lg in mod.LEAGUES}
    bat_pre = _battery_for_nologic(mod, runs_)
    bat_pre["manifiesto"] = mod.manifest(root, odds=False)
    bat_pre["config_sha256"] = mod.bat.config_hashes()
    monkeypatch.setattr(mod, "load_battery_pre", lambda data_root: bat_pre)
    monkeypatch.setattr(mod, "git_head", lambda cwd: "deadbeef")
    monkeypatch.setattr(mod, "git_status_porcelain", lambda cwd, paths=None: "")
    assert mod.informe_pre_H(root)["codigo_sha256"] == mod.code_hashes()


def test_f5_parity_of_all_leagues_runs_before_any_loss(mod, runs, monkeypatch):
    calls: list[str] = []
    orig = mod.total_loss
    monkeypatch.setattr(mod, "total_loss", lambda *a, **k: (calls.append("loss"), orig(*a, **k))[1])

    def fake_parity(run, outcomes, hs):
        calls.append(f"parity_{run.league}")
        if run.league == "nhl":
            raise SystemExit("PARIDAD 1 ROTA (simulada)")
        return {}

    monkeypatch.setattr(mod, "run_parity", fake_parity)
    monkeypatch.setattr(mod, "load_battery_pre", lambda root: {})
    monkeypatch.setattr(mod, "check_against_battery", lambda *a, **k: {"coincide": True})
    monkeypatch.setattr(mod, "LeagueRun", lambda lg, root: runs[lg])
    with pytest.raises(SystemExit, match="PARIDAD 1 ROTA"):
        mod.run_H(None, None, n_boot=5)
    assert "loss" not in calls and calls == ["parity_nba", "parity_nfl", "parity_nhl"]


def test_f6_quarter_lines_counted(mod, monkeypatch, tmp_path):
    root = _m_setup(mod, monkeypatch, tmp_path, league="nba", line=224.25)
    rows, lp, _ = mod.load_league_cut("nba", root, "2014-12-31")
    odds = mod.load_closing_odds(root, "nba")
    res = mod.measure_m_league("nba", rows, odds, lp, 90.0, set(), n_boot=10)
    assert res["n_lineas_cuarto_sin_paridad4"] == res["n"] > 0
    assert res["paridad_M"]["desviacion_max"] == 0.0
