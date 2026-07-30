# Pregame Refresh Loop

## Reglas comunes

- Cumplir `.claude/CLAUDE.md`, `.claude/ORCHESTRATOR.md` y `.claude/automation/autonomy-policy.md`.
- Ejecutar `/memoria-cargar` al inicio y actualizar `.claude/automation/runtime/current-task.md`.
- No promover modelos, calibradores ni cambios de producción sin aprobación humana explícita.
- No usar información posterior al inicio del evento para evaluar o reconstruir una predicción previa.
- Mantener snapshots inmutables, trazabilidad de versiones y evidencia de cada comando.
- Presupuesto predeterminado: 8 iteraciones; detenerse ante guardrails o evidencia insuficiente.
- Finalizar con `/verification-gate` y `/memoria-guardar`.
- Cerrar declarando `PASS`, `DEGRADED`, `BLOCKED` o `DONE` segun las definiciones exactas de `.claude/loops/quant/STATES.md`, con la evidencia que lo justifica en `current-task.md`.

## Objetivo
Actualizar únicamente eventos afectados por información material prepartido sin sobrescribir snapshots anteriores.

## Flujo
1. Identificar evento, snapshot previo y nueva información con fuente/timestamp.
2. Confirmar que el evento no comenzó.
3. Recalcular solo features y mercados afectados.
4. Crear un snapshot nuevo e inmutable.
5. Comparar probabilidad, línea, cuota, edge y elegibilidad antes/después.
6. Registrar si el pick se mantiene, cambia o se retira.
