# Investigación: calibrar p_model puro vs p_used blended

**Fecha:** 2026-07-02 · **Estado:** análisis completado, SIN cambios de serving (requiere
aprobación humana) · **Backlog:** ítem 1 del mandato del loop (`docs/loop-mandate-precision.md`).

> Salidas en lenguaje de estimación: todo lo de abajo son probabilidades estimadas y métricas
> fuera de muestra sobre una muestra chica y auto-seleccionada. Nada garantiza ROI.

## Pregunta

`estimated_probability` (lo que hoy se calibra) ya es 50% mercado:
`p_used = 0.5·p_model + 0.5·fair` (daily.py:544, `market_shrink=0.5`). Calibrar la mezcla
confunde la miscalibración del modelo con el anclaje al mercado: el calibrador gasta capacidad
en "deshacer" un blend que ya está bien calibrado. ¿Conviene calibrar `p_model` puro y
re-mezclar después (`p_used' = 0.5·cal(p_model) + 0.5·fair`)?

## Datos y método

- `data/bets/settled_*.csv` (graded win/loss, 360 filas con ambas probabilidades), vía
  `load_all_settled`. Fechas = `game_date` (fallback `generated_at`), orden temporal.
- `fair` reconstruido por identidad del pipeline: `fair = 2·p_used − p_model` (**supone
  s=0.5 constante en todo el período** — vigente desde el port del proyecto 2; verificado:
  0 filas sin ancla, 0 fair fuera de [0,1]).
- Isotónica con split temporal 80/20 (idéntico al trainer), y robustez con cortes 70/75/80/85.
- Métricas: ECE y Brier OOS — las mismas dos condiciones del gate de persistencia.

## Resultado 1 — ¿dónde vive la miscalibración? (muestra completa)

| grupo | n | p_model ECE/Brier | p_used ECE/Brier | fair ECE/Brier |
|---|---:|---|---|---|
| mlb/spreads | 96 | 0.1357 / 0.2481 | 0.1004 / 0.2393 | 0.1120 / 0.2361 |
| mlb/totals | 69 | 0.1637 / 0.2751 | 0.0867 / 0.2556 | 0.0633 / 0.2501 |
| mlb/h2h | 38 | 0.1593 / 0.2784 | 0.1189 / 0.2648 | 0.1305 / 0.2555 |
| mlb pooled | 203 | 0.1455 / 0.2629 | 0.0843 / 0.2496 | **0.0444 / 0.2445** |

Confirma el mecanismo: `p_model` es lo más sobreconfiado (media 0.560 vs obs 0.438 pooled),
`fair` lo mejor calibrado, `p_used` intermedio. El defecto vive en `p_model`; el blend ya
corrige la mitad mecánicamente.

## Resultado 2 — experimento de serving (split temporal 80/20)

| variante (val) | spreads ECE/Brier (n=20) | totals ECE/Brier (n=14) |
|---|---|---|
| p_used crudo (pipeline hoy) | 0.1528 / 0.2384 | 0.1689 / 0.2788 |
| cal(p_used) — enfoque actual | 0.0491 / 0.2418 ✗Brier | 0.1829 / 0.3255 ✗✗ |
| cal(p_model) puro (sin blend) | 0.0446 / 0.2409 ✗Brier | 0.2274 / 0.3851 ✗✗ |
| **0.5·cal(p_model) + 0.5·fair** | **0.0200 / 0.2358 ✓✓** | 0.2018 / 0.3018 ✗✗ |

**Hallazgo clave (spreads):** la propuesta es la ÚNICA variante que mejora ECE y Brier a la
vez — es decir, la única que habría PASADO el gate. El drop de hoy de `cal(p_used)` fue
precisamente por Brier (0.2384→0.2418). En totals (n_val=14) todo empeora vs crudo: el gate
las descartaría todas, correcto — no hay señal con esa muestra.

## Resultado 3 — robustez (mlb/spreads, 4 cortes temporales)

| corte | n_val | raw | cal(p_used) | reblend cal(p_model) |
|---:|---:|---|---|---|
| 0.70 | 29 | 0.1146 / 0.2403 | 0.0862 / 0.2535 | **0.0465 / 0.2395** |
| 0.75 | 24 | 0.1273 / 0.2403 | 0.0639 / 0.2494 | **0.0371 / 0.2384** |
| 0.80 | 20 | 0.1528 / 0.2384 | 0.0491 / 0.2418 | **0.0200 / 0.2358** |
| 0.85 | 15 | 0.1857 / 0.2684 | 0.1826 / 0.2956 | **0.1570 / 0.2719** |

El reblend domina a `cal(p_used)` en **ambas métricas en los 4 cortes**, y bate al Brier crudo
en 3 de 4 (en 0.85, n_val=15, todo degrada; sigue siendo el menos malo). Para una muestra de
n=96, es una dominancia inusualmente consistente.

## Conclusión y recomendación

1. **La hipótesis del backlog se confirma empíricamente**: calibrar la mezcla es
   estructuralmente peor que calibrar `p_model` y re-mezclar. La intuición del porqué: la
   isotónica sobre `p_used` tiene que aprender una corrección a través de un canal diluido al
   50% por una señal (fair) que no necesita corrección; sobre `p_model` ataca el defecto puro
   con la misma muestra.
2. **Recomendación (decisión humana):** cambiar el objetivo de calibración a `p_model` y
   servir `p_used' = (1−s)·cal(p_model) + s·fair`. Bosquejo de implementación:
   - Entrenar sobre `model_probability` de settled (la columna ya existe; misma tubería,
     mismo gate ECE+Brier+monotonía, mismo staging/promoción — solo cambia la columna).
   - En serve (daily.py:544-552): aplicar `calibrate_probability` a `p_model` ANTES del
     shrink, en vez de a `p_used` después. `estimated_probability` almacenada debe seguir
     siendo la cruda para no crear un loop calibrar-sobre-calibrado (mismo principio que hoy).
   - Consistencia train/serve garantizada: `p_model` no depende de odds ⇒ inmune al
     desanclaje apertura/cierre que rompía el entrenamiento sobre pick_history.
3. **No implementar todavía la promoción de nada**: con n=96 el candidato de spreads seguiría
   siendo frágil; el valor del cambio es que los candidatos futuros se entrenen contra el
   objetivo correcto a medida que crece la muestra.

## Caveats

- Muestra chica y AUTO-SELECCIONADA (solo apuestas colocadas; sesgo de selección documentado
  en [[shrink-analysis-adverse-selection]]) — la dominancia es direccional, no un tamaño de
  efecto confiable.
- Reconstrucción de `fair` supone `market_shrink=0.5` constante; filas de un período con otro
  shrink invalidarían su fila (verificación indirecta: 0 anomalías).
- Evidencia fuerte solo en UN grupo (mlb/spreads); totals/h2h sin muestra.
- Un solo mercado de referencia (consenso mediano); verificación real solo hacia adelante.

## Reproducibilidad

Análisis ejecutado con funciones del pipeline (`load_all_settled`, métricas de
`sqp.calibration.metrics`, `IsotonicRegression`) sobre los settled del 2026-07-02; el código
del experimento está inline en la sesión y es re-derivable de las fórmulas de arriba
(identidad del blend en daily.py:544, split temporal 80/20 del trainer).
