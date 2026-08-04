#!/usr/bin/env python3
"""Cheap, data-safe health scan for Claude Code routing.

This script intentionally does not read project datasets, environment files, or logs.
It returns non-zero only for structural errors; warnings are routing signals.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "pyproject.toml",
    "README.md",
    "CLAUDE.md",
    ".claude/CLAUDE.md",
    ".claude/ORCHESTRATOR.md",
    ".claude/automation/decision-engine.md",
    ".claude/automation/autonomy-policy.md",
    ".claude/commands/autopilot.md",
    "src",
    "tests",
]

FORBIDDEN_TRACKED = {".env", ".env.local", ".env.production"}


def git_output(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


_ACTIVE_TASK_STATES = {"active", "in-progress", "in_progress", "running"}
_TERMINAL_TASK_STATES = {"idle", "closed"}


def current_task_is_active(text: str) -> bool:
    """Return whether ``current-task.md`` describes work still in progress.

    The canonical lifecycle is ``idle | active | closed``. Legacy terminal
    records such as ``Status: closed (PASS)`` remain accepted. Missing or
    unknown status is treated as active so the health scan fails safe.
    """
    match = re.search(r"^Status:\s*([^\n]+)", text, flags=re.IGNORECASE | re.MULTILINE)
    if not match:
        return True
    raw = match.group(1).strip().casefold()
    state = raw.split(maxsplit=1)[0].rstrip(":")
    if state in _TERMINAL_TASK_STATES:
        return False
    if state in _ACTIVE_TASK_STATES:
        return True
    return True


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    facts: dict[str, object] = {}

    missing = [item for item in REQUIRED if not (ROOT / item).exists()]
    if missing:
        errors.append(f"Missing required paths: {', '.join(missing)}")

    tracked = set(git_output("ls-files").splitlines())
    leaked = sorted(FORBIDDEN_TRACKED.intersection(tracked))
    if leaked:
        errors.append(f"Sensitive environment files tracked by git: {', '.join(leaked)}")

    status = git_output("status", "--porcelain")
    changed = [line for line in status.splitlines() if line.strip()]
    facts["working_tree_changes"] = len(changed)
    if changed:
        warnings.append(f"Working tree has {len(changed)} changed/untracked entries")

    tests = list((ROOT / "tests").glob("test_*.py")) if (ROOT / "tests").exists() else []
    sources = list((ROOT / "src").rglob("*.py")) if (ROOT / "src").exists() else []
    facts["python_source_files"] = len(sources)
    facts["test_files"] = len(tests)
    if not tests:
        warnings.append("No test_*.py files found")

    current_task = ROOT / ".claude/automation/runtime/current-task.md"
    if current_task.exists() and current_task_is_active(
        current_task.read_text(encoding="utf-8")
    ):
        warnings.append("An autonomous task appears active; inspect current-task.md")

    report = {
        "status": "error" if errors else ("warning" if warnings else "ok"),
        "errors": errors,
        "warnings": warnings,
        "facts": facts,
        "next": (
            "Fix structural errors first"
            if errors
            else "Use warnings and the decision engine to route work"
            if warnings
            else "No static blocker detected; run tests for behavioral evidence"
        ),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
