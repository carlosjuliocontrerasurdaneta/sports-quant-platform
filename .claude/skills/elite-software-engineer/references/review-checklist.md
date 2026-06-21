# Code Review Checklist

Use this for PR review, self-review, and post-implementation checks.

## Correctness

- Handles happy path.
- Handles edge cases.
- Handles invalid input.
- Preserves contracts.
- Does not introduce off-by-one, null/undefined, timezone, encoding, or precision bugs.

## Maintainability

- Names are clear.
- Responsibilities are cohesive.
- No unnecessary abstraction.
- No duplicated business logic.
- Consistent with project conventions.

## Reliability

- Errors are handled intentionally.
- Retries/timeouts are appropriate.
- Resource cleanup is correct.
- Idempotency considered where relevant.

## Concurrency

- No shared mutable state hazards.
- No race-prone read-modify-write.
- Locks/transactions used where needed.

## Review output

```markdown
## Review Findings

### Critical
### High
### Medium
### Low
### Nitpicks
### Approval status
```
