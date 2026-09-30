"""Pruebas sinteticas de `scripts/research/measure_tilt_nhl.py`
(pre-registro `docs/research/2026-09-29-preregistro-tilt-nhl.md`).

Ninguna prueba lee `data/historical/results_nhl.csv` real ni ejecuta el modo
completo o `--pre`/`--parity-only` contra el historico de produccion (eso es
la medicion en si, fuera del alcance de esta suite): todo se ejercita con
partidos sinteticos pequenos y `warmup=0`, igual que
`tests/test_measure_rest_nhl.py` hace para su propio script hermano.
"""
from __future__ import annotations

import importlib.util
import sys

import numpy as np
import pandas as pd
import pytest

from sqp.config import ROOT

SCRIPT = ROOT / "scripts" / "research" / "measure_tilt_nhl.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("measure_tilt_nhl", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_module()


def test_script_exists():
    assert SCRIPT.exists()


def test_imports_measure_rest_nhl_as_sibling_module_not_a_copy(mod):
    """El script reutiliza measure_rest_nhl.py por referencia (import), no
    copia sus formulas: los objetos deben ser literalmente los mismos."""
    import measure_rest_nhl as rmnhl
    assert mod.home_win_vec is rmnhl.home_win_vec
    assert mod.cover_vec is rmnhl.cover_vec
    assert mod.over_vec is rmnhl.over_vec
    assert mod.diff_base_frame is rmnhl.diff_base_frame
    assert mod.FOLDS is rmnhl.FOLDS
    assert mod.NM_OPTS is rmnhl.NM_OPTS


# ------------------------------------------------------------ datos sinteticos --
def _synthetic_results(n_games: int = 40, start: str = "2015-01-01",
                       teams: tuple[str, ...] = ("A", "B", "C", "D")) -> list[dict]:
    """Partidos sinteticos con fechas consecutivas, marcadores variados
    (incluido un empate historico pre-2005 style para ejercitar el filtro de
    moneyline) y sin huecos de calendario."""
    rng = np.random.default_rng(7)
    dates = pd.date_range(start, periods=n_games, freq="D")
    rows = []
    for i, d in enumerate(dates):
        home, away = teams[i % len(teams)], teams[(i + 1) % len(teams)]
        hs, aws = int(rng.integers(0, 6)), int(rng.integers(0, 6))
        if i == 5:  # el UNICO empate deliberado: ejercita el filtro moneyline vs df_all
            aws = hs
        else:
            # Fuerza aws != hs en el resto: un empate accidental en otro
            # indice invalidaria el conteo exacto de la seccion de mas abajo
            # (un solo empate en i==5) que varias pruebas dan por sentado.
            while aws == hs:
                aws = int(rng.integers(0, 6))
        rows.append({"date": d.strftime("%Y-%m-%d"), "home": home, "away": away,
                    "game_id": str(i), "home_score": hs, "away_score": aws,
                    "neutral": False})
    return rows


NHL_PARAMS = {"elo_home_adv": 15.0}  # el unico override real de configs/leagues/ratings.yaml


# ------------------------------------------------------- game_calendar / frames --
def test_game_calendar_never_touches_scores(mod):
    results = _synthetic_results(10)
    cal = mod.game_calendar(results, warmup=0)
    assert "home_score" not in cal.columns and "away_score" not in cal.columns
    assert len(cal) == 10
    assert list(cal["idx"]) == list(range(10))


def test_game_calendar_respects_warmup(mod):
    results = _synthetic_results(10)
    cal = mod.game_calendar(results, warmup=4)
    assert len(cal) == 6
    assert cal["idx"].min() == 4


def test_diff_avg_for_pre_never_returns_outcome_columns(mod):
    """--pre nunca debe poder leer `y`: el frame que construye no puede tener
    ninguna columna derivada del marcador."""
    results = _synthetic_results(20)
    frame = mod.diff_avg_for_pre(results, NHL_PARAMS, warmup=0)
    for forbidden in ("y", "margin", "total", "home_score", "away_score"):
        assert forbidden not in frame.columns
    assert set(frame.columns) == {"idx", "date", "diff_base", "avg"}


