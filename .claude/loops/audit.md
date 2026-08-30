# Audit Loop

Loop de **solo lectura** para auditorías integrales. Sustituye a `refactor.md`
en la ruta `full-audit`: una auditoría diagnostica, no refactoriza. La
corrección vive en una skill distinta y detrás de un gate humano.

## Common guardrails

- Follow `.claude/CLAUDE.md`, repository rules, and data-access restrictions.
- Do not commit, push, deploy, release, or promote artifacts without explicit approval.
- Prefer the smallest reversible change.
- Maintain `.claude/automation/runtime/current-task.md`.
- Stop at the iteration budget or any human approval gate.

## Restricciones propias del diagnóstico

Se suman a las anteriores, no las sustituyen:

- no modificar código, configuración, datos ni dependencias durante las fases 0–3;
- único destino de escritura autorizado: `audit/latest/` y `.claude/automation/runtime/current-task.md`;
- "the smallest reversible change" se aplica a la fase de corrección; durante el diagnóstico el cambio correcto es **ninguno**.

## Pasos

1. Leer instrucciones aplicables y `.claude/memory/known-issues.md` antes de auditar.
2. Inventariar y construir la matriz de cobertura antes de buscar defectos.
3. Auditar por área, registrando evidencia con su estado.
4. Revalidar cada hallazgo activo con un segundo método independiente.
5. Persistir hallazgos en `audit/latest/FINDINGS.md` a medida que se confirman.
6. Entregar el plan priorizado y **detenerse**: la corrección exige aprobación explícita.
7. Si se aprueba, continuar con la skill `audit-remediation`, no con este loop.
8. Finish through `/verification-gate`.

La skill `full-audit` define el procedimiento completo. Este archivo fija los
guardarraíles de ejecución; no los duplica ni los reinterpreta.
