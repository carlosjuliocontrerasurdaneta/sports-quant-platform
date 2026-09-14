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
