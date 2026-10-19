"""Pruebas sinteticas de `scripts/research/measure_segment_market_weight.py`
(pre-registro `docs/research/2026-10-13-preregistro-peso-mercado-por-segmento.md`,
contrato en la seccion 11).

Ninguna prueba toca `data/` real: todo usa filas sinteticas y repositorios git
temporales (para resolver H y T0 y para los abortos de `--ajustar`/`--medir`).
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from argparse import Namespace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sqp.config import ROOT

# Modulo caro (CLAUDE-005 / H-2): fuera de la suite rapida del hook Stop; CI
# lo ejecuta siempre. A mano: `PYTHONPATH=src pytest -m heavy`.
pytestmark = pytest.mark.heavy

SCRIPT = ROOT / "scripts" / "research" / "measure_segment_market_weight.py"
T0 = pd.Timestamp("2026-11-05T00:00:00Z")


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("measure_segment_market_weight", SCRIPT)
    assert spec is not None and spec.loader is not None
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_script_exists():
    assert SCRIPT.exists()


# --------------------------------------------------------------- helpers git --
def _run_git(repo: Path, *args: str, date: str | None = None) -> str:
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    if date:
        env["GIT_COMMITTER_DATE"] = date
        env["GIT_AUTHOR_DATE"] = date
    res = subprocess.run(["git", *args], cwd=str(repo), env=env, capture_output=True,
                         text=True, check=True)
    return res.stdout.strip()


def _commit(repo: Path, files: dict[str, str], date: str = "2026-10-13T12:00:00+00:00") -> str:
    for rel, text in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        _run_git(repo, "add", rel)
    _run_git(repo, "commit", "-q", "-m", "c", date=date)
    return _run_git(repo, "rev-parse", "HEAD")


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init", "-q")
    for d in ("src", "configs", "scripts/research"):
        (repo / d).mkdir(parents=True, exist_ok=True)
        (repo / d / ".gitkeep").write_text("", encoding="utf-8")
    return repo


PRE_REL = "docs/research/2026-10-13-preregistro-peso-mercado-por-segmento.md"
MM_REL = "docs/research/2026-11-05-resultado-el-modelo-manda.md"


def _repo_with_h(tmp_path: Path, mod, monkeypatch) -> tuple[Path, Path]:
    repo = _init_repo(tmp_path)
    _commit(repo, {PRE_REL: "# pre\n", "src/.gitkeep": "", "configs/.gitkeep": "",
                   "scripts/research/.gitkeep": ""})
    monkeypatch.setattr(mod, "_WORKTREE_ROOT", repo)
    monkeypatch.setattr(mod, "settings_market_shrink", lambda: 0.5)
    return repo, repo / PRE_REL


# -------------------------------------------------------------- datos sinteticos --
def _row(event_id, start, *, league="nfl", market="h2h", selection="home",
         cal=0.55, fair=0.50, result="win", gen_h=5.0, price=2.0, line=np.nan):
    st = pd.Timestamp(start, tz="UTC") if not isinstance(start, pd.Timestamp) else start
    return {"league": league, "event_id": event_id, "market": market,
            "selection": selection, "line": line, "price_decimal": price,
            "calibrated_probability": cal, "implied_probability_novig": fair,
            "start_time": st.isoformat().replace("+00:00", "Z"),
            "generated_at": (st - pd.Timedelta(hours=gen_h)).isoformat(),
            "result": result, "data_label": "real", "model_probability": cal}


def _picks(mod, rows, table=None):
    df = pd.DataFrame(rows)
    return mod.prepare_picks(df, table or mod.parse_regime_table(None))


# Texto REAL vigente del pre-registro (7.4 + seccion Addenda con los Addenda (1) y (2)).
REAL_PRE_TEXT = '''### 7.4 Fecha y disparo

- La **primera** línea con `n ≥ 3.300` fija **T1 = E − 14 días**, que se escribe en un addendum (`T1 fijado = <ISO>` y `commit del registro = <sha>`) antes de `--medir`. Población de evaluación: eventos con `start_time ∈ (T0, T1]`.


## Addenda

Ninguno todavía. Aquí se añaden, por commits posteriores a H y sin editar lo anterior: la tabla de régimen de `s` y los cambios de régimen (§10), T0 si lo fija el operador (§3.7), el `.sk.json` (§5.4) y T1 (§7.4).

### Addendum 2026-10-13 (1) — formato de la tabla de régimen de `s` y columna `market_shrink` (antes de T0)

No cambia ningún criterio; fija el formato que §10 y §11 dejaban abierto (hallazgo de la revisión de Fable del script).

- **Fuente de `s_t` por fila, en este orden:** (1) la columna `market_shrink` de la fila, si existe y es finita (el stream la guarda desde el commit que la añade a `ServedStore.COLUMNS`; vale 0,0 cuando la fila no tuvo no-vig y no se mezcló); (2) si no, la tabla de régimen de abajo; (3) si ninguna aplica, `s_t` desconocido: la fila se excluye y se cuenta (§4.4).
- **Formato literal de cada entrada de la tabla**, una por línea, al inicio de línea, dentro de la sección «Addenda»:

      s servido = <valor en [0,1] | desconocido> | desde = <ISO-8601 con zona> | alcance = <global | liga|mercado>

  Entrada implícita: `s servido = 0.5 | desde = 2026-06-21T00:00:00+00:00 | alcance = global`. Gana la entrada aplicable con `desde` más reciente, comparada con el `generated_at` de la fila; a igual `desde`, la de alcance `liga|mercado` sobre la global.
- Cualquier línea de la sección «Addenda» que empiece por `s servido` y no cumpla este formato hace **abortar** `--ajustar` y `--medir`. Nunca se ignora en silencio.
- Si la columna y la tabla discrepan en una fila, manda la columna y la discrepancia se cuenta y se informa.

### Addendum 2026-10-13 (2) — precisiones a la tabla de régimen de `s` (antes de T0)

Redactado por Fable en la verificación del script. No cambia ningún criterio; precisa el Addendum 2026-10-13 (1).

- La discrepancia entre la columna `market_shrink` y la tabla se cuenta **después** de los filtros de §4.1 y del colapso de §4.2: solo sobre las filas que llegan a la reconstrucción de §4.4.
- Una columna `market_shrink` finita fuera de [0,1] no se sustituye por la tabla: la fila se excluye y se cuenta en un recuento propio.
- El `alcance` de una entrada `liga|mercado` es el **segmento** de §4.3. Para tenis es el circuito (`tennis_atp|<mercado>` o `tennis_wta|<mercado>`), nunca un torneo ni `atp`/`wta`. Una entrada con alcance de torneo, o con un `desde` sin zona horaria, no cumple el formato y hace abortar `--ajustar` y `--medir`.
- Si la tabla no puede leerse del pre-registro en HEAD, `--ajustar` y `--medir` abortan; `--contar` lo informa.
'''



# ------------------------------------------------------------------ estimador --
def _stats_arrays(seed=3, n_events=6, per=3):
    rng = np.random.default_rng(seed)
    n = n_events * per
    fair = rng.uniform(0.3, 0.7, n)
    p_cal = np.clip(fair + rng.normal(0, 0.1, n), 0.05, 0.95)
    y = (rng.uniform(size=n) < fair).astype(float)
    ev = np.repeat([f"e{i}" for i in range(n_events)], per)
    return p_cal - fair, p_cal, fair, y, ev


def test_s_hat_matches_numeric_brier_minimum(mod):
    d, p_cal, fair, y, ev = _stats_arrays()
    st = mod.node_stats(d, p_cal, y, ev)
    grid = np.linspace(-10, 10, 20001)
    brier = [np.mean((p_cal - s * d - y) ** 2) for s in grid]
    s_num = grid[int(np.argmin(brier))]
    assert st["s_hat"] == pytest.approx(s_num, abs=2e-3)
    # Y es el minimo exacto: el gradiente es cero en s_hat.
    assert np.sum(d * (p_cal - st["s_hat"] * d - y)) == pytest.approx(0.0, abs=1e-9)


def test_v_reproduces_hand_computed_sandwich_with_three_events(mod):
    d = np.array([0.1, -0.2, 0.3, 0.1])
    p_cal = np.array([0.6, 0.4, 0.7, 0.5])
    y = np.array([1.0, 0.0, 0.0, 1.0])
    ev = np.array(["a", "a", "b", "c"])
    g = {"a": 0.1 * (0.6 - 1) + (-0.2) * (0.4 - 0), "b": 0.3 * (0.7 - 0), "c": 0.1 * (0.5 - 1)}
    dd = {"a": 0.1 ** 2 + 0.2 ** 2, "b": 0.3 ** 2, "c": 0.1 ** 2}
    sd = sum(dd.values())
    s_hat = sum(g.values()) / sd
    v = sum((g[k] - s_hat * dd[k]) ** 2 for k in g) / sd ** 2
    st = mod.node_stats(d, p_cal, y, ev)
    assert st["n"] == 3
    assert st["s_hat"] == pytest.approx(s_hat)
    assert st["v"] == pytest.approx(v)


def test_node_with_zero_disagreement_has_no_estimate(mod):
    st = mod.node_stats(np.zeros(3), np.array([.5, .5, .5]), np.array([1., 0., 1.]),
                        np.array(["a", "b", "c"]))
    assert st["s_hat"] is None and st["v"] is None


# --------------------------------------------------------------- encogimiento --
def test_shrinkage_limits(mod):
    nodo = {"n": 100, "s_hat": 0.9, "v": 0.0}
    assert mod.shrink_node(nodo, parent=0.3) == pytest.approx(0.9)          # v -> 0
    nodo = {"n": 100, "s_hat": 0.9, "v": 1e9}
    assert mod.shrink_node(nodo, parent=0.3) == pytest.approx(0.3, abs=1e-6)  # v -> inf
    nodo = {"n": 29, "s_hat": 0.9, "v": 0.0}
    assert mod.shrink_node(nodo, parent=0.3) == 0.3                          # n < 30 hereda
    nodo = {"n": 100, "s_hat": None, "v": None}
    assert mod.shrink_node(nodo, parent=0.3) == 0.3                          # sum D = 0


def _synthetic_fit_rows(n_events, league, market, seed, shift):
    """Picks cuyo mercado es informativo: y ~ Bernoulli(fair)."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_events):
        fair = rng.uniform(0.35, 0.65)
        p_cal = float(np.clip(fair + shift * rng.choice([-1, 1]) * 0.1, 0.02, 0.98))
        cal = 0.5 * p_cal + 0.5 * fair
        rows.append(_row(f"{league}-{market}-{i}", T0 - pd.Timedelta(days=5 + i % 20),
                         league=league, market=market, cal=round(cal, 4),
                         fair=round(fair, 4),
                         result="win" if rng.uniform() < fair else "loss"))
    return rows


