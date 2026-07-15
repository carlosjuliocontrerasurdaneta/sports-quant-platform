# /autopilot

Autopilot is bounded autonomous maintenance, not unlimited execution.

1. Read the orchestration and autonomy policies.
2. Run `/project-health`.
3. If an explicit user task exists, route it. Otherwise select the highest-priority `ready`
   item from `.claude/automation/backlog.md`.
4. If no explicit task or ready backlog item exists, stop; do not invent work.
5. Execute the selected loop for at most 8 iterations.
6. After each iteration update `runtime/current-task.md` with evidence and next decision.
7. Stop on a human approval gate, iteration budget, repeated failure, ambiguity affecting safety,
   or completion.
8. Run `/verification-gate`.
9. Never commit, push, deploy, release, promote artifacts, delete data, or use paid/production
   services without explicit approval.
