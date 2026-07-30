# Loss Diagnosis Loop

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
Clasificar pérdidas sin asumir que toda derrota es fallo de modelo.

## Taxonomía
`EXPECTED_VARIANCE`, `DATA_QUALITY`, `IMPLEMENTATION`, `FEATURE_SPECIFICATION`, `MODEL_SPECIFICATION`, `CALIBRATION`, `SELECTION_POLICY`, `MARKET_MOVEMENT`, `IN_GAME_SHOCK`, `UNRESOLVED`.

## Flujo
1. Recuperar snapshot, versiones y datos disponibles en ese momento.
2. Reconstruir la predicción.
3. Revisar integridad, timestamps, features y mercado.
4. Asignar causa primaria, contribuyentes y confianza.
5. Proponer acción solo si la causa es reproducible.