def test_diff_avg_for_pre_matches_diff_base_frame(mod):
    """La ruta sin marcadores y la ruta con marcadores deben calcular EXACTAMENTE
    el mismo diff_base/avg (las dos ejecutan las mismas dos lineas de
    `PoissonAdapter._rates` previas al tilt)."""
    results = _synthetic_results(25)
    pre_frame = mod.diff_avg_for_pre(results, NHL_PARAMS, warmup=0)
    full_frame = mod.diff_base_frame(results, NHL_PARAMS, warmup=0)
    pd.testing.assert_series_equal(pre_frame["diff_base"], full_frame["diff_base"])
    pd.testing.assert_series_equal(pre_frame["avg"], full_frame["avg"])


def test_build_tilt_frame_excludes_draws_only_from_moneyline_view(mod):
    results = _synthetic_results(20)
    df, df_all = mod.build_tilt_frame(results, NHL_PARAMS, warmup=0)
    assert len(df_all) == 20
    assert len(df) == 19  # el empate sintetico (indice 5) sale de df, no de df_all
    assert df["y"].isin([0.0, 1.0]).all()
    assert (df_all["y"] == 0.5).sum() == 1


def test_build_tilt_frame_all_view_has_margin_and_total(mod):
    results = _synthetic_results(15)
    _, df_all = mod.build_tilt_frame(results, NHL_PARAMS, warmup=0)
    assert "margin" in df_all.columns and "total" in df_all.columns


# ---------------------------------------------- invariante de la seccion 1.3 --
def test_diff_avg_invariant_to_tilt_scale(mod):
    """Propiedad clave del pre-registro: `diff_base`/`avg` NO dependen de
    `tilt_scale` (el tilt no realimenta el Elo ni las tasas de anotacion)."""
    results = _synthetic_results(30)
    mod.assert_diff_avg_tilt_invariant(results, NHL_PARAMS, warmup=0)  # no debe lanzar


def test_diff_avg_invariant_detects_a_real_break(mod, monkeypatch):
    """Si el invariante se rompe (p.ej. alguien hiciera que el tilt afecte a
    diff_base), la aserccion debe abortar, no pasar en silencio."""
    results = _synthetic_results(15)

    real_diff_base_frame = mod.diff_base_frame

    def _fake_diff_base_frame(results_, params_, warmup_=mod.WARMUP):
        frame = real_diff_base_frame(results_, params_, warmup_)
        if params_.get("tilt_scale") == mod.PROBE_TILT:
            frame = frame.copy()
            frame["diff_base"] = frame["diff_base"] + 1.0  # rotura deliberada
        return frame

    monkeypatch.setattr(mod, "diff_base_frame", _fake_diff_base_frame)
    with pytest.raises(SystemExit):
        mod.assert_diff_avg_tilt_invariant(results, NHL_PARAMS, warmup=0)


# --------------------------------------------------------------------- paridad --
def test_assert_parity_passes_at_the_family_default_and_at_an_arbitrary_tilt(mod):
    results = _synthetic_results(80)
    df, df_all = mod.build_tilt_frame(results, NHL_PARAMS, warmup=0)
    rparams = mod.resolved_params(NHL_PARAMS)
    bonus = rparams["home_scoring_bonus"]
    max_goals = rparams["max_score"]
    mod.assert_parity(results, NHL_PARAMS, df, df_all, 0.9, bonus, max_goals,
                      warmup=0, label="test-base")
    mod.assert_parity(results, NHL_PARAMS, df, df_all, mod.PROBE_TILT, bonus, max_goals,
                      warmup=0, label="test-probe")


def test_assert_parity_detects_a_corrupted_diff_base(mod):
    """Si `df` no coincide con lo que recalcularia el motor (p.ej.
    `diff_base` corrompido), la paridad debe romperse: asegura que la
    aserccion realmente compara datos, no una tautologia consigo misma.

    (Sustituye a una version anterior de esta prueba que pasaba `tilt_scale`
    en `params` Y como argumento aparte: `assert_parity` siempre sobreescribe
    `params['tilt_scale']` con el argumento explicito para AMBOS lados de la
    comparacion -- `{**params, 'tilt_scale': tilt_scale}` --, asi que esa
    version nunca ejercitaba un `tilt` distinto en cada lado y pasaba solo
    por un efecto colateral no relacionado (empates accidentales del
    generador sintetico antes de forzar `aws != hs`, corregido en
    `_synthetic_results`). La paridad NEGATIVA vía `home_win_vec` perturbado
    esta en `test_assert_parity_fails_when_home_win_vec_is_perturbed`.)"""
    results = _synthetic_results(60)
    df, df_all = mod.build_tilt_frame(results, NHL_PARAMS, warmup=0)
    rparams = mod.resolved_params(NHL_PARAMS)
    bonus, max_goals = rparams["home_scoring_bonus"], rparams["max_score"]
    df_corrupto = df.copy()
    df_corrupto["diff_base"] = df_corrupto["diff_base"] + 50.0
    with pytest.raises(SystemExit):
        mod.assert_parity(results, NHL_PARAMS, df_corrupto, df_all, 0.9, bonus, max_goals,
                          warmup=0, label="diff_base corrupto")


