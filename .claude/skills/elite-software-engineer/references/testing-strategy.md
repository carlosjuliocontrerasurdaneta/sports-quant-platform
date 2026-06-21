# Testing Strategy

Use when creating or reviewing tests.

## Test layers

### Unit tests
Use for pure logic, validators, mappers, policies, and edge cases.

### Integration tests
Use when behavior crosses boundaries: DB, filesystem, network clients, queues, framework routing.

### E2E tests
Use for critical user flows and contract-level behavior.

### Regression tests
Add for every bug fix.

## Test quality rules

- Test behavior, not implementation details.
- Use meaningful names.
- Keep fixtures minimal.
- Cover edge cases and failure modes.
- Avoid sleeps and timing-dependent tests.
- Prefer deterministic fakes over brittle mocks.
- Do not weaken tests merely to pass.

## Output

```markdown
## Test Plan

Unit:
Integration:
E2E:
Edge cases:
Failure cases:
Regression coverage:
Commands to run:
```