def test_final_weights_are_within_unit_interval(mod):
    rows = _synthetic_fit_rows(60, "nfl", "h2h", 1, 1.0) + \
        _synthetic_fit_rows(50, "ncaaf", "spreads", 2, 1.0)
    picks, _ = _picks(mod, rows)
    fit = mod.fit_weights(picks)
    assert fit["segmentos"]
    for st in fit["segmentos"].values():
        assert 0.0 <= st["s_k"] <= 1.0
    # Un s_hat enorme se recorta.
    assert mod._clip01(7.0) == 1.0 and mod._clip01(-3.0) == 0.0


def test_segment_below_threshold_inherits_family_and_new_segment_uses_family(mod):
    rows = _synthetic_fit_rows(60, "wnba", "h2h", 5, 1.0) + \
        _synthetic_fit_rows(10, "nhl", "h2h", 6, 1.0)
    picks, _ = _picks(mod, rows)
    fit = mod.fit_weights(picks)
    nhl = fit["segmentos"]["nhl|h2h"]
    assert nhl["n"] < 30
    assert nhl["s_tilde"] == fit["familias"]["hockey|h2h"]["s_tilde"]
    # hockey|h2h solo tiene 10 eventos: hereda el global.
    assert fit["familias"]["hockey|h2h"]["s_tilde"] == fit["global"]["s_tilde"]
    # NBA no tiene ajuste: usa la familia basketball|h2h (ajustada sobre WNBA).
    s = mod.weights_for(fit, pd.Series(["nba|h2h"]), pd.Series(["basketball|h2h"]))
    assert s[0] == pytest.approx(mod._clip01(fit["familias"]["basketball|h2h"]["s_tilde"]))
    # Sin familia legible: el global.
    s = mod.weights_for(fit, pd.Series(["xx|h2h"]), pd.Series([None]))
    assert s[0] == pytest.approx(mod._clip01(fit["global"]["s_tilde"]))


def test_tennis_tournaments_group_by_circuit(mod):
    assert mod.segment_id("tennis_atp_cincinnati", "h2h") == "tennis_atp|h2h"
    assert mod.segment_id("atp", "h2h") == "tennis_atp|h2h"
    assert mod.segment_id("tennis_wta_us_open", "h2h") == "tennis_wta|h2h"
    assert mod.segment_id("wta", "h2h") == "tennis_wta|h2h"
    assert mod.segment_id("nfl", "spreads") == "nfl|spreads"
    assert mod.family_id("tennis_atp_cincinnati", "h2h") == "tennis|h2h"
    assert mod.family_id("nba", "totals") == "basketball|totals"
    assert mod.family_id("liga_inexistente_zz", "h2h") is None


