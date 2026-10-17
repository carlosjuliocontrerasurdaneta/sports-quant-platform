"""Pruebas sinteticas de `scripts/research/measure_el_modelo_manda.py`
(pre-registro `docs/research/2026-08-26-preregistro-el-modelo-manda.md`,
Addendum 2026-10-13 (2), seccion E9: los 9 grupos de pruebas minimas).

Ninguna prueba toca `data/calibration/` real ni el `.contar.jsonl` real: todo
usa filas sinteticas en `tmp_path` y rutas de pre-registro ficticias. Las
pruebas de aborto de `--medir` sustituyen el calculo estadistico por una
trampa que falla si se llega a calcular algo que dependa de `result`.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from sqp.config import ROOT
from sqp.evaluation.edge_information import one_row_per_pick
from sqp.evaluation.model_vs_market import score_model_vs_market

SCRIPT = ROOT / "scripts" / "research" / "measure_el_modelo_manda.py"
T_FAR = pd.Timestamp("2099-01-01", tz="UTC")


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location("measure_el_modelo_manda", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod() -> Any:
    return _load_module()


# ---------------------------------------------------------------- helpers --
def _row(event_id: str = "e1", selection: str = "home", market: str = "h2h",
         gen: str = "2026-01-01T10:00:00Z", result: str = "win",
         cal: float = 0.55, fair: float = 0.50, price: float = 2.0,
         league: str = "mlb", line: float = float("nan"),
         data_label: str = "real") -> dict[str, Any]:
    start = (pd.Timestamp(gen) + pd.Timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"league": league, "event_id": event_id, "market": market,
            "selection": selection, "line": line, "price_decimal": price,
            "generated_at": gen, "start_time": start, "result": result,
            "calibrated_probability": cal, "implied_probability_novig": fair,
            "estimated_probability": cal, "adjusted_probability": cal,
            "model_probability": cal, "estimated_edge": round(cal * price - 1.0, 4),
            "books_count": 10, "data_label": data_label}


def _synthetic(n_events: int, s: float = 0.5, seed: int = 1,
               leagues: tuple[str, ...] = ("mlb", "nba")) -> pd.DataFrame:
    """Una fila por evento; `estimated = (1-s)*a + s*fair` redondeada a 4
    decimales, como el stream real; sin calibrador (`cal == est`)."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_events):
        fair = round(float(rng.uniform(0.3, 0.7)), 4)
        a = round(float(np.clip(fair + rng.uniform(-0.15, 0.15), 0.2, 0.8)), 4)
        est = round((1 - s) * a + s * fair, 4)
        gen = (pd.Timestamp("2026-01-01") + pd.Timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ")
        r = _row(event_id=f"ev{i}", gen=gen, cal=est, fair=fair,
                 price=round(0.95 / fair, 2), league=leagues[i % len(leagues)],
                 result="win" if rng.random() < 0.5 else "loss")
        r["adjusted_probability"] = a
        r["model_probability"] = a
        r["estimated_probability"] = est
        rows.append(r)
    return pd.DataFrame(rows)


def _write_graded(root: Path, df: pd.DataFrame) -> None:
    cal = root / "data" / "calibration"
    cal.mkdir(parents=True, exist_ok=True)
    for liga, g in df.groupby("league"):
        g.to_csv(cal / f"graded_{liga}.csv", index=False)


def _pop(df: pd.DataFrame, mod: Any, t1: pd.Timestamp | None = T_FAR) -> pd.DataFrame:
    return mod.build_population(df, t1)["frame"]


def _keys(obj: Any) -> list[str]:
    out: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.append(str(k))
            out.extend(_keys(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(_keys(v))
    return out


class _Args(argparse.Namespace):
    pass


def _trap(*_a: Any, **_k: Any) -> None:
    raise AssertionError("se calculo algo que depende de `result` antes de abortar")


def _arm_traps(mod: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("score_model_vs_market", "cluster_bootstrap_ci", "primary_test",
                 "secondary_tests", "roi_comparison"):
        monkeypatch.setattr(mod, name, _trap)


def _fake_show(mapping: dict[str, str],
               by_ref: dict[tuple[str, str], str] | None = None) -> Any:
    def fake(ref: str, relpath: str, cwd: Path) -> str:
        if by_ref and (ref, relpath) in by_ref:
            return by_ref[(ref, relpath)]
        if relpath in mapping:
            return mapping[relpath]
        raise AssertionError(f"git_show_text inesperado: {relpath!r} (ref={ref!r})")
    return fake


def _medir_setup(mod: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, df: pd.DataFrame,
                 *, t1: str = "2027-01-01T00:00:00Z", n_required: int = 20,
                 doc_extra: str | None = None, jsonl_n: int = 20,
                 jsonl_at_commit: str | None = None) -> _Args:
    root = tmp_path / "repo"
    _write_graded(root, df)
    stem = "_test_fake_el_modelo_manda"
    pre = mod._WORKTREE_ROOT / "docs" / "research" / f"{stem}.md"
    rel_pre = f"docs/research/{stem}.md"
    rel_jsonl = f"docs/research/{stem}.contar.jsonl"
    commit = "0123456789abcdef0123456789abcdef01234567"
    doc = doc_extra if doc_extra is not None else (
        f"## Addendum\n\nT1 fijado = {t1}\ncommit del registro = {commit}\n")
    jsonl = json.dumps({"n_eventos": jsonl_n, "t1_candidato": t1}) + "\n"
    monkeypatch.setattr(mod, "N_REQUIRED", n_required)
    monkeypatch.setattr(mod, "git_status_porcelain", lambda cwd, *a, **k: "")
    by_ref = {(commit, rel_jsonl): jsonl_at_commit if jsonl_at_commit is not None else jsonl}
    monkeypatch.setattr(mod, "git_show_text",
                        _fake_show({rel_pre: doc, rel_jsonl: jsonl}, by_ref))
    monkeypatch.setattr(mod, "config_check", lambda root: {})
    args = _Args()
    args.data_root = root
    args.preregistro = pre
    args.t1 = t1
    args.seed = 42
    args.n_boot = 100
    return args


# ================================================= 1. lector sin efectos ==
def test_reader_never_mutates_corrupt_files_and_aborts_medir(
        mod: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "repo"
    cal = root / "data" / "calibration"
    (cal / "demo").mkdir(parents=True)
    good = _synthetic(6, leagues=("mlb",))
    good["league"] = "COLUMNA_DEL_CSV"          # debe ganar el nombre del fichero
    good.loc[0, "data_label"] = "synthetic"
    good.to_csv(cal / "graded_mlb.csv", index=False)
    (cal / "graded_zzz.csv").write_text("a,b\n1,2\n3,4,5,6\n", encoding="utf-8")
    _synthetic(3).to_csv(cal / "demo" / "graded_demo.csv", index=False)
    antes = {p.name: p.stat().st_mtime_ns for p in cal.iterdir() if p.is_file()}

    df, prov = mod.read_stream(root, "graded")

    despues = {p.name: p.stat().st_mtime_ns for p in cal.iterdir() if p.is_file()}
    assert antes == despues                                  # nada renombrado ni tocado
    assert sorted(p.name for p in cal.iterdir() if p.is_file()) == [
        "graded_mlb.csv", "graded_zzz.csv"]                  # sin cuarentena
    assert prov["faltantes"] == ["zzz"] and prov["errores_lectura"]
    assert set(df["league"]) == {"mlb"}                      # league del nombre del fichero
    real, n_no_real = mod.filter_real(df)
    assert n_no_real == 1 and len(real) == 5                 # filtra data_label == real

    _arm_traps(mod, monkeypatch)
    monkeypatch.setattr(mod, "_verify_registry",
                        lambda a, c: (pd.Timestamp("2027-01-01", tz="UTC"), "c", {}))
    args = _Args()
    args.data_root = root
    args.t1 = "2027-01-01T00:00:00Z"
    args.seed, args.n_boot = 42, 10
    with pytest.raises(SystemExit, match="no cargadas"):
        mod.run_medir(args)


def test_reader_header_only_file_is_reported_empty_without_abort(mod: Any, tmp_path: Path) -> None:
    cal = tmp_path / "repo" / "data" / "calibration"
    cal.mkdir(parents=True)
    _synthetic(4, leagues=("mlb",)).to_csv(cal / "graded_mlb.csv", index=False)
    (cal / "graded_vacia.csv").write_text(",".join(_synthetic(1).columns) + "\n", encoding="utf-8")
    _, prov = mod.read_stream(tmp_path / "repo", "graded")
    assert prov["vacias"] == ["vacia"] and prov["faltantes"] == []


# ============================================= 2. orden de E3 y sus cortes ==
def test_e3_filters_act_before_collapse_and_range_and_cut_exclude_whole_pick(
        mod: Any) -> None:
    t1 = pd.Timestamp("2026-03-01", tz="UTC")
    rows = [
        # P1: la servida mas antigua carece de calibrated_probability -> la
        # primera servida valida es la siguiente (igual que score_model_vs_market).
        _row("p1", gen="2026-01-01T00:00:00Z", cal=float("nan")),
        _row("p1", gen="2026-01-02T00:00:00Z", cal=0.60, fair=0.50),
        # P2: primera servida con p_cal = 2*0.9-0.1 = 1.7 fuera de [0,1]; la
        # segunda esta en rango, pero el pick entero queda fuera.
        _row("p2", gen="2026-01-01T00:00:00Z", cal=0.90, fair=0.10),
        _row("p2", gen="2026-01-03T00:00:00Z", cal=0.55, fair=0.50),
        # P3: la servida <= T1 carece de probabilidad; la primera valida es > T1.
        _row("p3", gen="2026-02-01T00:00:00Z", cal=float("nan")),
        _row("p3", gen="2026-04-01T00:00:00Z", cal=0.55, fair=0.50),
        # P4: dentro de todo.
        _row("p4", gen="2026-01-05T00:00:00Z", cal=0.52, fair=0.50),
        # Resultados excluidos: contados por valor, antes del colapso.
        _row("p5", result="push"), _row("p6", result="void"),
    ]
    res = mod.build_population(pd.DataFrame(rows), t1)
    pop, c = res["frame"], res["counts"]
    assert set(pop["event_id"]) == {"p1", "p4"}
    p1 = pop[pop["event_id"] == "p1"].iloc[0]
    assert p1["generated_at"] == "2026-01-02T00:00:00Z"
    assert p1["p_cal"] == pytest.approx(0.70)
    assert c["resultado_excluido_por_valor"] == {"push": 1, "void": 1}
    assert c["picks_p_cal_fuera_de_rango"] == 1
    assert c["primera_servida_posterior_a_t1"] == 1
    assert c["n_eventos"] == 2 and c["n_picks"] == 2
    # El colapso importado es el mismo: misma primera servida que one_row_per_pick.
    manual = one_row_per_pick(res["filtradas"])
    assert set(manual["generated_at"][manual["event_id"] == "p1"]) == {"2026-01-02T00:00:00Z"}
    # Sin corte (t1=None) P3 si entra.
    assert "p3" in set(mod.build_population(pd.DataFrame(rows), None)["frame"]["event_id"])


def test_aud003_nhl_h2h_first_serve_before_fix_excludes_whole_pick(mod: Any) -> None:
    """Addendum 2026-10-17: primera servida de nhl|h2h anterior a ffc5ad3 (o
    sin sello legible) -> pick entero fuera, sin saltar a una servida
    posterior; nhl|totals y mlb|h2h del mismo instante no se tocan."""
    antes, despues = "2026-10-16T12:56:02Z", "2026-10-16T12:56:03Z"
    ilegible = _row("n3", league="nhl", gen=antes)
    ilegible["generated_at"] = "no-es-fecha"
    rows = [
        _row("n1", league="nhl", gen=antes),
        _row("n1", league="nhl", gen="2026-10-17T10:00:00Z"),     # re-servida valida
        _row("n2", league="nhl", gen=despues),                     # justo en el corte
        ilegible,
        _row("n4", league="nhl", market="totals", gen=antes, line=5.5),
        _row("m1", league="mlb", gen=antes),
    ]
    for t1 in (T_FAR, None):
        res = mod.build_population(pd.DataFrame(rows), t1)
        assert set(res["frame"]["event_id"]) == {"n2", "n4", "m1"}
        assert res["counts"]["picks_mercado_invalido_aud003"] == 2
        assert res["counts"]["eventos_sin_corte"] == 3
        # La sensibilidad sin colapsar tampoco conserva la re-servida de n1.
        malos = res["filtradas"][res["gid"].isin(res["malos_gid"])]
        assert set(malos["event_id"]) == {"n1", "n3"}


def test_aud003_literal_matches_the_prediction_gate(mod: Any) -> None:
    """Si el gate anade o cambia una entrada, este test obliga a decidir por
    addendum como la trata esta medicion (enmienda del gate 2026-10-16)."""
    from sqp.risk.prediction_gate import INVALID_BEFORE
    assert mod.INVALID_BEFORE == INVALID_BEFORE


def test_e3_counts_non_pregame_and_illegible_first_serve_without_excluding(mod: Any) -> None:
    r = _row("a", gen="2026-01-01T10:00:00Z")
    r["start_time"] = "2026-01-01T09:00:00Z"                 # generado despues del inicio
    b = _row("b")
    b["start_time"] = "no-es-fecha"
    res = mod.build_population(pd.DataFrame([r, b]), T_FAR)
    assert res["counts"]["n_picks"] == 2
    assert res["counts"]["primera_servida_no_pregame"] == 1
    assert res["counts"]["primera_servida_start_time_ilegible"] == 1


# ============================================ 3. n cuenta eventos, no filas ==
def test_n_counts_events_not_picks_or_rows_and_cluster_is_event_id(mod: Any) -> None:
    rows = []
    for ev in ("e1", "e2", "e3"):
        for sel, cal, fair in (("home", 0.6, 0.5), ("away", 0.4, 0.5)):
            for d in ("2026-01-01", "2026-01-02"):          # dos servidas por pick
                rows.append(_row(ev, sel, gen=f"{d}T00:00:00Z", cal=cal, fair=fair,
                                 result="win" if sel == "home" else "loss"))
    df = pd.DataFrame(rows)
    res = mod.build_population(df, T_FAR)
    assert len(df) == 12 and res["counts"]["n_picks"] == 6 and res["counts"]["n_eventos"] == 3
    out = mod.primary_test(res["frame"], 42, 50)
    assert out["n_eventos"] == 3 and out["n_picks"] == 6
    # Un evento por segmento: eventos por segmento tambien son eventos distintos.
    assert mod.events_by_segment(res["frame"]) == {"mlb|h2h": 3}
    # CR1 agrupa por evento: 3 clusters aunque haya 6 picks.
    seg = mod.cr1_by_event(np.array([0.1, 0.1, 0.2, 0.2, 0.3, 0.3]),
                           res["frame"]["event_id"].to_numpy())
    assert seg["g"] == 3 and seg["n"] == 6


# ============================================== 4. --contar no revela nada ==
def _contar_args(tmp_path: Path, name: str, no_log: bool) -> _Args:
    root = tmp_path / f"repo_{name}"
    _write_graded(root, _synthetic(30))
    served = root / "data" / "calibration"
    _synthetic(30).drop(columns=["result"]).to_csv(served / "served_mlb.csv", index=False)
    args = _Args()
    args.data_root = root
    args.preregistro = tmp_path / f"{name}.md"
    args.no_log = no_log
    return args


def test_contar_emits_no_result_dependent_field_and_appends_exactly_one_line(
        mod: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "git_rev_parse", lambda ref, cwd: "deadbeef")
    monkeypatch.setattr(mod, "SEG_MIN_EVENTS", 10)
    args = _contar_args(tmp_path, "pre", no_log=False)
    out = mod.run_contar(args)
    prohibida = re.compile(r"brier|diff|acierto|roi|hit|p_valor|^z$|^p$|^pvalor$", re.I)
    for k in _keys(out):
        assert not prohibida.search(k), k
    texto = json.dumps(out)
    for sub in ("brier", "acierto", "p_valor", "roi_"):
        assert sub not in texto.lower()
    log = mod.contar_log_path(args.preregistro)
    lineas = log.read_text(encoding="utf-8").splitlines()
    assert len(lineas) == 1
    reg = json.loads(lineas[0])
    for k in ("instante_ejecucion_utc", "head", "t1_candidato", "n_eventos", "n_picks",
              "n_eventos_sin_corte", "eventos_por_segmento", "segmentos_con_800_o_mas",
              "exclusiones", "picks_sin_graduar", "chequeo_s", "csv_leidos"):
        assert k in reg
    assert reg["n_eventos"] == 30 and reg["segmentos_con_800_o_mas"] == ["mlb|h2h", "nba|h2h"]
    assert reg["csv_leidos"]["graded"][0]["sha256"]
    mod.run_contar(args)
    assert len(log.read_text(encoding="utf-8").splitlines()) == 2   # append-only


def test_contar_no_log_does_not_write_the_registry(
        mod: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "git_rev_parse", lambda ref, cwd: "deadbeef")
    args = _contar_args(tmp_path, "nolog", no_log=True)
    out = mod.run_contar(args)
    assert "no se escribio" in out["aviso"].lower()
    assert not mod.contar_log_path(args.preregistro).exists()


# ============================== 5. --medir aborta sin calcular nada (Brier) ==
def test_medir_without_t1_is_a_cli_error(mod: Any) -> None:
    with pytest.raises(SystemExit) as exc:
        mod.main(["--medir"])
    assert exc.value.code == 2


def test_medir_aborts_without_addendum_and_with_different_t1(
        mod: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    df = _synthetic(25)
    args = _medir_setup(mod, monkeypatch, tmp_path, df, doc_extra="# sin addendum\n")
    _arm_traps(mod, monkeypatch)
    with pytest.raises(SystemExit, match="No hay addendum"):
        mod.run_medir(args)
    # T1 pedido distinto del addendum
    args = _medir_setup(mod, monkeypatch, tmp_path, df)
    args.t1 = "2027-02-01T00:00:00Z"
    with pytest.raises(SystemExit, match="no coincide"):
        mod.run_medir(args)


def test_medir_accepts_same_instant_in_other_iso_form_and_aborts_on_registry_mismatch(
        mod: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    df = _synthetic(25)
    args = _medir_setup(mod, monkeypatch, tmp_path, df, jsonl_n=19)   # nunca cruzo N
    _arm_traps(mod, monkeypatch)
    with pytest.raises(SystemExit, match="registro"):
        mod.run_medir(args)


def test_medir_aborts_when_n_at_t1_is_below_threshold(
        mod: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    df = _synthetic(25)
    args = _medir_setup(mod, monkeypatch, tmp_path, df, n_required=26, jsonl_n=26)
    _arm_traps(mod, monkeypatch)
    with pytest.raises(SystemExit, match=r"n\(T1\) = 25"):
        mod.run_medir(args)


def test_medir_aborts_when_s_is_out_of_tolerance_without_computing_brier(
        mod: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    args = _medir_setup(mod, monkeypatch, tmp_path, _synthetic(25, s=0.4))
    _arm_traps(mod, monkeypatch)
    with pytest.raises(SystemExit, match="E7"):
        mod.run_medir(args)


def test_medir_aborts_when_the_cited_commit_lacks_the_registry_line(
        mod: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    args = _medir_setup(mod, monkeypatch, tmp_path, _synthetic(25), jsonl_at_commit="")
    _arm_traps(mod, monkeypatch)
    with pytest.raises(SystemExit, match="commit del registro citado"):
        mod.run_medir(args)


def test_medir_aborts_with_a_dirty_tree(
        mod: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    args = _medir_setup(mod, monkeypatch, tmp_path, _synthetic(25))
    monkeypatch.setattr(mod, "git_status_porcelain", lambda cwd, *a, **k: " M src/sqp/x.py\n")
    _arm_traps(mod, monkeypatch)
    with pytest.raises(SystemExit, match="NO esta vacio"):
        mod.run_medir(args)


def test_s_check_descriptive_subset_and_market_shrink_counts(mod: Any) -> None:
    pop = _pop(_synthetic(120), mod)
    pop.loc[pop.index[:20], "adjusted_probability"] = float("nan")   # esquema antiguo
    chk = mod.s_check(pop)
    d = chk["descriptivo_solo_con_adjusted_probability"]
    assert d["n_filas"] < chk["n_filas"] and chk["ok"]
    df = pd.DataFrame({"market_shrink": [float("nan"), 0.5, 0.0, 0.4]})
    assert mod.market_shrink_counts(df) == {"columna_presente": True, "no_nulas": 3,
                                            "distintas_de_0_5": 2}
    assert mod.market_shrink_counts(pd.DataFrame({"a": [1]}))["columna_presente"] is False


def test_parse_t1_addendum_requires_literal_lines_and_ignores_quoted_spec_text(mod: Any) -> None:
    spec = ("se escribe en un addendum con dos lineas literales: `T1 fijado = <ISO-8601>` y "
            "`commit del registro = <sha>`.\n")
    assert mod.parse_t1_addendum(spec) is None
    ok = spec + "T1 fijado = 2026-12-01T00:00:00Z\ncommit del registro = abcdef1\n"
    assert mod.parse_t1_addendum(ok) == ("2026-12-01T00:00:00Z", "abcdef1")
    dos = ok + "T1 fijado = 2026-12-02T00:00:00Z\n"
    with pytest.raises(SystemExit):
        mod.parse_t1_addendum(dos)


# ================================================== 6. primario (E5) ==
def _pop_with_probs(p_cal: np.ndarray, y: np.ndarray, fair: float = 0.5) -> pd.DataFrame:
    n = len(y)
    return pd.DataFrame({
        "league": "mlb", "market": "h2h", "event_id": [f"e{i}" for i in range(n)],
        "selection": "home", "line": float("nan"),
        "generated_at": "2026-01-01T00:00:00Z",
        "result": np.where(y == 1, "win", "loss"), "p_cal": p_cal,
        "implied_probability_novig": fair, "calibrated_probability": (p_cal + fair) / 2})


def test_primary_matches_score_model_vs_market_by_hand_and_decides_from_the_ci(mod: Any) -> None:
    df = _synthetic(60)
    pop = _pop(df, mod)
    out = mod.primary_test(pop, 42, 200)
    d = df[df["result"].isin(["win", "loss"])].dropna(
        subset=["calibrated_probability", "implied_probability_novig"]).copy()
    d["p_cal"] = 2 * d["calibrated_probability"] - d["implied_probability_novig"]
    d["_g"] = "g"
    ref = score_model_vs_market(d, by=["_g"], n_boot=200, seed=42, model_col="p_cal",
                                market_col="implied_probability_novig").iloc[0]
    assert out["brier_diff"] == ref["brier_diff"]
    assert out["brier_diff_lo"] == ref["brier_diff_lo"] and out["brier_diff_hi"] == ref["brier_diff_hi"]
    assert out["decision"] == ("PASA" if ref["brier_diff_hi"] < 0 else "FALLA")

    rng = np.random.default_rng(3)
    y = (rng.random(300) < 0.5).astype(int)
    mejor = mod.primary_test(_pop_with_probs(0.5 + 0.3 * (2 * y - 1.0), y), 42, 200)
    peor = mod.primary_test(_pop_with_probs(0.5 - 0.3 * (2 * y - 1.0), y), 42, 200)
    igual = mod.primary_test(_pop_with_probs(np.full(300, 0.5), y), 42, 200)
    assert mejor["decision"] == "PASA" and not mejor["modelo_peor"]
    assert peor["decision"] == "FALLA" and peor["modelo_peor"]
    assert igual["decision"] == "FALLA" and not igual["modelo_peor"]


# ====================================== 7. CR1 por evento y Holm (E5) ==
def test_cr1_by_event_matches_hand_computation_with_three_events(mod: Any) -> None:
    d = np.array([0.1, 0.3, 0.2, -0.2])
    cl = np.array(["a", "a", "b", "c"])
    out = mod.cr1_by_event(d, cl)
    # D = 0.1; sumas por evento de (d - D): a 0.2, b 0.1, c -0.3 -> 0.14
    se2 = (3 / 2) * 0.14 / 16
    assert out["d_hat"] == pytest.approx(0.1) and out["g"] == 3 and out["n"] == 4
    assert out["se"] == pytest.approx(math.sqrt(se2))
    z = 0.1 / math.sqrt(se2)
    assert out["z"] == pytest.approx(z)
    assert out["p"] == pytest.approx(math.erfc(abs(z) / math.sqrt(2)))
    assert mod.cr1_by_event(np.array([1.0, 2.0]), np.array(["a", "a"]))["se"] is None


def test_holm_stops_at_the_first_non_rejection(mod: Any) -> None:
    h = mod.holm({"a": 0.01, "b": 0.02, "c": 0.06})
    assert (h["a"]["rechaza"], h["b"]["rechaza"], h["c"]["rechaza"]) == (True, True, False)
    assert h["a"]["umbral_holm"] == pytest.approx(0.05 / 3)
    assert h["c"]["umbral_holm"] == pytest.approx(0.05)
    h2 = mod.holm({"a": 0.03, "b": 0.001, "c": 0.04})        # el menor rechaza, luego para
    assert h2["b"]["rechaza"] and not h2["a"]["rechaza"] and not h2["c"]["rechaza"]
    assert mod.holm({"a": None})["a"]["rechaza"] is False


def test_secondary_labels_worse_model_and_excludes_small_segments_from_m(
        mod: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "SEG_MIN_EVENTS", 40)
    rng = np.random.default_rng(11)
    frames = []
    for liga, n, signo in (("mlb", 150, -1.0), ("nba", 150, +1.0), ("nhl", 10, +1.0)):
        y = (rng.random(n) < 0.5).astype(int)
        amp = rng.uniform(0.1, 0.4, n)                       # ruido: SE > 0
        f = _pop_with_probs(0.5 + signo * amp * (2 * y - 1.0), y)
        f["league"] = liga
        f["event_id"] = [f"{liga}{i}" for i in range(n)]
        frames.append(f)
    pop = pd.concat(frames, ignore_index=True)
    out = mod.secondary_tests(pop, 42, 100)
    assert out["m"] == 2 and set(out["segmentos"]) == {"mlb|h2h", "nba|h2h"}   # nhl (10) fuera
    assert out["segmentos"]["mlb|h2h"]["decision"] == "MODELO_PEOR"            # rechaza con D > 0
    assert out["segmentos"]["nba|h2h"]["decision"] == "PASA_PRIMERA_PUERTA"
    assert out["segmentos"]["mlb|h2h"]["d_hat"] > 0 > out["segmentos"]["nba|h2h"]["d_hat"]
    assert mod.secondary_tests(pop[pop["league"] == "nhl"], 42, 100)["m"] == 0


# ============================================== 8. regla de apuesta E6 ==
def _bet(mod: Any, p: float, price: float, fair: float, books: float, rule: str = "full") -> bool:
    bet, _ = mod.bet_mask(np.array([p]), np.array([price]), np.array([fair]),
                          np.array([books]), rule)
    return bool(bet[0])


def test_bet_rule_boundaries(mod: Any) -> None:
    assert _bet(mod, 0.51, 2.0, 0.51, 10)                    # e_adj = 0.02 -> apuesta
    assert not _bet(mod, 0.5099, 2.0, 0.5099, 10)   # e_adj < 0.02 -> no
    assert _bet(mod, 0.5375, 2.0, 0.5375, 10)                # e = 0.075 -> apuesta
    assert not _bet(mod, 0.53755, 2.0, 0.53755, 10)          # e = 0.0751 -> no
    # books_count = 1 aplica 0.015: e = 0.025 pasa con 10 libros y no con 1
    assert _bet(mod, 0.5125, 2.0, 0.5125, 10) and not _bet(mod, 0.5125, 2.0, 0.5125, 1)
    # gap > 0.06 aplica +0.02 ademas de 0.35*gap
    assert _bet(mod, 0.56, 1.9, 0.51, 10)                    # gap 0.05: e_adj ~ 0.0465
    assert not _bet(mod, 0.56, 1.9, 0.49, 10)                # gap 0.07: e_adj ~ 0.0195
    # cuota <= 1 nunca; regla simple ignora la penalizacion
    assert not _bet(mod, 0.99, 1.0, 0.99, 10)
    assert _bet(mod, 0.56, 1.9, 0.49, 10, "simple")


def _roi_unit(n: int, ganador_selectivo: bool) -> pd.DataFrame:
    rng = np.random.default_rng(5)
    y = (rng.random(n) < 0.5).astype(int)
    p_cal = np.where(y == 1, 0.53, 0.40) if ganador_selectivo else np.full(n, 0.40)
    return pd.DataFrame({
        "event_id": [f"e{i}" for i in range(n)], "result": np.where(y == 1, "win", "loss"),
        "price_decimal": 2.0, "implied_probability_novig": 0.50, "books_count": 10,
        "calibrated_probability": 0.52, "p_cal": p_cal})


def test_roi_delta_ci_is_reproducible_and_a_policy_without_bets_fails(mod: Any) -> None:
    unit = _roi_unit(80, ganador_selectivo=True)
    a = mod.roi_comparison(unit, 42, 400)
    b = mod.roi_comparison(unit, 42, 400)
    assert a == b                                            # semilla 42 reproducible
    assert a["roi_s_0"] == pytest.approx(1.0)                # solo apuesta a ganadoras
    assert a["delta"] > 0 and a["ic95_lo"] > 0 and a["decision"] == "PASA"
    assert a["fraccion_indefinidas"] <= 0.01
    sin = mod.roi_comparison(_roi_unit(80, ganador_selectivo=False), 42, 400)
    assert sin["decision"] == "FALLA" and "no apuesta" in sin["razon"]


def test_second_gate_only_runs_for_units_that_passed_the_first_gate(mod: Any) -> None:
    pop = _roi_unit(40, True).assign(league="mlb", market="h2h")
    nada = mod.second_gate(pop, {"decision": "FALLA"}, {"segmentos": {}}, 42, 50)
    assert "ninguna unidad" in nada["nota"]
    algo = mod.second_gate(pop, {"decision": "PASA"}, {"segmentos": {}}, 42, 50)
    assert set(algo) == {"global"} and "sensibilidad_regla_simple" in algo["global"]


# ======================================================= 9. E7: s ==
def test_s_check_detects_s_0_4_and_accepts_s_0_5_with_four_decimal_rounding(mod: Any) -> None:
    malo = mod.s_check(_pop(_synthetic(200, s=0.4), mod))
    bueno = mod.s_check(_pop(_synthetic(200, s=0.5), mod))
    assert not malo["ok"] and malo["mediana_s_hat"] == pytest.approx(0.4, abs=0.01)
    assert bueno["ok"] and abs(bueno["mediana_s_hat"] - 0.5) <= 0.01
    assert mod.s_check(pd.DataFrame())["ok"] is False


def test_s_check_falls_back_to_model_probability_for_old_schema_rows(mod: Any) -> None:
    pop = _pop(_synthetic(100), mod).drop(columns=["adjusted_probability"])
    assert mod.s_check(pop)["ok"]


# ======================================== extremo a extremo (humo sintetico) ==
def test_medir_end_to_end_on_synthetic_data(
        mod: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "SEG_MIN_EVENTS", 20)
    args = _medir_setup(mod, monkeypatch, tmp_path, _synthetic(60))
    out = mod.run_medir(args)
    assert out["modo"] == "medir" and out["chequeo_s"]["ok"]
    assert out["primario"]["decision"] in ("PASA", "FALLA")
    assert out["secundarios"]["m"] == 2
    assert set(out["sensibilidades_sin_poder_de_decision"]) >= {
        "todas_las_servidas_sin_colapsar", "sin_corte_t1"}
    assert out["procedencia"]["commit_registro"] == "0123456789abcdef0123456789abcdef01234567"
    assert "commit_addendum_t1" in out["procedencia"]
    assert out["procedencia"]["market_shrink_en_graduado"]["columna_presente"] is False
    assert out["procedencia"]["difiere_de_lo_congelado"] is True      # n_boot = 100
    assert os.path.exists(mod.__file__) and "segunda_puerta" in out
