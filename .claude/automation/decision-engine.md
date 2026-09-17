# Decision Engine

El catálogo canónico es `model-routing.json`; `route_classifier.py::classify`
aplica sus keywords en prioridad descendente y cae al default cuando ninguna
coincide. Consultarlo bajo demanda mediante `/route-task`, no como hook automático.
La clasificación textual es orientativa: respetar el alcance explícito del usuario
y los triggers específicos de la skill. Registrar cualquier override y su motivo;
una coincidencia de keyword nunca autoriza modificar ni ampliar el encargo.

<!-- generated: routes -->
Catálogo derivado de `.claude/automation/model-routing.json`. La política de
modelos está en `MODEL_ROUTING.md`; esta tabla no cambia el modelo activo
ni autoriza delegación, escrituras o ejecución del loop.

| Ruta | Loop | Agente principal | Apoyo |
|---|---|---|---|
| `full-audit` | `audit.md` | principal-orchestrator | repository-cartographer, backend-architect, sports-quant-auditor, qa-engineer, security-reviewer |
| `quant-incident` | `quant/12-quant-incident.md` | principal-orchestrator | sports-quant-auditor, leakage-detector, qa-engineer |
| `incident` | `incident.md` | principal-orchestrator | qa-engineer, security-reviewer, devops-engineer |
| `quant-daily-prediction` | `quant/01-daily-prediction.md` | sports-quant-auditor | provider-integrator, qa-engineer |
| `quant-pregame-refresh` | `quant/02-pregame-refresh.md` | line-movement-analyst | odds-market-auditor, sports-quant-auditor |
| `quant-settlement` | `quant/03-postgame-settlement.md` | sports-quant-auditor | data-engineer, qa-engineer |
| `quant-daily-audit` | `quant/04-daily-audit.md` | sports-quant-auditor | calibration-auditor, backtest-reviewer |
| `quant-loss-diagnosis` | `quant/05-loss-diagnosis.md` | sports-quant-auditor | leakage-detector, odds-market-auditor |
| `quant-calibration-monitor` | `quant/06-calibration-monitor.md` | calibration-auditor | backtest-reviewer, risk-manager |
| `quant-drift-monitor` | `quant/07-drift-monitor.md` | ml-engineer | data-engineer, sports-quant-auditor |
| `quant-data-recovery` | `quant/08-data-quality-recovery.md` | data-engineer | provider-integrator, qa-engineer |
| `quant-champion-challenger` | `quant/09-champion-challenger.md` | backtest-reviewer | calibration-auditor, leakage-detector, risk-manager |
| `quant-controlled-recalibration` | `quant/10-controlled-recalibration.md` | calibration-auditor | backtest-reviewer, risk-manager |
| `quant-season-transition` | `quant/11-season-transition.md` | sports-quant-auditor | feature-engineer, ml-engineer |
| `quant-weekly-improvement` | `quant/13-weekly-continuous-improvement.md` | principal-orchestrator | sports-quant-auditor, calibration-auditor, ml-engineer |
| `calibration-only` | `calibration.md` | calibration-auditor | backtest-reviewer, risk-manager |
| `modeling` | `model.md` | ml-engineer | feature-engineer, leakage-detector, calibration-auditor, backtest-reviewer, risk-manager |
| `backtest` | `backtest.md` | backtest-reviewer | leakage-detector, sports-quant-auditor |
| `architecture` | `refactor.md` | backend-architect | repository-cartographer, python-engineer, qa-engineer |
| `provider` | `provider.md` | provider-integrator | data-engineer, leakage-detector, qa-engineer |
| `bugfix` | `bugfix.md` | python-engineer | repository-cartographer, qa-engineer |
| `security` | `refactor.md` | security-reviewer | python-engineer, qa-engineer |
| `release` | `release.md` | devops-engineer | qa-engineer, security-reviewer |
| `documentation` | `documentation.md` | documentation-writer |  |
| `default` | `feature.md` | python-engineer |  |
<!-- endgenerated: routes -->

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
