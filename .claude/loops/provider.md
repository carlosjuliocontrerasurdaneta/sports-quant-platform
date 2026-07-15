# Provider Integration Loop

## Common guardrails

- Follow `.claude/CLAUDE.md`, repository rules, and data-access restrictions.
- Do not commit, push, deploy, release, or promote artifacts without explicit approval.
- Prefer the smallest reversible change.
- Maintain `.claude/automation/runtime/current-task.md`.
- Stop at the iteration budget or any human approval gate.

1. Define the provider contract and sample schema without opening full datasets.
2. Map identifiers, time zones, event states, odds formats, nullability, retries, and rate limits.
3. Build an adapter isolated from domain logic.
4. Add contract tests with fixtures and failure cases.
5. Verify idempotency, deduplication, pagination, and temporal availability.
6. Run provider tests and downstream smoke tests.
7. Do not use paid quota or production credentials without approval.
8. Finish through `/verification-gate`.
