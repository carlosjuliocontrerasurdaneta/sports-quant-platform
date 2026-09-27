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


# --- KI-069: `_quita_heredocs` se comia el salto de linea entre el marcador --
# --- del heredoc y lo que le seguia, fusionando (via shlex) el delimitador --
# --- con el primer token de la siguiente linea y ocultando un `git add` ----
# --- real. Asi se colo el commit 58330c7. --------------------------------

# Contenido EXACTO del comando que colo el commit real (reproduccion KI-069):
# tres heredocs seguidos (uno con un cuerpo Python con comillas triples y
# caracteres no ASCII), y solo al final un `git add ... && git commit ...`.
_KI069_REPRO_CMD = 'cd /c/dev/3/sports-quant-platform && cat >> .claude/automation/runtime/current-task.md <<\'EOF\'\nFABLE-REVIEW: 2026-09-26 | veredicto: APTO CON CONDICIONES (x) | rutas: configs/leagues/ratings.yaml\nEOF\n/c/Users/Richard/AppData/Local/Programs/Python/Python314/python.exe - <<\'EOF\'\nfrom pathlib import Path\np=Path(\'Obsidian/Conocimiento/Señales por deporte.md\'); s=p.read_text(encoding=\'utf-8\')\na="## ❌ RECHAZADAS (infra queda dormida, no-op)"\nb="""## ✅ ACTIVA: x\n\n"""+a\nEOF\ncat >> "Obsidian/Bitácora/2026-09-26.md" <<\'EOF\'\n\n## Descanso NBA: ACEPTADO y activado\nEOF\ngit add configs/leagues/ratings.yaml tests/test_nba_rest_activation.py docs/research/2026-09-26-resultado-descanso-basket.md docs/research/2026-09-25-repreregistro-gate-k52.md docs/research/2026-08-26-preregistro-el-modelo-manda.md .claude/automation/runtime/current-task.md "Obsidian/Conocimiento/Señales por deporte.md" "Obsidian/Bitácora/2026-09-26.md" .claude/memory/project-decisions.md && git commit -q -F - <<\'EOF\'\nfeat(nba): activa el descanso/back-to-back (rest_points_per_day 0.795)\n\nPre-registro con revision Fable: ACEPTA 5/5 (Δ log loss -0,00224).\nEOF\ngit log --oneline -1\n'


def test_ki069_exact_bypass_reproduction_is_now_blocked(tmp_path):
    """Reproduccion exacta del agujero: antes de la correccion, este comando
    salia con 0 en <1s y sin ningun mensaje (el `git add` con las rutas
    sensibles quedaba invisible, fusionado con el heredoc anterior). Debe
    bloquear y listar las rutas sensibles del propio `git add`."""
    root = _repo(tmp_path)
    _current_task(root)
    result = _run(root, {"tool_name": "Bash", "tool_input": {"command": _KI069_REPRO_CMD}})
    assert result.returncode == 2, result.stderr
    for ruta in (
        "configs/leagues/ratings.yaml",
        "docs/research/2026-09-26-resultado-descanso-basket.md",
        "docs/research/2026-09-25-repreregistro-gate-k52.md",
        "docs/research/2026-08-26-preregistro-el-modelo-manda.md",
    ):
        assert ruta in result.stderr, result.stderr


def test_python_heredoc_with_triple_quotes_before_commit_is_detected(tmp_path):
    """Un heredoc de Python cuyo cuerpo contiene comillas triples (que antes
    de la correccion no era la causa del agujero, pero es el mismo patron que
    aparecio en el commit real) no debe esconder el `git commit` que viene
    despues en la siguiente linea."""
    root = _repo(tmp_path)
    _write_unstaged_sensitive_file(root)
    _current_task(root)
    command = (
        "git add configs/x.yaml && python - <<'EOF'\n"
        "texto = \"\"\"varias\n"
        "lineas\n"
        "con comillas triples\"\"\"\n"
        "print(texto)\n"
        "EOF\n"
        "git commit -m m"
    )
    result = _run(root, {"tool_name": "Bash", "tool_input": {"command": command}})
    assert result.returncode == 2, result.stderr
    assert "configs/x.yaml" in result.stderr


