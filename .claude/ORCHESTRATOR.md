# SQP Autonomous Development Orchestrator

## Purpose

Route every engineering request through a deterministic, evidence-based workflow.
This file complements `CLAUDE.md`; permanent repository rules always have precedence.

## Mandatory startup

1. Read `.claude/CLAUDE.md`.
2. Run `/memoria-cargar`.
3. Run `/project-health`.
4. Classify the request using `.claude/automation/decision-engine.md`.
5. Select exactly one primary skill (`.claude/skills/`, column `Skill` of the routing table below); its body is the operating loop.
6. Create or update `.claude/automation/runtime/current-task.md`.
7. Work in bounded iterations and stop on any guardrail.

## Routing table

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

## Quantitative operations

For prediction generation, pregame updates, settlement, daily auditing, loss diagnosis, calibration monitoring, drift monitoring, data-quality recovery, champion-challenger evaluation, controlled recalibration, season transitions, quantitative incidents, and weekly quantitative reviews:

1. Read `.claude/loops/quant/00-quant-operations-router.md`.
2. Select exactly one primary quantitative skill; its body is the loop.
3. Record the selected skill in `.claude/automation/runtime/current-task.md`.
4. Follow all repository guardrails and human approval gates.
5. Never promote a model or calibration artifact automatically.

## Supporting loops and handoffs

Exactly one loop remains the primary owner of a task. When that loop needs work
from another loop:

1. Record the supporting loop, scope, inputs and expected evidence under a
   `Supporting loops` subsection in `current-task.md`.
2. The supporting loop must append its evidence under that subsection and must
   not replace the task header, primary loop, lifecycle status or acceptance
   criteria.
3. The primary loop aggregates supporting results using the quantitative state
   precedence when applicable: required `BLOCKED` evidence blocks the parent;
   otherwise `DEGRADED` propagates and `PASS` permits continuation.
4. Only the primary loop runs the final `/verification-gate`, updates the final
   task result and closes the task.
5. If ownership must change rather than remain supportive, close the current
   task and create an explicit handoff with the next loop and acceptance
   criteria; never silently overwrite `current-task.md`.

## Iteration contract

Each iteration must produce:

- hypothesis or concrete task;
- smallest safe change;
- validation command and result;
- risk assessment;
- next decision.

Default iteration budget: 8. A user may explicitly raise it. Never silently loop without a bound.

## Evidence gates

A task is not complete because code was written. Completion requires:

- acceptance criteria mapped to evidence;
- relevant tests passing;
- no known regression hidden or ignored;
- statistical gates when probabilities, selection, staking, or evaluation change;
- Obsidian update when required by the ROOT `CLAUDE.md` (not `.claude/CLAUDE.md`, which does not mention Obsidian);
- explicit list of unverified items.

## Human approval gates

Stop and request approval before:

- commit, push, merge, tag, release, or deployment;
- destructive migrations or deletion;
- production configuration changes;
- paid/external API consumption beyond an existing approved test;
- changes to staking/risk limits;
- disabling `shadow_mode`, or moving any stake from 0 to a real amount;
- changing `pick_mode`, `accuracy_threshold` or `bankroll`, or any threshold that
  decides which picks are emitted, without out-of-sample evidence;
- promotion of a model or calibration artifact;
- handling real credentials or secrets.

## Failure policy

After two failed attempts with the same hypothesis, stop repeating it. Reassess the root cause.
After three materially different failed attempts, create a blocker report in
`.claude/automation/runtime/current-task.md` and stop.

## Finalization

Run `/verification-gate`, then `/memoria-guardar`.
Report changed files, commands executed, outcomes, residual risks, and recommended next action.

## Model routing

Before delegation, use `.claude/automation/model-routing.json`, consulted **on demand** via `/route-task` (classifier: `.claude/automation/route_classifier.py`). There is no automatic injection: the `UserPromptSubmit` hook was retired on 2026-09-01 because it had never been wired and, even wired, only injected advisory text. The model policy itself lives in `.claude/automation/MODEL_ROUTING.md` (single source). Delegate to the named primary subagent when its specialization matches the request. **The execution model is set by the `model` parameter of the `Agent` tool, which takes precedence over the subagent's frontmatter — see `## REGLA DE DESPACHO` in the policy.** Permanent rules, safety gates, and the decision engine take precedence over keyword routing.
