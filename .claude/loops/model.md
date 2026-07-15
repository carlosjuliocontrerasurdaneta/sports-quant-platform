# Model-change Loop

## Common guardrails

- Follow `.claude/CLAUDE.md`, repository rules, and data-access restrictions.
- Do not commit, push, deploy, release, or promote artifacts without explicit approval.
- Prefer the smallest reversible change.
- Maintain `.claude/automation/runtime/current-task.md`.
- Stop at the iteration budget or any human approval gate.

1. State the statistical hypothesis, target, decision use, and baseline.
2. Verify temporal split, feature availability time, and leakage risks.
3. Define primary and guardrail metrics before implementation.
4. Implement behind a reversible configuration or artifact boundary.
5. Run focused unit tests and deterministic evaluation.
6. Compare against baseline: Brier, Log Loss, ECE, discrimination, coverage, ROI/yield and CLV where applicable.
7. Segment results by sport, market, season/time, probability band, and sample size where meaningful.
8. Reject promotion if gains are not robust, calibration worsens materially, or leakage cannot be ruled out.
9. Require human approval before promoting any model/calibrator.
10. Finish through `/verification-gate`.