def test_two_heredocs_with_the_same_delimiter_are_both_detected(tmp_path):
    """Dos heredocs seguidos con el MISMO delimitador (`EOF` en ambos): el
    segundo no debe confundirse con el cierre del primero, y el `git commit`
    que sigue al segundo debe seguir detectandose."""
    root = _repo(tmp_path)
    _write_unstaged_sensitive_file(root)
    _current_task(root)
    command = (
        "cat > notas.md <<'EOF'\n"
        "primera nota\n"
        "EOF\n"
        "git add configs/x.yaml && git commit -F - <<'EOF'\n"
        "mensaje del commit\n"
        "EOF\n"
    )
    result = _run(root, {"tool_name": "Bash", "tool_input": {"command": command}})
    assert result.returncode == 2, result.stderr
    assert "configs/x.yaml" in result.stderr


def test_dash_dash_eof_heredoc_with_tabs_is_detected(tmp_path):
    """`<<-EOF` permite indentar el cuerpo y el delimitador de cierre con
    tabuladores; el `git commit` que sigue debe seguir detectandose."""
    root = _repo(tmp_path)
    _write_unstaged_sensitive_file(root)
    _current_task(root)
    command = (
        "git add configs/x.yaml && git commit -F - <<-'EOF'\n"
        "\t\tmensaje indentado con tabs\n"
        "\tEOF\n"
        "git log --oneline -1"
    )
    result = _run(root, {"tool_name": "Bash", "tool_input": {"command": command}})
    assert result.returncode == 2, result.stderr
    assert "configs/x.yaml" in result.stderr


def test_heredoc_body_mentioning_git_commit_followed_by_more_commands_still_passes(tmp_path):
    """Regresion especifica de la correccion: reponer el salto de linea tras
    un heredoc no debe hacer que un comando INOCUO que sigue a un heredoc
    informativo (cuyo cuerpo menciona `git commit` sin ser una invocacion
    real) se detecte como si fuera un commit."""
    root = _repo(tmp_path)
    _current_task(root)
    command = (
        "cat > notas.md <<'EOF'\n"
        "git add configs/x.yaml\n"
        "git commit -m m\n"
        "EOF\n"
        "echo listo"
    )
    result = _run(root, {"tool_name": "Bash", "tool_input": {"command": command}})
    assert result.returncode == 0, result.stderr


# --- KI-069, defensa en profundidad: la unica excepcion deliberada al -------
# --- fail-open. Un patron textual `git ... commit` que el analizador --------
# --- estructurado no consigue interpretar como invocacion real no puede -----
# --- salir con 0 en silencio si hay rutas sensibles ya staged. --------------

def test_defense_in_depth_blocks_an_unparseable_git_commit_pattern_with_sensitive_files_staged(tmp_path):
    """`git+commit` (un unico token pegado, sin espacio) no es una invocacion
    de `git` que el analizador estructurado sepa reconocer -- `_localiza_git`
    no encuentra ningun token exactamente igual a `git`. Pero el texto
    contiene el patron `git ... commit`, y ya hay una ruta sensible staged:
    el hook no puede darlo por inocuo en silencio."""
    root = _repo(tmp_path)
    _stage_sensitive_file(root)
    _current_task(root)
    result = _run(root, {"tool_name": "Bash",
                         "tool_input": {"command": 'git+commit -m "msg"'}})
    assert result.returncode == 2, result.stderr
    assert "configs/x.yaml" in result.stderr


