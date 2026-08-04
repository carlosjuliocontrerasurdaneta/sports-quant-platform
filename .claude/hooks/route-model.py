#!/usr/bin/env python3
"""Classify a Claude Code prompt and inject a subagent routing recommendation."""
from __future__ import annotations
import json
from pathlib import Path
import sys

def classify(prompt: str, config: dict) -> dict:
    normalized = prompt.casefold()
    routes = sorted(
        config.get("routes", []),
        key=lambda route: route.get("priority", 0),
        reverse=True,
    )
    for route in routes:
        if any(term.casefold() in normalized for term in route.get("keywords", [])):
            return route
    return config["default"] | {"id": "default", "support_agents": []}


def find_config_path(cwd: Path) -> Path:
    """Find model-routing.json from the project root or a nested cwd."""
    start = cwd.resolve()
    for candidate in (start, *start.parents):
        path = candidate / ".claude" / "automation" / "model-routing.json"
        if path.is_file():
            return path
    raise FileNotFoundError(
        f".claude/automation/model-routing.json not found from {start}"
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        project = Path(payload.get("cwd") or ".")
        cfg_path = find_config_path(project)
        config = json.loads(cfg_path.read_text(encoding="utf-8"))
        route = classify(str(payload.get("prompt", "")), config)
        support = ", ".join(route.get("support_agents", [])) or "ninguno"
        context = (
            "Clasificación automática SQP: "
            f"ruta={route['id']}; loop=.claude/loops/{route['loop']}; "
            f"subagente principal={route['primary_agent']} ({route['model']}); "
            f"apoyo={support}. La selección es una recomendación determinista: "
            "confirma la semántica de la solicitud y delega al subagente indicado salvo conflicto con reglas superiores."
        )
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": context}}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"SQP model router skipped: {exc}", file=sys.stderr)
        return 0

if __name__ == "__main__":
    raise SystemExit(main())
