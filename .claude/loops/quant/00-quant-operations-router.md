# Quant Operations Router

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
Seleccionar exactamente un loop cuantitativo primario.

| Situación | Loop |
|---|---|
| Predicción diaria | `01-daily-prediction.md` |
| Cambio prepartido material | `02-pregame-refresh.md` |
| Liquidación de resultados | `03-postgame-settlement.md` |
| Auditoría diaria | `04-daily-audit.md` |
| Diagnóstico de pérdidas | `05-loss-diagnosis.md` |
| Monitoreo de calibración | `06-calibration-monitor.md` |
| Monitoreo de drift | `07-drift-monitor.md` |
| Recuperación de calidad de datos | `08-data-quality-recovery.md` |
| Champion vs challenger | `09-champion-challenger.md` |
| Recalibración controlada | `10-controlled-recalibration.md` |
| Transición de temporada | `11-season-transition.md` |
| Incidente cuantitativo | `12-quant-incident.md` |
| Mejora continua semanal | `13-weekly-continuous-improvement.md` |

Registrar la elección, razón, alcance y criterio de salida en `current-task.md`.
