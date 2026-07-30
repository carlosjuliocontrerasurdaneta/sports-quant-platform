# Data Quality Recovery Loop

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
Restaurar integridad de datos mediante una corrección mínima y reversible.

## Flujo
1. Delimitar proveedor, período, campos y artefactos afectados.
2. Preservar evidencia y reproducir con muestra pequeña.
3. Identificar causa en provider, adapter, mapping, timezone, cache o persistencia.
4. Implementar corrección mínima y test de regresión.
5. Identificar predicciones y settlements afectados.
6. Reprocesar solo con aprobación cuando cambie historia o producción.