# --------------------------------------------------------- reconstruccion p_cal --
def test_p_cal_reconstruction_with_regime_values(mod):
    cal, fair = np.array([0.55]), np.array([0.50])
    p05 = mod.reconstruct_p_cal(cal, fair, np.array([0.5]))
    assert p05[0] == pytest.approx(2 * 0.55 - 0.50)
    p0 = mod.reconstruct_p_cal(cal, fair, np.array([0.0]))
    assert p0[0] == pytest.approx(0.55)
    assert np.isnan(mod.reconstruct_p_cal(cal, fair, np.array([1.0]))[0])
    assert np.isnan(mod.reconstruct_p_cal(cal, fair, np.array([np.nan]))[0])


def test_s_t_one_or_unknown_is_excluded_and_counted(mod):
    doc = ("## Addenda\n"
           "s servido = 1.0 | desde = 2026-10-15T00:00:00Z | alcance = nfl|h2h\n"
           "s servido = desconocido | desde = 2026-10-20T00:00:00Z | alcance = ncaaf|h2h\n"
           "s servido = 0 | desde = 2026-10-01T00:00:00Z | alcance = mlb|h2h\n")
    table = mod.parse_regime_table(doc)
    rows = [
        _row("e0", "2026-10-10T20:00:00Z", league="nfl"),                 # s=0.5 (antes)
        _row("e1", "2026-10-16T20:00:00Z", league="nfl"),                 # s=1 -> fuera
        _row("e2", "2026-10-21T20:00:00Z", league="ncaaf"),               # desconocido -> fuera
        _row("e3", "2026-10-21T20:00:00Z", league="mlb", cal=0.55),       # s=0 -> p_cal = cal
    ]
    picks, cnt = _picks(mod, rows, table)
    assert cnt["s_t_igual_1_o_desconocido"] == 2
    assert sorted(picks["event_id"]) == ["e0", "e3"]
    assert picks.set_index("event_id").loc["e3", "_p_cal"] == pytest.approx(0.55)
    assert picks.set_index("event_id").loc["e0", "_p_cal"] == pytest.approx(0.60)


def test_aud003_nhl_h2h_decision_row_before_fix_is_excluded_without_substitution(mod):
    """Addendum 2026-10-17: primera servida de nhl|h2h anterior a ffc5ad3 ->
    pick fuera aunque tenga una servida posterior valida; nhl|totals y
    nfl|h2h del mismo instante no se tocan; el corte es >= (gate)."""
    corte = pd.Timestamp("2026-10-16T12:56:03Z")
    st = corte + pd.Timedelta(hours=10)
    gen_antes = 10.0 + 1.0 / 3600            # 1 s antes del corte
    rows = [
        _row("n1", st, league="nhl", gen_h=gen_antes),
        _row("n1", st, league="nhl", gen_h=1.0),                  # re-servida valida
        _row("n2", st, league="nhl", gen_h=10.0),                 # justo en el corte
        _row("n3", st, league="nhl", market="totals", gen_h=gen_antes, line=5.5),
        _row("f1", st, league="nfl", gen_h=gen_antes),
    ]
    picks, cnt = _picks(mod, rows)
    assert cnt["mercado_invalido_aud003"] == 1
    assert sorted(picks["event_id"]) == ["f1", "n2", "n3"]
    # S1 (sin colapsar): el filtro actua por fila y la re-servida valida queda.
    s1, cnt1 = mod.prepare_picks(pd.DataFrame(rows), mod.parse_regime_table(None),
                                 collapse=False)
    assert cnt1["mercado_invalido_aud003"] == 1
    assert sorted(s1["event_id"]) == ["f1", "n1", "n2", "n3"]


def test_aud003_literal_matches_the_prediction_gate(mod):
    from sqp.risk.prediction_gate import INVALID_BEFORE
    assert mod.INVALID_BEFORE == INVALID_BEFORE


def test_p_cal_outside_unit_interval_is_excluded_not_clipped(mod):
    rows = [_row("e0", "2026-10-10T20:00:00Z", cal=0.10, fair=0.90),   # 2*0.1-0.9 < 0
            _row("e1", "2026-10-10T20:00:00Z", cal=0.55, fair=0.50)]
    picks, cnt = _picks(mod, rows)
    assert cnt["p_cal_fuera_de_rango"] == 1
    assert list(picks["event_id"]) == ["e1"]


def test_population_filters_and_collapse(mod):
    rows = [
        _row("e0", "2026-10-10T20:00:00Z"),
        _row("e0", "2026-10-10T20:00:00Z", gen_h=30.0),                       # 2a servida: se colapsa
        _row("e1", "2026-10-10T20:00:00Z", result="void"),
        _row("e2", "2026-10-10T20:00:00Z", gen_h=-1.0),                       # en vivo
        _row("e3", "2026-10-10T20:00:00Z", result=""),                        # sin graduar
        {**_row("e4", "2026-10-10T20:00:00Z"), "selection": ""},              # identidad incompleta
    ]
    picks, cnt = _picks(mod, rows)
    assert list(picks["event_id"]) == ["e0"]
    assert cnt["duplicados_colapsados"] == 1
    assert cnt["resultado_no_win_loss"] == 1
    assert cnt["generado_en_vivo_o_despues"] == 1
    assert cnt["identidad_incompleta"] == 1
    # Se conserva la PRIMERA servida (gen_h=30 es anterior).
    assert pd.Timestamp(picks["_gen"].iloc[0]) == (
        pd.Timestamp("2026-10-10T20:00:00Z") - pd.Timedelta(hours=30))


# ------------------------------------------------------------------ ventanas --
def test_windows_are_disjoint_and_use_start_time(mod):
    rows = [_row("a", T0 - pd.Timedelta(hours=1)), _row("b", T0),
            _row("c", T0 + pd.Timedelta(seconds=1)), _row("d", T0 + pd.Timedelta(days=3)),
            _row("e", T0 + pd.Timedelta(days=30))]
    picks, _ = _picks(mod, rows)
    ajuste, ev = mod.split_windows(picks, T0, T0 + pd.Timedelta(days=10))
    assert set(ajuste["event_id"]) == {"a", "b"}          # start <= T0
    assert set(ev["event_id"]) == {"c", "d"}              # T0 < start <= T1
    assert not set(ajuste["event_id"]) & set(ev["event_id"])
    assert (ajuste["_start"] <= T0).all() and (ev["_start"] > T0).all()


# --------------------------------------------------------------- estadistica --
def test_holm_and_h1_label(mod):
    out = mod.holm({"a": 0.001, "b": 0.03, "c": 0.04})
    assert out["a"]["rechaza"] and not out["b"]["rechaza"] and not out["c"]["rechaza"]
    assert out["a"]["p_holm"] == pytest.approx(0.003)
    out = mod.holm({"a": 0.001, "b": 0.01, "c": 0.04})
    assert out["a"]["rechaza"] and out["b"]["rechaza"] and out["c"]["rechaza"]
    assert mod.label_h1(-0.02, -0.001) == "PASA"
    assert mod.label_h1(0.001, 0.02) == "PEOR"
    assert mod.label_h1(-0.01, 0.01) == "FALLA"
    assert mod.label_h1(float("nan"), float("nan")) == "FALLA"


