# Bug-fix Loop

## Common guardrails

- Follow `.claude/CLAUDE.md`, repository rules, and data-access restrictions.
- Do not commit, push, deploy, release, or promote artifacts without explicit approval.
- Prefer the smallest reversible change.
- Maintain `.claude/automation/runtime/current-task.md`.
- Stop at the iteration budget or any human approval gate.

1. Reproduce the defect with a test or deterministic command.
2. Trace the root cause; do not patch symptoms.
3. Record the hypothesis and affected invariant.
4. Apply the smallest correction.
5. Prove the regression test fails before the correction and passes after. If
   that cannot be demonstrated safely, record the concrete reason and provide
   equivalent deterministic evidence.
6. Run adjacent regression tests.
7. Check whether historical outputs, settlement, odds, or probabilities are affected.
8. Finish through `/verification-gate`.
