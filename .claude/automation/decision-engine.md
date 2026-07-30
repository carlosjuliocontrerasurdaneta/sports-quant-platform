# Decision Engine

Use this order; the first matching condition wins.

1. Active incident or production outage -> `incident.md`.
2. Release/deploy/tag request -> `release.md`.
3. Failing test or reproducible incorrect behavior -> `bugfix.md`.
4. Daily prediction generation -> `quant/01-daily-prediction.md`.
5. Material pregame information update -> `quant/02-pregame-refresh.md`.
6. Completed-game settlement -> `quant/03-postgame-settlement.md`.
7. Daily quantitative performance audit -> `quant/04-daily-audit.md`.
8. Diagnosis of failed picks -> `quant/05-loss-diagnosis.md`.
9. Calibration monitoring without artifact modification -> `quant/06-calibration-monitor.md`.
10. Data or performance drift monitoring -> `quant/07-drift-monitor.md`.
11. Quantitative data-quality recovery -> `quant/08-data-quality-recovery.md`.
12. Champion-versus-challenger evaluation -> `quant/09-champion-challenger.md`.
13. Controlled recalibration request -> `quant/10-controlled-recalibration.md`.
14. Season-transition analysis -> `quant/11-season-transition.md`.
15. Quantitative production incident -> `quant/12-quant-incident.md`.
16. Weekly quantitative continuous-improvement review -> `quant/13-weekly-continuous-improvement.md`.
17. Probability/model/calibrator/feature-selection change -> `model.md`.
18. Evaluation-only or historical simulation change -> `backtest.md`.
19. Calibration-only analysis or artifact -> `calibration.md`.
20. External data source, parser, mapping, ETL -> `provider.md`.
21. Behavior-preserving structural change -> `refactor.md`.
22. New externally observable behavior -> `feature.md`.
23. Documentation-only request -> `documentation.md`.

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

## Model-selection layer

After selecting the loop, consult `.claude/automation/model-routing.json` to select the primary subagent. The model policy lives in `.claude/automation/MODEL_ROUTING.md` (single source; do not restate it here). Do not claim the main conversation model changed; model selection occurs through subagent delegation.
