# Controlled Recalibration Loop

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
Crear y validar un calibrador candidato sin tocar el activo.

## Flujo
1. Congelar campeón y splits temporales.
2. Registrar método y parámetros.
3. Ejecutar `scripts/train_calibration.py` o `scripts/train_pergame_calibration.py`.
4. Versionar artefacto candidato con hash y rango de datos.
5. Validar OOS y comparar con el activo.
6. Revisar Brier, Log Loss, ECE, reliability bins y estabilidad.
7. Pasar al loop 09.
8. Ejecutar promoción solo con aprobación humana explícita.
