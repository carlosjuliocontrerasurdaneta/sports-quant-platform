# Quant Operations Router

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
Seleccionar exactamente un loop cuantitativo primario.

<!-- generated: quant-routes -->
| Ruta | Loop |
|---|---|
| `quant-incident` | `12-quant-incident.md` |
| `quant-daily-prediction` | `01-daily-prediction.md` |
| `quant-pregame-refresh` | `02-pregame-refresh.md` |
| `quant-settlement` | `03-postgame-settlement.md` |
| `quant-daily-audit` | `04-daily-audit.md` |
| `quant-loss-diagnosis` | `05-loss-diagnosis.md` |
| `quant-calibration-monitor` | `06-calibration-monitor.md` |
| `quant-drift-monitor` | `07-drift-monitor.md` |
| `quant-data-recovery` | `08-data-quality-recovery.md` |
| `quant-champion-challenger` | `09-champion-challenger.md` |
| `quant-controlled-recalibration` | `10-controlled-recalibration.md` |
| `quant-season-transition` | `11-season-transition.md` |
| `quant-weekly-improvement` | `13-weekly-continuous-improvement.md` |
<!-- endgenerated: quant-routes -->

Registrar la elección, razón, alcance y criterio de salida en `current-task.md`.