def test_parse_regime_table_and_last_global_value(mod):
    doc = ("x\n## Addenda\ns servido = 0.3 | desde = 2026-12-01T00:00:00Z | alcance = global\n"
           "s servido = 0.9 | desde = 2026-12-10T00:00:00Z | alcance = nfl|h2h\n")
    table = mod.parse_regime_table(doc)
    assert len(table) == 3 and table[0]['desde'] == mod.BASE_DESDE
    assert mod.last_global_s(table, pd.Timestamp("2026-11-01", tz="UTC")) == 0.5
    assert mod.last_global_s(table, pd.Timestamp("2026-12-05", tz="UTC")) == pytest.approx(0.3)


# ----------------------------------------------------------------- git: H y T0 --
def test_resolve_h_fallback_tag_and_conflict(mod, tmp_path):
    repo = _init_repo(tmp_path)
    pre = repo / PRE_REL
    assert mod.resolve_h(pre, repo) is None
    h = _commit(repo, {PRE_REL: "# pre\n"})
    out = mod.resolve_h(pre, repo)
    assert out == {"h": h, "via": "fallback"}
    _run_git(repo, "tag", "-a", mod.TAG_NAME, "-m", "h")
    assert mod.resolve_h(pre, repo) == {"h": h, "via": "tag"}
    _commit(repo, {"otro.txt": "x"})
    _run_git(repo, "tag", "-f", "-a", mod.TAG_NAME, "-m", "h2")   # el tag apunta a otro commit
    with pytest.raises(SystemExit):
        mod.resolve_h(pre, repo)


def test_resolve_t0_zero_one_and_many(mod, tmp_path):
    repo = _init_repo(tmp_path)
    _commit(repo, {PRE_REL: "# pre\n"})
    assert mod.resolve_t0(repo) is None
    sha = _commit(repo, {MM_REL: "r\n"}, date="2026-11-05T00:00:00+00:00")
    out = mod.resolve_t0(repo)
    assert out is not None and out["commit"] == sha and out["t0"] == T0
    _commit(repo, {"docs/research/2026-11-06-resultado-el-modelo-manda-bis.md": "r2\n"})
    with pytest.raises(SystemExit):
        mod.resolve_t0(repo)


# --------------------------------------------------------------- argparse --
def test_modes_are_mutually_exclusive_and_required(mod):
    for argv in (["--contar", "--medir", "--t1", "2027-01-01T00:00:00Z"],
                 ["--contar", "--ajustar"], [], ["--medir"],
                 ["--ajustar", "--no-log"], ["--contar", "--t1", "2027-01-01T00:00:00Z"]):
        with pytest.raises(SystemExit):
            mod.main(argv)


# ------------------------------------------------------------------ --contar --
def _write_graded(data_root: Path, rows: list[dict], name: str = "graded_nfl.csv"):
    d = data_root / "data" / "calibration"
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(d / name, index=False)


def _contar_args(data_root, pre, no_log=False):
    return Namespace(data_root=data_root, preregistro=pre, no_log=no_log)


def test_contar_without_t0_prints_zero_and_has_no_result_fields(mod, tmp_path, monkeypatch):
    repo, pre = _repo_with_h(tmp_path, mod, monkeypatch)
    data_root = tmp_path / "dr"
    _write_graded(data_root, [_row("e0", "2026-10-10T20:00:00Z")])
    out = mod.run_contar(_contar_args(data_root, pre, no_log=True))
    assert out["registro"]["n_eventos_evaluacion"] == 0
    assert out["registro"]["t0"] is None
    assert not mod.contar_log_path(pre).exists()


def test_contar_emits_no_result_field_and_appends_exactly_one_line(mod, tmp_path, monkeypatch):
    repo, pre = _repo_with_h(tmp_path, mod, monkeypatch)
    _commit(repo, {MM_REL: "r\n"}, date="2026-11-05T00:00:00+00:00")
    monkeypatch.setattr(mod, "_now", lambda: pd.Timestamp("2026-12-01T00:00:00Z"))
    data_root = tmp_path / "dr"
    _write_graded(data_root, [_row("e0", "2026-11-10T20:00:00Z"),
                              _row("e1", "2026-11-12T20:00:00Z", result="loss"),
                              _row("e2", "2026-11-25T20:00:00Z"),      # > E - 14 d
                              _row("e3", "2026-10-10T20:00:00Z")])     # ajuste
    # servidos: e0 y e1 graduados; e5 y e6 (en ventana) sin graduar; e7 fuera de ventana.
    _write_graded(data_root, [_row("e0", "2026-11-10T20:00:00Z"), _row("e5", "2026-11-11T20:00:00Z"),
                              _row("e6", "2026-11-13T20:00:00Z", selection="away"),
                              _row("e7", "2026-11-28T20:00:00Z")], name="served_nfl.csv")
    out = mod.run_contar(_contar_args(data_root, pre))
    reg = out["registro"]
    assert set(reg) == mod.CONTAR_CAMPOS
    texto = json.dumps(out)
    for prohibido in ('"y"', "brier", "s_k", "p_valor", '"z"', "media", "diff", '"p_cal'):
        assert prohibido not in texto.lower()
    assert reg["n_eventos_evaluacion"] == 2 and reg["n_picks_evaluacion"] == 2
    assert reg["picks_sin_graduar_ventana"] == 2
    assert reg["t1_candidato"].startswith("2026-11-17")
    assert reg["market_shrink_difiere"] is False
    log = mod.contar_log_path(pre)
    assert len(log.read_text(encoding="utf-8").splitlines()) == 1
    mod.run_contar(_contar_args(data_root, pre))
    assert len(log.read_text(encoding="utf-8").splitlines()) == 2


def test_contar_flags_market_shrink_that_differs_from_table(mod, tmp_path, monkeypatch):
    repo, pre = _repo_with_h(tmp_path, mod, monkeypatch)
    monkeypatch.setattr(mod, "settings_market_shrink", lambda: 0.6)
    out = mod.run_contar(_contar_args(tmp_path / "dr", pre, no_log=True))
    assert out["registro"]["market_shrink_difiere"] is True


# ----------------------------------------------------------------- --ajustar --
def test_ajustar_aborts_without_t0_and_before_margin_and_when_sk_exists(
        mod, tmp_path, monkeypatch):
    repo, pre = _repo_with_h(tmp_path, mod, monkeypatch)
    data_root = tmp_path / "dr"
    _write_graded(data_root, _synthetic_fit_rows(40, "nfl", "h2h", 1, 1.0))
    args = Namespace(data_root=data_root, preregistro=pre)
    monkeypatch.setattr(mod, "_now", lambda: pd.Timestamp("2026-12-01T00:00:00Z"))
    with pytest.raises(SystemExit, match="T0"):
        mod.run_ajustar(args)
    _commit(repo, {MM_REL: "r\n"}, date="2026-11-05T00:00:00+00:00")
    monkeypatch.setattr(mod, "_now", lambda: pd.Timestamp("2026-11-18T23:59:00Z"))
    with pytest.raises(SystemExit, match="T0 \\+ 14"):
        mod.run_ajustar(args)
    monkeypatch.setattr(mod, "_now", lambda: pd.Timestamp("2026-11-19T00:00:00Z"))
    out = mod.run_ajustar(args)
    sk = json.loads(mod.sk_json_path(pre).read_text(encoding="utf-8"))
    assert sk["ajuste"]["segmentos"] and out["n_picks_ajuste"] == 40
    assert sk["t0"].startswith("2026-11-05") and sk["sha256_picks_ajuste"]
    with pytest.raises(SystemExit, match="ya existe"):
        mod.run_ajustar(args)