def test_defense_in_depth_does_not_block_when_nothing_sensitive_is_at_stake(tmp_path):
    """El mismo patron no identificable, pero sin nada staged ni ningun `git
    add` detectable: la red de seguridad no debe convertirse en un bloqueo
    generico de cualquier texto que contenga las palabras `git` y `commit`."""
    root = _repo(tmp_path)
    _current_task(root)
    result = _run(root, {"tool_name": "Bash",
                         "tool_input": {"command": 'git+commit -m "msg"'}})
    assert result.returncode == 0, result.stderr


def test_defense_in_depth_hard_blocks_with_an_explanatory_message_when_git_cannot_be_asked(tmp_path):
    """Si ademas de no poder interpretar la invocacion tampoco se puede
    preguntar a git (aqui: la raiz no es un repo git, asi que `git diff
    --cached` falla), el hook debe bloquear explicando la limitacion en vez
    de fallar abierto en silencio -- la unica excepcion deliberada al
    fail-open general de este candado."""
    root = tmp_path  # deliberadamente SIN `git init`
    result = _run(root, {"tool_name": "Bash",
                         "tool_input": {"command": 'git+commit -m "msg"'}})
    assert result.returncode == 2, result.stderr
    assert "no pudo" in result.stderr.lower()
    assert "separa" in result.stderr.lower()


# --- Revision Fable 2026-09-26 (APTO CON CAMBIOS): la defensa en profundidad -
# --- daba falso positivo con comandos DE SOLO LECTURA que nunca commitean ---
# --- nada -- regresion por cada uno de los cuatro hallados, con una ruta ----
# --- sensible YA staged (el escenario donde antes bloqueaban con exit 2). --

@pytest.mark.parametrize("command", [
    "git log --grep commit --oneline",
    "git commit-tree HEAD^{tree} -m x",
    'echo "use git to commit"',
    "grep -rn 'git commit' .claude/hooks",
])
def test_readonly_commands_mentioning_git_and_commit_do_not_false_positive(tmp_path, command):
    """Los cuatro falsos positivos exactos de la verificacion de Fable: ninguno
    de estos comandos commitea nada, asi que deben pasar con exit 0 aunque ya
    haya una ruta sensible staged sin ninguna linea de cobertura -- antes de
    la correccion, los cuatro salian con exit 2 por la red textual de la
    defensa en profundidad, que casaba `\\bgit\\b[^\\n]*\\bcommit\\b` en el
    texto crudo sin distinguir una invocacion real de una mera mencion."""
    root = _repo(tmp_path)
    _stage_sensitive_file(root)
    _current_task(root)
    result = _run(root, {"tool_name": "Bash", "tool_input": {"command": command}})
    assert result.returncode == 0, result.stderr


# --- Verificacion de Fable 2026-09-26, segunda ronda (NO APTO): agujero (c) --
# --- (blanqueo de comillas indiscriminado, ANTES de la lista blanca de -----
# --- comandos de solo lectura) y agujero (b) (tuberias sin partir en -------
# --- etapas, ANTES de que `_segmenta_nivel_superior` partiera tambien por --
# --- `|` suelto). Ver docstring del modulo, seccion "segunda ronda". -------

