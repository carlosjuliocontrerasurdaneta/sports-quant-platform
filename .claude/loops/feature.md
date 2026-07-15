# Feature Loop

## Common guardrails

- Follow `.claude/CLAUDE.md`, repository rules, and data-access restrictions.
- Do not commit, push, deploy, release, or promote artifacts without explicit approval.
- Prefer the smallest reversible change.
- Maintain `.claude/automation/runtime/current-task.md`.
- Stop at the iteration budget or any human approval gate.

1. Convert the request into measurable acceptance criteria.
2. Map affected modules and public contracts.
3. Write or identify a failing test for the new behavior.
4. Implement the smallest vertical slice.
5. Run focused tests, then the relevant regression suite.
6. Review architecture, compatibility, observability, and documentation.
7. Repeat only for unmet acceptance criteria.
8. Finish through `/verification-gate`.
