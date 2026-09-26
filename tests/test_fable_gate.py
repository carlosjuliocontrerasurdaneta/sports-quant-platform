"""Candado de proceso: revision Fable obligatoria antes de commitear una ruta
sensible del disparador de escalado (`.claude/automation/MODEL_ROUTING.md`,
seccion "Disparador de escalado").

Motivo (2026-09-26): se commiteo un cambio de parametro de modelo
(`configs/leagues/ratings.yaml`) sin la revision previa de Fable que exige la
politica. `.claude/hooks/fable_gate.py` cierra ese olvido especifico como
`PreToolUse` de `Bash`/`PowerShell`: bloquea `git commit` cuando toca una ruta
de `.claude/automation/fable-gate.json` y no hay, en
`.claude/automation/runtime/current-task.md`, una linea
`FABLE-REVIEW: <hoy> | veredicto: <texto sin NO APTO/REVERTIR/RECHAZ> | rutas: ...`
que la cubra.

Se ejecuta el hook REAL como subproceso contra repos git temporales -- igual
que `tests/test_audit_hooks.py` hace con los hooks de bash --, exigiendo el
comportamiento observable (codigo de salida, contenido de stderr) y no la
implementacion interna.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "fable_gate.py"
GATE_CONFIG = ROOT / ".claude" / "automation" / "fable-gate.json"

# Calculadas en cada ejecucion: el candado compara contra la fecha de HOY en
# hora local, no contra una fecha fija, asi que el test tampoco puede fijarla.
HOY = date.today().isoformat()
AYER = (date.today() - timedelta(days=1)).isoformat()


def _repo(tmp_path: Path) -> Path:
    """Repo git temporal con la config real del candado ya copiada dentro."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True,
                   capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"],
                   cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path,
                   check=True, capture_output=True)
    (tmp_path / ".claude" / "automation" / "runtime").mkdir(parents=True)
    (tmp_path / ".claude" / "automation" / "fable-gate.json").write_text(
        GATE_CONFIG.read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def _current_task(root: Path, lineas: tuple[str, ...] = ()) -> None:
    contenido = "# Current Task\n\n" + "\n".join(lineas) + "\n"
    (root / ".claude" / "automation" / "runtime" / "current-task.md").write_text(
        contenido, encoding="utf-8")


def _run(root: Path, payload: dict, env_extra: dict | None = None
         ) -> subprocess.CompletedProcess:
    return _run_raw(root, json.dumps(payload), env_extra)


def _run_raw(root: Path, stdin_text: str, env_extra: dict | None = None
             ) -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root)}
    env.pop("SQP_FABLE_GATE", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(HOOK)], cwd=root, input=stdin_text, text=True,
        capture_output=True, env=env, timeout=30,
    )


def _stage_sensitive_file(root: Path) -> None:
    (root / "configs").mkdir(exist_ok=True)
    (root / "configs" / "x.yaml").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "configs/x.yaml"], cwd=root, check=True,
                   capture_output=True)


# --- 1. Sin `git commit`, no hay nada que candar -----------------------------

def test_a_command_without_a_git_commit_passes(tmp_path):
    root = _repo(tmp_path)
    result = _run(root, {"tool_name": "Bash", "tool_input": {"command": "git status"}})
    assert result.returncode == 0, result.stderr


# --- 2. Commit sin ninguna ruta sensible -------------------------------------

def test_commit_touching_only_non_sensitive_paths_passes(tmp_path):
    root = _repo(tmp_path)
    (root / "README.md").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=root, check=True,
                   capture_output=True)
    _current_task(root)
    result = _run(root, {"tool_name": "Bash",
                         "tool_input": {"command": 'git commit -m "msg"'}})
    assert result.returncode == 0, result.stderr


# --- 3 y 12. Ruta sensible staged, sin linea de cobertura -> bloquea, en ambas
#             shells (misma logica: ambas leen `tool_input.command`) --------

@pytest.mark.parametrize("tool_name", ["Bash", "PowerShell"])
def test_staged_sensitive_path_without_a_review_line_blocks(tmp_path, tool_name):
    root = _repo(tmp_path)
    _stage_sensitive_file(root)
    _current_task(root)
    result = _run(root, {"tool_name": tool_name,
                         "tool_input": {"command": 'git commit -m "msg"'}})
    assert result.returncode == 2
    assert "configs/x.yaml" in result.stderr
    assert "FABLE-REVIEW" in result.stderr


