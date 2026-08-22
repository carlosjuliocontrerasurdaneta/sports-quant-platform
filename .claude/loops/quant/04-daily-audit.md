# Daily Quant Audit Loop

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
Medir rendimiento y calidad probabilística de la cohorte liquidada.

## Flujo
1. Congelar cohorte por fecha, mercado y versión.
2. Separar pushes, voids y pendientes.
3. Calcular `n`, hit rate, Brier, Log Loss y ECE.
4. Separar liga, mercado, modelo y banda probabilística.
5. Reportar por banda el hit rate observado y el `gap` = observado − prometido.
   **El hit rate se juzga contra el punto de equilibrio de la cuota** (1/price),
   no contra un umbral fijo — decisión 2026-07-31 que revirtió `picks.mode`
   de `accuracy` a `edge` (razón: favoritos a 1.07 pueden acertar el 90% y
   perder dinero). ROI realizado y yield requieren `staked > 0`; bajo el
   `prediction_gate` los stakes son 0 por (liga, mercado) no habilitado,
   lo que no implica equilibrio. CLV requiere cuota de entrada y de cierre
   emparejables; seguir calculándolo como evidencia del gate.
6. Comparar con baseline y ventanas móviles.
7. Derivar pérdidas relevantes al loop 05.

## Artefactos
- `data/bets/segment_diagnostics_latest.csv` (hit rate y `gap` por banda)
- `data/bets/degradation_pause.json`
- `data/bets/prediction_gate.json` (gate rector desde 2026-08-16: modelo puro vs mercado OOS + EV plano positivo)
- `data/bets/clv_gate.json` (secundario: evidencia CLV, no decide stakes)

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
