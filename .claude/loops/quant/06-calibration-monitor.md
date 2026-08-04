# Calibration Monitoring Loop

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
Detectar descalibración persistente sin reaccionar al ruido diario.

## Criterio previo obligatorio
Antes de calcular, registrar ventana, muestra mínima, tolerancias de Brier/Log Loss/ECE y número de ventanas consecutivas que separan `NORMAL`, `WATCH`, `PERSISTENT` y `CRITICAL`. Deben provenir del código, la configuración o una decisión humana anterior a la evaluación; si faltan, el resultado es `BLOCKED`.

## Flujo
1. Definir ventana, versión y baseline.
2. Ejecutar revisión de calibración aplicable.
3. Calcular reliability bins, Brier, Log Loss y ECE.
4. Comparar ventanas y segmentos con conteos por bin.
5. Clasificar `NORMAL`, `WATCH`, `PERSISTENT` o `CRITICAL`.
6. Derivar a recalibración solo con muestra suficiente y señal persistente.