# --- 4. Linea de HOY que cubre la ruta exacta -> pasa, en ambas shells -------

@pytest.mark.parametrize("tool_name", ["Bash", "PowerShell"])
def test_todays_review_line_covering_the_exact_path_passes(tmp_path, tool_name):
    root = _repo(tmp_path)
    _stage_sensitive_file(root)
    _current_task(root, (
        f"FABLE-REVIEW: {HOY} | veredicto: APTO, sin cambios | rutas: configs/x.yaml",
    ))
    result = _run(root, {"tool_name": tool_name,
                         "tool_input": {"command": 'git commit -m "msg"'}})
    assert result.returncode == 0, result.stderr


# --- 5. Linea de AYER no cubre el commit de hoy ------------------------------

def test_yesterdays_review_line_does_not_cover_todays_commit(tmp_path):
    root = _repo(tmp_path)
    _stage_sensitive_file(root)
    _current_task(root, (
        f"FABLE-REVIEW: {AYER} | veredicto: APTO | rutas: configs/x.yaml",
    ))
    result = _run(root, {"tool_name": "Bash",
                         "tool_input": {"command": 'git commit -m "msg"'}})
    assert result.returncode == 2
    assert "configs/x.yaml" in result.stderr


# --- 6. Veredictos descalificantes no cuentan como cobertura -----------------

@pytest.mark.parametrize("veredicto", [
    "NO APTO", "no apto", "No Apto", "REVERTIR", "revertir",
    "RECHAZADO", "se rechaza el cambio",
])
def test_disqualifying_verdicts_do_not_count_as_coverage(tmp_path, veredicto):
    root = _repo(tmp_path)
    _stage_sensitive_file(root)
    _current_task(root, (
        f"FABLE-REVIEW: {HOY} | veredicto: {veredicto} | rutas: configs/x.yaml",
    ))
    result = _run(root, {"tool_name": "Bash",
                         "tool_input": {"command": 'git commit -m "msg"'}})
    assert result.returncode == 2, (
        f"veredicto {veredicto!r} deberia haber sido rechazado como cobertura")


# --- 7. Cobertura por prefijo de directorio ("configs/") ---------------------

def test_directory_prefix_coverage_passes(tmp_path):
    root = _repo(tmp_path)
    _stage_sensitive_file(root)
    _current_task(root, (
        f"FABLE-REVIEW: {HOY} | veredicto: APTO | rutas: configs/",
    ))
    result = _run(root, {"tool_name": "Bash",
                         "tool_input": {"command": 'git commit -m "msg"'}})
    assert result.returncode == 0, result.stderr


# --- 8. `git add ... && git commit ...` sin nada staged de antemano ----------

def test_git_add_and_commit_chained_in_one_command_is_detected(tmp_path):
    """En el instante en que corre el hook (PreToolUse, ANTES de que la shell
    ejecute nada), `configs/x.yaml` todavia no esta en el indice real: si el
    hook solo mirara `git diff --cached` no veria nada. Tiene que leer el
    propio `git add` del comando."""
    root = _repo(tmp_path)
    _current_task(root)
    result = _run(root, {"tool_name": "Bash", "tool_input": {
        "command": "git add configs/x.yaml && git commit -m m"}})
    assert result.returncode == 2
    assert "configs/x.yaml" in result.stderr


# --- 9. `-am` arrastra cambios sin stagear ------------------------------------

def test_dash_am_pulls_in_unstaged_working_tree_changes(tmp_path):
    root = _repo(tmp_path)
    _stage_sensitive_file(root)
    subprocess.run(["git", "commit", "-m", "base"], cwd=root, check=True,
                   capture_output=True)
    (root / "configs" / "x.yaml").write_text("y", encoding="utf-8")  # sin `add`
    _current_task(root)
    result = _run(root, {"tool_name": "Bash",
                         "tool_input": {"command": 'git commit -am "msg"'}})
    assert result.returncode == 2
    assert "configs/x.yaml" in result.stderr


def test_plain_commit_without_dash_a_ignores_unstaged_changes(tmp_path):
    """El reverso de la prueba anterior: sin `-a`/`-am`, un cambio sin stagear
    no arma el candado aunque exista en el working tree."""
    root = _repo(tmp_path)
    _stage_sensitive_file(root)
    subprocess.run(["git", "commit", "-m", "base"], cwd=root, check=True,
                   capture_output=True)
    (root / "configs" / "x.yaml").write_text("y", encoding="utf-8")
    _current_task(root)
    result = _run(root, {"tool_name": "Bash",
                         "tool_input": {"command": 'git commit -m "msg"'}})
    assert result.returncode == 0, result.stderr


