# SQP Autonomous Development Orchestrator

## Purpose

Route every engineering request through a deterministic, evidence-based workflow.
This file complements `CLAUDE.md`; permanent repository rules always have precedence.

## Mandatory startup

1. Read `.claude/CLAUDE.md`.
2. Run `/memoria-cargar`.
3. Run `/project-health`.
4. Classify the request using `.claude/automation/decision-engine.md`.
5. Select exactly one primary loop from `.claude/loops/`.
6. Create or update `.claude/automation/runtime/current-task.md`.
7. Work in bounded iterations and stop on any guardrail.

## Routing table

| Task | Primary loop | Required specialists |
|---|---|---|
| New behavior | `feature.md` | repository-cartographer, backend-architect/python-engineer, qa-engineer |
| Defect | `bugfix.md` | repository-cartographer, python-engineer, qa-engineer |
| Refactor | `refactor.md` | backend-architect, python-engineer, qa-engineer |
| Model/probability change | `model.md` | feature-engineer, leakage-detector, ml-engineer, calibration-auditor, backtest-reviewer, risk-manager |
| Provider/ETL | `provider.md` | provider-integrator, data-engineer, leakage-detector, qa-engineer |
| Calibration | `calibration.md` | calibration-auditor, backtest-reviewer, risk-manager |
| Backtest/evaluation | `backtest.md` | leakage-detector, backtest-reviewer, sports-quant-auditor |
| Release | `release.md` | qa-engineer, security-reviewer, devops-engineer |
| Incident | `incident.md` | principal-orchestrator, relevant owner, qa-engineer |
| Documentation only | `documentation.md` | documentation-writer |
| Quantitative operation | `quant/00-quant-operations-router.md` | principal-orchestrator, sports-quant-auditor, relevant specialist |

## Quantitative operations

For prediction generation, pregame updates, settlement, daily auditing, loss diagnosis, calibration monitoring, drift monitoring, data-quality recovery, champion-challenger evaluation, controlled recalibration, season transitions, quantitative incidents, and weekly quantitative reviews:

1. Read `.claude/loops/quant/00-quant-operations-router.md`.
2. Select exactly one primary quantitative loop.
3. Record the selected loop in `.claude/automation/runtime/current-task.md`.
4. Follow all repository guardrails and human approval gates.
5. Never promote a model or calibration artifact automatically.

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
- Obsidian update when required by `.claude/CLAUDE.md`;
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

Before delegation, use `.claude/automation/model-routing.json` and the context injected by `.claude/hooks/route-model.py`. The model policy itself lives in `.claude/automation/MODEL_ROUTING.md` (single source). Delegate to the named primary subagent when its specialization matches the request. The subagent's `model` frontmatter controls the execution model. Permanent rules, safety gates, and the decision engine take precedence over keyword routing.
