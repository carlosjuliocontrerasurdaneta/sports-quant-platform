# Incident Loop

## Common guardrails

- Follow `.claude/CLAUDE.md`, repository rules, and data-access restrictions.
- Do not commit, push, deploy, release, or promote artifacts without explicit approval.
- Prefer the smallest reversible change.
- Maintain `.claude/automation/runtime/current-task.md`.
- Stop at the iteration budget or any human approval gate.

1. Declare impact, start time, affected components and current mitigation.
2. Identify the safest reversible containment action. Execute it only when it
   is local, non-production or covered by a previously approved runbook;
   otherwise stop for human approval.
3. Preserve evidence and avoid destructive cleanup.
4. Identify root cause only after impact is contained.
5. Add regression coverage and validate recovery.
6. Record timeline, cause, contributing factors, actions and owners.
7. Update `.claude/memory/incidents/` and Obsidian in the same session.
8. Stop before production changes unless explicitly approved.

9. Finish through `/verification-gate`.