def test_assert_parity_fails_when_home_win_vec_is_perturbed(mod, monkeypatch):
    """Prueba de paridad NEGATIVA (revision de Fable): si `home_win_vec` se
    perturba (probabilidad calculada con `diff + 0,05` en vez de `diff`), la
    comparacion contra el motor canonico debe romperse. Confirma que
    `assert_parity` realmente depende de `home_win_vec` y no es una
    tautologia que compara un vector contra si mismo."""
    import measure_rest_nhl as rmnhl
    results = _synthetic_results(60)
    df, df_all = mod.build_tilt_frame(results, NHL_PARAMS, warmup=0)
    rparams = mod.resolved_params(NHL_PARAMS)
    bonus, max_goals = rparams["home_scoring_bonus"], rparams["max_score"]
    monkeypatch.setattr(mod, "home_win_vec",
                        lambda d, a, t, b, m: rmnhl.home_win_vec(d, a, t + 0.05, b, m))
    with pytest.raises(SystemExit):
        mod.assert_parity(results, NHL_PARAMS, df, df_all, 0.9, bonus, max_goals,
                          warmup=0, label="perturbado")


# --------------------------------------------------------------- brazos (fit) --
def test_fit_t_recovers_a_known_tilt_from_data_generated_with_it(mod):
    """Genera resultados con el modelo Poisson EXACTO en tilt=0.6 (usando el
    propio `home_win_vec` para simular, no un modelo distinto) y comprueba que
    `fit_t` recupera un valor cercano."""
    rng = np.random.default_rng(11)
    n = 4000
    diff = rng.normal(0, 150, n)
    avg = np.full(n, 6.1)
    true_tilt = 0.6
    p = mod.home_win_vec(diff, avg, true_tilt, 0.1, 15)
    y = (rng.random(n) < p).astype(float)
    fitted = mod.fit_t(diff, avg, y, 0.1, 15)
    assert fitted == pytest.approx(true_tilt, abs=0.1)


def test_fit_platt_is_near_identity_when_base_probabilities_are_well_calibrated(mod):
    rng = np.random.default_rng(3)
    n = 4000
    diff = rng.normal(0, 150, n)
    avg = np.full(n, 6.1)
    p_base = mod.home_win_vec(diff, avg, 0.9, 0.1, 15)
    y = (rng.random(n) < p_base).astype(float)
    alpha, beta = mod.fit_platt(p_base, y)
    assert alpha == pytest.approx(0.0, abs=0.15)
    assert beta == pytest.approx(1.0, abs=0.15)


def test_fit_t2_starting_point_and_shape(mod):
    rng = np.random.default_rng(5)
    n = 3000
    diff = rng.normal(0, 150, n)
    avg = np.full(n, 6.1)
    p = mod.home_win_vec(diff, avg, 0.5, 0.1, 15)
    y = (rng.random(n) < p).astype(float)
    t2, a2 = mod.fit_t2(diff, avg, y, 0.1, 15)
    assert np.isfinite(t2) and np.isfinite(a2)


def test_fit_raises_systemexit_when_nelder_mead_does_not_converge(mod, monkeypatch):
    class _FakeResult:
        success = False
        message = "fallo sintetico"
        x = np.array([0.0])

    monkeypatch.setattr(mod, "fit", mod.fit)  # sanity: fit es el de rmnhl reexportado
    import measure_rest_nhl as rmnhl
    monkeypatch.setattr(rmnhl, "minimize", lambda *a, **k: _FakeResult())
    with pytest.raises(SystemExit):
        mod.fit_t(np.array([0.0]), np.array([6.1]), np.array([1.0]), 0.1, 15)


# ---------------------------------------------------------------- load_league --
def test_load_league_aborts_when_resolved_tilt_scale_is_not_0_9(mod, tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_league_meta",
                        lambda league: {"league_params": {"tilt_scale": 0.5}})
    with pytest.raises(ValueError, match="tilt_scale"):
        mod.load_league(tmp_path)


