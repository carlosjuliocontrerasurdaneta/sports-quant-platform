# Backtest Loop

## Common guardrails

- Follow `.claude/CLAUDE.md`, repository rules, and data-access restrictions.
- Do not commit, push, deploy, release, or promote artifacts without explicit approval.
- Prefer the smallest reversible change.
- Maintain `.claude/automation/runtime/current-task.md`.
- Stop at the iteration budget or any human approval gate.

1. Define decision timestamp, information set, market availability, odds source, settlement rules and baseline.
2. Use temporal walk-forward or another justified out-of-sample design.
3. Audit leakage, survivorship, duplicated events, stale odds, selection bias and look-ahead.
4. Include realistic costs, limits, voids, missing prices and execution assumptions.
5. Report sample size, ROI/yield, drawdown, hit rate, CLV and calibration metrics where applicable.
6. Segment results and disclose uncertainty; do not optimize repeatedly on the final holdout.
7. Finish through `/verification-gate`.