# ------------------------------------------------------------------- --medir --
class _MedirWorld:
    """Repo + datos sinteticos para ejercitar `--medir` de extremo a extremo."""

    def __init__(self, mod, tmp_path, monkeypatch):
        self.mod = mod
        self.repo, self.pre = _repo_with_h(tmp_path, mod, monkeypatch)
        monkeypatch.setattr(mod, "N_REQUIRED", 40)
        monkeypatch.setattr(mod, "MIN_SEGMENT_EVENTS_EVAL", 5)
        self.data_root = tmp_path / "dr"
        rows = _synthetic_fit_rows(80, "nfl", "h2h", 11, 1.0)
        rng = np.random.default_rng(99)
        for i in range(60):
            fair = rng.uniform(0.35, 0.65)
            p_cal = float(np.clip(fair + 0.1 * rng.choice([-1, 1]), 0.02, 0.98))
            rows.append(_row(f"ev-{i}", T0 + pd.Timedelta(days=2 + i % 20),
                             cal=round(0.5 * p_cal + 0.5 * fair, 4), fair=round(fair, 4),
                             result="win" if rng.uniform() < fair else "loss"))
        _write_graded(self.data_root, rows)
        _commit(self.repo, {MM_REL: "r\n"}, date="2026-11-05T00:00:00+00:00")
        monkeypatch.setattr(mod, "_now", lambda: pd.Timestamp("2026-12-01T00:00:00Z"))
        mod.run_ajustar(Namespace(data_root=self.data_root, preregistro=self.pre))
        self.sk_sha = _commit(self.repo, {mod.sk_json_path(self.pre).relative_to(self.repo)
                                          .as_posix(): mod.sk_json_path(self.pre)
                                          .read_text(encoding="utf-8")})
        self.t1 = pd.Timestamp("2026-12-01T00:00:00Z")
        self.args = Namespace(data_root=self.data_root, preregistro=self.pre,
                              t1=self.t1.isoformat(), seed=42, n_boot=60)

    def commit_log_and_addendum(self, t1_log=None, t1_add=None):
        linea = {"n_eventos_evaluacion": 60,
                 "t1_candidato": (t1_log or self.t1).isoformat()}
        rel = self.mod.contar_log_path(self.pre).relative_to(self.repo).as_posix()
        sha = _commit(self.repo, {rel: json.dumps(linea) + "\n"})
        add = (f"\n## Addenda\nT1 fijado = {(t1_add or self.t1).isoformat()}\n"
               f"commit del registro = {sha}\n")
        _commit(self.repo, {PRE_REL: "# pre\n" + add})


def test_medir_aborts_without_t1_addendum(mod, tmp_path, monkeypatch):
    w = _MedirWorld(mod, tmp_path, monkeypatch)
    with pytest.raises(SystemExit, match="addendum"):
        mod.run_medir(w.args)


def test_medir_aborts_with_different_t1(mod, tmp_path, monkeypatch):
    w = _MedirWorld(mod, tmp_path, monkeypatch)
    w.commit_log_and_addendum()
    w.args.t1 = "2026-12-02T00:00:00Z"
    with pytest.raises(SystemExit, match="no coincide"):
        mod.run_medir(w.args)


def test_medir_aborts_if_addendum_t1_differs_from_first_registry_line(mod, tmp_path, monkeypatch):
    w = _MedirWorld(mod, tmp_path, monkeypatch)
    w.commit_log_and_addendum(t1_add=pd.Timestamp("2026-12-03T00:00:00Z"))
    w.args.t1 = "2026-12-03T00:00:00Z"
    with pytest.raises(SystemExit, match="PRIMERA"):
        mod.run_medir(w.args)


def test_medir_aborts_with_n_below_threshold(mod, tmp_path, monkeypatch):
    w = _MedirWorld(mod, tmp_path, monkeypatch)
    w.commit_log_and_addendum()
    monkeypatch.setattr(mod, "N_REQUIRED", 61)
    # el registro debe seguir cruzando el umbral para llegar a la comprobacion de n.
    linea = {"n_eventos_evaluacion": 99, "t1_candidato": w.t1.isoformat()}
    rel = mod.contar_log_path(w.pre).relative_to(w.repo).as_posix()
    sha = _commit(w.repo, {rel: json.dumps(linea) + "\n"})
    _commit(w.repo, {PRE_REL: f"# pre\nT1 fijado = {w.t1.isoformat()}\n"
                              f"commit del registro = {sha}\n"})
    with pytest.raises(SystemExit, match=r"n\(T1\) = 60 < 61"):
        mod.run_medir(w.args)


def test_medir_aborts_without_committed_sk_json(mod, tmp_path, monkeypatch):
    w = _MedirWorld(mod, tmp_path, monkeypatch)
    w.commit_log_and_addendum()
    rel = mod.sk_json_path(w.pre).relative_to(w.repo).as_posix()
    _run_git(w.repo, "rm", "-q", rel)
    _run_git(w.repo, "commit", "-q", "-m", "rm sk")
    with pytest.raises(SystemExit, match="sk.json"):
        mod.run_medir(w.args)


def test_medir_end_to_end_on_synthetic_data(mod, tmp_path, monkeypatch):
    w = _MedirWorld(mod, tmp_path, monkeypatch)
    w.commit_log_and_addendum()
    out = mod.run_medir(w.args)
    assert out["modo"] == "medir"
    h1 = out["H1"]
    assert h1["n_eventos"] == 60 and h1["etiqueta"] in {"PASA", "PEOR", "FALLA"}
    assert h1["log_loss"]["peor_con_ic"] in (True, False)
    assert out["procedencia"]["seed_n_boot"]["difiere_de_lo_congelado"] is True   # n_boot=60
    assert out["s_k_commiteado_vs_recalculo"]["max_abs_s_k"] == pytest.approx(0.0)
    assert {"S1_sin_colapsar", "S2_tau", "S3_sin_filas_pre_regimen", "S4_particion_por_regimen",
            "S5_vs_s_vigente", "S6_por_familia", "S7_calibrador_aplanado", "ROI"} <= set(out)
    assert "p_valor" not in json.dumps(out["H1"])
    if h1["etiqueta"] == "PASA":
        assert "H2" in out["H2_y_segmentos_holm"]
    else:
        assert "aviso" in out["H2_y_segmentos_holm"]
    assert out["ROI"]["aviso"]


