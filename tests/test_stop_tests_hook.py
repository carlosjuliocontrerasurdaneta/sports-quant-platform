"""Regresion del gate local de tests del Stop (CLAUDE-005 / H-2, 2026-10-14).

El hook corria `-m "not slow"` con un autoacotado de 1080 s y la suite tardaba
1080,43 s: el veredicto no llegaba nunca. Y sin `pytest` borraba el centinela
sin comprobar nada. Estas pruebas fijan las tres salidas -- PASS, FAIL y NO
VERIFICADO -- y el reparto de suites (rapida local, completa en CI).

Se ejercita `_stop_tests.py` directamente y NO el `.sh`: `subprocess` en esta
maquina resuelve el bash de WSL (ver la cabecera de `test_hook_targets.py`). Los
comandos de pytest se sustituyen por `python -c` que imitan cada codigo de
salida, para no ejecutar la suite real dentro de la suite.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / ".claude" / "hooks" / "_stop_tests.py"
HEAVY = [
    "tests/research/test_measure_adjustment_battery.py",
    "tests/research/test_measure_segment_market_weight.py",
    "tests/research/test_measure_tier_a_gap.py",
    "tests/research/test_measure_totals_recency.py",
    "tests/test_dashboard_todos_picks.py",
    "tests/test_fable_gate.py",
    "tests/test_feature_manifest.py",
    "tests/test_feature_research.py",
    "tests/test_html_report.py",
    "tests/test_measure_tilt_nhl.py",
    "tests/test_picks_del_dia.py",
]


@pytest.fixture(scope="module")
def st():
    spec = importlib.util.spec_from_file_location("_stop_tests", RUNNER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # `@dataclass` resuelve las anotaciones via sys.modules[__module__].
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        del sys.modules[spec.name]
    return mod


def _py(codigo: str) -> list[str]:
    return [sys.executable, "-c", codigo]


@pytest.fixture
def proyecto(tmp_path, st, monkeypatch):
    """Arbol minimo con centinela, sin heavy y sin ficheros modificados."""
    (tmp_path / ".claude").mkdir()
    (tmp_path / st.MARCADOR).touch()
    (tmp_path / "tests").mkdir()
    monkeypatch.setattr(st, "pytest_disponible", lambda: True)
    monkeypatch.setattr(st, "ficheros_modificados", lambda cwd: [])
    return tmp_path


def _salida_json(capsys) -> tuple[dict, str]:
    out = capsys.readouterr()
    lineas = [ln for ln in out.out.splitlines() if ln.strip()]
    return (json.loads(lineas[-1]) if lineas else {}), out.err


# --- clasificacion ---------------------------------------------------------

@pytest.mark.parametrize("rc, esperado", [
    (0, "PASS"), (1, "FAIL"), (2, "FAIL"),
    (3, "NO VERIFICADO"), (4, "NO VERIFICADO"), (5, "NO VERIFICADO"),
    (137, "NO VERIFICADO"), (None, "NO VERIFICADO"),
])
def test_each_pytest_exit_code_maps_to_one_verdict(st, rc, esperado):
    assert st.clasificar(st.Ejecucion(rc, "")) == esperado


# --- ramas del hook ----------------------------------------------------------

def test_pass_removes_the_marker_and_says_it_was_the_fast_suite(st, proyecto, monkeypatch, capsys):
    monkeypatch.setattr(st, "comando_rapido", lambda: _py("print('7 passed in 0.1s')"))
    assert st.main("{}", proyecto) == 0
    assert not (proyecto / st.MARCADOR).exists()
    msg, _ = _salida_json(capsys)
    assert msg["systemMessage"].startswith("Tests locales: PASS.")
    assert "not slow and not heavy" in msg["systemMessage"]
    assert "CI" in msg["systemMessage"], "PASS debe decir que la suite completa es de CI"


def test_failing_tests_block_the_turn_and_keep_the_marker(st, proyecto, monkeypatch, capsys):
    monkeypatch.setattr(st, "comando_rapido",
                        lambda: _py("print('1 failed'); raise SystemExit(1)"))
    assert st.main("{}", proyecto) == 2
    assert (proyecto / st.MARCADOR).exists()
    out = capsys.readouterr()
    assert "FAIL" in out.err and "PASS" not in out.err + out.out


def test_collection_error_counts_as_fail(st, proyecto, monkeypatch):
    monkeypatch.setattr(st, "comando_rapido", lambda: _py("raise SystemExit(2)"))
    assert st.main("{}", proyecto) == 2
    assert (proyecto / st.MARCADOR).exists()


def test_timeout_is_not_verified_does_not_block_and_keeps_the_marker(st, proyecto, monkeypatch, capsys):
    monkeypatch.setattr(st, "comando_rapido", lambda: _py("import time; time.sleep(30)"))
    assert st.main("{}", proyecto, presupuesto_s=1) == 0
    assert (proyecto / st.MARCADOR).exists()
    msg, err = _salida_json(capsys)
    assert msg["systemMessage"].startswith("Tests locales: NO VERIFICADO.")
    assert "presupuesto" in msg["systemMessage"]
    assert "NO es una validacion satisfactoria" in msg["systemMessage"]
    assert "PASS" not in msg["systemMessage"] + err


@pytest.mark.parametrize("rc", [3, 4, 5])
def test_pytest_errors_without_verdict_are_not_verified(st, proyecto, monkeypatch, capsys, rc):
    monkeypatch.setattr(st, "comando_rapido", lambda: _py(f"raise SystemExit({rc})"))
    assert st.main("{}", proyecto) == 0
    assert (proyecto / st.MARCADOR).exists()
    msg, _ = _salida_json(capsys)
    assert "NO VERIFICADO" in msg["systemMessage"] and f"rc={rc}" in msg["systemMessage"]


def test_missing_pytest_keeps_the_marker(st, proyecto, monkeypatch, capsys):
    """Antes: `command -v pytest || { rm -f "$marker"; exit 0; }`."""
    monkeypatch.setattr(st, "pytest_disponible", lambda: False)
    monkeypatch.setattr(st, "comando_rapido",
                        lambda: pytest.fail("no debe lanzar pytest si no existe"))
    assert st.main("{}", proyecto) == 0
    assert (proyecto / st.MARCADOR).exists()
    msg, _ = _salida_json(capsys)
    assert "NO VERIFICADO" in msg["systemMessage"]


def test_unlaunchable_command_is_not_verified(st, proyecto, monkeypatch):
    monkeypatch.setattr(st, "comando_rapido", lambda: [str(proyecto / "no-existe.exe")])
    assert st.main("{}", proyecto) == 0
    assert (proyecto / st.MARCADOR).exists()


def test_no_marker_runs_nothing(st, proyecto, monkeypatch):
    (proyecto / st.MARCADOR).unlink()
    monkeypatch.setattr(st, "comando_rapido", lambda: pytest.fail("no debe ejecutar"))
    assert st.main("{}", proyecto) == 0


def test_stop_hook_active_runs_nothing_and_keeps_the_marker(st, proyecto, monkeypatch):
    monkeypatch.setattr(st, "comando_rapido", lambda: pytest.fail("no debe ejecutar"))
    assert st.main('{"stop_hook_active": true}', proyecto) == 0
    assert (proyecto / st.MARCADOR).exists()


def test_unreadable_git_is_not_verified_even_if_fast_suite_passes(st, proyecto, monkeypatch, capsys):
    monkeypatch.setattr(st, "comando_rapido", lambda: _py("print('7 passed')"))
    monkeypatch.setattr(st, "ficheros_modificados", lambda cwd: None)
    assert st.main("{}", proyecto) == 0
    assert (proyecto / st.MARCADOR).exists()
    msg, _ = _salida_json(capsys)
    assert msg["systemMessage"].startswith("Tests locales: NO VERIFICADO.")


# --- heavy relacionados ------------------------------------------------------

def _arbol_heavy(proyecto: Path) -> None:
    (proyecto / "tests" / "test_dash.py").write_text(
        "import pytest\nfrom sqp.audit import html_report\n"
        "pytestmark = pytest.mark.heavy\n", encoding="utf-8")
    (proyecto / "tests" / "test_script.py").write_text(
        'import pytest\nSCRIPT = "scripts/research/measure_x.py"\n'
        "pytestmark = pytest.mark.heavy\n", encoding="utf-8")
    (proyecto / "tests" / "test_gate.py").write_text(
        'import pytest\nHOOK = ROOT / ".claude" / "hooks" / "fable_gate.py"\n'
        "pytestmark = pytest.mark.heavy\n", encoding="utf-8")
    (proyecto / "tests" / "test_ligero.py").write_text(
        "from sqp.audit import html_report\n", encoding="utf-8")


def test_heavy_modules_are_found_by_their_module_marker(st, proyecto):
    _arbol_heavy(proyecto)
    assert st.modulos_heavy(proyecto) == [
        "tests/test_dash.py", "tests/test_gate.py", "tests/test_script.py"]


@pytest.mark.parametrize("modificados, esperado", [
    (["src/sqp/audit/html_report.py"], ["tests/test_dash.py"]),
    (["scripts/research/measure_x.py"], ["tests/test_script.py"]),
    (["tests/test_script.py"], ["tests/test_script.py"]),
    (["src/sqp/models/elo.py", "README.md"], []),
    # El candado Fable sale de la suite rapida, pero tocarlo lo vuelve a meter.
    ([".claude/hooks/fable_gate.py"], ["tests/test_gate.py"]),
])
def test_related_heavy_follow_the_modified_files(st, proyecto, modificados, esperado):
    _arbol_heavy(proyecto)
    heavy = st.modulos_heavy(proyecto)
    assert st.related_heavy_modules(modificados, heavy, proyecto) == esperado


def test_related_heavy_run_and_their_failure_blocks(st, proyecto, monkeypatch, capsys):
    _arbol_heavy(proyecto)
    monkeypatch.setattr(st, "ficheros_modificados", lambda cwd: ["src/sqp/audit/html_report.py"])
    monkeypatch.setattr(st, "comando_rapido", lambda: _py("print('7 passed')"))
    vistos = []

    def heavy(mods):
        vistos.extend(mods)
        return _py("raise SystemExit(1)")
    monkeypatch.setattr(st, "comando_heavy", heavy)
    assert st.main("{}", proyecto) == 2
    assert vistos == ["tests/test_dash.py"]
    assert (proyecto / st.MARCADOR).exists()


def test_related_heavy_without_budget_is_not_verified(st, proyecto, monkeypatch, capsys):
    _arbol_heavy(proyecto)
    monkeypatch.setattr(st, "ficheros_modificados", lambda cwd: ["tests/test_dash.py"])
    # La rapida cabe; los heavy agotan lo que sobra del MISMO presupuesto.
    monkeypatch.setattr(st, "comando_rapido", lambda: _py("print('7 passed')"))
    monkeypatch.setattr(st, "comando_heavy", lambda mods: _py("import time; time.sleep(30)"))
    assert st.main("{}", proyecto, presupuesto_s=4) == 0
    assert (proyecto / st.MARCADOR).exists()
    msg, _ = _salida_json(capsys)
    assert msg["systemMessage"].startswith("Tests locales: NO VERIFICADO.")
    assert "heavy relacionados" in msg["systemMessage"]


def test_related_heavy_passing_completes_pass(st, proyecto, monkeypatch, capsys):
    _arbol_heavy(proyecto)
    monkeypatch.setattr(st, "ficheros_modificados", lambda cwd: ["tests/test_dash.py"])
    monkeypatch.setattr(st, "comando_rapido", lambda: _py("print('7 passed')"))
    monkeypatch.setattr(st, "comando_heavy", lambda mods: _py("print('2 passed')"))
    assert st.main("{}", proyecto) == 0
    assert not (proyecto / st.MARCADOR).exists()
    msg, _ = _salida_json(capsys)
    assert "tests/test_dash.py" in msg["systemMessage"]


# --- contratos con el repositorio -----------------------------------------------

def test_fast_suite_excludes_slow_and_heavy(st):
    # El ULTIMO `-m`: el primero es el de `python -m pytest`.
    cmd = st.comando_rapido()
    assert cmd[len(cmd) - 1 - cmd[::-1].index("-m") + 1] == "not slow and not heavy"
    heavy = st.comando_heavy(["tests/x.py"])
    assert heavy[len(heavy) - 1 - heavy[::-1].index("-m") + 1] == "not slow"


def test_budget_stays_below_the_harness_timeout(st):
    cfg = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
    timeouts = [h["timeout"] for g in cfg["hooks"]["Stop"] for h in g["hooks"]
                if "run-tests-on-stop.sh" in h["command"]]
    assert timeouts == [1200]
    assert st.PRESUPUESTO_S < timeouts[0]


def test_heavy_marker_is_registered_and_on_the_measured_modules(st):
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'^\s*"heavy:', pyproject, re.MULTILINE)
    assert st.modulos_heavy(ROOT) == HEAVY


def test_ci_still_runs_the_full_suite():
    """CI no filtra por marcador: `slow` y `heavy` siguen ejecutandose alli."""
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    invocaciones = [ln.strip() for ln in ci.splitlines()
                    if re.search(r"\bpytest -q\b", ln)]
    assert len(invocaciones) >= 3
    assert all(" -m " not in ln and "--deselect" not in ln for ln in invocaciones)


def test_wrapper_delegates_and_never_deletes_the_marker():
    hook = (ROOT / ".claude/hooks/run-tests-on-stop.sh").read_text(encoding="utf-8")
    ejecutable = [ln for ln in hook.splitlines() if not ln.lstrip().startswith("#")]
    assert any('_stop_tests.py' in ln for ln in ejecutable)
    assert not any("rm " in ln for ln in ejecutable), (
        "el envoltorio no debe borrar el centinela: solo PASS lo retira")