# --- 10. Escape del operador --------------------------------------------------

def test_operator_escape_hatch_bypasses_everything(tmp_path):
    root = _repo(tmp_path)
    _stage_sensitive_file(root)
    _current_task(root)
    result = _run(root, {"tool_name": "Bash",
                         "tool_input": {"command": 'git commit -m "msg"'}},
                  env_extra={"SQP_FABLE_GATE": "off"})
    assert result.returncode == 0
    assert "SQP_FABLE_GATE=off" in result.stderr


# --- 11. JSON ilegible falla abierto ------------------------------------------

def test_unparseable_json_fails_open(tmp_path):
    root = _repo(tmp_path)
    result = _run_raw(root, "{esto no es json")
    assert result.returncode == 0
    assert result.stderr  # avisa, pero no bloquea


def test_fable_gate_json_missing_fails_open(tmp_path):
    """Si `fable-gate.json` no se puede leer, el candado no puede saber que es
    sensible: fail-open, no bloqueo por defecto."""
    root = _repo(tmp_path)
    (root / ".claude" / "automation" / "fable-gate.json").unlink()
    _stage_sensitive_file(root)
    _current_task(root)
    result = _run(root, {"tool_name": "Bash",
                         "tool_input": {"command": 'git commit -m "msg"'}})
    assert result.returncode == 0, result.stderr


# --- 13. Ruta con acento que no es sensible -----------------------------------

def test_accented_non_sensitive_path_passes(tmp_path):
    root = _repo(tmp_path)
    (root / "Obsidian").mkdir()
    (root / "Obsidian" / "Bitácora.md").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "Obsidian/Bitácora.md"], cwd=root,
                   check=True, capture_output=True)
    _current_task(root)
    result = _run(root, {"tool_name": "Bash",
                         "tool_input": {"command": 'git commit -m "msg"'}})
    assert result.returncode == 0, result.stderr


# --- 14. El candado de los propios patrones -----------------------------------

def test_the_sensitive_path_patterns_are_a_deliberate_list():
    """Fija el CONTENIDO EXACTO de `fable-gate.json`. Ampliarlo o recortarlo
    tiene que ser un cambio consciente de este test, no un efecto colateral
    de tocar el fichero por otra razon."""
    data = json.loads(GATE_CONFIG.read_text(encoding="utf-8"))
    assert data["patrones"] == [
        "configs/**",
        "docs/research/*preregistro*",
        "docs/research/*resultado*",
        "src/sqp/risk/**",
        "src/sqp/settlement/**",
        "src/sqp/calibration/**",
        "src/sqp/storage/**",
        "src/sqp/models/**",
        "src/sqp/pipeline/probabilities.py",
        "src/sqp/sports/adapters.py",
        "src/sqp/config.py",
        "src/sqp/markets/edge.py",
        "src/sqp/markets/vig.py",
        "src/sqp/markets/settlement_math.py",
    ]
    assert isinstance(data.get("_why"), str) and data["_why"].strip()


# --- Revision Fable 2026-09-26 (APTO CON CAMBIOS): regresion por cada hallazgo -

def _write_unstaged_sensitive_file(root: Path, relpath: str = "configs/x.yaml") -> None:
    """Como `_stage_sensitive_file`, pero SIN `git add`: para probar que el
    propio `git add` del comando (o su resolucion via `--dry-run`) es lo que
    lo detecta, no un `git diff --cached` de algo ya en el indice."""
    p = root / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x", encoding="utf-8")


# 15. Hallazgo 8: nuevas rutas sensibles (config.py, edge.py, vig.py,
#     settlement_math.py) bloquean igual que cualquier otra.

@pytest.mark.parametrize("relpath", [
    "src/sqp/config.py",
    "src/sqp/markets/edge.py",
    "src/sqp/markets/vig.py",
    "src/sqp/markets/settlement_math.py",
])
def test_new_market_and_config_paths_are_sensitive(tmp_path, relpath):
    root = _repo(tmp_path)
    (root / relpath).parent.mkdir(parents=True, exist_ok=True)
    (root / relpath).write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", relpath], cwd=root, check=True, capture_output=True)
    _current_task(root)
    result = _run(root, {"tool_name": "Bash",
                         "tool_input": {"command": 'git commit -m "msg"'}})
    assert result.returncode == 2
    assert relpath in result.stderr


