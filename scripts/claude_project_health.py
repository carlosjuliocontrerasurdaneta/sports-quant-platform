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


_RESULTS_REQUIRING_EVIDENCE = {"pass", "done"}

# STATES.md, "Registro de evidencia": un resultado positivo exige (3) comandos
# ejecutados con sus codigos de salida y (4) rutas de los artefactos. Se piden
# como secciones nombradas porque es lo unico verificable sin interpretar prosa.
_EVIDENCE_SECTIONS = (
    ("comandos ejecutados", r"^#+\s*Comandos ejecutados"),
    ("artefactos producidos", r"^#+\s*Artefactos"),
)


def pass_result_missing_evidence(text: str) -> list[str]:
    """Secciones de evidencia que faltan en un ``current-task.md`` cuyo
    ``Result`` es PASS o DONE. Lista vacia si cumple, o si el resultado es
    DEGRADED/BLOCKED (donde la falta de evidencia es justamente lo que se
    declara) o no hay resultado declarado.

    Existe porque el 2026-08-04 la tarea cerro en ``Result: PASS`` con la suite
    en 5 failed y ruff/mypy sin ejecutar. STATES.md ya lo prohibia; nada lo
    hacia cumplir (auditoria 2026-08-04, B-1).
    """
    match = re.search(r"^Result:\s*([^\n]+)", text,
                      flags=re.IGNORECASE | re.MULTILINE)
    if not match:
        return []
    result = match.group(1).strip().casefold().split(maxsplit=1)[0].rstrip(":")
    if result not in _RESULTS_REQUIRING_EVIDENCE:
        return []
    return [name for name, pattern in _EVIDENCE_SECTIONS
            if not re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)]


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
    if current_task.exists():
        task_text = current_task.read_text(encoding="utf-8")
        if current_task_is_active(task_text):
            warnings.append(
                "An autonomous task appears active; inspect current-task.md")
        missing = pass_result_missing_evidence(task_text)
        if missing:
            # Un PASS sin evidencia es peor que un BLOCKED honesto: se propaga
            # como estado bueno a la bitacora y a la siguiente sesion.
            errors.append(
                "current-task.md declares a positive Result without the evidence "
                f"STATES.md requires (missing: {', '.join(missing)})")

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
