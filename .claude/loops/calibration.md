# Calibration Loop

## Common guardrails

- Follow `.claude/CLAUDE.md`, repository rules, and data-access restrictions.
- Do not commit, push, deploy, release, or promote artifacts without explicit approval.
- Prefer the smallest reversible change.
- Maintain `.claude/automation/runtime/current-task.md`.
- Stop at the iteration budget or any human approval gate.

1. Freeze the evaluation period, source probabilities, baseline, and sample inclusion rules.
2. Check leakage and ensure calibration data predates evaluated outcomes correctly.
3. Evaluate reliability curves/bins, ECE, Brier and Log Loss with sample counts.
4. Compare global and segmented behavior; flag sparse bins.
5. Test stability across time and relevant leagues/markets.
6. Record candidate parameters and exact reproducibility inputs.
7. Never promote calibration artifacts without human approval.
8. Finish through `/verification-gate`.