# 16. Hallazgo 1 y 2: un prefijo de variable de entorno DENTRO del comando ni
#     escapa la deteccion ni desactiva el candado (solo cuenta `os.environ`).

def test_env_var_prefix_on_git_add_and_commit_is_still_detected(tmp_path):
    root = _repo(tmp_path)
    _write_unstaged_sensitive_file(root)
    _current_task(root)
    result = _run(root, {"tool_name": "Bash", "tool_input": {
        "command": "SQP_FABLE_GATE=off git add configs/x.yaml "
                   "&& SQP_FABLE_GATE=off git commit -m m"}})
    assert result.returncode == 2
    assert "configs/x.yaml" in result.stderr


def test_command_prefix_env_var_does_not_bypass_the_gate(tmp_path):
    """Requisito 2, explicito: `SQP_FABLE_GATE=off` escrito DENTRO de
    `command` nunca desactiva el candado -- solo cuenta la variable de
    ENTORNO DE SESION (`os.environ`) que el operador fija al arrancar Claude
    Code, comprobada por `test_operator_escape_hatch_bypasses_everything`."""
    root = _repo(tmp_path)
    _stage_sensitive_file(root)
    _current_task(root)
    result = _run(root, {"tool_name": "Bash", "tool_input": {
        "command": 'SQP_FABLE_GATE=off git commit -m "msg"'}})
    assert result.returncode == 2
    assert "configs/x.yaml" in result.stderr


# 17. Hallazgo 1: PowerShell `...; if ($?) { git commit ... }`.

def test_powershell_if_dollar_q_wrapper_is_detected(tmp_path):
    root = _repo(tmp_path)
    _write_unstaged_sensitive_file(root)
    _current_task(root)
    result = _run(root, {"tool_name": "PowerShell", "tool_input": {
        "command": "git add configs/x.yaml; if ($?) { git commit -m m }"}})
    assert result.returncode == 2
    assert "configs/x.yaml" in result.stderr


# 18. Hallazgo 1: grupo de llaves `{ git commit ...; }`.

def test_brace_group_around_git_commit_is_detected(tmp_path):
    root = _repo(tmp_path)
    _stage_sensitive_file(root)
    _current_task(root)
    result = _run(root, {"tool_name": "Bash",
                         "tool_input": {"command": "{ git commit -m m; }"}})
    assert result.returncode == 2
    assert "configs/x.yaml" in result.stderr


# 19. Hallazgo 1: `bash -c`, `sh -c` y `pwsh -Command` se analizan recursivamente.

@pytest.mark.parametrize("command", [
    "bash -c 'git add configs/x.yaml && git commit -m m'",
    "sh -c 'git add configs/x.yaml && git commit -m m'",
    'pwsh -Command "git add configs/x.yaml && git commit -m m"',
])
def test_shell_wrapper_c_command_string_is_analyzed_recursively(tmp_path, command):
    root = _repo(tmp_path)
    _write_unstaged_sensitive_file(root)
    _current_task(root)
    result = _run(root, {"tool_name": "Bash", "tool_input": {"command": command}})
    assert result.returncode == 2
    assert "configs/x.yaml" in result.stderr


# 20. Hallazgo 3: el cuerpo de un heredoc no rompe la deteccion del commit real
#     que lo precede (apostrofe y saltos de linea incluidos).

def test_heredoc_commit_message_body_is_still_detected(tmp_path):
    root = _repo(tmp_path)
    _write_unstaged_sensitive_file(root)
    (root / "Obsidian").mkdir()
    (root / "Obsidian" / "x.md").write_text("x", encoding="utf-8")
    _current_task(root)
    command = (
        "git add configs/x.yaml Obsidian/x.md && git commit -F - <<'EOF'\n"
        "feat(mlb): pitcher_bound 0.05; don't\n\n"
        "Co-Authored-By: X\nEOF"
    )
    result = _run(root, {"tool_name": "Bash", "tool_input": {"command": command}})
    assert result.returncode == 2
    assert "configs/x.yaml" in result.stderr


# 21. Hallazgo 3: un heredoc que solo ESCRIBE un fichero cuyo contenido
#     literal menciona `git add`/`git commit` no es una invocacion real.

