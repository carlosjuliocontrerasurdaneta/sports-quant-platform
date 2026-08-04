# Controlled Recalibration Loop

## Reglas comunes

- Cumplir `.claude/CLAUDE.md`, `.claude/ORCHESTRATOR.md` y `.claude/automation/autonomy-policy.md`.
- Ejecutar `/memoria-cargar` al inicio y actualizar `.claude/automation/runtime/current-task.md`.
- No promover modelos, calibradores ni cambios de producción sin aprobación humana explícita.
- No usar información posterior al inicio del evento para evaluar o reconstruir una predicción previa.
- Mantener snapshots inmutables, trazabilidad de versiones y evidencia de cada comando.
- Presupuesto predeterminado: 8 iteraciones; detenerse ante guardrails o evidencia insuficiente.
- Finalizar con `/verification-gate` y `/memoria-guardar`.
- Cerrar declarando `PASS`, `DEGRADED`, `BLOCKED` o `DONE` según las definiciones exactas de `.claude/loops/quant/STATES.md`, con la evidencia que lo justifica en `current-task.md`.

## Objetivo
Crear y validar un calibrador candidato sin tocar el activo.

## Flujo
1. Congelar campeón y splits temporales.
2. Registrar método y parámetros.
3. Ejecutar `scripts/train_calibration.py` o `scripts/train_pergame_calibration.py`.
4. Versionar artefacto candidato con hash y rango de datos.
5. Validar OOS y comparar con el activo.
6. Revisar Brier, Log Loss, ECE, reliability bins y estabilidad.
7. Ejecutar el loop 09 como loop de apoyo conforme al protocolo del
   `ORCHESTRATOR.md`, sin reemplazar el encabezado de `current-task.md`.
8. Entregar `REJECT`, `CONTINUE_SHADOW` o `CANDIDATE_FOR_APPROVAL`. La promoción
   no forma parte de este loop; requiere una tarea posterior y aprobación humana
   explícita.
