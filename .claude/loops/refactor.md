# Refactor Loop

## Common guardrails

- Follow `.claude/CLAUDE.md`, repository rules, and data-access restrictions.
- Do not commit, push, deploy, release, or promote artifacts without explicit approval.
- Prefer the smallest reversible change.
- Maintain `.claude/automation/runtime/current-task.md`.
- Stop at the iteration budget or any human approval gate.

1. State the maintainability problem and preserved behavior.
2. Capture characterization tests if behavior lacks coverage.
3. Refactor in small mechanically verifiable steps.
4. Run focused tests after each step.
5. Reject abstractions without at least two concrete consumers or a clear boundary need.
6. Compare complexity, coupling, and public API before and after.
7. Finish through `/verification-gate`.