def test_heredoc_document_mentioning_git_commit_in_its_body_passes(tmp_path):
    root = _repo(tmp_path)
    _current_task(root)
    command = (
        "cat > notas.md <<'EOF'\n"
        "git add configs/x.yaml\n"
        "git commit -m m\n"
        "EOF"
    )
    result = _run(root, {"tool_name": "Bash", "tool_input": {"command": command}})
    assert result.returncode == 0, result.stderr


# 22. Hallazgo 3: continuacion de linea (`\` + salto de linea) se une antes de
#     trocear.

def test_line_continuation_is_joined_before_tokenizing(tmp_path):
    root = _repo(tmp_path)
    _write_unstaged_sensitive_file(root)
    (root / "Obsidian").mkdir()
    (root / "Obsidian" / "x.md").write_text("x", encoding="utf-8")
    _current_task(root)
    command = "git add Obsidian/x.md \\\n  configs/x.yaml && git commit -m m"
    result = _run(root, {"tool_name": "Bash", "tool_input": {"command": command}})
    assert result.returncode == 2
    assert "configs/x.yaml" in result.stderr


# 23. Hallazgo 4: el VALOR de `-m` (y de `-F`/`-C`/`-c`/`-t`/`--author`/`--date`)
#     nunca se inspecciona como si fuera un flag corto.

def test_dash_m_message_starting_with_dash_a_word_does_not_trigger_dash_a(tmp_path):
    root = _repo(tmp_path)
    _stage_sensitive_file(root)
    subprocess.run(["git", "commit", "-m", "base"], cwd=root, check=True,
                   capture_output=True)
    (root / "configs" / "x.yaml").write_text("y", encoding="utf-8")  # sin stagear
    (root / "README.md").write_text("r", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=root, check=True,
                   capture_output=True)
    _current_task(root)
    result = _run(root, {"tool_name": "Bash", "tool_input": {
        "command": 'git commit -m "- actualiza README"'}})
    assert result.returncode == 0, result.stderr


# 24. Hallazgo 5: lista blanca anclada al inicio del veredicto, no lista negra
#     por substring.

@pytest.mark.parametrize("veredicto", [
    "APTO; no hace falta revertir nada",
    "APTO CON CAMBIOS aplicados",
    "apto con cambios",
])
def test_apto_prefixed_verdicts_count_even_mentioning_forbidden_words(tmp_path, veredicto):
    root = _repo(tmp_path)
    _stage_sensitive_file(root)
    _current_task(root, (
        f"FABLE-REVIEW: {HOY} | veredicto: {veredicto} | rutas: configs/x.yaml",
    ))
    result = _run(root, {"tool_name": "Bash",
                         "tool_input": {"command": 'git commit -m "msg"'}})
    assert result.returncode == 0, result.stderr


def test_non_apto_verdict_without_forbidden_words_still_blocks(tmp_path):
    """Antes (lista negra por substring), 'BLOQUEANTE, no commitear' pasaba
    como cobertura valida porque no citaba 'no apto'/'revertir'/'rechaz'. La
    lista blanca anclada al inicio lo bloquea correctamente."""
    root = _repo(tmp_path)
    _stage_sensitive_file(root)
    _current_task(root, (
        f"FABLE-REVIEW: {HOY} | veredicto: BLOQUEANTE, no commitear | rutas: configs/x.yaml",
    ))
    result = _run(root, {"tool_name": "Bash",
                         "tool_input": {"command": 'git commit -m "msg"'}})
    assert result.returncode == 2


# 25. Hallazgo 6: resolucion de rutas de `git add` via `git add --dry-run`
#     (`.`, `-A`, directorio) y de pathspecs de `git commit` via `ls-files`.

def test_git_add_dot_resolves_to_real_sensitive_files(tmp_path):
    root = _repo(tmp_path)
    _write_unstaged_sensitive_file(root)
    _current_task(root)
    result = _run(root, {"tool_name": "Bash", "tool_input": {
        "command": "git add . && git commit -m m"}})
    assert result.returncode == 2
    assert "configs/x.yaml" in result.stderr


def test_git_add_dash_capital_a_resolves_to_real_sensitive_files(tmp_path):
    root = _repo(tmp_path)
    _write_unstaged_sensitive_file(root)
    _current_task(root)
    result = _run(root, {"tool_name": "Bash", "tool_input": {
        "command": "git add -A && git commit -m m"}})
    assert result.returncode == 2
    assert "configs/x.yaml" in result.stderr


