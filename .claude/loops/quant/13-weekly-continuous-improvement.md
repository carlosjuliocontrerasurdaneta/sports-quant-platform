# Weekly Continuous Improvement Loop

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
Integrar auditoría, calibración, drift, calidad de datos y diagnósticos para decidir acciones semanales.

## Flujo
1. Consolidar auditorías reconciliadas.
2. Resumir métricas por deporte, mercado, versión y banda.
3. Revisar causas de pérdidas con confianza media/alta.
4. Ejecutar los loops 06 y 07 como loops de apoyo conforme al protocolo del `ORCHESTRATOR.md`.
5. Priorizar problemas por impacto, evidencia y riesgo de leakage.
6. Crear máximo tres hipótesis falsables.
7. Decidir `MAINTAIN`, `MONITOR`, `FIX_DATA`, `RUN_EXPERIMENT` o `ESCALATE_INCIDENT`.
8. Mantener producción intacta hasta aprobación.


## Regla de decisión

- `ESCALATE_INCIDENT`: existe evidencia reproducible de leakage, predicción
  posterior al inicio, liquidación incorrecta, duplicación o modelo equivocado.
- `FIX_DATA`: existe un fallo reproducible de integridad, mapping, timezone,
  provider, cache o persistencia y no constituye un incidente activo.
- `RUN_EXPERIMENT`: existe una hipótesis falsable pre-registrada, con métrica,
  muestra mínima y guardrails definidos antes de evaluar.
- `MONITOR`: la señal no supera el umbral pre-registrado o la muestra es
  insuficiente, sin fallo crítico reproducible.
- `MAINTAIN`: calibración y drift están dentro de los límites pre-registrados y
  no existe un problema reproducible.
- Si faltan umbrales o criterios pre-registrados, el resultado es `BLOCKED`; no
  se elige una acción después de observar los datos.
