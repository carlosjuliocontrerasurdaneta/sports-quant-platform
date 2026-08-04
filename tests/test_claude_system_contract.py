from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _load_health_module():
    path = ROOT / "scripts/claude_project_health.py"
    spec = importlib.util.spec_from_file_location("claude_project_health", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_root_claude_markdown_is_plain_utf8_without_nul_bytes():
    raw = (ROOT / "CLAUDE.md").read_bytes()
    assert b"\x00" not in raw
    raw.decode("utf-8")


def test_health_recognizes_active_and_terminal_task_states():
    health = _load_health_module()
    assert health.current_task_is_active("Status: active\nResult: N/A\n")
    assert health.current_task_is_active("Status: in-progress\n")
    for terminal in ("idle", "closed"):
        assert not health.current_task_is_active(f"Status: {terminal}\n")
    assert not health.current_task_is_active("Status: closed (PASS)\n")


def test_default_configuration_requires_human_calibrator_promotion():
    cfg = yaml.safe_load((ROOT / "configs/default.yaml").read_text(encoding="utf-8"))
    assert cfg["calibration"]["auto_promote"] is False


def test_quant_state_contract_has_no_loop_specific_done_contradiction():
    states = (ROOT / ".claude/loops/quant/STATES.md").read_text(encoding="utf-8")
    assert "solo un loop" not in states
    assert "Un loop periódico" not in states
    assert "Precedencia" in states


def test_orchestrator_defines_supporting_loop_handoffs():
    orchestrator = (ROOT / ".claude/ORCHESTRATOR.md").read_text(encoding="utf-8")
    assert "Supporting loops and handoffs" in orchestrator
    normalized = " ".join(orchestrator.split())
    assert "must not replace the task header" in normalized


def test_daily_audit_does_not_require_stake_for_clv():
    loop = (ROOT / ".claude/loops/quant/04-daily-audit.md").read_text(
        encoding="utf-8"
    )
    assert "CLV solo es válido" not in loop
    normalized = " ".join(loop.split())
    assert "CLV requiere una cuota de entrada" in normalized


def test_all_general_loops_finish_through_verification_gate():
    missing = [
        path.name
        for path in (ROOT / ".claude/loops").glob("*.md")
        if "/verification-gate" not in path.read_text(encoding="utf-8")
    ]
    assert missing == []


def test_quant_loop_common_spelling_is_consistent():
    bad = [
        p.name
        for p in (ROOT / ".claude/loops/quant").glob("*.md")
        if " segun " in p.read_text(encoding="utf-8")
    ]
    assert bad == []