def test_roi_gate_counts_only_bets_inside_the_edge_band(mod):
    ev = pd.DataFrame({
        "event_id": ["a", "b", "c"], "_y": [1.0, 0.0, 1.0], "price_decimal": [2.0, 2.0, 2.0],
        "_fair": [0.5, 0.5, 0.5], "_p_k": [0.52, 0.52, 0.60], "_p_05": [0.50, 0.50, 0.50]})
    # p_k*2-1 = 0.04 (apuesta) en a y b; 0.20 (> techo) en c. p_05 nunca apuesta.
    out = mod.roi_gate(ev, n_boot=50, seed=1)
    assert out["politica_p_k"]["n_apuestas"] == 2
    assert out["politica_p_05"]["n_apuestas"] == 0
    assert out["delta_pnl_por_evento"] == pytest.approx((1.0 - 1.0) / 3)


# ------------------------------------------------- bloqueante 1: addendum de T1 --
def test_real_preregistro_text_has_no_t1_addendum_today(mod):
    """El texto REAL (7aa8468) cita `T1 fijado = <ISO>` entre comillas inversas en
    7.4: no es un addendum. Hoy no hay T1."""
    assert "`T1 fijado = <ISO>`" in REAL_PRE_TEXT
    assert mod.parse_t1_addendum(REAL_PRE_TEXT) is None


def test_parse_t1_addendum_anchored_unreadable_and_conflicts(mod):
    ok = "## Addenda\nT1 fijado = 2027-03-07T00:00:00Z\ncommit del registro = abcdef1\n"
    assert mod.parse_t1_addendum(REAL_PRE_TEXT + ok) == ("2027-03-07T00:00:00Z", "abcdef1")
    # ISO ilegible: se descarta.
    assert mod.parse_t1_addendum("T1 fijado = manana\ncommit del registro = abcdef1\n") is None
    # prosa con la cita en medio de linea: no cuenta.
    assert mod.parse_t1_addendum("ver T1 fijado = 2027-03-07T00:00:00Z y\n"
                                 "commit del registro = abcdef1\n") is None
    dos = ok + "T1 fijado = 2027-03-09T00:00:00Z\n"
    with pytest.raises(SystemExit, match="varios"):
        mod.parse_t1_addendum(dos)
    # mismo instante en dos representaciones: no es conflicto.
    mismo = ok + "T1 fijado = 2027-03-07T00:00:00+00:00\n"
    assert mod.parse_t1_addendum(mismo) is not None


# ------------------------------------------ bloqueante 2: tabla de regimen de s --
def test_real_preregistro_text_yields_only_the_implicit_regime_entry(mod):
    tabla = mod.parse_regime_table(REAL_PRE_TEXT)
    assert tabla == [{"s": 0.5, "desde": pd.Timestamp("2026-06-21T00:00:00+00:00"),
                      "alcance": "global"}]


def test_regime_table_formats_and_invalid_lines_abort(mod):
    base = "## Addenda\n"
    assert len(mod.parse_regime_table(base + "s servido = 0.25 | desde = 2026-12-01T00:00:00+00:00"
                                      " | alcance = nfl|h2h\n")) == 2
    assert len(mod.parse_regime_table(base + "s servido = desconocido | desde = "
                                      "2026-12-01T00:00:00Z | alcance = global\n")) == 2
    for mala in ("s servido = 0,3 | desde = 2026-12-01T00:00:00Z | alcance = global",
                 "s servido = 1.5 | desde = 2026-12-01T00:00:00Z | alcance = global",
                 "s servido = 0.3 | desde = ayer | alcance = global",
                 "s servido = 0.3 | desde = 2026-12-01T00:00:00Z | alcance = nfl",
                 "s servido: 0.3"):
        with pytest.raises(SystemExit, match="Tabla de regimen"):
            mod.parse_regime_table(base + mala + "\n")
    # Fuera de la seccion Addenda o con sangria no se interpreta.
    assert len(mod.parse_regime_table("s servido = basura\n" + base + "  s servido = x\n")) == 1


def test_regime_most_recent_desde_wins_then_specific_scope(mod):
    doc = ("## Addenda\n"
           "s servido = 0.2 | desde = 2026-10-10T00:00:00Z | alcance = global\n"
           "s servido = 0.9 | desde = 2026-10-10T00:00:00Z | alcance = nfl|h2h\n"
           "s servido = 0.4 | desde = 2026-10-20T00:00:00Z | alcance = global\n")
    tabla = mod.parse_regime_table(doc)
    gen = pd.Series(pd.to_datetime(["2026-07-01", "2026-10-11", "2026-10-11", "2026-10-25",
                                    "2026-06-01"], utc=True))
    seg = pd.Series(["nfl|h2h", "nfl|h2h", "mlb|h2h", "nfl|h2h", "nfl|h2h"])
    s = mod.regime_s(gen, seg, tabla)
    assert s[0] == 0.5 and s[1] == 0.9 and s[2] == 0.2 and s[3] == 0.4
    assert np.isnan(s[4])    # anterior a la entrada implicita: desconocido


def test_market_shrink_column_beats_table_and_discrepancies_are_counted(mod):
    rows = [
        {**_row("c0", "2026-10-10T20:00:00Z", cal=0.60, fair=0.50), "market_shrink": 0.0},   # col != tabla
        {**_row("c1", "2026-10-10T20:00:00Z", cal=0.55, fair=0.50), "market_shrink": 0.5},   # col == tabla
        {**_row("c2", "2026-10-10T20:00:00Z", cal=0.55, fair=0.50), "market_shrink": np.nan},  # tabla
        {**_row("c3", "2026-10-10T20:00:00Z", cal=0.55, fair=0.50), "market_shrink": 1.0},   # no recuperable
        {**_row("c4", "2026-10-10T20:00:00Z", cal=0.55, fair=0.50), "market_shrink": 2.0},   # fuera de rango
    ]
    picks, cnt = _picks(mod, rows)
    assert cnt["s_desde_columna"] == 4
    # Add. (2): la discrepancia solo cuenta filas que llegan a la reconstruccion (c0).
    assert cnt["s_columna_vs_tabla_discrepancias"] == 1
    assert cnt["s_columna_fuera_de_rango"] == 1              # c4 (2.0), contador propio
    assert cnt["s_t_igual_1_o_desconocido"] == 1             # c3 (s=1)
    p = picks.set_index("event_id")
    assert p.loc["c0", "_p_cal"] == pytest.approx(0.60)       # s=0: p_cal = cal
    assert p.loc["c1", "_p_cal"] == pytest.approx(0.60)       # s=0.5
    assert p.loc["c2", "_p_cal"] == pytest.approx(0.60)       # tabla 0.5


