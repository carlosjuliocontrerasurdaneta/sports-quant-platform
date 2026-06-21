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
