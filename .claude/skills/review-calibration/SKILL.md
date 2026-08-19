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

## Loop de referencia

Antes de ejecutar, leer y seguir el loop correspondiente:
- Monitoreo de calibración → `.claude/loops/quant/06-calibration-monitor.md`
- Recalibración controlada → `.claude/loops/quant/10-controlled-recalibration.md`
