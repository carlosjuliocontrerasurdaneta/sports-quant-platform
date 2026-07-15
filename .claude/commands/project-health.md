# /project-health

1. Run `python scripts/claude_project_health.py`.
2. If requested or needed, run:
   - `python -m ruff check src tests scripts`
   - `python -m pytest tests -q`
   - `python -m mypy src`
3. Do not open protected datasets.
4. Summarize failures by routing priority from `.claude/automation/decision-engine.md`.
5. Record only actionable findings; do not modify source code.