def test_row_before_implicit_entry_has_unknown_s_and_is_excluded(mod):
    picks, cnt = _picks(mod, [_row("o0", "2026-06-10T20:00:00Z")])
    assert cnt["s_t_igual_1_o_desconocido"] == 1 and picks.empty


def _prereg_con_linea_mala(repo, mod, linea):
    return _commit(repo, {PRE_REL: "# pre\n## Addenda\n" + linea + "\n"})


def test_ajustar_and_medir_abort_on_malformed_regime_line_but_contar_informs(
        mod, tmp_path, monkeypatch):
    repo, pre = _repo_with_h(tmp_path, mod, monkeypatch)
    _commit(repo, {MM_REL: "r\n"}, date="2026-11-05T00:00:00+00:00")
    _prereg_con_linea_mala(repo, mod, "s servido = 0,3 | desde = 2026-12-01T00:00:00Z | alcance = global")
    monkeypatch.setattr(mod, "_now", lambda: pd.Timestamp("2026-12-01T00:00:00Z"))
    data_root = tmp_path / "dr"
    _write_graded(data_root, _synthetic_fit_rows(40, "nfl", "h2h", 1, 1.0))
    with pytest.raises(SystemExit, match="Tabla de regimen"):
        mod.run_ajustar(Namespace(data_root=data_root, preregistro=pre))
    assert not mod.sk_json_path(pre).exists()
    out = mod.run_contar(_contar_args(data_root, pre, no_log=True))
    assert "Tabla de regimen" in out["registro"]["error_tabla_regimen"]


def test_medir_aborts_on_malformed_regime_line_after_a_valid_t1_addendum(
        mod, tmp_path, monkeypatch):
    w = _MedirWorld(mod, tmp_path, monkeypatch)
    w.commit_log_and_addendum()
    _commit(w.repo, {PRE_REL: (w.repo / PRE_REL).read_text(encoding="utf-8")
                     + "s servido = nope\n"})
    with pytest.raises(SystemExit, match="Tabla de regimen"):
        mod.run_medir(w.args)


# ------------------------------------------------- bloqueante 3: CSV ilegibles --
def test_corrupt_graded_csv_aborts_strict_without_touching_the_file(mod, tmp_path):
    d = tmp_path / "dr" / "data" / "calibration"
    d.mkdir(parents=True)
    bad = d / "graded_mlb.csv"
    bad.write_text("a,b,c\n1,2,3\n1,2,3,4,5,6\n", encoding="utf-8")
    (d / "graded_nfl.csv").write_text("league,event_id\nnfl,e0\n", encoding="utf-8")
    ilegible = d / "graded_epl.csv"
    ilegible.write_bytes(b"\xff\xfe\x00bad\xff\xff,\x80\n\x81\x82\n")
    antes = {p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in d.iterdir()}
    with pytest.raises(SystemExit, match="ilegibles"):
        mod.load_graded_real(tmp_path / "dr", strict=True)
    df, errores = mod.load_graded_real(tmp_path / "dr", strict=False)
    assert {Path(e["fichero"]).name for e in errores} == {"graded_mlb.csv", "graded_epl.csv"}
    assert list(df["league"]) == ["nfl"]
    despues = {p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in d.iterdir()}
    assert antes == despues and sorted(despues) == sorted(antes)    # nada renombrado ni tocado


def test_ajustar_aborts_on_unreadable_graded_csv(mod, tmp_path, monkeypatch):
    repo, pre = _repo_with_h(tmp_path, mod, monkeypatch)
    _commit(repo, {MM_REL: "r\n"}, date="2026-11-05T00:00:00+00:00")
    monkeypatch.setattr(mod, "_now", lambda: pd.Timestamp("2026-12-01T00:00:00Z"))
    data_root = tmp_path / "dr"
    _write_graded(data_root, _synthetic_fit_rows(40, "nfl", "h2h", 1, 1.0))
    (data_root / "data" / "calibration" / "graded_mlb.csv").write_text(
        "a,b,c\n1,2,3\n1,2,3,4,5,6\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="ilegibles"):
        mod.run_ajustar(Namespace(data_root=data_root, preregistro=pre))
    assert not mod.sk_json_path(pre).exists()


def test_league_comes_from_the_file_name_like_load_all_graded(mod, tmp_path):
    d = tmp_path / "dr" / "data" / "calibration"
    d.mkdir(parents=True)
    pd.DataFrame([{"event_id": "e0", "league": "mal_puesta", "data_label": "real"},
                  {"event_id": "e1", "league": "otra", "data_label": "real"}]
                 ).to_csv(d / "graded_ncaaf.csv", index=False)
    df, _ = mod.load_graded_real(tmp_path / "dr")
    assert set(df["league"]) == {"ncaaf"}


# ------------------------------------------------------------ menores 4, 5, 6 --
def test_label_contraste_requires_negative_mean_to_pass(mod):
    assert mod.label_contraste(True, -0.001) == "PASA"
    assert mod.label_contraste(True, 0.001) == "PEOR"
    assert mod.label_contraste(False, -0.5) == "NO_RECHAZA"
    assert mod.label_contraste(True, None) == "NO_RECHAZA"


def test_count_sin_graduar_counts_served_picks_without_graded_row(mod):
    t1 = T0 + pd.Timedelta(days=20)
    servidos = pd.DataFrame([
        _row("s0", T0 + pd.Timedelta(days=1)), _row("s1", T0 + pd.Timedelta(days=2)),
        _row("s2", T0 - pd.Timedelta(days=1)), _row("s3", T0 + pd.Timedelta(days=30)),
        _row("s1", T0 + pd.Timedelta(days=2), gen_h=40.0)])      # 2a servida de s1: un solo pick
    graduados = pd.DataFrame([_row("s0", T0 + pd.Timedelta(days=1), result="void")])
    assert mod.count_sin_graduar(servidos, graduados, T0, t1) == 1      # solo s1
    assert mod.count_sin_graduar(servidos, pd.DataFrame(), T0, t1) == 2


def test_liga_familia_is_saved_in_sk_and_overrides_live_lookup(mod, tmp_path, monkeypatch):
    w = _MedirWorld(mod, tmp_path, monkeypatch)
    sk = json.loads(mod.sk_json_path(w.pre).read_text(encoding="utf-8"))
    assert sk["liga_familia"] == {"nfl": "football"}
    rows = [_row("f0", "2026-10-10T20:00:00Z", league="nfl"),
            # nhl|h2h posterior a ffc5ad3: anterior lo excluye AUD-003 (Addendum 2026-10-17).
            _row("f1", "2026-10-20T20:00:00Z", league="nhl")]
    picks, cnt = mod.prepare_picks(pd.DataFrame(rows), mod.parse_regime_table(None),
                                   liga_familia={"nfl": "inventada"})
    p = picks.set_index("event_id")
    assert p.loc["f0", "_fam"] == "inventada|h2h"          # manda el mapa commiteado
    assert p.loc["f1", "_fam"] == "hockey|h2h"             # liga nueva: vivo, y marcada
    assert cnt["ligas_sin_entrada_en_mapa"] == ["nhl"]


# ------------------------------------------------------- Addendum (2): precisiones --
def test_regime_scope_for_tennis_must_be_the_circuit(mod):
    base = "## Addenda\n"
    ok = mod.parse_regime_table(base + "s servido = 0.3 | desde = 2026-12-01T00:00:00Z | "
                                "alcance = tennis_atp|h2h\n")
    assert ok[-1]["alcance"] == "tennis_atp|h2h"
    for mal in ("tennis_atp_cincinnati|h2h", "atp|h2h", "wta|h2h", "tennis_wta_us_open|h2h"):
        with pytest.raises(SystemExit, match="circuito"):
            mod.parse_regime_table(base + f"s servido = 0.3 | desde = 2026-12-01T00:00:00Z | "
                                   f"alcance = {mal}\n")


def test_regime_desde_requires_a_timezone(mod):
    base = "## Addenda\n"
    for bien in ("2026-12-01T00:00:00Z", "2026-12-01T00:00:00+02:00", "2026-12-01T00:00:00-05:00"):
        assert len(mod.parse_regime_table(
            base + f"s servido = 0.3 | desde = {bien} | alcance = global\n")) == 2
    for mal in ("2026-12-01T00:00:00", "2026-12-01", "2026-12-01T00:00:00+0200"):
        with pytest.raises(SystemExit, match="formato invalido"):
            mod.parse_regime_table(base + f"s servido = 0.3 | desde = {mal} | alcance = global\n")


def test_regime_table_unreadable_in_head_aborts(mod, tmp_path, monkeypatch):
    repo, pre = _repo_with_h(tmp_path, mod, monkeypatch)
    # fuera del repositorio
    with pytest.raises(SystemExit, match="no se pudo leer|No se pudo leer"):
        mod.load_regime_table(tmp_path / "fuera.md", repo)
    # dentro del repo pero no commiteado en HEAD
    nuevo = repo / "docs" / "research" / "otro.md"
    nuevo.write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit, match="No se pudo leer"):
        mod.load_regime_table(nuevo, repo)
    assert mod.load_regime_table(pre, repo)      # el commiteado si


