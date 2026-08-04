# Postgame Settlement Loop

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
Liquidar picks de forma determinista contra el snapshot original.

## Precondiciones
- Existe el snapshot de la cohorte. Un archivo de candidatos vacío es un caso
  válido y debe cerrar con evidencia de `n_emitidos = 0`; un snapshot ausente es
  `BLOCKED`.
- Debe correr ANTES del run diario del día (ver loop 01, orden crítico).

## Comandos
1. `SETTLE_ALL.bat`. **Consume cuota de proveedores externos: requiere aprobación
   humana salvo que corra como la tarea programada ya aprobada.**
2. Verificar resultado oficial y reglas del mercado.
3. Clasificar `WIN`, `LOSS`, `PUSH`, `VOID` o `PENDING`.
4. Evitar doble liquidación (dedup en `sqp.settlement.runner`).
5. Reconciliar `emitidos = WIN + LOSS + PUSH + VOID + PENDING`.
6. Guardar score, proveedor y regla aplicada.

## Artefactos
- `data/bets/settled_<liga>.csv`
- `data/calibration/served_<liga>.csv` con las filas graduadas

## Criterios de salida
Definiciones exactas en `.claude/loops/quant/STATES.md`. Específicos:
- `BLOCKED`: score inconsistente, identidad de equipo/jugador ambigua, snapshot
  ausente, o la reconciliación no cuadra.
- `DEGRADED`: quedan `PENDING` por resultados aún no publicados; registrar cuántos
  y de qué liga.
- `PASS`: reconciliación cuadrada y `settled_<liga>.csv` legible; también aplica
  a una cohorte válida con `n_emitidos = 0`.
- `DONE`: además, la cohorte finita queda cerrada sin pendientes y se cumplen las
  condiciones generales de `DONE`.
