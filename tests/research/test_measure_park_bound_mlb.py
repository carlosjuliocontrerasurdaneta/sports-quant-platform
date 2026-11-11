"""Pruebas SINTETICAS de `scripts/research/measure_park_bound_mlb.py` (pre-registro
`docs/research/2026-11-10-preregistro-park-bound-mlb.md`, seccion 14).

Ninguna prueba lee `data/` real ni ejecuta el script contra datos reales: eso es la
medicion de ejecucion unica. Todo se ejercita con partidos SINTETICOS (equipos A..F,
dos con efecto de parque fuerte, marcadores aleatorios con semilla fija) en raices
temporales. Las pruebas de paridad usan el `dist.poisson_match_probs` REAL; las demas
lo sustituyen por un sucedaneo rapido (el contrato exige la funcion real en la
medicion, no en las pruebas de plomeria).
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import inspect
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sqp.config import ROOT
from sqp.models import distributions as dist

# Modulo caro: fuera de la suite rapida del hook Stop; CI lo ejecuta siempre.
pytestmark = pytest.mark.heavy

SCRIPT = ROOT / "scripts" / "research" / "measure_park_bound_mlb.py"
TEAMS = ("A", "B", "C", "D", "E", "F")
PARK = {"A": 1.35, "B": 0.75}            # efecto de parque FUERTE en dos equipos
SYN_FOLDS = {"A": {"train_end": "2024-05-10", "test_start": "2024-05-11", "test_end": "2024-05-31"},
             "B": {"train_end": "2024-05-31", "test_start": "2024-06-01", "test_end": "2024-06-20"},
             "C": {"train_end": "2024-06-20", "test_start": "2024-06-21", "test_end": "2024-07-09"}}
SYN_CUTOFF = "2024-12-31"


def _load_module():
    spec = importlib.util.spec_from_file_location("measure_park_bound_mlb", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_module()


@pytest.fixture()
def syn(mod, monkeypatch):
    monkeypatch.setattr(mod, "FOLDS", SYN_FOLDS)
    monkeypatch.setattr(mod, "CUTOFF", SYN_CUTOFF)
    return mod


def _games(n_days: int = 100, start: str = "2024-04-01", per_day: int = 3, seed: int = 7,
           tie_at: int | None = None) -> list[dict]:
    rng = np.random.default_rng(seed)
    rows, gid = [], 0
    for d in pd.date_range(start, periods=n_days, freq="D"):
        order = list(rng.permutation(TEAMS))
        for j in range(per_day):
            h, a = order[2 * j], order[2 * j + 1]
            m = PARK.get(h, 1.0)
            hs, aw = int(rng.poisson(4.6 * m)), int(rng.poisson(4.3 * m))
            if hs == aw:
                hs += 1
            if tie_at is not None and gid == tie_at:
                aw = hs
            rows.append({"date": d.strftime("%Y-%m-%d"), "home": h, "away": a, "game_id": str(gid),
                         "home_score": hs, "away_score": aw, "neutral": False})
            gid += 1
    return rows


def _write_root(tmp_path: Path, rows: list[dict] | None = None, **kw) -> Path:
    hist = tmp_path / "data" / "historical"
    hist.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows if rows is not None else _games(**kw)).assign(ingested_at="x").to_csv(
        hist / "results_mlb.csv", index=False)
    return tmp_path


def _fast_pmp(lam_home, lam_away, spread_line, total_line, three_way=False, max_goals=15,
              dc_rho=0.0, dispersion_k=None, score_rho=0.0, tie_adds_goal=False):
    """Sucedaneo normal y rapido de `poisson_match_probs` (misma firma y claves)."""
    def cdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
    mu = lam_home + lam_away
    sd = math.sqrt(2.0 * mu)
    out = {"home_win": cdf((lam_home - lam_away) / sd)}
    out["away_win"] = 1.0 - out["home_win"]
    if spread_line is not None:
        out["home_cover"] = 1.0 - cdf((-spread_line - (lam_home - lam_away)) / sd)
        out["away_cover"] = 1.0 - out["home_cover"]
    if total_line is not None:
        out["over"] = 1.0 - cdf((total_line - mu) / sd)
        out["under"] = 1.0 - out["over"]
    return out


@pytest.fixture()
def fast(monkeypatch):
    monkeypatch.setattr(dist, "poisson_match_probs", _fast_pmp)


def _patch_git(mod, monkeypatch, head: str = "deadbeef"):
    monkeypatch.setattr(mod, "git_head", lambda cwd: head)
    monkeypatch.setattr(mod, "git_status_porcelain", lambda cwd, paths=None: "")


# ------------------------------------------------------------ constantes --
def test_constants_are_the_preregistered_ones(mod):
    assert mod.GRID == (0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50)
    assert mod.CUTOFF == "2026-09-26" and mod.WARMUP == 60 and mod.SEED == 42
    assert mod.N_BOOT == 10_000 and mod.TOL == 1e-12 and mod.NM_OPTS == {
        "xatol": 1e-7, "fatol": 1e-10, "maxiter": 2000}
    from sqp.backtesting import tuning
    assert mod.MARGIN == tuning.IMPROVEMENT_MARGIN == 0.002 and mod.MIN_EVAL == tuning.MIN_EVAL_MARKET
    assert [f["test_start"][:4] for f in mod.FOLDS.values()] == ["2024", "2025", "2026"]
    assert mod.FOLDS["C"]["test_end"] == "2026-09-26"


def test_resolved_params_match_the_base_and_abort_otherwise(mod):
    lp, ap = mod.assert_family_and_params()           # configuracion real del repo
    assert lp["park_bound"] == 0.1 and ap["park_bound"] == 0.1
    with pytest.raises(SystemExit):
        mod.assert_resolved_params({**lp, "park_bound": 0.2}, ap)
    with pytest.raises(SystemExit):
        mod.assert_resolved_params(lp, {**ap, "pitcher_signal": "fip"})
    with pytest.raises(SystemExit):
        mod.assert_resolved_params(lp, {**ap, "park_prior_games": 10.0})
    mod.assert_resolved_params(lp, {**ap, "scoring_half_life_days": 0})     # 0 == ausente
    with pytest.raises(SystemExit):
        mod.assert_resolved_params(lp, {**ap, "scoring_half_life_days": 90.0})


# --------------------------------------------- (1) paridad con el motor (real) --
def test_parity_against_walk_forward_backtest_to_1e12(syn):
    mod = syn
    lp, _ = mod.assert_family_and_params()
    results = _games(n_days=100, tie_at=150)           # incluye un empate (se excluye del h2h)
    kw = mod.pricing_kwargs(mod.get_adapter(mod.LEAGUE, mod.FAMILY, lp))
    rep = mod.run_parity(results, lp, kw, stride=4)
    assert set(rep["cotas"]) == {"0.0", "0.1", "0.2"}
    for dev in rep["cotas"].values():
        assert set(dev) == {"h2h", "spreads@-1.5", "spreads@1.5", "totals@8.5"}
        assert all(v <= 1e-12 for v in dev.values())
    assert rep["lam0_f_identicos_bajo_las_tres_cotas"] is True


def test_parity_aborts_when_a_probability_is_perturbed(syn, monkeypatch):
    mod = syn
    lp, _ = mod.assert_family_and_params()
    results = _games(n_days=70)
    kw = mod.pricing_kwargs(mod.get_adapter(mod.LEAGUE, mod.FAMILY, lp))
    real = mod.lam_arm

    def broken(comp, b, a=0.0):
        lh, la = real(comp, b, a)
        return lh * 1.001, la

    monkeypatch.setattr(mod, "lam_arm", broken)
    with pytest.raises(SystemExit, match="PARIDAD ROTA"):
        mod.run_parity(results, lp, kw, stride=7)


# ------------------------------------------- (2) invariancia de f y pf(0,10) --
def test_shadow_f_is_identical_under_the_three_bounds_and_pf_matches_production(syn):
    mod = syn
    lp, _ = mod.assert_family_and_params()
    results = _games(n_days=100)
    comps = {b: mod.walk_components(results, {**lp, "park_bound": b}) for b in (0.0, 0.10, 0.20)}
    ref = comps[0.0]
    for b, c in comps.items():
        for key in ("lam_h0", "lam_a0", "f"):
            assert np.array_equal(ref[key], c[key]), (b, key)
        assert np.array_equal(c["pf_prod"], mod.pf_of(c["f"], b)), b
    f = ref["f"]
    assert np.any(f > 1.10) and np.any(f < 0.90) and np.any(f == 1.0)    # sin recortar y con muestra corta
    assert np.any(comps[0.10]["pf_prod"] != f)                           # la cota 0,10 SI recorta aqui
    assert np.all(comps[0.0]["pf_prod"] == 1.0)
    assert np.array_equal(mod.pf_of(f, 1e9), f)                          # la sombra no recorta


# ------------------------------------------------------------- (3) desempate --
def test_select_b_tie_rules_and_float_symmetry(mod):
    flat = {b: 0.7 for b in mod.GRID}
    assert mod.select_b(flat) == 0.10                                    # todas iguales: la vigente
    assert mod.select_b({**flat, 0.05: 0.6, 0.15: 0.6}) == 0.05          # equidistantes: la menor
    assert mod.select_b({**flat, 0.30: 0.6, 0.50: 0.6}) == 0.30          # la mas cercana a 0,10
    assert mod.select_b({**flat, 0.0: 0.6, 0.50: 0.6}) == 0.0
    assert mod.select_b({**flat, 0.20: 0.6}) == 0.20                     # sin empate: argmin
    with pytest.raises(SystemExit):
        mod.select_b({0.0: float("nan"), 0.1: 0.5})
    with pytest.raises(SystemExit):
        mod.select_b({})
    assert mod.min_gap({0.0: 0.7, 0.1: 0.7, 0.2: 0.65}) == 0.0


def test_non_binding_bounds_have_exactly_equal_losses_and_the_tie_rule_applies(syn, fast):
    mod = syn
    lp, _ = mod.assert_family_and_params()
    results = _games(n_days=100)
    comp = mod.walk_components(results, lp)
    # Se fuerza un historico sin recortes entre 0,30 y 0,50: f dentro de [0,7; 1,3].
    comp["f"] = np.clip(comp["f"], 0.9, 1.1)
    arms = mod.Arms(comp, mod.pricing_kwargs(mod.get_adapter(mod.LEAGUE, mod.FAMILY, lp)))
    assert np.array_equal(arms.over(0.20), arms.over(0.30))
    assert np.array_equal(arms.over(0.30), arms.over(0.50))
    oc = mod.read_outcomes(results)
    y = (oc["total"] > arms.line).astype(float)
    train = comp["date"] <= SYN_FOLDS["C"]["train_end"]
    tl = {b: float(np.mean(mod.ll_vec(arms.over(b), y)[train])) for b in mod.GRID}
    assert tl[0.20] == tl[0.30] == tl[0.50]
    best = min(tl.values())
    tied = [b for b, v in tl.items() if v == best]
    assert set(tied) >= {0.20, 0.30, 0.50} or best < tl[0.20]
    chosen = mod.select_b(tl)
    assert chosen == min(tied, key=lambda b: (round(abs(b - 0.10), 12), b))


# ---------------------------------------------------- (4) --pre sin desenlaces --
def test_build_pre_signature_receives_no_outcomes(mod):
    assert list(inspect.signature(mod.build_pre).parameters) == ["comp", "arms"]
    assert list(inspect.signature(mod.walk_components).parameters)[:2] == ["results", "league_params"]
    assert "oc" not in inspect.signature(mod.Arms.__init__).parameters


def test_pre_does_not_read_outcomes_and_ignores_the_scores_of_the_last_day(syn, fast, monkeypatch, tmp_path):
    mod = syn
    _patch_git(mod, monkeypatch)

    def boom(*a, **k):
        raise AssertionError("--pre no puede leer desenlaces (read_outcomes)")

    monkeypatch.setattr(mod, "read_outcomes", boom)
    rows = _games(n_days=100)
    root = _write_root(tmp_path / "a", rows)
    pre = mod.informe_pre(root)
    assert pre["cota_050_no_vinculante"] in (True, False)
    assert set(pre["fraccion_recortada_por_cota"]) == set(SYN_FOLDS)
    # Centinela: los marcadores del ULTIMO dia solo podrian entrar por `observe`, que ya
    # no se llama para ellos -> todo lo que el modo deriva de esas filas es identico.
    last = rows[-1]["date"]
    tampered = [dict(r, home_score=10 ** 6, away_score=10 ** 6 + 1) if r["date"] == last else dict(r)
                for r in rows]
    root2 = _write_root(tmp_path / "b", tampered)
    pre2 = mod.informe_pre(root2)
    for key in ("recuentos", "distribucion_f", "fraccion_recortada_por_cota", "delta_p_por_cota",
                "media_P_over_por_brazo", "escenarios_KL", "clases_de_equivalencia_entrenamiento"):
        assert pre[key] == pre2[key], key
    text = json.dumps(mod._clean(pre))
    assert "home_score" not in text and "away_score" not in text and "margin" not in text


def test_pre_requires_a_clean_git_tree(syn, fast, monkeypatch, tmp_path):
    mod = syn
    monkeypatch.setattr(mod, "git_head", lambda cwd: "x")
    monkeypatch.setattr(mod, "git_status_porcelain", lambda cwd, paths=None: " M src/x.py\n")
    with pytest.raises(SystemExit):
        mod.informe_pre(_write_root(tmp_path, _games(n_days=100)))


# ------------------------------------------------ (5) sin roi_engine ni cuotas --
def test_script_does_not_import_roi_engine_nor_read_odds(tmp_path):
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            mods.add(base)
            mods.update(f"{base}.{a.name}" for a in node.names)
    assert not [m for m in mods if "roi_engine" in m or "measure_adjustment_battery" in m]
    src = SCRIPT.read_text(encoding="utf-8").lower()
    assert "data/odds" not in src and "odds_" not in src and "load_closing_odds" not in src
    code = ("import importlib.util, sys\n"
            f"spec = importlib.util.spec_from_file_location('m', r'{SCRIPT}')\n"
            "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
            "bad = [k for k in sys.modules if 'roi_engine' in k]\n"
            "print('BAD:' + ','.join(bad))\n")
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env,
                         cwd=str(tmp_path), timeout=300)
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip().endswith("BAD:"), res.stdout


# ------------------------------------------------------------- CLI y --data-root --
def test_data_root_rules(mod, tmp_path):
    def ns(**kw):
        base = dict(pre=False, parity_only=False, data_root=None, out=None)
        base.update(kw)
        return argparse.Namespace(**base)

    assert mod._data_root_error(ns(data_root=None, pre=True))                        # obligatorio
    assert mod._data_root_error(ns(data_root=None, parity_only=True))                # tambien en paridad
    assert mod._data_root_error(ns(data_root=mod.DEFAULT_ROOT, pre=True))            # raiz del repo
    assert mod._data_root_error(ns(data_root=ROOT, parity_only=True))                # checkout git
    snap = tmp_path / "snap"
    snap.mkdir()
    assert mod._data_root_error(ns(data_root=snap, pre=True, out=tmp_path / "pre.json")) is None
    (snap / ".git").mkdir()
    assert mod._data_root_error(ns(data_root=snap, pre=True))
    (snap / ".git").rmdir()
    out = tmp_path / "res.json"
    assert mod._data_root_error(ns(data_root=snap, out=out)) is None
    out.write_text("{}")
    assert "UNA SOLA EJECUCION" in (mod._data_root_error(ns(data_root=snap, out=out)) or "")
    assert mod._data_root_error(ns(data_root=snap, pre=True, out=out)) is None      # --pre puede reescribir


def test_main_rejects_repo_root_before_touching_anything(mod, tmp_path):
    with pytest.raises(SystemExit):
        mod.main(["--pre", "--data-root", str(ROOT), "--out", str(tmp_path / "x.json")])
    with pytest.raises(SystemExit):
        mod.main(["--parity-only"])


# ----------------------------------------------------------------- bootstrap --
def test_bootstrap_is_deterministic_and_reports_threshold_fractions(mod):
    dates = np.repeat(np.array([f"2024-05-{d:02d}" for d in range(1, 21)]), 5)
    x = np.linspace(-0.01, 0.0, len(dates))
    stats = {"d": (x, np.ones(len(x)))}
    a = mod.bootstrap_dias(dates, stats, 200, 42, thresholds={"d": ("le", -0.002)})
    b = mod.bootstrap_dias(dates, stats, 200, 42, thresholds={"d": ("le", -0.002)})
    assert a == b and 0.0 <= a["d"]["fraccion_replicas"] <= 1.0
    assert a["d"]["n_dias"] == 20 and a["d"]["n_replicas"] == 200
    assert mod.p_value(-0.01, 0.005) < 0.05 and mod.p_value(None, 0.1) == 1.0 and mod.p_value(0.1, 0.0) == 1.0


# ------------------------------------------------ (6) humo del JSON completo --
def test_full_mode_smoke_json_and_determinism(syn, fast, monkeypatch, tmp_path, capsys):
    mod = syn
    _patch_git(mod, monkeypatch)
    root = _write_root(tmp_path / "snap", _games(n_days=100))
    pre_path, r1, r2 = tmp_path / "pre.json", tmp_path / "r1.json", tmp_path / "r2.json"
    assert mod.main(["--pre", "--data-root", str(root), "--out", str(pre_path)]) in (0, 2)
    pre = json.loads(pre_path.read_text(encoding="utf-8"))
    assert pre["git_head"] == "deadbeef" and "resultados" not in json.dumps(pre).lower()
    pre["cota_050_no_vinculante"] = True                  # la liga sintetica puede recortar con 0,50
    pre_path.write_text(json.dumps(pre), encoding="utf-8")
    for out in (r1, r2):
        rc = mod.main(["--data-root", str(root), "--pre-json", str(pre_path), "--out", str(out),
                       "--n-boot", "50"])
        assert rc == 0
    res = json.loads(r1.read_text(encoding="utf-8"))
    assert set(res["criterios"]) == {
        "1_delta_logloss_combinado", "2_delta_negativo_en_cada_particion", "3_bP_positivo_en_las_tres",
        "4_brier_T_le_N", "5_ece_T_le_N", "6_logloss_T_lt_C", "7_moneyline_y_runline_no_empeoran"}
    assert all(isinstance(c["pasa"], bool) for c in res["criterios"].values())
    assert res["veredicto"]["veredicto"] in ("ACEPTA", "RECHAZA")
    assert set(res["particiones"]) == {"A", "B", "C"}
    assert all(p["b_P"] in mod.GRID for p in res["particiones"].values())
    assert res["veredicto"]["b_C"] == res["particiones"]["C"]["b_P"]
    assert res["pre_json_sha256"] and res["git_head"] == "deadbeef" and res["n_boot"] == 50
    assert {"python", "numpy", "pandas", "scipy"} <= set(res["versiones"])
    assert res["bootstrap"]["delta_logloss"]["n_replicas"] == 50
    assert len(res["informes"]) == 10
    errores = {k: v["error"] for k, v in res["informes"].items() if isinstance(v, dict) and "error" in v}
    assert not errores, errores
    assert set(res["perdidas"]["entrenamiento_por_cota"]["A"]) == {str(b) for b in mod.GRID}
    again = json.loads(r2.read_text(encoding="utf-8"))
    for key in ("criterios", "bootstrap", "veredicto", "particiones", "perdidas", "informes"):
        assert res[key] == again[key], key               # determinista bit a bit
    with pytest.raises(SystemExit):                       # una sola ejecucion: --out existente
        mod.main(["--data-root", str(root), "--pre-json", str(pre_path), "--out", str(r1)])


def test_full_mode_aborts_when_inputs_change_after_pre(syn, fast, monkeypatch, tmp_path):
    mod = syn
    _patch_git(mod, monkeypatch)
    rows = _games(n_days=100)
    root = _write_root(tmp_path / "snap", rows)
    pre_path = tmp_path / "pre.json"
    mod.main(["--pre", "--data-root", str(root), "--out", str(pre_path)])
    pre = json.loads(pre_path.read_text(encoding="utf-8"))
    pre["cota_050_no_vinculante"] = True
    pre_path.write_text(json.dumps(pre), encoding="utf-8")
    monkeypatch.setattr(mod, "git_head", lambda cwd: "otro")                 # HEAD distinto
    with pytest.raises(SystemExit, match="HEAD"):
        mod.main(["--data-root", str(root), "--pre-json", str(pre_path), "--out", str(tmp_path / "o.json")])
    monkeypatch.setattr(mod, "git_head", lambda cwd: "deadbeef")
    _write_root(tmp_path / "snap", rows[:-3])                                # datos distintos
    with pytest.raises(SystemExit, match="HASH"):
        mod.main(["--data-root", str(root), "--pre-json", str(pre_path), "--out", str(tmp_path / "o2.json")])


# --------------------------------------------------- C1 / C2 / C3 / R2 (revision Fable) --
def test_parity_stride_is_rejected_outside_parity_only(mod, tmp_path):
    with pytest.raises(SystemExit):
        mod.main(["--data-root", str(tmp_path), "--pre-json", str(tmp_path / "p.json"),
                  "--out", str(tmp_path / "o.json"), "--parity-stride", "5"])


def test_partial_json_with_criteria_exists_if_informes_fail(syn, fast, monkeypatch, tmp_path):
    mod = syn
    _patch_git(mod, monkeypatch)
    root = _write_root(tmp_path / "snap", _games(n_days=100))
    pre_path, out = tmp_path / "pre.json", tmp_path / "r.json"
    mod.main(["--pre", "--data-root", str(root), "--out", str(pre_path)])
    pre = json.loads(pre_path.read_text(encoding="utf-8"))
    pre["cota_050_no_vinculante"] = True
    pre_path.write_text(json.dumps(pre), encoding="utf-8")

    def boom(*a, **k):
        raise KeyboardInterrupt("interrumpido")

    monkeypatch.setattr(mod, "_informes", boom)
    with pytest.raises(KeyboardInterrupt):
        mod.main(["--data-root", str(root), "--pre-json", str(pre_path), "--out", str(out),
                  "--n-boot", "20"])
    part = json.loads(out.read_text(encoding="utf-8"))
    assert part["parcial"] is True and part["informes"] == {"estado": "en curso"}
    assert len(part["criterios"]) == 7 and part["veredicto"]["veredicto"] in ("ACEPTA", "RECHAZA")
    assert all("n_test_sin_muestra" in p for p in part["particiones"].values())
    with pytest.raises(SystemExit):                      # la guarda de --out sigue activa
        mod.main(["--data-root", str(root), "--pre-json", str(pre_path), "--out", str(out)])


def test_t2_reuses_fits_of_identical_models_bit_for_bit(syn, fast, monkeypatch):
    mod = syn
    lp, _ = mod.assert_family_and_params()
    results = _games(n_days=100)
    comp = mod.walk_components(results, lp)
    comp["f"] = np.clip(comp["f"], 0.9, 1.1)             # b >= 0,10 no recorta: mismo modelo
    arms = mod.Arms(comp, mod.pricing_kwargs(mod.get_adapter(mod.LEAGUE, mod.FAMILY, lp)))
    oc = mod.read_outcomes(results)
    y = (oc["total"] > arms.line).astype(float)
    train = comp["date"] <= SYN_FOLDS["C"]["train_end"]
    naive = {b: mod.fit_level(arms, b, y, train) for b in mod.GRID}
    calls = []
    real = mod.fit_level
    monkeypatch.setattr(mod, "fit_level", lambda *a, **k: (calls.append(1), real(*a, **k))[1])
    reused = mod.fit_t2_per_bound(arms, y, train)
    assert reused == naive                               # bit a bit
    assert len(calls) < len(mod.GRID)
