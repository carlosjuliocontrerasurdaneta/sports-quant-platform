"""Pruebas sinteticas del portero NHL (pre-registro
`docs/research/2026-09-26-preregistro-portero-nhl.md`).

Cubre dos cosas:

1. La IMPLEMENTACION del modelo (`GoalieRatings`, `HockeyAdapter`, `Event`,
   motor): con los valores por defecto la salida es EXACTAMENTE la de hoy, un
   portero desconocido da f = 1, y el proxy/q solo usan fechas estrictamente
   anteriores.
2. El SCRIPT `scripts/research/measure_goalie_nhl.py`: paridad con el motor,
   `--pre` sin columnas de resultado, particiones, E, k, desempates y un
   recorrido completo sobre datos sinteticos.

Ninguna prueba lee `data/` real ni ejecuta ningun modo contra el historico.
"""
from __future__ import annotations

import importlib.util
import sys

import numpy as np
import pandas as pd
import pytest

from sqp.backtesting.engine import walk_forward_backtest
from sqp.config import ROOT
from sqp.domain.models import Event
from sqp.models import distributions as dist
from sqp.models.goalies import GoalieRatings, season_of
from sqp.pipeline.daily import _league_meta
from sqp.sports.adapters import HockeyAdapter, PoissonAdapter
from sqp.sports.registry import get_adapter

SCRIPT = ROOT / "scripts" / "research" / "measure_goalie_nhl.py"


