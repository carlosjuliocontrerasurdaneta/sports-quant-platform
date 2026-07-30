# Data and Performance Drift Loop

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
Distinguir drift de datos, concepto, mercado, pipeline o simple varianza.

## Flujo
1. Definir referencia y período actual.
2. Comparar distribuciones, missing, schema y cobertura.
3. Comparar probabilidades, outcomes, Brier, Log Loss, ECE y CLV.
4. Revisar cambios de proveedor, reglas, temporada y código.
5. Clasificar `NO_DRIFT`, `DATA_DRIFT`, `CONCEPT_DRIFT`, `MARKET_DRIFT`, `PIPELINE_DRIFT` o `INCONCLUSIVE`.
6. Proponer experimento; no modificar producción.
