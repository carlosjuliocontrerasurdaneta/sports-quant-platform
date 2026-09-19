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
ni autoriza delegación, escrituras o ejecución de la skill.

| Ruta | Skill | Agente principal | Apoyo |
|---|---|---|---|
| `full-audit` | `full-audit` | principal-orchestrator | repository-cartographer, backend-architect, sports-quant-auditor, qa-engineer, security-reviewer |
| `quant-incident` | `quant-incident` | principal-orchestrator | sports-quant-auditor, leakage-detector, qa-engineer |
| `incident` | `incident` | principal-orchestrator | qa-engineer, security-reviewer, devops-engineer |
| `quant-daily-prediction` | `daily-operations` | sports-quant-auditor | provider-integrator, qa-engineer |
| `quant-pregame-refresh` | `pregame-refresh` | line-movement-analyst | odds-market-auditor, sports-quant-auditor |
| `quant-settlement` | `daily-operations` | sports-quant-auditor | data-engineer, qa-engineer |
| `quant-daily-audit` | `daily-audit` | sports-quant-auditor | calibration-auditor, backtest-reviewer |
| `quant-loss-diagnosis` | `loss-diagnosis` | sports-quant-auditor | leakage-detector, odds-market-auditor |
| `quant-calibration-monitor` | `review-calibration` | calibration-auditor | backtest-reviewer, risk-manager |
| `quant-drift-monitor` | `drift-monitor` | ml-engineer | data-engineer, sports-quant-auditor |
| `quant-data-recovery` | `data-quality-recovery` | data-engineer | provider-integrator, qa-engineer |
| `quant-champion-challenger` | `champion-challenger` | backtest-reviewer | calibration-auditor, leakage-detector, risk-manager |
| `quant-controlled-recalibration` | `controlled-recalibration` | calibration-auditor | backtest-reviewer, risk-manager |
| `quant-season-transition` | `season-transition` | sports-quant-auditor | feature-engineer, ml-engineer |
| `quant-weekly-improvement` | `weekly-improvement` | principal-orchestrator | sports-quant-auditor, calibration-auditor, ml-engineer |
| `calibration-only` | `review-calibration` | calibration-auditor | backtest-reviewer, risk-manager |
| `modeling` | `model-change` | ml-engineer | feature-engineer, leakage-detector, calibration-auditor, backtest-reviewer, risk-manager |
| `backtest` | — | backtest-reviewer | leakage-detector, sports-quant-auditor |
| `architecture` | — | backend-architect | repository-cartographer, python-engineer, qa-engineer |
| `provider` | `provider-integration` | provider-integrator | data-engineer, leakage-detector, qa-engineer |
| `bugfix` | `bugfix` | python-engineer | repository-cartographer, qa-engineer |
| `security` | — | security-reviewer | python-engineer, qa-engineer |
| `release` | — | devops-engineer | qa-engineer, security-reviewer |
| `documentation` | `documentation` | documentation-writer |  |
| `default` | `feature-engineering` | python-engineer |  |
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