@pytest.mark.parametrize("command", [
    'cmd /c "git add configs/x.yaml && git commit -m m"',
    'cmd.exe /c "git commit -m m"',
    'eval "git add configs/x.yaml && git commit -m m"',
    'env bash -c "git commit -m m"',
    'timeout 60 bash -c "git commit -m m"',
    'nohup sh -c "git commit -m m"',
    'echo configs/x.yaml | xargs -I{} sh -c "git add {} && git commit -m m"',
    'Invoke-Expression "git commit -m m"',
    'iex "git commit -m m"',
    'python -c "import subprocess; subprocess.run([\'git\',\'commit\',\'-m\',\'m\'])"',
    'git status | sh -c "git commit -m m"',
    'git diff --cached --name-only | xargs git commit -m m --',
])
def test_quote_emptying_and_pipe_bypasses_are_now_blocked(tmp_path, command):
    """Los ocho bypasses del agujero (c) (vaciado indiscriminado de comillas
    en cualquier segmento no reconocido) y los dos del agujero (b) (tuberias
    tratadas como un unico segmento) hallados en la verificacion de Fable del
    2026-09-26: con una ruta sensible ya staged y ninguna linea de cobertura,
    el candado debe bloquear -- las dos tuberias, resueltas ahora por el
    propio analizador estructurado al partir tambien por `|`; el resto, por
    la red de la defensa en profundidad, que ya no les blanquea las comillas
    porque su primer comando (`cmd`, `eval`, `env`, `timeout`, `nohup`,
    `xargs`, `Invoke-Expression`, `iex`, `python`) no esta en la lista blanca
    de comandos de solo lectura."""
    root = _repo(tmp_path)
    _stage_sensitive_file(root)
    _current_task(root)
    result = _run(root, {"tool_name": "Bash", "tool_input": {"command": command}})
    assert result.returncode == 2, result.stderr


def test_readonly_pipe_stage_does_not_false_positive(tmp_path):
    """`git status | grep modified`: ninguna etapa commitea nada (`git
    status` es un subcomando de `git` reconocido sin accion sobre rutas, y
    `grep` es de solo lectura), asi que debe pasar aunque haya una ruta
    sensible staged sin ninguna linea de cobertura. Regresion especifica de
    partir tambien por `|`: la nueva segmentacion no debe convertirse en un
    bloqueo generico de cualquier tuberia que mencione `git`."""
    root = _repo(tmp_path)
    _stage_sensitive_file(root)
    _current_task(root)
    result = _run(root, {"tool_name": "Bash",
                         "tool_input": {"command": "git status | grep modified"}})
    assert result.returncode == 0, result.stderr


def test_known_limitation_git_alias_commit_is_not_detected(tmp_path):
    """Limitacion documentada en el docstring del modulo, deliberadamente sin
    cerrar: un alias de git definido en la propia invocacion (`-c
    alias.ci=commit`) no se detecta, porque el segmento SI se reconoce como
    una invocacion real de `git` (subcomando `ci`) y por eso se retira por
    completo de la red textual. Fijado aqui para que un cambio futuro que lo
    corrija (o rompa por accidente) no lo pierda de vista."""
    root = _repo(tmp_path)
    _stage_sensitive_file(root)
    _current_task(root)
    result = _run(root, {"tool_name": "Bash", "tool_input": {
        "command": "git -c alias.ci=commit ci -m m"}})
    assert result.returncode == 0, result.stderr


def test_known_limitation_start_process_git_argumentlist_is_not_detected(tmp_path):
    """Limitacion documentada en el docstring del modulo, deliberadamente sin
    cerrar: `Start-Process git -ArgumentList "commit -m m"` no se detecta --
    `git` aparece como token exacto (se reconoce por busqueda de ultimo
    recurso) pero el "subcomando" resultante es el valor completo de
    `-ArgumentList`, que nunca casa con `commit`, y el segmento se da por
    reconocido y desaparece de la red igual que el caso anterior."""
    root = _repo(tmp_path)
    _stage_sensitive_file(root)
    _current_task(root)
    result = _run(root, {"tool_name": "PowerShell", "tool_input": {
        "command": 'Start-Process git -ArgumentList "commit -m m"'}})
    assert result.returncode == 0, result.stderr


# --- Verificacion de Fable 2026-09-26, tercera ronda (NO APTO): dos agujeros -
# --- mas en la propia lista blanca de comandos de solo lectura introducida --
# --- en la segunda ronda. Ver docstring del modulo, seccion "tercera ronda". -