def test_load_league_aborts_when_rest_elo_per_day_is_nonzero(mod, tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_league_meta",
                        lambda league: {"league_params": {"rest_elo_per_day": 25.0}})
    with pytest.raises(ValueError, match="rest_elo_per_day"):
        mod.load_league(tmp_path)


def test_load_league_aborts_when_goalie_beta_is_nonzero(mod, tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_league_meta",
                        lambda league: {"league_params": {"goalie_beta": 0.3}})
    with pytest.raises(ValueError, match="goalie_beta"):
        mod.load_league(tmp_path)


def test_load_league_passes_with_the_real_nhl_base_configuration(mod, tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_league_meta",
                        lambda league: {"league_params": dict(NHL_PARAMS)})
    results, params, procedencia = mod.load_league(tmp_path)
    assert results == []
    assert procedencia["filas"] == 0
    assert "sha256" not in procedencia  # no existe results_nhl.csv en tmp_path


# --------------------------------------------------------- git_head (procedencia) --
def test_git_head_returns_none_when_not_a_git_repo(mod, tmp_path):
    assert mod.git_head(tmp_path) is None


def test_git_head_returns_a_string_for_this_repository(mod):
    head = mod.git_head(ROOT)
    assert head is None or (isinstance(head, str) and len(head) == 40)


# ------------------------------------------ git status --porcelain (punto 6) --
def test_git_status_porcelain_returns_none_when_not_a_git_repo(mod, tmp_path):
    assert mod.git_status_porcelain(tmp_path) is None


def test_git_status_porcelain_returns_a_string_for_this_repository(mod):
    status = mod.git_status_porcelain(ROOT)
    assert status is None or isinstance(status, str)


def test_check_git_clean_raises_when_status_is_none(mod):
    with pytest.raises(SystemExit):
        mod._check_git_clean(None)


def test_check_git_clean_raises_when_status_is_nonempty(mod):
    with pytest.raises(SystemExit):
        mod._check_git_clean(" M scripts/research/measure_tilt_nhl.py\n")


def test_check_git_clean_passes_when_status_is_empty(mod):
    mod._check_git_clean("")  # no lanza


# --------------------------------------------------- escenarios (seccion 9.2) --
def test_escenarios_9_2_covers_the_preregistered_tstars(mod):
    rng = np.random.default_rng(21)
    n = 2000
    diff = rng.normal(0, 100, n)
    avg = np.full(n, 6.1)
    out = mod.escenarios_9_2(diff, avg, bonus=0.1, max_goals=15)
    assert set(out) == {str(t) for t in mod.TSTAR_9_2}
    for t, fila in out.items():
        # KL(p_t* || p_0,9) >= 0 siempre (desigualdad de Gibbs); la ganancia
        # esperada de pasar de 0,9 a cualquier t* < 0,9 no puede ser negativa.
        assert fila["ganancia_esperada_vs_base"] >= -1e-12
        assert fila["ee_delta"] is not None and fila["ee_delta"] >= 0.0
        assert fila["ventaja_sobre_constante"] is not None


def test_escenarios_9_2_ganancia_es_cero_cuando_tstar_es_la_base(mod):
    rng = np.random.default_rng(9)
    diff = rng.normal(0, 100, 500)
    avg = np.full(500, 6.1)
    out = mod.escenarios_9_2(diff, avg, bonus=0.1, max_goals=15, tstars=(0.9,), tilt_base=0.9)
    assert out["0.9"]["ganancia_esperada_vs_base"] == pytest.approx(0.0, abs=1e-9)


def test_informe_pre_includes_escenarios_9_2_without_reading_y(mod, tmp_path, monkeypatch):
    results = _synthetic_results(100)
    monkeypatch.setattr(mod, "load_league",
                        lambda data_root: (results, NHL_PARAMS, {"filas": len(results)}))
    out = mod.informe_pre(tmp_path)
    assert "escenarios_9_2" in out
    assert set(out["escenarios_9_2"]) == {str(t) for t in mod.TSTAR_9_2}
    for fila in out["escenarios_9_2"].values():
        assert np.isfinite(fila["ganancia_esperada_vs_base"])
        assert fila["ganancia_esperada_vs_base"] >= -1e-12


# ------------------------------------------- linea capturada (informe 11) --
def test_informe_linea_capturada_returns_none_without_matched_games(mod, monkeypatch):
    monkeypatch.setattr(mod, "captured_lines",
                        lambda results: {"spreads": {}, "game_ids_emparejados": set(),
                                        "ficheros_sha256": {}})
    assert mod.informe_linea_capturada([], pd.DataFrame(), mod.FOLDS["C"], 0.1, 15, 0.9, 0.5) is None


