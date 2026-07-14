---
tags: [calibracion, sqp]
creada: 2026-07-08
actualizada: 2026-07-14
---

# Calibración

Estado al 2026-07-13: **solo `mlb_h2h` LIVE** (isotónico, auto-promovido 07-13: ECE OOS 0.117→0.037 con 23 eventos de validación, preview compresivo 0.90→0.61). El resto de la plataforma sirve probabilidades crudas (no-op). En staging solo wnba_totals (plano en 0.48, bloqueado por <15 eventos).

## Arquitectura del subsistema

- Calibradores **por (liga, mercado)** con método por grupo (`method: auto` → registro `calibration_methods.json` elige isotonic/beta según ECE OOS).
- **Train ≠ promote**: el reentreno diario solo *presenta candidatos* (staging); la promoción a live es un paso humano explícito (`scripts/promote_calibration.py`). Decisión del 2026-06-30.
- **Gate OOS de CUATRO condiciones** en `train_calibration` (auto-sanador → no-op seguro): (1) no empeorar ECE OOS, (2) no empeorar Brier OOS, (3) monotonía no decreciente, (4) **no-inflación a extremos** (2026-07-13): ningún input ≤0.90 puede mapear a ≥0.95. Solo se guarda el lado alto porque los picks nacen de estimada > implícita — inflar crea edges fantasma; corregir a la baja solo suprime picks y sigue permitido.
- **ServedStore** (2026-07-05/07): captura la distribución completa de probabilidades servidas (no solo picks apostados) y las liquida como stream stake-0 → entrenamiento futuro sin sesgo de selección.

## Historia de incidentes (por qué tantos guardas)

1. **Mismatch train/serve** (detectado 2026-06-30, fix 2026-07-01 `d39f975`): se entrenaba sobre pick_history anclado al **cierre** (bien calibrado) pero se servía anclado a **apertura** (sobreconfiado) — la miscalibración era inaprendible. Ahora entrena sobre `data/bets/settled_*.csv` (distribución de servicio).
2. **Calibradores degenerados** (regresión 2026-06-30): el retrain diario re-persistió un isotónico mlb_spreads sobreajustado (step function que el gate monótono no detectaba); empujaba favoritos a 0.92–0.99 creando edges fantasma. Fix: drop a no-op + gate de Brier OOS (TDD, verificado sobre el incidente real). nhl_h2h también degenerado → drop.
3. **Sobreconfianza per-game vs per-bet**: el calibrador entrena sobre apuestas colocadas por mercado (muestra chica y sesgada), no sobre el set per-game del backtest — la sobreconfianza del moneyline MLB (bins 0.5–0.7) no es corregible por esta vía. **Actualización 2026-07-14**: la ruta per-game existe (`sqp/calibration/pergame.py`, clave sandbox `mlb_h2h_pergame` solo en staging). El candidato beta es sólido en su dominio (ECE per-game 0.0289→0.0141, 1.738 eventos de validación, 4 gates OK) pero NO se adopta: en la evaluación cruzada sobre picks liquidados (n=10 cola / n=52 total — ruido) no mejora al raw. Hallazgo clave: la miscalibración de servicio (ECE ~0.26 en la cola) es ~10× la per-game (0.029) → el daño dominante es la SELECCIÓN, no la calibración del modelo. Re-evaluar cuando los h2h liquidados de MLB acumulen n≥50 en la cola.
4. **Los tres gates no bastan con validación chica** (2026-07-13): un candidato wnba_h2h pasó ECE+Brier+monotonía sobre 24 filas / 8 eventos mientras mapeaba 0.80→0.99 — la misma forma del incidente 06-30. Solo lo frenaba el umbral de ≥15 eventos de la auto-promoción; con una semana más de datos WNBA habría entrado a live. Fix: condición `extreme_ok` en el fit (rechazo en origen, no en promoción).

## Lección central

La calibración por sí sola no crea ventaja: con **selección adversa** (ver [[Conocimiento/CLV y selección adversa]]) hasta la probabilidad justa del mercado pierde en los picks seleccionados. Por eso la regla de salida del shadow exige CLV positivo **además** de calibración.

Relacionado: [[Estado del proyecto]], [[Errores y lecciones/Errores detectados y soluciones]].
