"""AUD-006 (ronda audit-2026-10-18): escaneo de secretos de los ficheros
rastreados, la capa del CI previa a publicar en un repositorio publico."""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_HEX = "a1b2c3d4" * 4


def _script():
    spec = importlib.util.spec_from_file_location(
        "scan_tracked_secrets", ROOT / "scripts" / "scan_tracked_secrets.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _repo(tmp_path: Path, ficheros: dict[str, str]) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, capture_output=True)
    for rel, contenido in ficheros.items():
        ruta = tmp_path / rel
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(contenido, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    return tmp_path


def test_tracked_literal_is_found_also_under_audit(tmp_path):
    root = _repo(tmp_path, {
        "audit/latest/claude/EVIDENCE.json": f'{{"x": "ODDS_API_KEY={_HEX}"}}',
        "src/ok.py": "x = 1\n",
    })
    assert _script().hallazgos(root) == [("audit/latest/claude/EVIDENCE.json", [1])]


def test_untracked_data_and_detector_fixtures_are_skipped(tmp_path):
    root = _repo(tmp_path, {
        "data/odds/x.csv": f"ODDS_API_KEY={_HEX}\n",
        "tests/test_audit_hooks.py": f'ODDS_API_KEY="{_HEX}"\n',
    })
    (root / "suelto.py").write_text(f'ODDS_API_KEY="{_HEX}"\n', encoding="utf-8")
    assert _script().hallazgos(root) == []


def test_current_repository_is_clean():
    assert _script().hallazgos(ROOT) == []


def test_hook_and_ci_scanner_exempt_the_same_fixture_files():
    """El hook PostToolUse y el escaner del CI no pueden divergir en sus
    exenciones (revision Fable 2026-10-18)."""
    hook = (ROOT / ".claude" / "hooks" / "check-secrets.sh").read_text(encoding="utf-8")
    for rel in _script()._FIXTURES_DEL_DETECTOR:
        assert f"{rel}) continue" in hook, rel
