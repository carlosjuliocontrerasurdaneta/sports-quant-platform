---
tags: [calibracion, sqp]
creada: 2026-07-08
actualizada: 2026-07-08
---

# Calibración

Estado al 2026-07-08: **registro live VACÍO** — toda la plataforma sirve probabilidades crudas (no-op) hasta que un mercado pase el gate de Brier OOS. Hay un candidato en staging (MLB spreads, ECE OOS +0.0524) pendiente de revisión humana.

## Arquitectura del subsistema

- Calibradores **por (liga, mercado)** con método por grupo (`method: auto` → registro `calibration_methods.json` elige isotonic/beta según ECE OOS).
- **Train ≠ promote**: el reentreno diario solo *presenta candidatos* (staging); la promoción a live es un paso humano explícito (`scripts/promote_calibration.py`). Decisión del 2026-06-30.
- **Gate de Brier OOS** en `train_calibration`: un calibrador solo se persiste/mantiene si mejora la métrica fuera de muestra; si deja de ayudar, el retrain borra su entrada (auto-sanador → no-op seguro).
- **ServedStore** (2026-07-05/07): captura la distribución completa de probabilidades servidas (no solo picks apostados) y las liquida como stream stake-0 → entrenamiento futuro sin sesgo de selección.

## Historia de incidentes (por qué tantos guardas)

1. **Mismatch train/serve** (detectado 2026-06-30, fix 2026-07-01 `d39f975`): se entrenaba sobre pick_history anclado al **cierre** (bien calibrado) pero se servía anclado a **apertura** (sobreconfiado) — la miscalibración era inaprendible. Ahora entrena sobre `data/bets/settled_*.csv` (distribución de servicio).
2. **Calibradores degenerados** (regresión 2026-06-30): el retrain diario re-persistió un isotónico mlb_spreads sobreajustado (step function que el gate monótono no detectaba); empujaba favoritos a 0.92–0.99 creando edges fantasma. Fix: drop a no-op + gate de Brier OOS (TDD, verificado sobre el incidente real). nhl_h2h también degenerado → drop.
3. **Sobreconfianza per-game vs per-bet**: el calibrador entrena sobre apuestas colocadas por mercado (muestra chica y sesgada), no sobre el set per-game del backtest — la sobreconfianza del moneyline MLB (bins 0.5–0.7) no es corregible por esta vía.

## Lección central

La calibración por sí sola no crea ventaja: con **selección adversa** (ver [[Conocimiento/CLV y selección adversa]]) hasta la probabilidad justa del mercado pierde en los picks seleccionados. Por eso la regla de salida del shadow exige CLV positivo **además** de calibración.

Relacionado: [[Estado del proyecto]], [[Errores y lecciones/Errores detectados y soluciones]].
