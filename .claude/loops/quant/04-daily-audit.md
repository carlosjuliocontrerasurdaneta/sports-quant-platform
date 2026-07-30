# Daily Quant Audit Loop

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
Medir rendimiento y calidad probabilística de la cohorte liquidada.

## Flujo
1. Congelar cohorte por fecha, mercado y versión.
2. Separar pushes, voids y pendientes.
3. Calcular `n`, hit rate, Brier, Log Loss y ECE.
4. Separar liga, mercado, modelo y banda probabilística.
5. **El objetivo vigente es el hit rate** (decisión 2026-07-27). Reportar por
   banda el hit rate observado y el `gap` = observado − prometido. ROI realizado,
   yield y CLV son métricas SECUNDARIAS y solo válidas con `staked > 0`: bajo
   `shadow_mode` el ROI sale `0.0` por no haberse arriesgado nada, lo que NO es
   equilibrio (auditoría 2026-07-29, B-10).
6. Comparar con baseline y ventanas móviles.
7. Derivar pérdidas relevantes al loop 05.

## Artefactos
- `data/bets/segment_diagnostics_latest.csv` (hit rate y `gap` por banda)
- `data/bets/degradation_pause.json`, `data/bets/clv_gate.json`

## Criterios de salida
Definiciones exactas en `.claude/loops/quant/STATES.md`. Específicos:
- `DEGRADED` (sustituye al antiguo `INSUFFICIENT`): `n < 15` en el segmento
  evaluado; reportar el `n` y no concluir.
- `BLOCKED`: `segment_diagnostics_latest.csv` ausente o ilegible, o la cohorte no
  puede congelarse.
- `PASS`: métricas calculadas, cada una con su `n`, en todos los segmentos con
  muestra suficiente.

## Prohibido sin aprobación humana
Pausar o reactivar mercados a mano, promover calibradores, o concluir que un
segmento "funciona" a partir de un único máximo in-sample sin intervalo de
confianza.
