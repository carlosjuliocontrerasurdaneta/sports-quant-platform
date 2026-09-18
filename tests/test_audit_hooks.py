"""AUD-009/010: exercise actual hooks using Git Bash on Windows."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _bash():
    executable = ("C:/Program Files/Git/bin/bash.exe" if os.name == "nt"
                  else shutil.which("bash"))
    if not executable or not Path(executable).exists():
        pytest.skip("Git Bash/native bash unavailable")
    return executable


def _run(root, script, payload=None):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root)}
    return subprocess.run([_bash(), str(root / script)], cwd=root,
                          input=json.dumps(payload or {}), text=True,
                          capture_output=True, env=env, timeout=30)


@pytest.mark.parametrize("assignment", [
    'ODDS_API_KEY="ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"',
    'set ODDS_API_KEY=ABCDEFGHIJKLMNOPQRSTUVWXYZ012345',
    'api_key: ABCDEFGHIJKLMNOPQRSTUVWXYZ012345',
])
@pytest.mark.parametrize("comment", ["", " # replaces the example key"])
def test_comments_do_not_hide_literal(tmp_path, assignment, comment):
    shutil.copytree(ROOT / ".claude/hooks", tmp_path / ".claude/hooks")
    target = tmp_path / "fixture.txt"
    target.write_text(assignment + comment, encoding="utf-8")
    result = _run(tmp_path, ".claude/hooks/check-secrets.sh",
                  {"tool_input": {"file_path": str(target)}})
    assert result.returncode == 2
    assert "ABCDEFGHIJKLMNOPQRSTUVWXYZ012345" not in result.stderr


@pytest.mark.parametrize("value", ['"TU_CLAVE"', '"your_placeholder"',
                                   'os.environ["ODDS_API_KEY"]', '%ODDS_API_KEY%'])
def test_placeholders_remain_allowed(tmp_path, value):
    shutil.copytree(ROOT / ".claude/hooks", tmp_path / ".claude/hooks")
    target = tmp_path / "fixture.txt"
    target.write_text("ODDS_API_KEY=" + value, encoding="utf-8")
    assert _run(tmp_path, ".claude/hooks/check-secrets.sh",
                {"tool_input": {"file_path": str(target)}}).returncode == 0


def test_reinstall_preserves_runtime_hooks_and_bash_targets(tmp_path):
    shutil.copytree(ROOT / ".claude/hooks", tmp_path / ".claude/hooks")
    shutil.copy2(ROOT / "instalar-candados.sh", tmp_path)
    hooks = [tmp_path / ".claude/hooks" / f"{name}.sh" for name in
             ("require-dispatch-model", "mark-crossreview-pending", "crossreview-on-stop")]
    before = [p.read_bytes() for p in hooks]
    result = _run(tmp_path, "instalar-candados.sh")
    assert result.returncode == 0, result.stderr
    assert "Edit|Write|Bash" in result.stdout
    assert [p.read_bytes() for p in hooks] == before
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs/test.yaml").write_text("x", encoding="utf-8")
    result = _run(tmp_path, ".claude/hooks/mark-crossreview-pending.sh",
                  {"tool_name": "Bash", "tool_input": {"command": "echo x > configs/test.yaml"}})
    assert result.returncode == 0
    assert (tmp_path / ".claude/.crossreview-pending").exists()


# AUD-007 (ronda audit-2026-09-18): el detector marcaba como secreto una
# asignacion REFLEXIVA (`self.api_key = api_key`) seguida de `\r\n` escapado
# dentro de una cadena JSON (codigo fuente citado en un EVIDENCE.json): el
# "valor" capturado era el propio identificador mas los 4 caracteres de
# escape. Y `check-secrets.sh` re-escaneaba ese fichero, ajeno al turno, en
# cada comando Bash con operador de escritura: >15 avisos identicos por sesion.
def _suspicious_lines():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "secret_literals", ROOT / ".claude/hooks/_secret_literals.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.suspicious_lines


@pytest.mark.parametrize("line", [
    # asignacion reflexiva citada dentro de una cadena JSON (escape literal)
    '"output": "        self.api_key = api_key\r\n        self.regions = regions"',
    # asignacion reflexiva en codigo fuente
    "        self.api_key = api_key",
    "settings.odds_api_key = odds_api_key  # inyectada",
    # el valor es una llamada / atributo, no un literal
    "api_key = settings.odds_api_key",
    "token = read_token_from(path)",
])
def test_reflexive_or_symbolic_assignments_are_not_secrets(line):
    assert _suspicious_lines()(line) == []


@pytest.mark.parametrize("line", [
    'ODDS_API_KEY="ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"',
    "api_key = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ012345'",
    "TOKEN: ABCDEFGHIJKLMNOPQRSTUVWXYZ012345",
    '"api_key": "ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"',
])
def test_real_literals_still_detected(line):
    assert _suspicious_lines()(line) == [1]


def test_audit_reports_are_excluded_from_the_scan(tmp_path):
    """Los informes de auditoria citan codigo y evidencias de otros agentes;
    no son ficheros del turno y no llevan secretos del proyecto. Se excluyen
    como ya se excluian data/, logs/ y exports/."""
    shutil.copytree(ROOT / ".claude/hooks", tmp_path / ".claude/hooks")
    for rel in ("audit/latest/openai/EVIDENCE.json", "audits/x/REPORT.md"):
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('ODDS_API_KEY="ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"',
                          encoding="utf-8")
        result = _run(tmp_path, ".claude/hooks/check-secrets.sh",
                      {"tool_input": {"file_path": str(target)}})
        assert result.returncode == 0, result.stderr
    # ...pero un fichero de codigo con el mismo literal sigue bloqueando, y el
    # paquete de PRODUCCION `src/sqp/audit/` NO queda excluido: la exclusion esta
    # anclada a la raiz (revision cruzada de Codex al cierre, 2026-09-18: un
    # `*/audit/*` sin anclar dejaba ese codigo sin escanear).
    for rel in ("src/x.py", "src/sqp/audit/html_report.py", "scripts/audit_team_names.py"):
        src = tmp_path / rel
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text('ODDS_API_KEY="ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"', encoding="utf-8")
        assert _run(tmp_path, ".claude/hooks/check-secrets.sh",
                    {"tool_input": {"file_path": str(src)}}).returncode == 2, rel
