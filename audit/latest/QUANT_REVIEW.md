# Revisión cuantitativa — Auditoría 2026-07-29/30

Todo lo que sigue son **probabilidades estimadas** y controles de proceso. No hay
en este documento ninguna afirmación de rentabilidad.

## 1. Qué política está realmente en producción

`configs/default.yaml`: `pick_mode: accuracy`, `accuracy_threshold: 0.70`,
`market_shrink: 0.5`, `shadow_mode: true`.

Camino de decisión verificado en el código:

```
p_model  = adapter.estimate(...)                     # Elo + distribución por familia
fair     = remove_vig_power(mediana consenso)         # no-vig del mercado
p_cal    = calibrate_probability(p_model, liga, mercado, "auto")
p_decision = (1 - 0.5) * p_cal + 0.5 * fair
pick     ⟺ mercado == "h2h"  y  p_decision >= 0.70   y  mercado completo
stake    = bankroll * max_stake_pct                   # plano, NO Kelly
stake    → 0 por shadow_mode
```

## 2. El hallazgo central: el umbral no mide lo que dice medir

**Estado: implementado, premisa no cumplida.**

`data/models/calibration_methods.json` contiene únicamente
`{"mlb_totals": "isotonic", "wnba_totals": "isotonic"}`. Los únicos `.joblib` de
calibración son de `totals`. **No existe ningún `*_h2h_calibration_*`.**

Con `method: "auto"` y clave ausente, `calibrator.py:500-512` hace `return probs`:
un no-op. Y el modo precisión opera **solo** en h2h (`daily.py:398`), el único
mercado sin calibrador. Consecuencia: `p_cal == p_model` crudo, y

> "probabilidad calibrada ≥ 0.70" es, en la práctica,
> "media de un modelo no calibrado y del favorito del mercado ≥ 0.70".

La columna persistida se llama `calibrated_probability` de todos modos
(`daily.py:665`), lo que choca con `.claude/rules/betting-output-rules.md`.
El health check lo confirma independientemente: `calibration=True` solo en MLB, y
ese calibrador es de totals.

**Corrección aplicada:** el pipeline ahora emite un WARNING por liga cuando el modo
precisión corre sin calibrador h2h promovido. **No suprime picks**: dejar de
emitirlos es un cambio de política productiva que requiere decisión humana.

## 3. Selección cuasi-tautológica y herencia de vig

Con `market_shrink = 0.5`, la condición `p_decision ≥ 0.70` equivale exactamente a

```
p_model + fair ≥ 1.40
```

`p_model` y `fair` están fuertemente correlacionados (ambos son fuerza relativa del
equipo), así que el criterio selecciona **favoritos claros del mercado**, y el
mercado aporta la mitad del criterio por construcción.

Peor: el edge se calcula contra el precio **con vig** (`daily.py:584`). Si
`p_decision ≈ fair`, entonces `e = fair·d − 1 < 0` mecánicamente, porque `d < 1/fair`.
**Los picks de precisión son estructuralmente de EV estimado negativo.**

Muestra real de producción (`candidates_*.csv`): cuotas 1.07, 1.10, 1.16, 1.20, 1.24.
Con `price = 1.07` el punto de equilibrio es `1/1.07 = 0.9346`, frente a
`calibrated_probability = 0.8759` observado en esa fila.

**Lo que esto implica para leer el KPI:** el hit rate esperado tenderá a la
frecuencia implícita del mercado en la banda seleccionada, **no al 0.70 nominal**.
Un hit rate del 85% en esa banda no sería evidencia de habilidad predictiva; sería
lo que el mercado ya decía. La métrica informativa es el `gap` = observado −
prometido, y su interpretación exige el `n` y un intervalo de confianza que hoy no
se calcula.

## 4. Sobreconfianza del modelo h2h (medido, no inferido)

Medición ejecutando el adapter real (`get_adapter` + `estimate`, ratings sintéticos,
P(local gana)):

| Δ Elo | NHL | MLB | NBA | NFL | EPL |
|---|---|---|---|---|---|
| 0 | 0.553 | 0.546 | 0.565 | 0.541 | 0.416 |
| 50 | 0.670 | 0.610 | 0.610 | 0.577 | 0.508 |
| 100 | **0.769** | 0.668 | 0.654 | 0.613 | 0.596 |
| 200 | 0.898 | **0.757** | 0.736 | 0.682 | 0.739 |
| 300 | 0.940 | 0.813 | 0.806 | 0.745 | 0.768 |

