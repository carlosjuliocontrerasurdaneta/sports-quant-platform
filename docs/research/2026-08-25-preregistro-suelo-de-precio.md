# Pre-registro — suelo de probabilidad implícita como filtro de picks

**Fecha:** 2026-08-25. Escrito **antes** de re-medir sobre datos nuevos. Deriva de
un hallazgo **post-hoc** de la auditoría integral del 2026-08-25 (bitácora del
día). Precedente metodológico: KI-020 (criterio del gate intradía, pre-registrado
antes de mirar el reparto de signos).

## Estatus honesto de la observación

Lo que sigue es una **hipótesis generada mirando los datos**, no evidencia. Se
pre-registra precisamente porque no puede usarse tal cual: el mismo barrido que
la produjo probó ~20 combinaciones de umbral, así que el mejor punto está
sesgado al alza por construcción.

Observación (misma muestra que la generó, `n = 13.861`, 1.200 eventos):

| filtro | n filas | ROI plano | IC95 clusterizado |
|---|---:|---:|---|
| `min_edge ≥ 0` (regla actual) | 2.769 | −0,1102 | [−0,2002, −0,0145] |
| `min_edge ≥ 0` **y** `p_novig ≥ 0,35` | 2.218 | −0,0624 | [−0,1558, +0,0291] |
| `min_edge ≥ 0,08` | 813 | −0,2385 | [−0,4096, −0,0536] |
| `min_edge ≥ 0,08` **y** `p_novig ≥ 0,35` | 518 | −0,1208 | [−0,3197, +0,0772] |

Mecanismo propuesto: el error de probabilidad del modelo es aproximadamente
uniforme en la escala de probabilidad, pero su **coste en ROI escala con el
precio**. En el quintil de precio más largo (`p_novig ≈ 0,24`) el tercil de mayor
desacuerdo modelo-mercado rindió **−31,5%** contra **+8,4%** del tercil menor;
dentro de los quintiles centrales no aparece un patrón monótono. Es decir: no es
que el modelo acierte mejor en favoritos, sino que **se equivoca más barato**.

## Hipótesis registrada

> Restringir los picks a `implied_probability_novig ≥ 0,35` **reduce la pérdida
> de ROI plano** frente a la regla vigente, sobre datos que no participaron en su
> descubrimiento.

**Lo que la hipótesis NO afirma, y no debe leerse como si lo afirmara:**

- **No afirma rentabilidad.** El mejor punto observado es −6,2%. La hipótesis es
  sobre **reducir pérdida**, no sobre ganar. Ningún resultado de este experimento
  puede presentarse como evidencia de que el sistema gana dinero.
- **No afirma que el modelo tenga ventaja.** El agregado modelo-vs-mercado sigue
  a favor del mercado (Brier diff +0,00248, IC95 [+0,00051, +0,00444]) y el
  `market_shrink` óptimo walk-forward es 1,00 en los cuatro cortes.
- **No es un cambio de modelo**, sino de la regla de selección.

## Ventana y muestra

- **Datos:** filas del stream servido (`data/calibration/graded_*.csv`) con
  `game_date` **estrictamente posterior a 2026-08-25**. Las filas usadas para
  generar la hipótesis quedan excluidas por construcción.
- **`n` mínimo:** 800 filas graduadas y **≥ 250 eventos distintos** en el brazo
  con filtro. Por debajo no se evalúa; se espera.
- **Sin re-barrido de umbral.** El umbral queda **congelado en 0,35**. Si al
  re-medir otro valor luce mejor, es información para una hipótesis futura, no
  para esta.

## Métrica primaria y umbral de decisión (fijados antes de mirar)

- **Primaria:** `Δ = ROI_plano(con suelo) − ROI_plano(sin suelo)`, sobre el mismo
  conjunto de picks candidatos, con **IC95 por bootstrap agrupado por evento**
  (`sqp.evaluation.bootstrap.cluster_bootstrap_ci`, ≥ 3.000 réplicas, seed 42).
- **ACEPTAR** si `Δ > 0` **y el IC95 de `Δ` excluye el cero**. Un punto estimado
  favorable con IC que cruza cero es **RECHAZO**, no "prometedor".
- **RECHAZAR** en cualquier otro caso, incluida muestra insuficiente al cierre de
  la ventana.
- **Secundaria, no decisoria** (solo para el informe): número de picks retenidos,
  hit rate, y que la escalera de `min_edge` bajo el suelo no sea más negativa que
  sin él.

## Falsación

La hipótesis queda refutada si `Δ ≤ 0`, o si `Δ > 0` con IC que cruza cero. Se
registrará el resultado **sea cual sea**, en `docs/research/` y en la bitácora,
igual que se hizo con `home_scoring_bonus` (RECHAZADO) y con el momentum de línea
(NO CONFIRMADO).

Contraprueba obligatoria antes de aceptar: comprobar que el efecto **no es solo
composición de precio**. Se re-evalúa `Δ` dentro de cada quintil de `p_novig`
por separado; si el efecto desaparece al condicionar, lo que se midió es el sesgo
favorito-longshot y no el filtro.

## Ejecución y frontera reversible

- Se mide con `scripts/model_vs_market_report.py --price-floor 0.35`, que ya
  produce las dos escaleras (con y sin suelo) y **no consume cuota de API**.
- **No se despliega nada al pre-registrar.** `shadow_mode` sigue en `true`, los
  stakes en 0 y `configs/default.yaml` sin tocar.
- Una eventual adopción exigiría, además de ACEPTAR: aprobación explícita del
  operador, un parámetro nuevo en `configs/default.yaml` con su comentario del
  efecto **compuesto** (lección F-05) y su propio test de propiedad.

## Riesgo declarado

Aun aceptándose, el efecto medido lleva el ROI de −11% a −6%, que sigue siendo
**pérdida**. El valor de este experimento es **acotar dónde vive el daño**, no
abrir una vía de rentabilidad. Con la evidencia de hoy —seis mediciones negativas
independientes— la salida más probable de este pre-registro es un rechazo o una
aceptación irrelevante para el fin último, y conviene tenerlo escrito antes de
mirar.
