# Loss Diagnosis Loop

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
Clasificar pérdidas sin asumir que toda derrota es fallo de modelo.

## Taxonomía
`EXPECTED_VARIANCE`, `DATA_QUALITY`, `IMPLEMENTATION`, `FEATURE_SPECIFICATION`, `MODEL_SPECIFICATION`, `CALIBRATION`, `SELECTION_POLICY`, `MARKET_MOVEMENT`, `IN_GAME_SHOCK`, `UNRESOLVED`.

## Flujo
1. Recuperar snapshot, versiones y datos disponibles en ese momento.
2. Reconstruir la predicción.
3. Revisar integridad, timestamps, features y mercado.
4. Asignar causa primaria, contribuyentes y confianza.
5. Proponer acción solo si la causa es reproducible.

## Artefactos
- `data/bets/audit_<día>.md` (cohorte liquidada con ROI y hit rate)
- `data/bets/segment_diagnostics_<día>.md` (gaps y flags por segmento)
- `data/bets/clv_<día>.md` (CLV y beat-close-rate)
- `data/bets/degradation_pause.json` (mercados pausados activos)

## Criterios de salida
Definiciones exactas en `.claude/loops/quant/STATES.md`. Específicos de este loop:
- `BLOCKED`: snapshot de la cohorte ausente o ilegible; `segment_diagnostics` no disponible;
  no puede determinarse si la pérdida es reproducible sin datos adicionales.
- `DEGRADED`: causa asignada con confianza BAJA o `n < 15` en el segmento analizado;
  reportar el `n` y la limitación; no escalar a acción sin muestra suficiente.
- `PASS`: causa primaria asignada con confianza MEDIA o ALTA, con `n` reportado, para
  todos los segmentos materiales; acciones propuestas solo para causas reproducibles.

## Prohibido sin aprobación humana
Iniciar recalibración, modificar features o pausar mercados como consecuencia directa
de este loop. El diagnóstico propone; la ejecución requiere una tarea separada y aprobación.
