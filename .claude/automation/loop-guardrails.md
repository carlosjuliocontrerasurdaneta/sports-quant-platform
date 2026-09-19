# Guardarraíles comunes de loops

Editar solo esta fuente y ejecutar `python scripts/sync_agent_instructions.py --write`.
Cada skill operativa (las de `.claude/skills/` con bloque `## Reglas comunes` o
`## Common guardrails`) y el router quant conservan el bloque expandido para
funcionar al cargarse aisladamente. `--check` y los tests comprueban la
sincronización; las reglas de dominio siguen en cada skill. Las reglas de autoridad de `CLAUDE.md`/`AGENTS.md` prevalecen.

<!-- section: general -->
- Follow `.claude/CLAUDE.md`, repository rules, and data-access restrictions.
- Do not commit, push, deploy, release, or promote artifacts without explicit approval.
- Prefer the smallest reversible change.
- Maintain `.claude/automation/runtime/current-task.md`.
- Stop at the iteration budget or any human approval gate.
<!-- endsection -->

<!-- section: quant -->
- Cumplir `.claude/CLAUDE.md`, `.claude/ORCHESTRATOR.md` y `.claude/automation/autonomy-policy.md`.
- Ejecutar `/memoria-cargar` al inicio y actualizar `.claude/automation/runtime/current-task.md`.
- No promover modelos, calibradores ni cambios de producción sin aprobación humana explícita.
- No usar información posterior al inicio del evento para evaluar o reconstruir una predicción previa.
- Mantener snapshots inmutables, trazabilidad de versiones y evidencia de cada comando.
- Presupuesto predeterminado: 8 iteraciones; detenerse ante guardrails o evidencia insuficiente.
- Finalizar con `/verification-gate` y `/memoria-guardar`.
- Cerrar declarando `PASS`, `DEGRADED`, `BLOCKED` o `DONE` según las definiciones exactas de `.claude/loops/quant/STATES.md`, con la evidencia que lo justifica en `current-task.md`.
<!-- endsection -->