Mecanismo (`adapters.py:101-105`): `tilt = clip((p_home − 0.5)·tilt_scale, ±0.30)`
reparte λ. En NHL (`tilt_scale` 0.9, `avg_total` 6.1) una ventaja Elo rutinaria de
100 puntos produce λ ≈ 4.0 vs 2.2 — un reparto de anotación implausible.
MLB con Δ200 da 0.757, por encima de cualquier moneyline plausible de béisbol.

Efecto sobre el umbral (`fair` necesaria = `1.40 − p_model`):
- NHL Δ100: basta `fair ≥ 0.631` (≈ −171).
- MLB Δ200: basta `fair ≥ 0.643` (≈ −180).

Es decir: picks etiquetados "≥0.70" cuya única evidencia externa los sitúa en
0.63–0.65. Sin calibrador h2h, nada corrige esa brecha.

## 5. Por deporte y mercado

| Liga | Familia / distribución | Estado del h2h para el modo precisión |
|---|---|---|
| **MLB** | Poisson con `tilt`; park factor **validado OOS y activo**; `pitcher_bound: 0.0` | **El abridor es un no-op.** `factor()` devuelve 1.0 incondicionalmente, pero `reliability_warning` sigue bloqueando el evento por `is_known()`. El abridor funciona como gate de disponibilidad, no como feature — mientras el docstring afirma que es "the largest single factor". Las probabilidades h2h de MLB no contienen información del factor dominante del moneyline de béisbol. `pitcher_signal` sigue en `"ra"` (v1); el trabajo de FIP per-start no está activo. |
| **NBA** | Normal sobre margen | Sobreconfianza moderada (0.654 a Δ100). Sin señales de pace/ratings/back-to-back integradas al h2h. |
| **NFL** | Normal sobre margen | La menos sobreconfiada (0.613 a Δ100), pero las normales **ignoran key numbers (3, 7)**; afecta a spreads más que a h2h. |
| **NHL** | Poisson `tilt_scale` 0.9 | **La más sobreconfiada** (0.769 a Δ100). Además la masa de empate se reparte 50/50 (`distributions.py:100`), cuando el favorito gana algo más del 50% en OT/penales — sesga hacia el underdog, lo que *atenúa* la sobreconfianza sin compensarla. |
| **Soccer (1X2)** | Poisson + Dixon-Coles `dc_rho` | Único caso `three_way`. Con calibración por outcome y sin renormalización, la suma de tres `p_decision` dejaría de ser 1 en cuanto se promueva un calibrador. |
| **Tenis** | Elo por jugador, tour-wide | Sin scores en The Odds API → settlement vía ESPN (no oficial). El histórico orienta `home = ganador` (`espn_tennis.py:75-78`), compensado con `neutral: True`; cualquier feature futura de localía sobre esos CSV leería un sesgo del 100%. Solo auditabilidad. |

## 6. Calibración

**Correctamente implementado (verificado, no tocar):**

- **Split temporal por grupos de evento** (`calibrator.py:194-217`): los lados
  complementarios del mismo partido nunca caen en train y val a la vez, y
  `n_val_events` se expone al gate. Es la decisión de diseño más importante y está
  bien resuelta.
- Target = `model_probability` **pre-blend, serve-anchored** (`calibration/data.py`):
  ni loop calibrar-sobre-calibrado, ni anclaje al cierre.
- Cuotas de cierre solo con `--source backtest`, con advertencia explícita en el
  docstring; no es el default ni lo que usa `run_all.py`.
- El stream servido captura **todos** los lados con precio antes de cualquier filtro
  de stake, así que cambiar `pick_mode` no sesga el conjunto de entrenamiento.
- `date` = `game_date` real con fallback, filas sin fecha usable descartadas.

**Déficits:**

- **Los gates no validan la región donde vive el modo precisión** (Q-04).
  `_no_extreme_expansion` solo prohíbe inflar hacia ≥0.95; un mapeo `0.55 → 0.85`
  pasa los cuatro gates. La ECE es un promedio ponderado sobre 10 bins, así que un
  desajuste en la banda ≥0.70 se diluye si hay pocas filas ahí. Con el modo
  precisión activo, un calibrador que infle la zona media-alta ya no fabrica solo
  edges fantasma: **fabrica picks en masa**.
- **Sin conjunto test** (Q-12): `best_method` se elige por ECE sobre el mismo
  `val_df` cuyo ECE se reporta como out-of-sample y alimenta el gate. Optimismo de
  selección reconocido en el propio código y mitigado subiendo `min_n_val` a 30,
  no eliminado.
