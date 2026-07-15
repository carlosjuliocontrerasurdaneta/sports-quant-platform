# Decision Engine

Use this order; the first matching condition wins.

1. Active incident or production outage -> `incident.md`.
2. Release/deploy/tag request -> `release.md`.
3. Failing test or reproducible incorrect behavior -> `bugfix.md`.
4. Probability/model/calibrator/feature-selection change -> `model.md`.
5. Evaluation-only or historical simulation change -> `backtest.md`.
6. Calibration-only analysis or artifact -> `calibration.md`.
7. External data source, parser, mapping, ETL -> `provider.md`.
8. Behavior-preserving structural change -> `refactor.md`.
9. New externally observable behavior -> `feature.md`.
10. Documentation-only request -> `documentation.md`.

## Health-driven priority

When no concrete task is supplied:

1. Security/secrets or repository corruption.
2. Failing build/imports.
3. Failing tests.
4. Lint/type-check failures.
5. Data integrity or leakage risk.
6. Calibration/model regression.
7. Operational reliability.
8. Maintainability.
9. Documentation freshness.

Do not invent product requirements. If health is green and no approved backlog item exists, stop.