def test_contar_reports_unreadable_regime_table(mod, tmp_path, monkeypatch):
    repo, pre = _repo_with_h(tmp_path, mod, monkeypatch)
    nuevo = repo / "docs" / "research" / "sin-commit.md"
    nuevo.write_text("x", encoding="utf-8")
    out = mod.run_contar(_contar_args(tmp_path / "dr", nuevo, no_log=True))
    assert "No se pudo leer" in out["registro"]["error_tabla_regimen"]


def test_ajustar_aborts_when_preregistro_not_in_head(mod, tmp_path, monkeypatch):
    repo, pre = _repo_with_h(tmp_path, mod, monkeypatch)
    _commit(repo, {MM_REL: "r\n"}, date="2026-11-05T00:00:00+00:00")
    monkeypatch.setattr(mod, "_now", lambda: pd.Timestamp("2026-12-01T00:00:00Z"))
    nuevo = repo / "docs" / "research" / "sin-commit.md"
    nuevo.write_text("x", encoding="utf-8")
    monkeypatch.setattr(mod, "resolve_h", lambda *a, **k: {"h": "x", "via": "tag"})
    with pytest.raises(SystemExit, match="No se pudo leer"):
        mod.run_ajustar(Namespace(data_root=tmp_path / "dr", preregistro=nuevo))


def test_csv_provenance_oserror_is_reported_not_raised(mod, tmp_path, monkeypatch):
    d = tmp_path / "dr" / "data" / "calibration"
    d.mkdir(parents=True)
    (d / "graded_nfl.csv").write_text("a\n1\n", encoding="utf-8")
    real_open = open

    def fallido(path, *a, **k):
        if str(path).endswith("graded_nfl.csv"):
            raise PermissionError("bloqueado")
        return real_open(path, *a, **k)

    monkeypatch.setattr("builtins.open", fallido)
    out = mod.csv_provenance(tmp_path / "dr")
    assert out and "bloqueado" in out[0]["error"]


# AUD-017 (ronda audit-2026-10-18): con la maquina cargada, `git log` pasaba de
# 30 s, `_git` devolvia None y `--medir` abortaba con "T0 no existe", un motivo
# falso. Un fallo del entorno se reintenta y, si persiste, se dice que fue git.
def test_resolve_t0_git_timeout_is_not_read_as_missing_t0(mod, tmp_path, monkeypatch):
    llamadas = []

    def _lento(*a, **k):
        llamadas.append(k.get("timeout"))
        raise subprocess.TimeoutExpired(cmd="git", timeout=k.get("timeout"))

    monkeypatch.setattr(mod.subprocess, "run", _lento)
    with pytest.raises(SystemExit, match="no respondio"):
        mod.resolve_t0(tmp_path)
    assert llamadas == list(mod._GIT_DECIDE_TIMEOUTS)


def test_resolve_t0_retries_once_after_a_transient_timeout(mod, tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    _commit(repo, {MM_REL: "r\n"}, date="2026-11-05T00:00:00+00:00")
    real = subprocess.run
    estado = {"n": 0}

    def _una_vez_lento(*a, **k):
        estado["n"] += 1
        if estado["n"] == 1:
            raise subprocess.TimeoutExpired(cmd="git", timeout=k.get("timeout"))
        return real(*a, **k)

    monkeypatch.setattr(mod.subprocess, "run", _una_vez_lento)
    out = mod.resolve_t0(repo)
    assert out is not None and out["t0"] == T0


# Addendum 2026-10-18 (AUD-008): linea de cuarto graduada sin medias antes de c578f52.
def test_aud008_pre_fix_quarter_line_rows_are_excluded(mod):
    corte = pd.Timestamp(mod.QUARTER_LINE_INVALID_BEFORE)
    st = corte + pd.Timedelta(hours=10)
    antes = 10.0 + 1.0 / 3600
    rows = [
        _row("q1", st, league="laliga", market="totals", gen_h=antes, line=2.75),
        _row("q2", st, league="laliga", market="spreads", gen_h=antes, line=-0.25),
        _row("q3", st, league="laliga", market="totals", gen_h=10.0, line=2.75),   # en el corte
        _row("h1", st, league="laliga", market="totals", gen_h=antes, line=2.5),   # media linea
    ]
    picks, cnt = _picks(mod, rows)
    assert cnt["linea_cuarto_aud008"] == 2
    assert sorted(picks["event_id"]) == ["h1", "q3"]


def test_aud008_literal_matches_quarter_line_fix(mod):
    from sqp.settlement.quarter_line_fix import QUARTER_LINE_GRADING_FIXED_AT
    assert mod.QUARTER_LINE_INVALID_BEFORE == QUARTER_LINE_GRADING_FIXED_AT