- **Champion vs challenger incompleto** (Q-15): el gate compara el challenger contra
  *raw*, no contra el calibrador live. Y **no hay rollback**: `promote_calibrators`
  sobrescribe el live con `shutil.copyfile` sin respaldo, y la democión hace
  `unlink`, así que no se puede volver a un champion previo.
- **Sin renormalización por mercado** (Q-06): defecto latente. Hoy enmascarado
  porque sin calibrador `p_decision(local) + p_decision(visita) = 1` exacto. Al
  promover un calibrador h2h, ambos lados podrían superar 0.70 → dos picks
  contradictorios sobre el mismo evento, contaminando el KPI por banda con pares
  mutuamente excluyentes.
- Deriva doc↔código: el comentario del yaml dice `n_val_events >= 15`; el código usa
  30 (Q-11). El comportamiento es el correcto; la documentación miente.

## 7. Backtesting y evidencia out-of-sample

**Lo que está bien:** walk-forward real (`adapter.observe(r)` siempre después de
estimar, sin splits aleatorios, orden estable por fecha); holdout rolling-origin en
`tuning.py`; selección y evaluación en mitades disjuntas en `compare.py`; ROI con
denominador = stake realmente arriesgado; emparejamiento de snapshots por menor
distancia de día con consumo único.

**Lo que invalida las conclusiones para la política vigente:**

1. **No existe backtest de la regla de producción** (B-02). `grep -rn "accuracy"
   src/sqp/backtesting/ src/sqp/audit/` devuelve una sola coincidencia, y es un
   comentario. `validate_oos.py`, `backtest_roi.py` y `patterns.py` miden la regla
   por edge/Kelly. **El −5.32% de ROI OOS conocido no describe el modo precisión.**
   Y `_summarize` no expone hit rate global, así que el validador no puede reportar
   el KPI del proyecto.
2. **Ancla temporal desalineada** (B-03). El backtest usa el último snapshot antes
   del comienzo, tanto como precio de entrada como ancla no-vig; producción decide a
   las 11:00 con el consenso de apertura. El propio código lo documenta
   (`calibration/data.py:3-7`). El sesgo va en la dirección desfavorable: el
   resultado real esperado es **peor** que el del backtest.
3. **Data snooping en los parámetros de riesgo** (B-04). `max_plausible_edge`,
   `uncertainty_penalty`, `market_shrink`, `min_edge` y `max_stake_pct` se eligieron
   maximizando ROI sobre el mismo histórico capturado que después se llama ventana
   de test; `_freeze_on_train` congela solo los de rating. El "OOS" es OOS para los
   ratings, in-sample para el riesgo.
4. **`tilt_scale` sobreajustado a train** (B-18): argmin crudo del grid sin gate de
   muestra ni holdout, a diferencia de `elo_home_adv` y `dc_rho`.
5. **Sesgo de supervivencia en la cobertura** (B-20). Declarado en el código: solo
   eventos con snapshot capturado. Y la captura de cierre se gasta solo en ligas con
   picks abiertos, así que los eventos con mejor cobertura de cierre son
   precisamente los que el sistema eligió apostar.
6. **Conclusiones in-sample presentadas en negrita** (B-12). `patterns.py:178-188`
   publica `best = bm.iloc[0]` como "Mercado con mayor tasa de acierto": el argmax
   de docenas de comparaciones, sobre el histórico completo, con los parámetros
   sintonizados sobre ese mismo histórico, sin corrección ni intervalo.

## 8. Tamaños de muestra e incertidumbre

**No existe ninguna implementación de incertidumbre en el repositorio.** Búsqueda de
`bootstrap|confidence|_interval|wilson|binomtest|std_err` en `src/` y `scripts/`: cero
resultados. `calibration/metrics.py` expone Brier, log-loss, tabla de fiabilidad y ECE,
todos como puntos estimados.

Todos los gates son umbrales duros de `n` sin banda: 15 (segmentos), 30 (CLV gate),
30 (degradación), 30 (auto-promoción), 200/80 (tuning).

Caso más agudo: `segments.py:155-159` marca "sobreconfianza" con `|gap| >= 0.07` a
`n >= 15`. El error estándar de una proporción con n=15 es ≈0.13: **el umbral está
por debajo del ruido muestral**. Y se evalúan 4 dimensiones × (liga × mercado)
segmentos sin ningún control de comparaciones múltiples.

Consecuencia directa: con 2 días de producción en modo precisión, **cualquier hit
rate observado hoy es indistinguible del azar**. No puedo confirmar ningún hit rate
del modo precisión.

