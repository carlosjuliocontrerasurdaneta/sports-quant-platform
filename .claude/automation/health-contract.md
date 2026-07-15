# Project Health Contract

`python scripts/claude_project_health.py` performs a cheap, data-safe static health scan.

A full health assessment consists of:

1. Static scan from the script.
2. `python -m ruff check src tests scripts` when Ruff is available.
3. `python -m pytest tests -q`.
4. `python -m mypy src` when MyPy is available and relevant.
5. Domain checks selected by the active loop.

The static scan is not proof that the application is correct. It is a routing signal.
Results must be copied into `automation/runtime/current-task.md` when they affect decisions.
