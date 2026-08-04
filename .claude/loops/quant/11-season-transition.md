# Season Transition Loop

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
Adaptar priors, ventanas y disponibilidad de features al inicio o cambio de temporada.

## Criterio previo obligatorio
Pre-registrar qué evidencia y umbrales separan `NORMAL`, `CONSERVATIVE`, `SHADOW` y `BLOCKED`, incluyendo muestra mínima y disponibilidad de features. Si no existen en código, configuración o decisión humana previa, el resultado es `BLOCKED`.

## Flujo
1. Identificar cambios de reglas, calendario, roster, proveedores y mercado.
2. Detectar features con muestra insuficiente.
3. Revisar priors y ponderación entre temporadas.
4. Ejecutar walk-forward que reproduzca inicios históricos.
5. Comparar calibración y cobertura tempranas.
6. Definir modo `NORMAL`, `CONSERVATIVE`, `SHADOW` o `BLOCKED`.
