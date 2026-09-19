---
name: review-calibration
description: Use this skill to review, stage, or promote probability calibrators — "revisar calibración", "promover calibrador", staging candidates, Brier/ECE gate decisions, or anything touching the live calibration registry. Covers the full staging → gate → human promotion flow (train_calibration.py / promote_calibration.py).
---

# Review Calibration

Flujo de calibración por (liga, mercado). Regla central: **entrenar ≠ promover**.
El retrain diario solo deja candidatos en staging; el registro live cambia
únicamente por decisión humana (o con `CALIBRATION_AUTO_PROMOTE=1`, OFF por defecto).

## Flujo

1. **Entrenar / re-staging**: `python scripts/train_calibration.py`
   - Entrena sobre apuestas liquidadas reales (`data/bets/settled_*.csv`,
     distribución de servicio anclada a la apertura — fix train/serve 2026-07-01).
   - Deja candidatos en `data/models/staging/`. NUNCA toca el registro live.
   - Gates OOS aplicados al staging: ECE + Brier + monotonía + no-inflación
     a extremos (`extreme_ok`, 2026-07-13: ningún input ≤0.90 puede mapear
     a ≥0.95) + n_val_events.
   - `--source {combined,settled,served,backtest}`; `--rebuild` solo aplica
     con `--source backtest`. `--min-n` por (liga, mercado).
2. **Dry-run**: `python scripts/promote_calibration.py` (sin flags)
   - Muestra diff staging vs live y preview del candidato sobre una grilla
     de probabilidades.
3. **Decisión humana** — promover solo si:
   - El candidato mejora ECE/Brier OOS con suficientes eventos de validación
     independientes.
   - El preview NO es degenerado. Señal de alarma histórica (incidente
     2026-06-30): isotónica escalonada que empuja favoritos a 0.9+ →
     edges fantasma. El gate de monotonía NO detecta ese caso por sí solo.
4. **Promover**: `python scripts/promote_calibration.py --keys <k1,k2>`
   (o `--yes` para todos los staged).

Wrapper BAT de referencia: `REVIEW_CALIBRATION_MLB_H2H.bat` (train + dry-run +
log en `logs/calibration_review.log`). Guía de decisión:
`docs/CALIBRATION-2026-06-21.md`.

## Reglas

- Registro live vacío (todo no-op/raw) es un estado VÁLIDO y preferible a un
  calibrador degenerado. No promover por presión de tener "algo" live.
- Nunca promover sin revisar el dry-run y el preview.
- La probabilidad almacenada para reentrenar queda SIN calibrar (no hay bucle
  calibrar-sobre-calibrado).
- No abrir CSV completos: usar encabezados y muestras.
- Lenguaje: probabilidad estimada, nunca certezas ni profit garantizado.

## Entregar

1. Estado del staging (candidatos, métricas OOS) y del registro live.
2. Diff staging vs live del dry-run.
3. Veredicto por candidato: promover / rechazar / esperar más muestra, con
   evidencia (ECE/Brier OOS, forma del preview, n de validación).

## Skill hermana

Entrenar un calibrador candidato (no revisarlo ni promoverlo) es la skill `controlled-recalibration`.

## Loop: Calibration Monitoring Loop

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

## Loop: Calibration Loop

1. Freeze the evaluation period, source probabilities, baseline, and sample inclusion rules.
2. Verify every source probability was generated before its event started using
   only information available at that timestamp, and ensure the calibration
   training period strictly precedes the evaluation period.
3. Evaluate reliability curves/bins, ECE, Brier and Log Loss with sample counts.
4. Compare global and segmented behavior; flag sparse bins.
5. Test stability across time and relevant leagues/markets.
6. Record candidate parameters and exact reproducibility inputs.
7. Never promote calibration artifacts without human approval.
8. Finish through `/verification-gate`.
