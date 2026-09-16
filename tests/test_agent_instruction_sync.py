"""Validate generation, compatibility and no-write checks in isolated trees."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import shutil

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("instruction_sync", ROOT / "scripts/sync_agent_instructions.py")
assert SPEC and SPEC.loader
SYNC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SYNC)


@pytest.fixture
def tree(tmp_path):
    shutil.copytree(ROOT / ".claude/loops", tmp_path / ".claude/loops")
    for name in ("audit-workflow.md", "model-routing.json", "decision-engine.md", "loop-guardrails.md"):
        dest = tmp_path / ".claude/automation" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / ".claude/automation" / name, dest)
    shutil.copyfile(ROOT / ".claude/ORCHESTRATOR.md", tmp_path / ".claude/ORCHESTRATOR.md")
    shutil.copytree(ROOT / "audits/prompts", tmp_path / "audits/prompts")
    for name in ("audit/latest/FINDINGS.md", "audit/old/STATUS.md", "audits/consolidated/latest.md"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("AUD-MED-001: historical evidence\n", encoding="utf-8")
    return tmp_path


def snapshot(root):
    return {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_repository_generated_instructions_are_current():
    assert SYNC.sync(ROOT) == []


def test_shared_rule_propagates_and_check_is_read_only(tree):
    source = tree / SYNC.WORKFLOW
    source.write_text(source.read_text(encoding="utf-8").replace(
        "<!-- section: common -->", "<!-- section: common -->\nShared fixture rule."), encoding="utf-8")
    before = snapshot(tree)
    expected = {Path("audits/prompts") / name for name in SYNC.PROMPTS}
    assert set(SYNC.sync(tree)) == expected
    assert snapshot(tree) == before
    assert set(SYNC.sync(tree, write=True)) == expected
    after = snapshot(tree)
    assert {p for p in before if before[p] != after[p]} == expected
    assert SYNC.sync(tree, write=True) == []
    assert snapshot(tree) == after


def test_phase_change_does_not_rewrite_other_phases(tree):
    source = tree / SYNC.WORKFLOW
    source.write_text(source.read_text(encoding="utf-8").replace(
        "<!-- section: verify -->", "<!-- section: verify -->\nVerification fixture rule."), encoding="utf-8")
    assert SYNC.sync(tree) == [Path("audits/prompts/verificar-remediacion.md")]


def test_invalid_route_prevents_partial_writes(tree):
    prompt = tree / "audits/prompts/corregir-auditoria.md"
    prompt.write_text("stale", encoding="utf-8")
    config = tree / ".claude/automation/model-routing.json"
    data = json.loads(config.read_text(encoding="utf-8"))
    data["routes"][0]["loop"] = "does-not-exist.md"
    config.write_text(json.dumps(data), encoding="utf-8")
    before = snapshot(tree)
    with pytest.raises(ValueError, match="Unknown loop"):
        SYNC.sync(tree, write=True)
    assert snapshot(tree) == before


def test_routing_change_updates_all_three_views(tree):
    config = tree / ".claude/automation/model-routing.json"
    data = json.loads(config.read_text(encoding="utf-8"))
    route = next(r for r in data["routes"] if r["loop"].startswith("quant/"))
    route["id"] = "fixture-quant-route"
    config.write_text(json.dumps(data), encoding="utf-8")
    assert set(SYNC.sync(tree, write=True)) == {
        Path(".claude/ORCHESTRATOR.md"),
        Path(".claude/automation/decision-engine.md"),
        Path(".claude/loops/quant/00-quant-operations-router.md"),
    }
    assert SYNC.sync(tree) == []


def test_guardrails_remain_self_contained_in_each_general_loop(tree):
    source = tree / ".claude/automation/loop-guardrails.md"
    source.write_text(source.read_text(encoding="utf-8").replace(
        "<!-- section: general -->", "<!-- section: general -->\n- Fixture safety rule."), encoding="utf-8")
    expected = {p.relative_to(tree) for p in (tree / ".claude/loops").glob("*.md")}
    assert set(SYNC.sync(tree, write=True)) == expected
    for path in expected:
        assert "- Fixture safety rule." in (tree / path).read_text(encoding="utf-8")


def test_skill_metadata_and_relative_links_are_valid():
    for path in (ROOT / ".claude/skills").glob("*/SKILL.md"):
        text = path.read_text(encoding="utf-8")
        metadata = yaml.safe_load(text.split("---", 2)[1])
        assert metadata["name"] == path.parent.name
        assert isinstance(metadata["description"], str)
    for folder in ("full-audit", "audit-remediation", "code-audit", "mlb-pipeline"):
        for path in (ROOT / ".claude/skills" / folder).rglob("*.md"):
            for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                if "://" not in target and not target.startswith("#"):
                    assert (path.parent / target.split("#")[0]).exists(), (path, target)


@pytest.mark.parametrize("source", [
    "<!-- section: x --> missing end",
    "<!-- section: x --><!-- section: y --><!-- endsection -->",
    "<!-- section: x --><!-- endsection --><!-- section: x --><!-- endsection -->",
])
def test_malformed_source_sections_are_rejected(source):
    with pytest.raises(ValueError):
        SYNC.section(source, "x")