def test_informe_linea_capturada_smoke(mod, monkeypatch):
    """Calculo propio con float() explicito (punto 5 de la revision de
    Fable): no reutiliza measure_rest_nhl._informe_linea_capturada."""
    test_all_mny = pd.DataFrame({
        "game_id": ["1", "2", "3"],
        "date": ["2023-01-01", "2023-01-02", "2023-01-03"],
        "diff_base": [10.0, -20.0, 5.0],
        "avg": [6.1, 6.1, 6.1],
        "y": [1.0, 0.0, 1.0],
        "margin": [2.0, -1.0, 3.0],
    })
    fake_cap = {"spreads": {"1": -1.5, "2": -1.5},
               "game_ids_emparejados": {"1", "2", "3"},
               "ficheros_sha256": {"odds_nhl_2023.csv": "deadbeef"}}
    monkeypatch.setattr(mod, "captured_lines", lambda results: fake_cap)
    out = mod.informe_linea_capturada([], test_all_mny, mod.FOLDS["C"], 0.1, 15, 0.9, 0.5)
    assert out is not None
    assert out["n_h2h"] == 3
    assert isinstance(out["delta_ll_h2h"], float) and np.isfinite(out["delta_ll_h2h"])
    assert out["n_spread_con_linea"] == 2
    assert out["ficheros_odds_sha256"] == fake_cap["ficheros_sha256"]
    if out.get("n_spread_evaluado", 0):
        assert isinstance(out["delta_ll_spread"], float) and np.isfinite(out["delta_ll_spread"])


# --------------------------------------------------- --pre-json / procedencia --
def test_check_pre_provenance_raises_when_pre_json_lacks_hash(mod):
    with pytest.raises(SystemExit):
        mod._check_pre_provenance({}, {"sha256": "aaa"}, "headnow")


def test_check_pre_provenance_raises_when_current_file_lacks_hash(mod):
    with pytest.raises(SystemExit):
        mod._check_pre_provenance({"sha256": "aaa", "git_head": "h"}, {}, "h")


def test_check_pre_provenance_raises_on_hash_mismatch(mod):
    with pytest.raises(SystemExit):
        mod._check_pre_provenance({"sha256": "aaa", "git_head": "h"}, {"sha256": "bbb"}, "h")


def test_check_pre_provenance_raises_when_pre_json_lacks_head(mod):
    with pytest.raises(SystemExit):
        mod._check_pre_provenance({"sha256": "aaa"}, {"sha256": "aaa"}, "h")


def test_check_pre_provenance_raises_when_head_now_is_none(mod):
    with pytest.raises(SystemExit):
        mod._check_pre_provenance({"sha256": "aaa", "git_head": "h"}, {"sha256": "aaa"}, None)


def test_check_pre_provenance_raises_on_head_mismatch(mod):
    with pytest.raises(SystemExit):
        mod._check_pre_provenance({"sha256": "aaa", "git_head": "old"}, {"sha256": "aaa"}, "new")


def test_check_pre_provenance_passes_on_full_match(mod):
    mod._check_pre_provenance({"sha256": "aaa", "git_head": "h"}, {"sha256": "aaa"}, "h")  # no lanza


# ------------------------------------------------------------------- argparse --
def test_full_mode_requires_pre_json_argument(mod, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["measure_tilt_nhl.py", "--out", "ignored.json"])
    with pytest.raises(SystemExit):
        mod.main()


def test_pre_json_rejected_outside_full_mode(mod, monkeypatch, tmp_path):
    pre_json = tmp_path / "pre.json"
    pre_json.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(sys, "argv",
                        ["measure_tilt_nhl.py", "--parity-only", "--pre-json", str(pre_json)])
    with pytest.raises(SystemExit):
        mod.main()


def test_pre_and_parity_only_are_mutually_exclusive(mod, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["measure_tilt_nhl.py", "--pre", "--parity-only"])
    with pytest.raises(SystemExit):
        mod.main()


def test_out_is_required_outside_parity_only(mod, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["measure_tilt_nhl.py", "--pre"])
    with pytest.raises(SystemExit):
        mod.main()


