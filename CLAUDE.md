# Sports Quant Platform

- Python package: `src/sqp`; tests: `tests`; operational scripts: `scripts`.
- Search before reading. Open only relevant files, symbols, schemas, or short samples.
- Never read complete CSV/Parquet files or broad `data/`, `logs/`, `historical/`, or `exports/` trees.
- Keep changes scoped. Do not generate documentation unless requested or required by the Obsidian rule below.
- Run the narrowest relevant test first; use `pytest -q`, `ruff check src scripts tests`, and `mypy src` for final validation when appropriate.
- For quantitative work, check temporal/target leakage, train-test contamination, timestamps, odds freshness, calibration, and backtest validity.
- Betting output must distinguish estimated probability, implied probability, edge, observed hit rate, expected ROI, and realized ROI; never promise profit.
- Relevant changes must update the same-session Obsidian log/topic/task notes. Do not open the repository root as an Obsidian vault.
- Daily order is settlement before generation: `SETTLE_ALL.bat` then `RUN_DIARIO_ALL.bat`.
- Prefer Sonnet for normal work. Use Opus only for genuinely complex architecture, critical incidents, or exhaustive quantitative audits; use Haiku for bounded lookup/summarization and use claude-opus-5 when maximum reasoning is needed.
- Do not spawn support agents by default. Delegate only when independent parallel work materially helps.
- Keep command output small: targeted tests/diffs and at most 100 log lines unless more evidence is necessary.

# Compact instructions

Preserve only decisions, changed files, unresolved errors, test results, quantitative assumptions, and the next action. Discard verbose tool output, repeated explanations, and stale exploration.
