# Resultado — suelo de precio `p_novig ≥ 0,35`

**Fecha:** 2026-09-19. Ejecuta el pre-registro
`docs/research/2026-08-25-preregistro-suelo-de-precio.md`.
**Veredicto formal de la primaria: ACEPTAR. Contraprueba obligatoria: NO
SUPERADA — el efecto es composición de precio (sesgo favorito-longshot), no
una propiedad del filtro.** Adopción: NO se adopta; ver «Qué se hace con esto».

## Por qué se ejecutó ahora

La ventana alcanzó hoy el mínimo endurecido el 2026-08-27 (800 picks únicos y
250 eventos en el brazo con filtro): **824 picks / 424 eventos** con
`game_date > 2026-08-25` (datos del 2026-08-26 al 2026-09-18). Se midió una
sola vez, con el umbral congelado en 0,35, sin re-barrer.

Medición: `scripts/research/measure_price_floor_preregistration.py` (nuevo;
solo lee `data/calibration/graded_*.csv`, no consume cuota ni escribe en
`data/` ni `configs/`). Una fila por pick (`one_row_per_pick`), candidatos
`estimated_edge ≥ 0`, IC95 por bootstrap agrupado por evento, 4.000 réplicas,
semilla 42.

## Resultado

| brazo | picks | eventos | hit rate | ROI plano | IC95 |
|---|---|---|---|---|---|
| sin suelo (`edge ≥ 0`) | 1.077 | 547 | 0,385 | **−17,80 %** | [−26,45 %, −9,22 %] |
| con suelo (`p_novig ≥ 0,35`) | 824 | 424 | 0,459 | **−11,25 %** | [−20,02 %, −2,23 %] |

**Δ = +6,56 pp, IC95 [+1,61, +11,47]** → excluye el cero → la primaria
**ACEPTA**.

Ambos brazos siguen en pérdida con IC que excluye el cero. La ventana nueva
rinde peor que la muestra que generó la hipótesis (−17,8 % frente a −11,0 %).

## Contraprueba (obligatoria antes de aceptar): NO superada

ROI por quintil de `p_novig` entre los candidatos:

| quintil | `p_novig` | n | ROI plano | IC95 | fracción en el brazo |
|---|---|---|---|---|---|
| Q1 | [0,012, 0,317] | 216 | **−40,3 %** | [−61,3 %, −15,6 %] | 0,00 |
| Q2 | [0,317, 0,455] | 215 | −17,9 % | [−34,0 %, −1,7 %] | 0,83 |
| Q3 | [0,456, 0,500] | 329 | −18,8 % | [−30,8 %, −6,7 %] | 1,00 |
| Q4 | [0,501, 0,505] | 101 | −23,2 % | [−42,2 %, −3,4 %] | 1,00 |
| Q5 | [0,505, 0,814] | 216 | +8,7 % | [−4,3 %, +21,5 %] | 1,00 |

- El único quintil donde el suelo actúa es Q2; **condicionado a Q2, Δ =
  +3,0 pp con IC95 [−4,7, +10,4] — cruza el cero**. El efecto desaparece al
  condicionar.
- Toda la ganancia viene de retirar Q1 entero: los *longshots* a los que el
  modelo declara edge rinden −40 %. Es la definición del sesgo
  favorito-longshot, y el pre-registro fijó por adelantado que en ese caso «lo
  que se midió es el sesgo favorito-longshot y no el filtro».

Conclusión conforme al diseño: **la primaria acepta y la contraprueba no**. No
hay aceptación limpia. Lo que sí queda establecido, y es lo útil, es **dónde
vive el daño**: el modelo sobreestima sistemáticamente la probabilidad de los
lados con `p_novig < 0,32` (asigna edge donde el mercado tiene razón), y ese
tramo concentra la peor pérdida del sistema.

## Secundaria (no decisoria)

La escalera de `min_edge` bajo el suelo sigue **invertida** (−11,2 % en
`≥ 0` → −21,1 % en `≥ 0,12`), aunque menos que sin suelo (−17,8 % → −36,0 %).
Confirma otra vez que el edge declarado es error de medida, y que el suelo
solo recorta el tramo donde ese error es mayor.

## Qué se hace con esto

- **No se despliega el suelo como filtro.** La contraprueba lo descalifica
  como «filtro con valor propio» y, aun aceptado, dejaría el ROI en −11 %:
  irrelevante para el fin último (estimar bien para ganar), como el propio
  pre-registro anticipó en «Riesgo declarado».
- **Se convierte en diagnóstico.** La pérdida del tramo `p_novig < 0,32`
  (−40 %) es un síntoma de calibración por *dirección del precio*: el modelo
  no es demasiado extremo, es demasiado plano en las colas. Cualquier
  hipótesis que salga de aquí (calibrador por banda de precio, prior hacia el
  mercado en longshots, revisar `market_shrink` en colas) es **post-hoc** y
  exige su propio pre-registro antes de medirse sobre datos nuevos.
- Q5 (+8,7 %, IC que cruza cero) **no se vende**: es un quintil, sin
  corrección por multiplicidad, y la escalera de `min_edge` dice que buscar
  «el tramo bueno» por precio es exactamente la clase de selección que hasta
  ahora ha perdido.

Regla de lenguaje: nada de lo anterior es evidencia de que el sistema gane
dinero. Es ROI realizado sobre muestra histórica y todo él negativo.
