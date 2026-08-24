# Pre-registro — alinear el objetivo de calibración con la prob servida (`_p_adj`)

**Fecha:** 2026-08-24. Escrito antes de implementar. Deriva del análisis del sesgo
train/serve (bitácora 2026-08-24). Opción A elegida por el operador.

## Hipótesis y su uso

Al servir, `_decision_probability` calibra `cal(_p_adj)` (prob ajustada por
features, pre-shrink), pero el entrenamiento ajusta el calibrador sobre la columna
`model_probability` (cruda). Cuando `Σajustes ≠ 0` el calibrador se **aplica fuera
del dominio en que se entrenó**. Medido: solo `streak_coef=0.01` activo, `|Σadj|`
media 0.0011, cola hasta 0.10 en h2h/spreads. Bajo impacto hoy, **riesgo latente**
si se activan más coefs.

**Opción A:** entrenar el calibrador sobre la **misma** cantidad que recibe al
servir (`_p_adj`), persistiéndola como columna nueva `adjusted_probability`. El
serve ya calibra `_p_adj` → no se toca la matemática del serve; solo se alinea el
target de entrenamiento.

**Uso:** restaurar consistencia train==serve en la calibración, que decide
`calibrated_probability` (gate) y la prob reportada.

## Cambio (frontera reversible)

- `served_store.COLUMNS`: añadir `adjusted_probability` (unión de columnas
  auto-sana CSVs viejos; decisión 2026-06-21/07-01).
- `daily.py` (stream servido): persistir `adjusted_probability = round(_p_adj, 4)`.
  **`model_probability` se conserva cruda** (la usa el gate de predicción como
  "modelo puro", decisión 2026-08-17 — NO se sobrescribe).
- `calibration/data.py`: entrenar con `prob_col="adjusted_probability"`, con
  **fallback fila a fila a `model_probability`** para filas históricas sin la
  columna (donde además `_p_adj ≈ model` porque Σadj era ínfimo).
- Reversibilidad: `auto_promote: false` (decisión 2026-06-30). Restagear NO cambia
  calibradores vivos; la promoción sigue siendo humana. Revertir = volver
  `prob_col` a `model_probability`.

## Métrica primaria y umbral (fijados antes de medir)

Sobre la historia graduada real (served ∪ settled, dedup), split temporal:

- **Primaria:** ECE OOS de la `calibrated_probability` reblendeada
  `(1−s)·cal(·)+s·fair`, target nuevo (`adjusted_probability`) vs actual
  (`model_probability`).
- **Umbral de aceptación:** ECE OOS **no empeora** más de `+0.002` en ningún
  (liga, mercado) con `n ≥ 200`, y Brier OOS **no empeora** más de `+0.001`.
- **Expectativa registrada:** dado que Σadj es ínfimo hoy, el delta será
  **≈ 0**. El cambio se justifica por corrección estructural y prevención del
  riesgo latente, **no** por mejora medible inmediata.

## Regla de decisión

- **STAGE + proponer** si no hay regresión sobre el umbral. **No se promueve**;
  la promoción requiere aprobación humana explícita y su propio gate (Brier/ECE).
- **RECHAZAR** (revertir `prob_col`) si cualquier corte regresa sobre el umbral —
  indicaría que calibrar `_p_adj` es peor que calibrar la prob cruda, en cuyo caso
  la vía correcta es la **Opción B** (restaurar `cal(p_model)` en el serve).

## Guardarraíl operativo

No activar más coeficientes de ajuste (rest, form, h2h, margin, …) hasta que este
cambio esté promovido; de lo contrario el sesgo train/serve crece invisible.

## Lo que NO promete

No promete mejorar la calibración de forma medible hoy (Σadj ínfimo). No promete
edge. Es higiene estructural con validación OOS de no-regresión.
