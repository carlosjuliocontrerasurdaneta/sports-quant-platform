---
name: feature-engineering
description: Use this skill to design, audit, and improve feature engineering for the Sports Quant Platform while preventing data leakage and preserving temporal correctness.
---

# Feature Engineering

## Purpose

Design and audit features for MLB, NBA, NFL, and NHL probabilistic models.

## Rules

- Use only information available before the event.
- Do not use postgame fields in pregame features.
- Rolling features must use past games only.
- Every feature must define timestamp availability.
- Missing values must be handled explicitly.
- Synthetic examples must be labeled as synthetic.

## Output

1. Feature name
2. Sport and market
3. Source fields
4. Calculation
5. Timestamp requirement
6. Leakage risk
7. Validation tests

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
