# Release Loop

## Common guardrails

- Follow `.claude/CLAUDE.md`, repository rules, and data-access restrictions.
- Do not commit, push, deploy, release, or promote artifacts without explicit approval.
- Prefer the smallest reversible change.
- Maintain `.claude/automation/runtime/current-task.md`.
- Stop at the iteration budget or any human approval gate.

1. Freeze scope and enumerate included changes.
2. Run health check, lint, tests and required statistical gates.
3. Review configuration precedence, migrations, secrets, rollback and operational runbooks.
4. Complete `.claude/checklists/pre-release.md`.
5. Produce release notes and unresolved-risk list.
6. Stop for human approval before commit/tag/release/deployment.