@pytest.mark.parametrize("command", [
    # Hallazgo 1: sustitucion de comandos DENTRO de una cadena entre comillas
    # DOBLES de un segmento de la lista blanca -- `_blanquea_comillas` vaciaba
    # ese contenido por igual que un argumento de texto plano, ocultando la
    # invocacion real que bash/PowerShell SI expanden y ejecutan.
    'echo "$(git commit -m m)"',
    'echo "`git commit -m m`"',
    'grep "$(git commit -m m)" f',
    'Write-Output "$(git commit -m m)"',
    # Hallazgo 2: tuberia de un segmento de la lista blanca HACIA un
    # interprete -- su salida se canaliza a otra etapa que la ejecuta, asi
    # que ya no es inocuo blanquear lo que "dice".
    'echo "git commit -m m" | sh',
    "printf 'git commit -m m' | bash",
    'Write-Output "git commit -m m" | iex',
])
def test_third_round_whitelist_holes_are_now_blocked(tmp_path, command):
    """Los siete agujeros exactos de la tercera verificacion de Fable
    (2026-09-26, NO APTO): con una ruta sensible ya staged y ninguna linea de
    cobertura, el candado debe bloquear -- los cuatro primeros porque
    `_blanquea_comillas` ya no vacia una cadena entre comillas dobles cuyo
    contenido contenga `$(` o una comilla invertida, y los tres ultimos
    porque `_segmenta_nivel_superior` marca el segmento de la lista blanca
    como seguido de tuberia y `_procesa_texto` lo protege de la red en vez de
    blanquearlo."""
    root = _repo(tmp_path)
    _stage_sensitive_file(root)
    _current_task(root)
    result = _run(root, {"tool_name": "Bash", "tool_input": {"command": command}})
    assert result.returncode == 2, result.stderr


@pytest.mark.parametrize("command", [
    "grep -E 'git|commit' src",
    "git log | grep -E 'fix|commit'",
    "rg 'git commit|push' .",
    "git status || echo 'git commit failed'",
])
def test_third_round_fix_keeps_these_readonly_commands_at_zero(tmp_path, command):
    """Regresion especifica de la correccion de la tercera ronda: el contenido
    de una cadena entre comillas SIMPLES se sigue blanqueando siempre (no solo
    cuando no contiene `$(`/backtick), y una etapa de la lista blanca que es
    la ULTIMA de su tuberia (sin `|` despues) se sigue blanqueando como
    siempre. Ninguno de estos cuatro comandos commitea nada, asi que deben
    seguir pasando con exit 0 aunque haya una ruta sensible staged sin ninguna
    linea de cobertura."""
    root = _repo(tmp_path)
    _stage_sensitive_file(root)
    _current_task(root)
    result = _run(root, {"tool_name": "Bash", "tool_input": {"command": command}})
    assert result.returncode == 0, result.stderr


def test_known_tradeoff_whitelist_segment_piped_to_a_readonly_command_now_overblocks(tmp_path):
    """Efecto secundario CONOCIDO y deliberadamente aceptado del arreglo minimo
    de la tercera ronda (documentado en el docstring del modulo): la
    correccion protege CUALQUIER segmento de la lista blanca seguido de una
    tuberia, sin distinguir si la etapa que la recibe es un interprete
    (`sh`, `bash`, `iex`) o, como aqui, otro comando de solo lectura
    (`grep`) -- es la opcion mas simple y segura que la propia revision de
    Fable senala explicitamente ("cualquier etapa posterior en la tuberia").
    Antes de la tercera ronda este comando pasaba con exit 0; ahora bloquea
    porque el contenido citado de `echo`, aunque el pipe destino sea inocuo,
    ya no se blanquea. Fijado aqui para que un cambio futuro que lo afine (o
    lo pierda) no lo haga sin darse cuenta."""
    root = _repo(tmp_path)
    _stage_sensitive_file(root)
    _current_task(root)
    result = _run(root, {"tool_name": "Bash", "tool_input": {
        "command": 'echo "a | git commit" | grep x'}})
    assert result.returncode == 2, result.stderr