def test_git_add_directory_resolves_to_the_exact_file_inside_and_a_review_of_that_exact_file_covers_it(tmp_path):
    root = _repo(tmp_path)
    _write_unstaged_sensitive_file(root)
    _current_task(root, (
        f"FABLE-REVIEW: {HOY} | veredicto: APTO | rutas: configs/x.yaml",
    ))
    result = _run(root, {"tool_name": "Bash", "tool_input": {
        "command": "git add configs/ && git commit -m m"}})
    assert result.returncode == 0, result.stderr


def test_git_commit_pathspec_after_double_dash_is_resolved(tmp_path):
    root = _repo(tmp_path)
    _write_unstaged_sensitive_file(root)
    _current_task(root)
    result = _run(root, {"tool_name": "Bash", "tool_input": {
        "command": "git commit -m m -- configs/x.yaml"}})
    assert result.returncode == 2
    assert "configs/x.yaml" in result.stderr


# 26. Hallazgo 7: `fnmatch.fnmatchcase`, no `fnmatch.fnmatch` -- un repo git es
#     sensible a mayusculas/minusculas aunque el sistema de ficheros local no
#     lo sea.

def test_case_differing_path_is_not_treated_as_sensitive(tmp_path):
    root = _repo(tmp_path)
    (root / "Configs").mkdir()
    (root / "Configs" / "X.yaml").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "Configs/X.yaml"], cwd=root, check=True,
                   capture_output=True)
    _current_task(root)
    result = _run(root, {"tool_name": "Bash",
                         "tool_input": {"command": 'git commit -m "msg"'}})
    assert result.returncode == 0, result.stderr


# 27. Hallazgo 9: timeout acotado y `GIT_OPTIONAL_LOCKS=0` en cada llamada a git.

def _carga_modulo_del_hook():
    import importlib.util
    spec = importlib.util.spec_from_file_location("fable_gate_bajo_prueba", HOOK)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_git_calls_use_a_bounded_timeout_and_disable_optional_locks():
    modulo = _carga_modulo_del_hook()
    assert 0 < modulo._GIT_TIMEOUT_SEGUNDOS <= 15
    entorno = modulo._entorno_git()
    assert entorno["GIT_OPTIONAL_LOCKS"] == "0"


# 28. Hallazgo 10: un `UnicodeEncodeError` al imprimir el bloqueo (ruta no
#     ASCII bajo stdio de codificacion limitada) no debe volverse fail-open.

def test_blocking_message_with_non_ascii_path_does_not_crash_under_ascii_stdio(tmp_path):
    root = _repo(tmp_path)
    (root / "configs").mkdir(exist_ok=True)
    (root / "configs" / "ratingsá.yaml").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True)
    _current_task(root)
    result = _run(root, {"tool_name": "Bash",
                         "tool_input": {"command": 'git commit -m "msg"'}},
                  env_extra={"PYTHONIOENCODING": "ascii"})
    assert result.returncode == 2
    assert "fable_gate" in result.stderr


# Verificacion de Fable (2026-09-26), hueco A: `-c` combinado (`bash -lc`).

@pytest.mark.parametrize("command", [
    "bash -lc 'git add configs/x.yaml && git commit -m m'",
    "sh -ec 'git add configs/x.yaml && git commit -m m'",
])
def test_combined_short_c_flag_wrapper_is_analyzed(tmp_path, command):
    root = _repo(tmp_path)
    _write_unstaged_sensitive_file(root)
    _current_task(root)
    result = _run(root, {"tool_name": "Bash", "tool_input": {"command": command}})
    assert result.returncode == 2
    assert "configs/x.yaml" in result.stderr


# Verificacion de Fable (2026-09-26), hueco B: `-m"mensaje"` pegado no es `-a`,
# pero `-am` sigue siendolo.

def test_glued_dash_m_message_does_not_trigger_dash_a(tmp_path):
    root = _repo(tmp_path)
    _stage_sensitive_file(root)
    subprocess.run(["git", "commit", "-m", "base"], cwd=root, check=True,
                   capture_output=True)
    (root / "configs" / "x.yaml").write_text("y", encoding="utf-8")  # sin stagear
    (root / "README.md").write_text("r", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=root, check=True,
                   capture_output=True)
    _current_task(root)
    ok = _run(root, {"tool_name": "Bash", "tool_input": {
        "command": 'git commit -m"arregla README"'}})
    assert ok.returncode == 0, ok.stderr
    blocked = _run(root, {"tool_name": "Bash", "tool_input": {
        "command": 'git commit -am "arregla README"'}})
    assert blocked.returncode == 2
