# Audit Loop

Entrada operacional de solo lectura para auditorías integrales. La fuente del
procedimiento es `.claude/automation/audit-workflow.md`; la skill `full-audit`
selecciona las referencias especializadas según el alcance.

## Common guardrails

- Follow `.claude/CLAUDE.md`, repository rules, and data-access restrictions.
- Do not commit, push, deploy, release, or promote artifacts without explicit approval.
- Prefer the smallest reversible change.
- Maintain `.claude/automation/runtime/current-task.md`.
- Stop at the iteration budget or any human approval gate.

## Pasos

1. Leer instrucciones aplicables y las secciones comunes/diagnóstico del contrato.
2. Identificar ronda y auditor; preservar la ronda anterior antes de reemplazarla
   según «Rondas, archivos y compatibilidad». No reiniciar la ronda al sumar auditor.
3. Inventariar, auditar y revalidar con independencia; no leer conclusiones de
   auditores previos durante la fase principal. Declarar contexto contaminado.
4. Persistir solo los entregables autorizados de la fase. Si se requiere backlog,
   consolidar después del diagnóstico según el contrato común.
5. Entregar y terminar el diagnóstico. Correcciones autorizadas continúan mediante
   `audit-remediation`, no dentro de este loop.
6. Finish through `/verification-gate`, sujeto a los límites de escritura del
   diagnóstico. Registrar cualquier bookkeeping excluido; no editar el proyecto.