def _load_module():
    sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("measure_goalie_nhl", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_module()


TEAMS = ["Boston Bruins", "Toronto Maple Leafs", "Montreal Canadiens", "New York Rangers",
         "Chicago Blackhawks", "Detroit Red Wings", "Calgary Flames", "Vancouver Canucks"]


def _short(name: str) -> str:
    return name.split()[-1]


def make_world(seasons=(2014, 2015, 2016, 2017), days=40, seed=3, skill_sd=0.03):
    """(results, appearances) sinteticos. 8 equipos, 4 partidos por dia, dos
    porteros por equipo con talento distinto, `goals_against` envenenado."""
    rng = np.random.default_rng(seed)
    skill = {f"G{t}_{j}": rng.normal(0.0, skill_sd) for t in range(8) for j in range(2)}
    results, apps = [], []
    gid = 0
    for s in seasons:
        base = pd.Timestamp(f"{s}-10-01")
        for d in range(days):
            date = (base + pd.Timedelta(days=d)).strftime("%Y-%m-%d")
            order = rng.permutation(8)
            for p in range(4):
                h, a = int(order[2 * p]), int(order[2 * p + 1])
                hs, aws = int(rng.integers(0, 7)), int(rng.integers(0, 7))
                while aws == hs:
                    aws = int(rng.integers(0, 7))
                gid += 1
                results.append({"date": date, "home": TEAMS[h], "away": TEAMS[a],
                                "game_id": str(400000 + gid), "home_score": hs,
                                "away_score": aws, "neutral": False})
                for side, t in (("home", h), ("away", a)):
                    starter = 0 if rng.random() < 0.7 else 1
                    for j in (0, 1):
                        played = j == starter
                        sa = int(rng.integers(20, 38)) if played else None
                        sv = int(rng.binomial(sa, min(0.99, 0.91 + skill[f"G{t}_{j}"]))) if played else None
                        apps.append({
                            "nhl_game_id": f"N{gid}", "espn_game_id": str(400000 + gid),
                            "date": date, "game_type": "2",
                            "start_time_utc": f"{date}T23:00:00Z", "team_side": side,
                            "team_nhl": _short(TEAMS[t]), "matched": True,
                            "goalie_player_id": f"G{t}_{j}", "starter": played,
                            "shots_against": sa, "saves": sv, "goals_against": "POISON",
                            "goalie_name": "POISON", "toi": "POISON"})
    return results, pd.DataFrame(apps)


def nhl_params():
    params = dict(_league_meta("nhl").get("league_params") or {})
    return params, get_adapter("nhl", "hockey", params).params


# ============================================================ implementacion ==
def _fake_rows(n=30):
    rng = np.random.default_rng(1)
    rows = []
    for i in range(n):
        h, a = TEAMS[i % 4], TEAMS[(i + 1) % 4]
        rows.append({"date": f"2015-10-{1 + i // 2:02d}", "home": h, "away": a,
                     "game_id": str(i), "home_score": int(rng.integers(0, 6)),
                     "away_score": int(rng.integers(0, 6)) + 7 * 0, "neutral": False,
                     "home_goalie_appearances": [{"id": "X", "shots_against": 30.0, "saves": 27.0, "starter": True}],
                     "away_goalie_appearances": [{"id": "Y", "shots_against": 30.0, "saves": 28.0, "starter": True}]})
    return rows


class _Plain(PoissonAdapter):
    """Hockey SIN portero: la referencia de 'lo que hace hoy el modelo'."""
    family = "hockey"
    TIE_ADDS_GOAL = True


def test_defaults_are_byte_identical_to_the_model_without_goalies():
    rows = _fake_rows()
    params, _ = nhl_params()
    a = HockeyAdapter("nhl", {**get_adapter("nhl", "hockey", params).params})
    b = _Plain("nhl", {**get_adapter("nhl", "hockey", params).params})
    assert a.goalie_beta == 0.0
    for r in rows:
        a.observe(r)
        b.observe(r)
        ev = Event(event_id="1", sport_key="bt", league="nhl", home=r["home"], away=r["away"],
                   start_time=r["date"])
        assert a._rates(ev) == b._rates(ev)
        ea, eb = a.estimate(ev, -1.5, 5.5), b.estimate(ev, -1.5, 5.5)
        assert ea == eb
    assert not a.goalies.excess and not a.goalies.last_starter   # ni se alimenta


def test_engine_output_is_identical_with_defaults_and_with_goalie_rows():
    """Filas con apariciones y `home_goalie_announced`, beta por defecto: el
    motor devuelve EXACTAMENTE lo mismo que sin ellas."""
    results, _ = make_world(seasons=(2014,), days=15)
    params, _ = nhl_params()
    plain = walk_forward_backtest(results, "nhl", "hockey", params, warmup=5,
                                  spread_lines=(-1.5,), total_lines=(5.5,))
    rich = [dict(r, home_goalie_appearances=[{"id": "Q", "shots_against": 30.0, "saves": 20.0, "starter": True}],
                 away_goalie_appearances=[], home_goalie_announced="Q", away_goalie_announced="Z")
            for r in results]
    with_rows = walk_forward_backtest(rich, "nhl", "hockey", {**params, "goalie_beta": 0.0},
                                      warmup=5, spread_lines=(-1.5,), total_lines=(5.5,))
    assert plain["binary_probs"] == with_rows["binary_probs"]
    assert plain["markets"]["spreads@-1.5"]["probs"] == with_rows["markets"]["spreads@-1.5"]["probs"]
    assert plain["markets"]["totals@5.5"]["probs"] == with_rows["markets"]["totals@5.5"]["probs"]


def test_unknown_goalie_gives_factor_one_and_does_not_block():
    params, _ = nhl_params()
    ad = get_adapter("nhl", "hockey", {**params, "goalie_beta": 1.0, "goalie_prior_shots": 100.0})
    base = _Plain("nhl", dict(get_adapter("nhl", "hockey", params).params))
    ev = Event(event_id="1", sport_key="bt", league="nhl", home=TEAMS[0], away=TEAMS[1],
               start_time="2015-10-05", home_goalie="nunca-visto", away_goalie=None)
    assert ad._rates(ev) == base._rates(ev)           # sin datos de nadie: f = 1
    assert ad.reliability_warning(ev) == base.reliability_warning(ev)


def test_goalie_ratings_hand_computed_and_strictly_prior():
    g = GoalieRatings(prior_shots=10.0)
    app = lambda i, sa, sv, st=True: [{"id": i, "shots_against": sa, "saves": sv, "starter": st}]  # noqa: E731
    g.observe_game("2015-10-01", "A", "B", app("G1", 30, 27), app("G2", 30, 27))
    assert g.quality("G1") == 0.0                       # sin referencia el primer dia ever
    assert g.league_ref("2015-10-02") == pytest.approx(0.9)
    g.observe_game("2015-10-02", "A", "B", app("G1", 20, 19), app("G3", 40, 34))
    # e = 19 - 20*0.9 = 1 ; el 2o goleador del dia 2 usa la MISMA referencia congelada
    assert g.quality("G1") == pytest.approx(1.0 / (20 + 10))
    assert g.quality("G3") == pytest.approx((34 - 40 * 0.9) / (40 + 10))
    assert g.proxy("A") == "G1" and g.proxy("B") == "G3"
    # factor: 1 - beta*q/(1-L), acotado
    f = g.factor("G1", "2015-10-03", 1.0)
    assert f == pytest.approx(1.0 - g.quality("G1") / (1.0 - g.league_ref("2015-10-03")))
    assert g.factor("G1", "2015-10-03", 1e6) == pytest.approx(0.65)
    assert g.factor("G1", "2015-10-03", -1e6) == pytest.approx(1.35)
    # primer dia de temporada: usa la temporada anterior completa
    assert season_of("2016-07-31") == 2015 and season_of("2016-08-01") == 2016
    assert g.league_ref("2016-10-05") == pytest.approx(g.league_ref("2015-12-01"))
    # varios o ningun titular: sin proxy
    g.observe_game("2015-10-04", "A", "B", app("G1", 10, 9) + app("G9", 5, 5), [])
    assert g.proxy("A") is None and g.proxy("B") is None


def test_no_temporal_leak_in_engine_estimates():
    """Perturbar TODO lo que ocurre desde la fecha D (inclusive) no cambia
    ninguna probabilidad estimada para partidos con fecha ESTRICTAMENTE anterior
    a D. La invariancia del propio dia D se prueba aparte
    (`test_engine_probabilities_of_day_d_ignore_day_d_data`)."""
    results, _ = make_world(seasons=(2014,), days=12)
    app_rows, _ = _rows_with_goalies(results)
    params, _ = nhl_params()
    p = {**params, "goalie_beta": 1.7, "goalie_prior_shots": 200.0}
    d0 = "2014-10-08"
    pert = []
    for r in app_rows:
        r = dict(r)
        if r["date"] >= d0:
            r["home_goalie_appearances"] = [dict(a, shots_against=99.0, saves=1.0, id="ZZ")
                                            for a in r["home_goalie_appearances"]]
            r["away_goalie_appearances"] = [dict(a, starter=not a["starter"])
                                            for a in r["away_goalie_appearances"]]
            r["home_goalie_announced"] = "ZZ"
        pert.append(r)
    ref = walk_forward_backtest(app_rows, "nhl", "hockey", p, warmup=0)
    alt = walk_forward_backtest(pert, "nhl", "hockey", p, warmup=0)
    n_prev = sum(1 for r in app_rows if r["date"] < d0)
    assert n_prev > 20
    assert ref["binary_probs"][:n_prev] == alt["binary_probs"][:n_prev]


def test_engine_probabilities_of_day_d_ignore_day_d_data():
    """M2 (sin `*_goalie_announced`): perturbar las apariciones Y los marcadores
    de los partidos del propio dia D no cambia ninguna probabilidad de ese dia
    (el motor predice el dia contra el cierre del anterior); la perturbacion
    SI mueve los dias posteriores (la prueba no es vacua)."""
    results, _ = make_world(seasons=(2014,), days=12)
    app_rows, _ = _rows_with_goalies(results)
    for r in app_rows:
        r.pop("home_goalie_announced"), r.pop("away_goalie_announced")
    params, _ = nhl_params()
    p = {**params, "goalie_beta": 1.7, "goalie_prior_shots": 200.0}
    d0 = "2014-10-08"
    pert = []
    for r in app_rows:
        r = dict(r)
        if r["date"] == d0:
            r["home_goalie_appearances"] = [dict(a, shots_against=99.0, saves=1.0, id="ZZ")
                                            for a in r["home_goalie_appearances"]]
            r["away_goalie_appearances"] = [dict(a, shots_against=10.0, saves=10.0, id="YY")
                                            for a in r["away_goalie_appearances"]]
            r["home_score"], r["away_score"] = r["away_score"], r["home_score"]
        pert.append(r)
    ref = walk_forward_backtest(app_rows, "nhl", "hockey", p, warmup=0)
    alt = walk_forward_backtest(pert, "nhl", "hockey", p, warmup=0)
    n_le = sum(1 for r in app_rows if r["date"] <= d0)
    n_d = sum(1 for r in app_rows if r["date"] == d0)
    assert n_d >= 2 and len(ref["binary_probs"]) == len(app_rows)
    assert ref["binary_probs"][:n_le] == alt["binary_probs"][:n_le]
    assert ref["binary_probs"][n_le:] != alt["binary_probs"][n_le:]


def _rows_with_goalies(results):
    """Filas con apariciones sinteticas deterministas (sin DataFrame)."""
    rng = np.random.default_rng(11)
    out = []
    for r in results:
        d = dict(r)
        for side in ("home", "away"):
            t = d[side]
            gid = f"{t[:3]}{int(rng.integers(0, 2))}"
            sa = float(rng.integers(20, 38))
            d[f"{side}_goalie_appearances"] = [
                {"id": gid, "shots_against": sa, "saves": float(rng.binomial(int(sa), 0.9)),
                 "starter": True}]
        d["home_goalie_announced"] = d["home_goalie_appearances"][0]["id"]
        d["away_goalie_announced"] = d["away_goalie_appearances"][0]["id"]
        out.append(d)
    return out, None


# ================================================================== script ==
def test_pricing_vectorized_matches_scalar_engine(mod):
    rng = np.random.default_rng(5)
    lh = rng.uniform(1.8, 4.2, 40)
    la = rng.uniform(1.8, 4.2, 40)
    for tie in (True, False):
        mg, tt = mod.score_dists(lh, la, tie_adds_goal=tie)
        for i in range(len(lh)):
            sc = dist.poisson_match_probs(float(lh[i]), float(la[i]), -1.5, 5.5, max_goals=15,
                                          tie_adds_goal=tie)
            assert mod.p_home_from(mg)[i] == pytest.approx(sc["home_win"], abs=1e-12)
            assert mod.p_cover_from(mg, -1.5)[i] == pytest.approx(sc["home_cover"], abs=1e-12)
            assert mod.p_over_from(tt, 5.5)[i] == pytest.approx(sc["over"], abs=1e-12)
            sc2 = dist.poisson_match_probs(float(lh[i]), float(la[i]), 1.5, 6.5, max_goals=15,
                                           tie_adds_goal=tie)
            assert mod.p_cover_from(mg, 1.5)[i] == pytest.approx(sc2["home_cover"], abs=1e-12)
            assert mod.p_over_from(tt, 6.5)[i] == pytest.approx(sc2["over"], abs=1e-12)
    assert mod.p_home_fast(lh, la) == pytest.approx(mod.p_home_from(mod.score_dists(lh, la)[0]), abs=1e-12)


def _frame(mod, world, with_outcomes=True, failed=()):
    results, app = world
    mod.WARMUP = 5
    params, rparams = nhl_params()
    rows2, rows1, info = mod.attach_goalies(results, app)
    fr = mod.build_frame(rows2, params, rparams, list(failed), with_outcomes)
    return rows2, rows1, info, fr, params, rparams


@pytest.fixture
def small_mod(mod, monkeypatch):
    monkeypatch.setattr(mod, "WARMUP", 5)
    return mod


@pytest.mark.slow
def test_parity_with_engine_for_arbitrary_beta_and_k(small_mod):
    mod = small_mod
    world = make_world(seasons=(2014,), days=12)
    rows2, rows1, _, fr, params, rparams = _frame(mod, world)
    for beta, k in ((1.3, 1500.0), (-0.7, 200.0)):
        mod.assert_parity(rows2, rows1, params, rparams, fr, beta, k, label="test")
    # y el brazo T realmente se mueve (la prueba no es vacua)
    lh, la = mod.treat_lambdas(fr, "M2", 1500.0, 1.3)
    assert not np.allclose(lh, fr["lam_h"].to_numpy())


@pytest.mark.slow
def test_parity_detects_a_broken_reconstruction(small_mod):
    mod = small_mod
    world = make_world(seasons=(2014,), days=10)
    rows2, rows1, _, fr, params, rparams = _frame(mod, world)
    broken = fr.copy()
    broken["h2_num"] = broken["h2_num"] + 5.0
    with pytest.raises(SystemExit):
        mod.assert_parity(rows2, rows1, params, rparams, broken, 1.3, 800.0)


def test_goalie_state_matches_adapter_state_and_is_strictly_prior(small_mod):
    mod = small_mod
    world = make_world(seasons=(2014,), days=10)
    rows2, _, _, fr, params, rparams = _frame(mod, world)
    ad = get_adapter("nhl", "hockey", {**params, "goalie_beta": 1.0, "goalie_prior_shots": 77.0})
    pending, cur = [], None
    for i, r in enumerate(rows2):
        if pending and r["date"] != cur:
            for done in pending:
                ad.observe(done)
            pending.clear()
        cur = r["date"]
        if i >= mod.WARMUP:
            row = fr[fr["idx"] == i].iloc[0]
            gid = ad.goalies.proxy(ad.normalize(r["home"]))
            assert gid == (row["h2_id"] if isinstance(row["h2_id"], str) else None)
            if gid is not None:
                q = mod.q_of(np.array([row["h2_num"]]), np.array([row["h2_den"]]), 77.0)[0]
                assert q == pytest.approx(ad.goalies.quality(gid), abs=1e-12)
            ref = ad.goalies.league_ref(r["date"])
            assert (ref is None and np.isnan(row["ref"])) or ref == pytest.approx(row["ref"])
        pending.append(r)


def test_pre_frame_has_no_outcome_columns_and_loader_never_asks_for_result_columns(small_mod, monkeypatch, tmp_path):
    mod = small_mod
    world = make_world(seasons=(2014,), days=10)
    _, _, _, fr, _, _ = _frame(mod, world, with_outcomes=False)
    for col in ("y", "margin", "total", "home_score", "away_score"):
        assert col not in fr.columns
    # El cargador de porteros pide SOLO sus columnas: goals_against/name/toi nunca.
    p = tmp_path / "goalies.csv"
    world[1].to_csv(p, index=False)
    seen = {}
    real = pd.read_csv

    def spy(*a, **kw):
        seen["usecols"] = kw.get("usecols")
        return real(*a, **kw)
    monkeypatch.setattr(pd, "read_csv", spy)
    app = mod.read_appearances(p)
    assert set(seen["usecols"]).isdisjoint(mod.FORBIDDEN_COLS)
    assert "goals_against" not in app.columns and "goalie_name" not in app.columns
    assert set(app.columns) == set(mod.APP_USECOLS)


def test_pre_fails_if_a_forbidden_column_is_accessed(small_mod, tmp_path):
    """Un CSV sin goals_against/goalie_name/toi funciona igual: no se necesitan."""
    mod = small_mod
    world = make_world(seasons=(2014,), days=8)
    p = tmp_path / "g.csv"
    world[1].drop(columns=["goals_against", "goalie_name", "toi"]).to_csv(p, index=False)
    assert len(mod.read_appearances(p)) == len(world[1])


def test_pre_report_end_to_end_on_a_frozen_snapshot(small_mod, monkeypatch, tmp_path):
    mod = small_mod
    results, app = make_world(seasons=(2014, 2015), days=25)
    hist = tmp_path / "data" / "historical"
    hist.mkdir(parents=True)
    pd.DataFrame(results).assign(ingested_at="2026-01-01T00:00:00+00:00").to_csv(
        hist / "results_nhl.csv", index=False)
    app.to_csv(hist / "goalies_nhl.csv", index=False)
    (hist / ".goalies_nhl_backfill_failed_dates.json").write_text(
        '{"failed": [{"date": "2014-10-20", "kind": "score_http", "http_status": 500, '
        '"season_phase": "regular_season"}]}', encoding="utf-8")
    (hist / ".goalies_nhl_backfill_checkpoint.json").write_text("{}", encoding="utf-8")
    fold = {"A": {"train_end": "2014-10-10", "test_start": "2014-10-11", "test_end": "2015-10-31"},
            "B": {"train_end": "2015-10-31", "test_start": "2015-11-01", "test_end": "2015-11-30"},
            "C": {"train_end": "2015-11-15", "test_start": "2015-11-16", "test_end": "2015-12-31"}}
    monkeypatch.setattr(mod, "FOLDS", fold)
    monkeypatch.setattr(mod, "SIGMAS_Q", (0.004,))
    out = mod.informe_pre(tmp_path)
    assert out["hashes"]["goalies_nhl.csv"]["sha256"]
    assert out["E"]["n_fechas"] == 1 and out["E"]["E1_filas"] == 4
    assert out["E"]["E2_filas"] > 0
    assert set(out["particiones"]) == {"A", "B", "C"}
    assert out["particiones"]["A"]["k_momentos"]["k"] is not None
    assert "M1" in out["particiones"]["A"] and "M2" in out["particiones"]["A"]
    text = mod._dump(out)
    for banned in ("delta_ll", "log_loss", "veredicto", "POISON"):
        assert banned not in text
    # los recuentos con E son menores que sin E
    assert (out["recuentos_seccion_10_con_E"]["combinado"]["n_test"]
            < out["recuentos_seccion_10_sin_E"]["combinado"]["n_test"])


def test_folds_are_the_preregistered_partitions(mod):
    assert mod.FOLDS == {
        "A": {"train_end": "2014-09-30", "test_start": "2014-10-01", "test_end": "2018-09-30"},
        "B": {"train_end": "2018-09-30", "test_start": "2018-10-01", "test_end": "2022-09-30"},
        "C": {"train_end": "2022-09-30", "test_start": "2022-10-01", "test_end": "2026-06-30"}}
    prev_end = None
    for f in mod.FOLDS.values():
        assert f["train_end"] < f["test_start"] <= f["test_end"]
        if prev_end is not None:
            assert f["test_start"] > prev_end            # tests sin solape
        prev_end = f["test_end"]
    assert (mod.N_BOOT, mod.SEED, mod.BOUND) == (10_000, 42, 0.35)
    assert mod.rmnhl.NM_OPTS == {"xatol": 1e-7, "fatol": 1e-10, "maxiter": 2000}


def test_fold_masks_are_strictly_temporal(mod):
    fr = pd.DataFrame({"date": ["2014-09-30", "2014-10-01", "2018-09-30", "2018-10-01"]})
    tr, te = mod.fold_masks(fr, mod.FOLDS["A"])
    assert tr.tolist() == [True, False, False, False]
    assert te.tolist() == [False, True, True, False]
    assert not (tr & te).any()


def test_exclusion_set_rule_e1_e2(mod):
    dates = ["2015-01-01", "2015-01-02", "2015-01-03", "2015-01-04", "2015-01-05"]
    home = [TEAMS[0], TEAMS[2], TEAMS[0], TEAMS[2], TEAMS[0]]
    away = [TEAMS[1], TEAMS[3], TEAMS[2], TEAMS[1], TEAMS[3]]
    e1, e2 = mod.exclusion_set(dates, home, away, ["2015-01-02"])
    assert e1.tolist() == [False, True, False, False, False]
    # Rangers (TEAMS[3]) jugaron el 02 (E1) y su siguiente partido es el 05; Canadiens (2) el 03
    assert e2.tolist() == [False, False, True, False, True]


def test_k_moments_zero_talent_variance_rejects_and_heterogeneity_gives_k(mod):
    apps = pd.DataFrame({"id": ["a", "b", "c", "d"] * 2, "season": [2014] * 4 + [2015] * 4,
                         "date": ["2014-11-01"] * 4 + ["2015-11-01"] * 4,
                         "sa": [1000.0] * 8, "sv": [900.0] * 8})
    km = mod.k_moments(apps, "2016-01-01")
    assert km["tau2"] < 0 and km["k"] is None                  # V = 0 < B
    apps["sv"] = [850.0, 950.0, 880.0, 920.0] * 2               # talento muy disperso
    km2 = mod.k_moments(apps, "2016-01-01")
    assert km2["tau2"] > 0 and km2["k"] > 0
    assert km2["k"] == pytest.approx(km2["L_global"] * (1 - km2["L_global"]) / km2["tau2"])
    # solo apariciones del entrenamiento
    assert mod.k_moments(apps, "2014-12-31")["n_unidades"] == 4


def test_assign_appearances_tiebreak_duplicates_by_order(mod):
    ordered = [{"date": "2016-04-15", "home": "New York Islanders", "away": "Florida Panthers", "game_id": "400900002"},
               {"date": "2016-04-15", "home": "New York Islanders", "away": "Florida Panthers", "game_id": "400900001"},
               {"date": "2016-04-16", "home": "Boston Bruins", "away": "Detroit Red Wings", "game_id": "5"}]
    rows = []
    for gid, start in (("N2", "2016-04-15T23:00:00Z"), ("N1", "2016-04-15T20:00:00Z")):
        for side, team in (("home", "Islanders"), ("away", "Panthers")):
            rows.append({"nhl_game_id": gid, "espn_game_id": "", "date": "2016-04-15", "game_type": "3",
                         "start_time_utc": start, "team_side": side, "team_nhl": team, "matched": False,
                         "goalie_player_id": f"{gid}{side}", "starter": True,
                         "shots_against": 20.0, "saves": 18.0})
    for side, team in (("home", "Bruins"), ("away", "Flyers")):          # no existe en el historico
        rows.append({"nhl_game_id": "N3", "espn_game_id": "", "date": "2016-04-16", "game_type": "2",
                     "start_time_utc": "2016-04-16T23:00:00Z", "team_side": side, "team_nhl": team,
                     "matched": False, "goalie_player_id": f"N3{side}", "starter": True,
                     "shots_against": 20.0, "saves": 18.0})
    assigned, info = mod.assign_appearances(ordered, pd.DataFrame(rows))
    # el mas temprano (N1) se empareja con el game_id de ESPN mas bajo (400900001 = posicion 1)
    assert assigned == {"N1": 1, "N2": 0}
    assert info["desempatados_por_orden"] == 2
    assert [u["home_nhl"] for u in info["sin_emparejar"]] == ["Bruins"]
    assert "goalie_name" not in str(info)


def test_base_params_assertion_rejects_old_tilt(mod, monkeypatch):
    mod.check_base_params(nhl_params()[0])                       # la base vigente pasa
    with pytest.raises(ValueError):
        mod.check_base_params({**nhl_params()[0], "tilt_scale": 0.9})
    with pytest.raises(ValueError):
        mod.check_base_params({**nhl_params()[0], "goalie_beta": 0.5})
    with pytest.raises(ValueError):
        mod.check_base_params({**nhl_params()[0], "rest_elo_per_day": 2.0})


def test_verdict_table(mod):
    assert mod._veredicto(True, False) == "ACEPTA"
    assert mod._veredicto(True, True) == "ACEPTA"
    assert mod._veredicto(False, True).startswith("RECHAZA, con senal")
    assert mod._veredicto(False, False) == "RECHAZA"


@pytest.mark.slow
def test_full_run_on_synthetic_data_end_to_end(small_mod, monkeypatch, tmp_path):
    mod = small_mod
    monkeypatch.setattr(mod, "N_BOOT", 60)
    monkeypatch.setattr(mod.rmnhl, "N_BOOT", 60)
    fold = {"A": {"train_end": "2014-11-30", "test_start": "2015-10-01", "test_end": "2015-11-30"},
            "B": {"train_end": "2015-11-30", "test_start": "2016-10-01", "test_end": "2016-11-30"},
            "C": {"train_end": "2016-11-30", "test_start": "2017-10-01", "test_end": "2017-11-30"}}
    monkeypatch.setattr(mod, "FOLDS", fold)
    results, app = make_world(seasons=(2014, 2015, 2016, 2017), days=16, skill_sd=0.05)
    params, rparams = nhl_params()
    app = app.drop(columns=["goals_against", "goalie_name", "toi"])
    out = mod.run_nhl(results, params, rparams, app, [], tmp_path)
    assert out["veredicto"] in ("ACEPTA", "RECHAZA", "RECHAZA, con senal en la cota superior")
    for arm in ("M1", "M2"):
        assert set(out[arm]["criterios"]) == {
            "1_delta_afectados_combinado_le_-0.002", "2_delta_afectados_negativo_en_cada_particion",
            "3_ece_T_no_empeora", "4_beta_positivo_en_las_tres_particiones", "5_T_bate_control",
            "6a_totales_no_empeora", "6b_spreads_no_empeora"}
        assert set(out[arm]["folds"]) == {"A", "B", "C"}
        assert out[arm]["combinado"]["bootstrap_delta_afectados"]["n_dias"] > 0
        for name, sec in out[arm]["secundarios"].items():
            assert sec is None or "error" not in sec or name == "9_linea_capturada", (name, sec)


def test_main_requires_pre_json_for_the_full_mode(mod, monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["x", "--out", str(tmp_path / "o.json")])
    with pytest.raises(SystemExit) as e:
        mod.main()
    assert e.value.code == 2
    monkeypatch.setattr(sys, "argv", ["x", "--pre", "--parity-only"])
    with pytest.raises(SystemExit) as e2:
        mod.main()
    assert e2.value.code == 2


def test_hash_and_head_mismatch_abort_the_full_mode(mod):
    now = {k: {"sha256": "a"} for k in ("results_nhl.csv", "goalies_nhl.csv", "failed_dates",
                                        "checkpoint", "ratings.yaml")}
    now["odds_cierre_nhl"] = {}
    pre = {"hashes": dict(now), "git_head": "h", "git_status_porcelain": "",
           "parametros_resueltos": {"a": 1}, "E": {"lista_E_posiciones": [1, 2]}}
    mod._check_pre_provenance(pre, now, "h", {"a": 1}, [1, 2])         # coincide: no aborta
    bad = {**now, "goalies_nhl.csv": {"sha256": "b"}}
    for args in ((pre, bad, "h", {"a": 1}, [1, 2]), (pre, now, "x", {"a": 1}, [1, 2]),
                 (pre, now, "h", {"a": 2}, [1, 2]), (pre, now, "h", {"a": 1}, [1])):
        with pytest.raises(SystemExit):
            mod._check_pre_provenance(*args)
    with pytest.raises(SystemExit):
        mod._check_git_clean(" M src/x.py\n")


# ============================================ arreglos de la revision Fable ==
def _folds_all(mod, monkeypatch):
    monkeypatch.setattr(mod, "FOLDS", {
        "A": {"train_end": "2014-10-02", "test_start": "2014-10-03", "test_end": "2014-11-05"},
        "B": {"train_end": "2014-11-05", "test_start": "2014-11-06", "test_end": "2014-11-08"},
        "C": {"train_end": "2014-11-08", "test_start": "2014-11-09", "test_end": "2014-12-31"}})


def test_cobertura_reports_measured_preseason_counts_not_a_fixed_claim(small_mod, monkeypatch):
    mod = small_mod
    _folds_all(mod, monkeypatch)
    results, app = make_world(seasons=(2014,), days=10)
    first = {r["game_id"] for r in results if r["date"] == "2014-10-01"}
    for r in results:
        if r["game_id"] in first:
            r["date"] = "2014-09-30"                       # septiembre CON apariciones
    app = app.copy()
    app.loc[app["espn_game_id"].isin(first), "date"] = "2014-09-30"
    app.loc[app.index[10:14], "game_type"] = "1"
    app.loc[app.index[20:23], "game_type"] = None
    rows2, _, _, fr, _, _ = _frame(mod, (results, app))
    cob = mod._cobertura(rows2, fr, app)
    want = app["game_type"].fillna("<nulo>").value_counts().to_dict()
    assert cob["apariciones_por_game_type"] == want and want["<nulo>"] == 3
    assert cob["filas_historico_septiembre"] == 4
    assert cob["filas_historico_septiembre_con_apariciones"] == 4
    assert "no lista la pretemporada" not in mod._dump(cob)


def test_matched_without_unique_row_and_test_rows_without_appearances_are_listed_by_name(small_mod, monkeypatch):
    mod = small_mod
    _folds_all(mod, monkeypatch)
    results, app = make_world(seasons=(2014,), days=10)
    victim = results[29]
    gone = app["nhl_game_id"] == "N30"                     # sin apariciones en este partido
    app = app[~gone].reset_index(drop=True)
    ghost = app[app["nhl_game_id"] == "N31"].copy()        # matched=True pero su ESPN id no existe
    ghost["nhl_game_id"], ghost["espn_game_id"] = "NG", "999999"
    app2 = pd.concat([app, ghost], ignore_index=True)
    rows2, _, info, fr, _, _ = _frame(mod, (results, app2))
    assert info["matched_sin_fila_unica_en_historico"] == 1
    lst = info["matched_sin_fila_unica_lista"]
    assert len(lst) == 1 and lst[0]["date"] == ghost["date"].iloc[0]
    assert {lst[0]["home_nhl"], lst[0]["away_nhl"]} == set(ghost["team_nhl"])
    cob = mod._cobertura(rows2, fr, app2)
    listed = [e for p in cob["por_particion"].values() for e in p["filas_sin_apariciones_lista"]]
    mine = [e for e in listed if (e["date"], e["home"], e["away"]) ==
            (victim["date"], victim["home"], victim["away"])]
    assert len(mine) == 1 and mine[0]["n_apariciones_local"] == 0 == mine[0]["n_apariciones_visitante"]
    assert "goalie_name" not in str(cob)


def test_assign_appearances_separates_tied_groups_from_individual_rescues(mod):
    ordered = [{"date": "2016-04-15", "home": "New York Islanders", "away": "Florida Panthers", "game_id": "400900002"},
               {"date": "2016-04-15", "home": "New York Islanders", "away": "Florida Panthers", "game_id": "400900001"},
               {"date": "2016-04-16", "home": "Boston Bruins", "away": "Detroit Red Wings", "game_id": "5"}]
    rows = []
    for gid, d, start, h, a in (("N2", "2016-04-15", "2016-04-15T23:00:00Z", "Islanders", "Panthers"),
                                ("N1", "2016-04-15", "2016-04-15T20:00:00Z", "Islanders", "Panthers"),
                                ("N3", "2016-04-16", "2016-04-16T23:00:00Z", "Bruins", "Red Wings")):
        for side, team in (("home", h), ("away", a)):
            rows.append({"nhl_game_id": gid, "espn_game_id": "", "date": d, "game_type": "2",
                         "start_time_utc": start, "team_side": side, "team_nhl": team, "matched": False,
                         "goalie_player_id": f"{gid}{side}", "starter": True,
                         "shots_against": 20.0, "saves": 18.0})
    assigned, info = mod.assign_appearances(ordered, pd.DataFrame(rows))
    assert assigned == {"N1": 1, "N2": 0}                       # el individual NO se une (Enmienda 5)
    assert info["desempatados_por_orden"] == 2
    assert info["desempatados_en_grupos_de_2_o_mas"] == 2
    assert info["individuales_no_asignados"] == 1
    assert [u["home_nhl"] for u in info["sin_emparejar"]] == ["Bruins"]
    assert info["sin_emparejar"][0]["motivo"] == mod.MOTIVO_INDIVIDUAL


def test_sin_pretemporada_report_adds_game_type_concordance(mod):
    t = pd.DataFrame({"date": ["2015-09-20", "2015-09-21", "2015-10-05", "2015-10-06", "2015-09-22"],
                      "game_type": ["1", "2", "2", None, "1"],
                      "aff": [True, True, True, True, False],
                      "t_ml": [0.6] * 5, "b_ml": [0.5] * 5})
    y = np.array([1.0, 0.0, 1.0, 1.0, 0.0])
    out = mod._informe_sin_pretemporada(t, y)
    assert out["n"] == 2 and out["delta_ll_afectados"] is not None      # estimacion por mes intacta
    c = out["concordancia_con_game_type"]
    assert c["n_con_game_type"] == 4 and c["coinciden"] == 3 and c["difieren"] == 1
    assert c["sin_game_type"] == 1 and c["afectados_difieren"] == 1


def test_exclusion_sides_split_e2_by_team_side_and_match_exclusion_set(mod):
    dates = ["2015-01-01", "2015-01-02", "2015-01-03", "2015-01-04", "2015-01-05"]
    home = [TEAMS[0], TEAMS[2], TEAMS[0], TEAMS[2], TEAMS[3]]
    away = [TEAMS[1], TEAMS[3], TEAMS[2], TEAMS[1], TEAMS[0]]
    e1, e2 = mod.exclusion_set(dates, home, away, ["2015-01-02"])
    e2h, e2a = mod.exclusion_sides(dates, home, away, ["2015-01-02"])
    assert (e2h | e2a).tolist() == e2.tolist() and e2.any()
    assert e2a[2] and not e2h[2]            # Canadiens (TEAMS[2]) visitantes el 03
    assert e2h[4] and not e2a[4]            # Rangers (TEAMS[3]) locales el 05


def test_safe_informe_catches_exceptions_only_so_systemexit_aborts(small_mod):
    """Pre-registro 7: si `fit` no converge el script ABORTA (precedente
    measure_rest_nhl._safe_informe: solo `Exception`)."""
    mod = small_mod

    def boom():
        raise ValueError("informe roto")

    def no_converge():
        raise SystemExit("no convergio")
    res = mod._safe_informe("x", boom)
    assert res is not None and "informe roto" in res["error"]
    assert mod._safe_informe("ok", lambda: {"a": 1}) == {"a": 1}
    with pytest.raises(SystemExit):
        mod._safe_informe("x", no_converge)
    assert mod._safe_informe is mod.rmnhl._safe_informe


def test_blank_goalie_player_id_is_treated_as_no_id(small_mod, tmp_path):
    mod = small_mod
    results, app = make_world(seasons=(2014,), days=8)
    app = app.copy()
    i = app.index[(app["nhl_game_id"] == "N10") & (app["team_side"] == "home") & app["starter"]][0]
    app.loc[i, "goalie_player_id"] = ""
    p = tmp_path / "g.csv"
    app.to_csv(p, index=False)
    loaded = mod.read_appearances(p)
    rows2, rows1, _ = mod.attach_goalies(results, loaded)
    ids = [a["id"] for r in rows2 for a in r["home_goalie_appearances"] + r["away_goalie_appearances"]]
    assert all(x is None or isinstance(x, str) for x in ids) and ids.count(None) == 1
    assert rows1[9]["home_goalie_announced"] is None
    assert mod.appearance_table(rows2)["id"].map(lambda x: isinstance(x, str)).all()


@pytest.mark.slow
def test_parity_failure_messages_do_not_reveal_beta(small_mod):
    mod = small_mod
    world = make_world(seasons=(2014,), days=10)
    rows2, rows1, _, fr, params, rparams = _frame(mod, world)
    broken = fr.copy()
    broken["h2_num"] = broken["h2_num"] + 5.0
    with pytest.raises(SystemExit) as e:
        mod.assert_parity(rows2, rows1, params, rparams, broken, 1.2345, 800.0)
    assert "1.2345" not in str(e.value) and "beta=" not in str(e.value)


def test_data_root_must_be_explicit_and_not_the_live_root_outside_parity_only(mod, monkeypatch, tmp_path):
    out = tmp_path / "o.json"
    pre = tmp_path / "pre.json"
    cases = [["--pre", "--out", str(out)],                                       # sin --data-root
             ["--pre", "--out", str(out), "--data-root", str(mod.DEFAULT_ROOT)],  # raiz viva
             ["--out", str(out), "--pre-json", str(pre)],
             ["--out", str(out), "--pre-json", str(pre), "--data-root", str(mod.DEFAULT_ROOT)]]
    for argv in cases:
        monkeypatch.setattr(sys, "argv", ["x", *argv])
        with pytest.raises(SystemExit) as e:
            mod.main()
        assert e.value.code == 2, argv
    out.write_text("{}", encoding="utf-8")                                       # --out ya existe
    monkeypatch.setattr(sys, "argv", ["x", "--out", str(out), "--pre-json", str(pre),
                                      "--data-root", str(tmp_path)])
    with pytest.raises(SystemExit) as e:
        mod.main()
    assert e.value.code == 2
    # reglas puras: parity-only conserva el default; un data-root ajeno y explicito pasa.
    ns = lambda **k: type("NS", (), k)()  # noqa: E731
    assert mod._data_root_error(ns(pre=False, parity_only=True, data_root=None, out=None)) is None
    assert mod._data_root_error(ns(pre=True, parity_only=False, data_root=tmp_path, out=out)) is None


def test_informe_linea_capturada_declares_its_scope_is_test_c(small_mod, monkeypatch, tmp_path):
    mod = small_mod
    ids = ["1", "2"]
    monkeypatch.setattr(mod, "captured_lines_root", lambda rows, root: {
        "spreads": {"1": -1.5, "2": -1.5}, "totals": {"1": 5.5, "2": 5.5}, "ids": set(ids), "sha": {}})
    tc = pd.DataFrame({"game_id": ids, "lam_h": [3.1, 2.9], "lam_a": [2.8, 3.0], "y": [1.0, 0.0],
                       "margin": [2, -1], "total": [6, 5]})
    lam_t = (np.array([3.0, 3.0]), np.array([2.9, 2.9]))
    out = mod.informe_linea_capturada([], tc, lam_t, tmp_path, {"max_score": 15})
    assert out is not None and "particion C" in out["alcance"] and "test C" in out["alcance"]


# ====================================================== ronda 2 de arreglos ==
def test_clean_id_direct(mod):
    assert mod._clean_id("8478403.0") == "8478403.0"
    assert mod._clean_id(" 8478403 ") == "8478403"
    for v in ("", "  ", float("nan"), pd.NA, None):
        assert mod._clean_id(v) is None


def test_exclusion_sides_both_sides_case(mod):
    # Rangers (3) y Canadiens (2) juegan el 02 (E1) y se enfrentan el 03: la fila es E2 por ambos lados.
    dates = ["2015-01-02", "2015-01-02", "2015-01-03"]
    home = [TEAMS[2], TEAMS[3], TEAMS[2]]
    away = [TEAMS[0], TEAMS[1], TEAMS[3]]
    e2h, e2a = mod.exclusion_sides(dates, home, away, ["2015-01-02"])
    assert e2h[2] and e2a[2]
    e1, e2 = mod.exclusion_set(dates, home, away, ["2015-01-02"])
    assert e2.tolist() == (e2h | e2a).tolist()


def test_game_type_is_compared_numerically(mod):
    t = pd.DataFrame({"date": ["2015-09-20", "2015-09-21", "2015-10-05", "2015-10-06"],
                      "game_type": ["1.0", "2.0", "2", "1"],
                      "aff": [True, True, True, True], "t_ml": [0.6] * 4, "b_ml": [0.5] * 4})
    c = mod._informe_sin_pretemporada(t, np.array([1.0, 0.0, 1.0, 1.0]))["concordancia_con_game_type"]
    assert c["n_con_game_type"] == 4 and c["coinciden"] == 2 and c["difieren"] == 2
    assert c["game_type_1_pero_no_septiembre"] == 1
    assert mod._game_type_label("1.0") == "1" and mod._game_type_label("2") == "2"
    assert mod._game_type_label(None) == "<nulo>" and mod._game_type_label(float("nan")) == "<nulo>"


def test_cobertura_groups_game_type_numerically_and_counts_idless_appearances(small_mod, monkeypatch):
    mod = small_mod
    _folds_all(mod, monkeypatch)
    results, app = make_world(seasons=(2014,), days=10)
    app = app.copy()
    app["game_type"] = app["game_type"].astype(object)
    app.loc[app.index[:6], "game_type"] = "2.0"
    app.loc[app.index[6:9], "game_type"] = "1.0"
    played = app.index[app["shots_against"].notna()][:2]
    app.loc[played, "goalie_player_id"] = None
    rows2, _, _, fr, _, _ = _frame(mod, (results, app))
    cob = mod._cobertura(rows2, fr, app)
    assert cob["apariciones_por_game_type"]["1"] == 3 and "1.0" not in cob["apariciones_por_game_type"]
    assert cob["apariciones_con_tiros_y_paradas_sin_goalie_player_id"] == 2


def test_e2_breakdown_by_game_type_is_numeric(mod):
    e2 = pd.DataFrame({"game_type": ["1.0", "2", None, "2.0"]})
    assert mod._e2_por_game_type(e2) == {"1": 1, "2": 2, "<nulo>": 1}


def test_data_root_rejects_any_git_checkout(mod, tmp_path):
    ns = lambda **k: type("NS", (), k)()  # noqa: E731
    root = tmp_path / "snap"
    root.mkdir()
    args = ns(pre=True, parity_only=False, data_root=root, out=tmp_path / "o.json")
    assert mod._data_root_error(args) is None
    (root / ".git").mkdir()
    assert mod._data_root_error(args) is not None                 # directorio
    (root / ".git").rmdir()
    (root / ".git").write_text("gitdir: elsewhere", encoding="utf-8")
    assert mod._data_root_error(args) is not None                 # fichero (worktree)
    assert mod._data_root_error(ns(pre=True, parity_only=True, data_root=root, out=None)) is None


def test_hockey_adapter_distinguishes_not_informed_from_declared_unknown():
    params, _ = nhl_params()
    ad = get_adapter("nhl", "hockey", {**params, "goalie_beta": 1.0, "goalie_prior_shots": 100.0})
    base = _Plain("nhl", dict(get_adapter("nhl", "hockey", params).params))
    for r in _fake_rows(24):
        ad.observe(r)
        base.observe(r)
    ev = dict(event_id="1", sport_key="bt", league="nhl", home=TEAMS[0], away=TEAMS[1],
              start_time="2015-10-20")
    assert ad.goalies.proxy(ad.normalize(TEAMS[0])) is not None
    assert ad.goalies.proxy(ad.normalize(TEAMS[1])) is not None
    # None = no informado: se aplica el proxy
    assert ad._rates(Event(**ev)) != base._rates(Event(**ev))
    # "" = desconocido declarado: lambdas de base aunque haya proxy
    assert ad._rates(Event(**ev, home_goalie="", away_goalie="")) == base._rates(Event(**ev))
    only_home = ad._rates(Event(**ev, home_goalie=""))
    only_away = ad._rates(Event(**ev, away_goalie=""))
    full = ad._rates(Event(**ev))
    assert only_home[1] == base._rates(Event(**ev))[1] and only_home[0] == full[0]
    assert only_away[0] == base._rates(Event(**ev))[0] and only_away[1] == full[1]


def test_exhibition_vs_non_nhl_club_gets_factor_one_and_keeps_engine_parity(small_mod, monkeypatch):
    mod = small_mod
    _folds_all(mod, monkeypatch)
    results, app = make_world(seasons=(2014,), days=12)
    ex = {"date": "2014-10-08", "home": TEAMS[0], "away": "Ottawa Exhibition Club",
          "game_id": "999001", "home_score": 3, "away_score": 1, "neutral": False}
    nxt = {"date": "2014-10-09", "home": TEAMS[0], "away": TEAMS[1],
           "game_id": "999002", "home_score": 2, "away_score": 1, "neutral": False}
    results = [*results, ex, nxt]
    rows2, rows1, info, fr, params, rparams = _frame(mod, (results, app))
    clubs = mod.nhl_club_keys(rows2)
    assert "Ottawa Exhibition Club" not in clubs and len(clubs) == 8
    mask = mod.exhibition_mask(rows2, clubs)
    pos = [i for i, r in enumerate(rows2) if r["game_id"] == "999001"][0]
    assert [i for i, m in enumerate(mask) if m] == [pos]
    assert rows2[pos]["exhibicion_no_nhl"] and rows1[pos]["exhibicion_no_nhl"]
    for rr in (rows2[pos], rows1[pos]):
        assert rr["home_goalie_announced"] == "" == rr["away_goalie_announced"]
    assert info["exhibiciones_no_nhl"] == 1
    assert info["exhibiciones_no_nhl_lista"][0]["con_apariciones"] is False
    row = fr[fr["idx"] == pos].iloc[0]
    for tag in ("h1", "a1", "h2", "a2"):
        assert row[f"{tag}_id"] is None or pd.isna(row[f"{tag}_id"])
    for arm in mod.ARMS:
        qh, qa, fh, fa = mod.arm_qf(fr[fr["idx"] == pos], arm, 1500.0, 1.3)
        assert qh[0] == 0.0 and qa[0] == 0.0 and fh[0] == 1.0 and fa[0] == 1.0
        assert not mod.affected_mask(fr[fr["idx"] == pos], arm, 1500.0)[0]
    # la exhibicion no cuenta como "sin proxy": se informa aparte
    assert fr[fr["idx"] == pos].iloc[0]["proxy_h"] is not None
    assert not pd.isna(fr[fr["idx"] == pos].iloc[0]["proxy_h"])
    cob = mod._cobertura(rows2, fr, app)
    assert cob["lados_sin_proxy_tras_warmup"]["lados_exhibicion_no_nhl"] == 2
    assert cob["lados_sin_proxy_tras_warmup"]["M2_local"] == int(fr["proxy_h"].isna().sum())
    assert sum(p["lados_exhibicion"] for p in cob["por_particion"].values()) <= 2
    # el partido siguiente a una exhibicion sin datos: sin proxy del equipo, f = 1
    npos = [i for i, r in enumerate(rows2) if r["game_id"] == "999002"][0]
    assert pd.isna(fr[fr["idx"] == npos].iloc[0]["h2_id"])
    for beta, k in ((1.3, 1500.0), (-0.7, 200.0)):
        mod.assert_parity(rows2, rows1, params, rparams, fr, beta, k, label="test")


def test_sin_pretemporada_report_uses_game_type_and_counts_missing(mod):
    t = pd.DataFrame({"date": ["2015-10-01", "2015-10-05", "2015-09-20", "2015-10-07"],
                      "game_type": ["1", "2", "3", None],
                      "aff": [True, True, True, True],
                      "t_ml": [0.6] * 4, "b_ml": [0.5] * 4})
    y = np.array([1.0, 0.0, 1.0, 1.0])
    out = mod._informe_sin_pretemporada(t, y)
    assert out["n"] == 2                          # octubre con game_type 1 fuera; septiembre con 3 dentro
    assert out["n_game_type_1"] == 1
    assert out["n_sin_game_type_excluidos"] == 1


def test_goalie_state_splits_sides_without_proxy_by_cause(mod):
    m = mod
    ap = lambda sid, st: {"id": sid, "shots_against": 20.0, "saves": 18.0, "starter": st}  # noqa: E731
    rows = [
        {"date": "2015-10-01", "home": TEAMS[0], "away": TEAMS[1],
         "home_goalie_appearances": [], "away_goalie_appearances": [ap("A", True), ap("B", True)]},
        {"date": "2015-10-02", "home": TEAMS[0], "away": TEAMS[1],
         "home_goalie_appearances": [ap("C", True)], "away_goalie_appearances": [ap("D", True)]},
        {"date": "2015-10-03", "home": TEAMS[0], "away": TEAMS[2],
         "home_goalie_appearances": [], "away_goalie_appearances": []},
    ]
    st = m.goalie_state(rows)
    assert list(st["cause_h"])[0] == m.CAUSA_SIN_PARTIDO_PREVIO
    assert st["cause_h"][1] == m.CAUSA_SIN_APARICIONES
    assert st["cause_a"][1] == m.CAUSA_TITULARES
    assert pd.isna(st["cause_h"][2]) and st["proxy_h"][2] == "C"
    assert st["cause_a"][2] == m.CAUSA_SIN_PARTIDO_PREVIO
    assert m._por_causa(st)[m.CAUSA_TITULARES] == {"local": 0, "visitante": 1}