## 9. Leakage

**No se detectó leakage en el camino de calibración ni en el de ratings.**
Verificado positivamente:

- Elo, team scoring, park y starters actualizan **solo con resultados previos**
  (`base.py:38-42`, `team_scoring.py:40-62`).
- `_merge_results` ordena cronológicamente y deduplica con tolerancia de ±1 día para
  no contar dos veces el mismo partido por el desfase UTC/local; los scores recientes
  se usan solo en memoria y no se persisten, así que ese desfase no contamina el store.
- El target del calibrador es pre-blend y serve-anchored; las cuotas de cierre no
  entran por defecto.
- El backtest excluye deliberadamente el entrenamiento del calibrador
  (`roi_engine.py:12-14`).

Riesgo residual no de leakage sino de **contaminación metodológica**: el data
snooping de B-04 y la selección in-sample de B-12/Q-12 producen el mismo efecto
práctico (optimismo) por otra vía.

## 10. Riesgo

- **Shadow mode: verificado sin ruta de escape en el código.** Un solo
  `BetCandidate(` en todo el repo, `_zero_stake_flag` con precedencia correcta
  (shadow antes de clv_gate), la revalidación solo baja stakes, ambos caps solo
  escalan `stake > 0`. El punto débil no era la ruta de stake sino la **resolución
  del flag** (B-08, fail-open), ya corregida.
- **Agujero post-shadow corregido** (B-06): banca negativa producía stake negativo,
  y `settle.py:61` grada una pérdida como `pnl = -stake`, es decir **positivo**,
  realimentando el ledger con ganancias falsas. La rama por edge estaba cubierta por
  Kelly; el stake plano no pasaba por ahí.
- **El modo precisión elude tres controles de riesgo** porque sobrescribe el
  resultado de Kelly: el filtro de cuota degenerada (B-05, **corregido**), la
  penalización por mercado delgado (`low_book_penalty`, `min_books_for_consensus`)
  y la penalización por discrepancia modelo-mercado (Q-07, pendiente de decisión).
  Un h2h con `books_count = 1` genera pick a stake pleno, y `fair` —el 50% del
  criterio— puede venir de un solo libro.
- **Sin kill switch ni límite de drawdown con enforcement** (B-15): `_max_drawdown`
  se calcula y solo se publica.
- **Exposición sobre banca no comprometida** (B-16): `realized_pnl` suma solo
  liquidadas; los picks en vuelo no se descuentan.
- **El monitor de degradación puede apagar el único mercado habilitado** (B-07):
  juzga por ROI (`roi_pause: -0.15`) sobre una probabilidad que ya no decide
  (`estimated_probability` en lugar de `calibrated_probability`), y el modo precisión
  produce ROI plano estructuralmente negativo. La histéresis exige `roi_flat >= -0.05`
  para reanudar, umbral que el modo precisión probablemente nunca alcance.
  **No puedo confirmar** si ya se disparó: no leí `degradation_pause.json`.

## 11. Resumen: qué está demostrado y qué no

**Demostrado (verificable ejecutando el repositorio):**
- La matemática de cuotas, de-vig e implied probability es correcta.
- El split temporal de calibración es correcto y no filtra información futura.
- El walk-forward de ratings es real.
- Shadow mode fuerza stake 0 y no hay ruta de código que lo eluda.
- El modelo h2h está sobreconfiado en la banda relevante (medido, tabla §4).
- No existe calibrador h2h, luego el umbral no se aplica a una probabilidad calibrada.
- Los picks de precisión seleccionan favoritos con cuotas donde el punto de
  equilibrio supera la probabilidad estimada.

**No demostrado. No puedo confirmar esto:**
- Que el modo precisión alcance el 70% de aciertos, ni ningún otro hit rate.
- Que el sistema tenga ventaja predictiva sobre el mercado en cualquier liga o mercado.
- Que el −5.32% de ROI OOS sea representativo de la política vigente (no lo es:
  mide otra regla).
- Que la calibración mejore la selección (los calibradores existentes son de totals
  y el modo precisión no los usa).
- La magnitud del sesgo de la no-vig sintética (Q-19).
- El hit rate realizado por banda: la muestra es de 2 días.

**Requisito mínimo antes de considerar dinero real** (no una recomendación de
hacerlo, sino la condición sin la cual la pregunta no es respondible): un backtest
de la regla vigente, anclado a la apertura, con hit rate y `gap` por banda,
intervalo de confianza que excluya el umbral, y parámetros de riesgo congelados
fuera de la ventana de test.
