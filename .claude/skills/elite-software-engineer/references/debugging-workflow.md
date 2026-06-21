# Debugging Workflow

Use this for bugs, failing tests, incidents, regressions, and unexpected behavior.

## RCA process

1. Reproduce or inspect the failure.
2. Capture the exact symptom.
3. Form hypotheses.
4. Gather evidence from code, logs, tests, and recent changes.
5. Identify root cause.
6. Implement the smallest fix.
7. Add regression coverage.
8. Validate.

## Debugging report

```markdown
## Debugging Report

Symptom:
Scope:
Hypotheses:
Evidence:
Root cause:
Fix:
Regression test:
Validation:
```

## Rules

Do not patch symptoms without identifying the cause.

Do not delete tests to make a suite pass.

Do not weaken assertions unless the expected behavior was wrong and that is justified.
