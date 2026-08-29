# Resultado — objetivo de calibración `_p_adj` vs prob cruda

**Fecha:** 2026-08-29. Ejecuta el pre-registro
`docs/research/2026-08-24-preregistro-calibracion-train-serve.md`.
**Veredicto formal: ACEPTAR — pero la prueba no tiene potencia hoy.**

## Por qué se ejecutó ahora

El cambio de la Opción A estaba **implementado y vivo** desde el 2026-08-24
(`calibration/data.py` entrena con `prob_col="adjusted_probability"`), pero su
medición de no-regresión **nunca se había ejecutado ni registrado**. Es decir, el
entrenamiento llevaba cinco días corriendo sobre un objetivo cuya no-regresión no
se había verificado, contra lo que manda la propia regla de decisión.

Medición: `scripts/measure_calibration_target.py` (nuevo, solo lee datos
guardados, no toca el registro live ni consume cuota de API).

## Resultado

22 cortes (liga, mercado) evaluados; 4 con `n_val ≥ 200`. **Ningún corte regresa
sobre los umbrales** del pre-registro (ECE `+0.002`, Brier `+0.001`).

Pero todos los deltas son **exactamente 0,00000**. La causa no es que el cambio
sea neutro en un sentido interesante:

```
filas graduadas en la historia de entrenamiento : 14.639
con adjusted_probability != model_probability   :    161  (1,10%)
|dif| donde difieren                            : media 0,0367 · max 0,09
distribución temporal                           : las 161 son de agosto
```

La columna `adjusted_probability` solo empezó a persistirse el 2026-08-24, y para
todo lo anterior el proyector cae a `model_probability`. **En el 98,9% de las
filas los dos brazos reciben la misma entrada**, así que el delta es cero por
construcción, no por evidencia.

## Interpretación honesta

- **El criterio pre-registrado se cumple**: no hay regresión. Formalmente,
  ACEPTAR.
- **La prueba no puede distinguir**: con 1,10% de filas divergentes no tiene
  potencia para detectar ni una mejora ni un daño. Un veredicto favorable aquí
  confirma **ausencia de regresión**, no beneficio.
- Esto **coincide con lo que el propio pre-registro predijo**: «dado que Σadj es
  ínfimo hoy, el delta será ≈ 0. El cambio se justifica por corrección
  estructural y prevención del riesgo latente, **no** por mejora medible
  inmediata». El resultado no añade evidencia a favor; confirma que el cambio es
  inocuo con la configuración actual.
- Por tanto el cambio **se sostiene sobre el argumento estructural** (entrenar y
  servir sobre la misma cantidad), que es exactamente como se planteó.

## Qué NO se puede concluir

No se puede afirmar que calibrar `_p_adj` mejore la calibración. Tampoco que sea
equivalente en el régimen que importa: el desajuste train/serve crece con `Σadj`,
y hoy `Σadj` es ínfimo porque **solo `streak_coef = 0,01` está activo** de los
doce coeficientes de ajuste.

## Consecuencias operativas

1. **El guardarraíl sigue vigente y ahora se entiende mejor:** no activar más
   coeficientes de ajuste hasta que este cambio esté promovido. Es justo al
   activarlos cuando los dos objetivos divergen — y sólo entonces esta prueba
   tendría potencia.
2. **Re-ejecutar** `scripts/measure_calibration_target.py` cuando la fracción
   divergente sea material. El script imprime esa fracción en cada corrida, así
   que la falta de potencia es visible sin releer este documento.
3. No se promueve nada: la promoción sigue exigiendo aprobación humana explícita
   y su propio gate (Brier/ECE), como fija el pre-registro.

## Nota metodológica

La primera versión de la medición aplicaba cada calibrador a su propia columna de
entrenamiento y daba **RECHAZAR** (`mlb|h2h`, `d_ece = +0,0065`). Era incorrecta:
al servir, `daily._decision_probability` calibra **siempre** `_p_adj`, y lo único
que el pre-registro compara es el *objetivo de entrenamiento*. Aplicar cada brazo
a su propia columna medía un sistema coherente que nunca existió y convertía el
brazo «actual» en una ficción. Corregido: ambos brazos se aplican sobre
`adjusted_probability`.

Métricas de calibración sobre muestra histórica. No es una promesa de ganancia.
