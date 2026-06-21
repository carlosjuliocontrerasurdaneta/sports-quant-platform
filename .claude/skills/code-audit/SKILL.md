---
name: code-audit
description: Use this skill for targeted code audits in the Sports Quant Platform, including Python quality, pipeline safety, error handling, testing, security, and maintainability.
---

# Code Audit

## Scope

Audit code changes or selected modules without unnecessarily scanning large data folders.

## Check

- Imports and dependencies.
- Error handling.
- Type hints.
- Tests.
- Data leakage risk.
- Secret handling.
- Logging.
- Runtime risk.
- Maintainability.

## Avoid

- Opening large data files unless explicitly required.
- Inventing results.
- Claiming tests passed without command output.

## Output

1. Files inspected
2. Findings by severity
3. Evidence
4. Recommended fix
5. Validation command
