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
Seleccionar exactamente una skill cuantitativa primaria; su cuerpo es el loop (hasta el 2026-09-18 los loops eran ficheros aparte en este directorio y las skills solo los apuntaban).

<!-- generated: quant-routes -->
| Ruta | Skill |
|---|---|
| `quant-incident` | `quant-incident` |
| `quant-daily-prediction` | `daily-operations` |
| `quant-pregame-refresh` | `pregame-refresh` |
| `quant-settlement` | `daily-operations` |
| `quant-daily-audit` | `daily-audit` |
| `quant-loss-diagnosis` | `loss-diagnosis` |
| `quant-calibration-monitor` | `review-calibration` |
| `quant-drift-monitor` | `drift-monitor` |
| `quant-data-recovery` | `data-quality-recovery` |
| `quant-champion-challenger` | `champion-challenger` |
| `quant-controlled-recalibration` | `controlled-recalibration` |
| `quant-season-transition` | `season-transition` |
| `quant-weekly-improvement` | `weekly-improvement` |
<!-- endgenerated: quant-routes -->

Registrar la elección, razón, alcance y criterio de salida en `current-task.md`.
