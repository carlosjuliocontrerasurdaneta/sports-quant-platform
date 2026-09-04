# Sports Quant Platform

- Python package: `src/sqp`; tests: `tests`; operational scripts: `scripts`.
- Search before broad exploration. If the target file, symbol, schema, or path is already known, read it directly.
- Never load complete CSV/Parquet datasets or broad `data/`, `logs/`, `historical/`, or `exports/` trees into model context. Programmatic full-dataset scans are allowed when necessary if only targeted aggregates, schemas, samples, or findings are returned to context.
- Keep changes scoped to the requested behavior. Do not perform unrelated refactors, formatting, dependency updates, cleanup, or documentation unless requested or required by the Obsidian rule below.
- Run the narrowest relevant test first. For final validation, use `pytest -q`, `ruff check src scripts tests`, and `mypy src` when they are relevant to the files changed. Inspect non-Python operational scripts with an appropriate targeted validation rather than assuming the Python checks cover them.
- For quantitative work, verify temporal/target leakage, train-test contamination, timestamp semantics, odds freshness, calibration, numerical validity, and backtest validity against the project's canonical implementation/configuration. Never invent thresholds, cutoffs, or formulas that are not defined by the project.
- Treat the information/prediction cutoff as an explicit invariant when reviewing historical features, odds, calibration, or backtests. Distinguish event time from the time information became available when the project stores both.
- Betting output must distinguish estimated probability, implied probability, edge, observed hit rate, expected ROI, and realized ROI; never promise profit. Use the project's canonical definitions for these metrics; if a definition is not discoverable, state that it is not verifiable instead of inventing one.
- Relevant implementation changes must update the same-session Obsidian log/topic/task notes when the configured vault and note conventions are available. Do not open the repository root as an Obsidian vault. If the vault location or required note target cannot be determined safely, report the limitation instead of guessing.
- Daily order is settlement before generation: `SETTLE_ALL.bat` then `RUN_DIARIO_ALL.bat`. Treat settlement as a prerequisite only if the scripts/configuration establish that contract; if settlement fails, do not infer that generation is safe to continue without verifying the workflow.
- GOVERNING PRINCIPLE for model choice (operator order, restated 2026-09-01, carved in stone): always use the superior model for tasks demanding the highest level of reasoning, and delegate the rest according to their complexity and to where each model performs best. It governs: when a specific rule conflicts with it, the principle wins and the rule gets fixed. Operational split: `claude-opus-5` is the default and the starting point; Sonnet handles normal engineering work and Haiku bounded lookup/summarization; `claude-fable-5-1` is the ceiling (note the hyphens: `claude-fable-5.1` is not a valid ID, and `claude-fable-5` is a different, now-legacy model), reserved for maximum-reasoning tasks and the destination of the escalation trigger — starting point and ceiling are deliberately separate. Escalation is decided by observable task CLASS, never by self-assessed difficulty: irreversible work, risk/model/strategy/threshold/gate parameters, publishable figures, contradicting a recorded decision, or changing a persisted artifact's contract. When in doubt between two rungs, go up, and record it in `current-task.md`. No model rung substitutes for a measurement: if the question is empirically resolvable with stored data, measure first. Full policy and its locks: `.claude/automation/MODEL_ROUTING.md`. Editing `CLAUDE.md` does not change the active model of a running session.
- Do not spawn subagents or agent-team teammates by default. Delegate only when the task contains independent workstreams and parallel execution materially improves coverage, verification, or latency.
- Keep command output small: targeted tests/diffs and at most 100 log lines unless additional evidence is necessary.
- During a `full-audit`, the skill's stricter read-only and authorization rules override the general validation guidance in this file for phases 0–3.

# Compact instructions

Preserve:
- the current objective and acceptance criteria;
- active user constraints, prohibitions, approvals, and authorized scope;
- decisions and quantitative assumptions still in force;
- changed files and relevant diffs;
- unresolved errors and known limitations;
- test/validation commands and results;
- evidence needed to continue safely;
- the next action.

Discard verbose tool output, repeated explanations, stale exploration, superseded hypotheses, and information already recoverable from `CLAUDE.md` or repository files.