# ------------------------------------------------------- modo completo (sintetico) --
def _synthetic_results_spanning_folds(mod) -> list[dict]:
    """Suficientes partidos sinteticos DENTRO de las ventanas reales de
    entrenamiento/test de las tres particiones (`FOLDS`) para que `run_nhl`
    pueda ajustar los cinco brazos y evaluar los 7 criterios sin tocar datos
    de produccion. No se afirma nada sobre el resultado (es ruido sintetico);
    solo se comprueba que el pipeline completo no rompe con datos de forma
    correcta."""
    rng = np.random.default_rng(99)
    teams = ("A", "B", "C", "D", "E", "F")
    rows: list[dict] = []
    gid = 0
    # Un tramo de entrenamiento y uno de test por particion, suficientes para
    # que Nelder-Mead tenga datos con los que converger.
    spans = [
        ("2010-01-01", "2014-09-30"), ("2014-10-01", "2014-12-31"),
        ("2015-01-01", "2018-09-30"), ("2018-10-01", "2018-12-31"),
        ("2019-01-01", "2022-09-30"), ("2022-10-01", "2022-12-31"),
    ]
    for start, end in spans:
        dates = pd.date_range(start, end, freq="3D")
        for i, d in enumerate(dates):
            home, away = teams[i % len(teams)], teams[(i + 1) % len(teams)]
            hs, aws = int(rng.integers(0, 6)), int(rng.integers(0, 6))
            rows.append({"date": d.strftime("%Y-%m-%d"), "home": home, "away": away,
                        "game_id": str(gid), "home_score": hs, "away_score": aws,
                        "neutral": False})
            gid += 1
    return rows


def test_run_nhl_end_to_end_on_synthetic_data_produces_a_well_formed_verdict(mod):
    results = _synthetic_results_spanning_folds(mod)
    out = mod.run_nhl(results, NHL_PARAMS)
    assert out["veredicto"] in ("ACEPTA", "RECHAZA")
    assert set(out["criterios"]) == {
        "1_delta_universo_combinado_le_-0.002",
        "2_delta_negativo_en_cada_particion",
        "3_t_bate_constante_signo",
        "4_ece_no_empeora",
        "5_t_entre_0_y_0.9_en_las_tres_particiones",
        "6_puck_line_no_empeora",
        "7_t2_menor_que_0.9_en_las_tres_particiones",
    }
    assert set(out["folds"]) == {"A", "B", "C"}
    for f in out["folds"].values():
        assert np.isfinite(f["t"])
        assert 0.0 <= f["k"] <= 1.0
        assert np.isfinite(f["bias_t2_test"])
        assert np.isfinite(f["bias_platt_test"])
    # Informe 1 completo (seccion 10.1) y bootstrap del criterio 3 (seccion
    # 8, punto 4 de la revision de Fable): sesgo de los cuatro brazos y
    # fraccion de replicas con T-K<0 en el combinado.
    assert "ll_base" in out["combinado"]
    assert np.isfinite(out["combinado"]["bias_t2"])
    assert np.isfinite(out["combinado"]["bias_platt"])
    assert "prob_supera_margen" in out["combinado"]["bootstrap_trat_vs_const"]
    # Informes secundarios: nunca deben faltar la clave, aunque hayan
    # fallado (en cuyo caso llevarian un campo "error").
    for key in ("secundario_auc", "secundario_grid_rolling_origin",
               "secundario_puck_line_detalle",
               "secundario_totales_max_abs_delta_p_over",
               "secundario_redondeo_tc", "secundario_fraccion_platt",
               "secundario_pendiente_calibracion", "secundario_fiabilidad_y_quintiles",
               "secundario_por_temporada", "secundario_linea_capturada"):
        assert key in out


def test_grid_report_parity_failure_does_not_kill_the_main_json(mod, monkeypatch):
    """Revision de Fable (2026-09-30): un fallo de paridad en la rejilla del
    informe 4 lanzaba SystemExit, que `_safe_informe` (solo Exception) no
    captura, y se perdia el JSON de la ejecucion unica. Ahora el informe
    anota el error y el veredicto sigue calculandose."""
    real = mod.assert_parity

    def fake(*args, label="", **kwargs):
        if str(label).startswith("informe4"):
            raise SystemExit("paridad rota simulada")
        return real(*args, label=label, **kwargs)

    monkeypatch.setattr(mod, "assert_parity", fake)
    results = _synthetic_results_spanning_folds(mod)
    out = mod.run_nhl(results, NHL_PARAMS)
    assert out["veredicto"] in ("ACEPTA", "RECHAZA")
    grid = out["secundario_grid_rolling_origin"]
    assert "PARIDAD ROTA" in grid["error"]
    assert grid["rolling_origin"] is None
