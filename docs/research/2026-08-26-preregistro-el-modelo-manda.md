# Pre-registro — ¿puede el modelo mandar también en el stake?

**Fecha:** 2026-08-26. Escrito **antes** de medir el efecto. Lo único que se ha
calculado sobre los datos hoy son **parámetros de nuisance** (número de eventos
por segmento y desviación típica de la diferencia pareada), necesarios para el
cálculo de potencia. **Ninguna media, ninguna diferencia y ningún signo se han
mirado.** Ese es el compromiso que este documento sella.

## La pregunta

El operador formuló una tesis: **«el modelo manda, el mercado benchmarkea»**.

La frase solo tiene contenido donde modelo y mercado **discrepan**: cuando
coinciden, no dice nada. Operativamente significa una cosa concreta y medible:
llevar `market_shrink` de 0,5 a **0** — dejar de mezclar la probabilidad del
modelo con la del mercado sin vig — de modo que la probabilidad servida sea la
del modelo y nada más.

Este documento fija, por adelantado, **qué tendría que ocurrir para que eso se
despliegue**, y qué se hará si no ocurre.

## Lo que ya está medido (y va en contra)

Un pre-registro que ignore la evidencia previa es teatro. Esta es la que hay:

| Medición | Resultado | Fecha |
|---|---|---|
| Brier modelo vs mercado, muestra completa | modelo peor por **+0,00248**, IC excluye el cero | 2026-07-31 |
| Escalera de `min_edge` (= quedarse solo con el desacuerdo) | hit rate 0,430 → 0,301; ROI −11,0% → −23,9%; **monótono**; IC95 excluye el cero en 3 de 5 escalones | 2026-08-25 |
| `market_shrink: 0` sobre picks liquidados | 1.824 picks más; ROI −3,02% → **−10,85%** | 2026-08-26 |
| Cap de plausibilidad (= cortar el desacuerdo extremo) | lo que corta rinde **−22,6%**; lo que deja pasar, −5,6%; barrido monótono | 2026-08-26 |

También está medido lo favorable, y no es poco: el modelo **le gana a la moneda**
(0,25000) y **a la tasa base** (0,24829) con Brier 0,23261 e IC que excluyen el
cero, y cubre el **87,5%** de la distancia entre la moneda y el mercado (0,23013).

**La lectura honesta:** el modelo estima bien; lo que no está demostrado es que
estime *mejor que el mercado*. Y la distancia a la rentabilidad no es 0,00248
sino **0,00248 más el vig**: empatar con el mercado sigue siendo perder.

Este pre-registro existe porque la tesis del operador merece una prueba limpia y
falsable en vez de quedar zanjada por acumulación de indicios indirectos. Nada de
lo anterior mide *directamente* el Brier del modelo **calibrado y sin mercado**
sobre el stream insesgado. Eso es lo que se va a medir.

## Qué se compara exactamente

**Muestra.** `data/calibration/graded_*.csv`: todas las caras con precio,
capturadas **antes** de cualquier filtro de stake. Es la muestra insesgada. Las
apuestas liquidadas NO sirven aquí: son una selección adversa (solo pasa lo que
superó `min_edge`, que es justo la población donde ya sabemos que el modelo
rinde peor).

**Columna del modelo — decisión crítica.** Ninguna columna almacenada contiene lo
que hay que medir, así que se **reconstruye**:

```
p_decision = (1−s)·cal(p_model) + s·fair      con s = 0,5 (verificado en configs/default.yaml)
⇒  p_cal   = 2·calibrated_probability − implied_probability_novig
```

Verificado hoy: la reconstrucción cae dentro de [0,1] en **13.999 de 13.999**
filas, así que no hay recorte que distorsione.

Por qué **no** las otras dos candidatas:

- `estimated_probability` **contiene el mercado** (es la mezcla al 50%).
  Compararla contra el no-vig sería circular y sesgaría el test a favor.
- `model_probability` es el modelo **sin calibrar**. Es un rival de paja: un
  despliegue real de `market_shrink: 0` serviría `cal(p_model)`, no `p_model`.
  Usarla haría el test injustamente duro con la tesis del operador.

`p_cal` es exactamente lo que se serviría. Es la comparación justa.

**Columna del mercado.** `implied_probability_novig`, el consenso sin vig.

**Métrica primaria.** Diferencia **pareada** de Brier sobre las mismas filas:

```
diff = Brier(p_cal) − Brier(fair)        negativo = el modelo gana
```

**Intervalo.** Bootstrap agrupado **por evento** (`cluster_bootstrap_ci`,
n_boot=10.000, seed=42). El stream guarda los dos lados de cada mercado y están
perfectamente correlacionados; tratarlos como independientes fabricaría
significancia. La unidad de muestra es el **evento**, no la fila.

**Exclusiones:** `result ∉ {win, loss}` (pushes y voids no tienen resultado
binario que puntuar) y filas sin alguna de las dos probabilidades.

## Potencia — calculado HOY, antes de medir el efecto

Desviación típica de la diferencia pareada **por evento** y mínimo efecto
detectable al 95% (`MDE = 1,96·DE/√N`):

| segmento | eventos | DE por evento | MDE |
|---|---:|---:|---:|
| **global (todos)** | **1.214** | 0,0744 | **±0,00418** |
| mlb h2h | 477 | 0,0591 | ±0,00531 |
| mlb spreads | 477 | 0,0709 | ±0,00637 |
| mlb totals | 465 | 0,0774 | ±0,00703 |
| wnba h2h | 130 | 0,0708 | ±0,01217 |
| wnba spreads | 130 | 0,0895 | ±0,01539 |
| wnba totals | 130 | 0,0919 | ±0,01579 |
| tennis wta cincinnati h2h | 104 | 0,1196 | ±0,02299 |
| tennis atp cincinnati h2h | 96 | 0,1087 | ±0,02175 |
| tennis atp canadian h2h | 85 | 0,0990 | ±0,02104 |
| tennis wta canadian h2h | 83 | 0,1029 | ±0,02215 |
| mls h2h | 61 | 0,0453 | ±0,01138 |
| mls totals | 61 | 0,0474 | ±0,01190 |
| mls spreads | 60 | 0,0886 | ±0,02241 |
| brasileirao h2h | 43 | 0,0378 | ±0,01130 |
| brasileirao totals | 43 | 0,0510 | ±0,01524 |
| brasileirao spreads | 41 | 0,0838 | ±0,02565 |

**Este es el hallazgo más importante del documento, y llega antes de medir nada:
la muestra actual NO puede resolver la pregunta.** El MDE global (0,00418) es
**1,7 veces mayor** que la brecha que creemos que existe (0,00248). Ni siquiera
el segmento más profundo (mlb h2h, 477 eventos) baja de 0,0053.

Medir hoy garantizaría un «no significativo» **por falta de muestra**, y ese
resultado es exactamente el que se puede malinterpretar como «el modelo empata
con el mercado». No empata: no lo sabemos. **Por eso el test no se ejecuta hoy.**

### Efecto mínimo de interés y N requerido

Se fija **δ = 0,0025** de Brier como efecto mínimo de interés. Justificación: es
la magnitud de la brecha actualmente estimada **a favor del mercado**; un modelo
que aspire a *mandar* tiene que, como mínimo, revertir una brecha de ese tamaño.
Es una elección simétrica y anclada en un número ya publicado, no un umbral
elegido para que salga lo que queremos.

`N = (1,96·DE/δ)²`, con acumulación medida de **24,3 eventos/día** (1.214 en 50
días, 2026-07-07 → 2026-08-26):

| test | N requerido | faltan | fecha estimada |
|---|---:|---:|---|
| **global (primario)** | **3.402 eventos** | 2.188 | **≈ 2026-11-24** |
| mlb h2h (secundario) | 2.147 eventos | 1.670 (a 9,5/día propios) | fuera de temporada MLB — **probablemente inalcanzable en 2026** |

La estimación de fecha es **conservadora a la baja**: entre septiembre y
noviembre arrancan NFL, NBA, NHL y NCAAF, así que la tasa real subirá. La fecha
se revisará contra los eventos realmente acumulados, no contra el calendario.

## Hipótesis y regla de decisión

**H₀:** `Brier(p_cal) − Brier(fair) = 0`. El modelo sin mercado iguala al
mercado.
**H₁ (la tesis del operador):** la diferencia es **negativa** — el modelo gana.

El contraste es **bilateral**; la decisión, **unilateral**: solo «modelo mejor»
cambia la política.

### Test primario

Se ejecuta **una sola vez**, cuando el stream graduado alcance **≥ 3.402
eventos** con `result ∈ {win, loss}`, sobre **todos** los segmentos agrupados.

- **PASA** si el IC95 bootstrap de `diff` está **enteramente por debajo de 0**.
- **FALLA** si el IC contiene 0 o está enteramente por encima.

### Test secundario (segmentos)

Solo se examinan los segmentos que alcancen **≥ 800 eventos** propios. Corrección
de multiplicidad por **Holm** sobre el número de segmentos elegibles, decidido
por el conteo real en el momento del test. Un segmento que pase Holm es
candidato aunque el global falle — pero solo ese segmento.

Sin esta corrección, examinar 17 segmentos al 95% produce ~1 falso positivo por
puro azar. Ese falso positivo se llamaría «el modelo manda en tenis WTA» y
costaría dinero real.

### Segunda puerta: ROI (necesaria, no suficiente)

Ganar en Brier es **necesario pero no suficiente** para tocar el stake. Un
segmento que pase la primera puerta debe además, sobre el mismo periodo y en
walk-forward:

- `market_shrink: 0` debe dar **ROI mayor** que `market_shrink: 0,5`,
- con IC95 bootstrap agrupado por evento que **excluya el cero**.

Motivo: el Brier premia la calidad de la probabilidad en todo el rango, pero el
dinero solo se juega donde el modelo discrepa lo bastante para superar `min_edge`.
Un modelo puede ser mejor en Brier global y peor justo en esa cola — y la
escalera de `min_edge` dice que esa es precisamente la cola donde falla.

**Ambas puertas deben pasar.** Cualquiera que falle → el mercado sigue mandando
en el stake.

## Qué cambia si pasa, qué se registra si no

**Si pasan las dos puertas**, para el segmento que las pase y solo para ese:
`market_shrink → 0`, en shadow durante 30 días antes de tocar stake real, con la
regla de salida vigente (`2026-08-16-preregistro-regla-de-salida.md`).

**Si falla**, se registra el resultado con su IC en
`docs/research/2026-11-XX-resultado-el-modelo-manda.md` y la tesis queda cerrada
**para esta temporada y esta configuración**. No se reabre cambiando el segmento,
la métrica ni la ventana después de ver el número: eso sería el mismo dragado que
este documento existe para impedir.

**Si el modelo sale significativamente PEOR**, se registra igual, y pasa a ser
argumento para *subir* `market_shrink` por encima de 0,5 — lo que exigiría su
propio pre-registro.

**En los tres casos el resultado se commitea.** No hay salida por la que este
documento no produzca un número público.

## Lo que NO prueba este pre-registro

- **No prueba rentabilidad.** Batir al mercado en Brier no implica ROI positivo:
  hay que batirlo por más que el vig. Esta prueba mide precisión, no dinero.
- **No cubre el sesgo de selección del propio feed.** Todo se mide sobre el mismo
  feed público de cuotas donde seis mediciones independientes no han encontrado
  ventaja.
- **No cubre mercados finos.** Con `casas < 10` el «consenso» son unas pocas
  opiniones y el no-vig es un patrón de medida pobre. Además, la única medición
  que tenemos ahí (el cap de plausibilidad) salió **en contra**. Los mercados
  finos son la única región donde la eficiencia del mercado es débil *a priori*,
  pero necesitan su propio pre-registro, no un carril en este.
- **La ventana es corta.** 50 días, un régimen deportivo (verano: MLB, WNBA,
  fútbol sudamericano, tenis). Que el resultado se sostenga al añadir NFL/NBA/NHL
  no está garantizado, y el test no lo comprueba.

## Amenazas a la validez, declaradas

1. **Redondeo.** Las columnas se almacenan a 4 decimales, así que `p_cal`
   reconstruida arrastra hasta ~1,5·10⁻⁴ de error. Es **dos órdenes de magnitud
   menor** que δ=0,0025; no afecta a la decisión, pero queda dicho.
2. **`s` debe seguir siendo 0,5.** Si `market_shrink` cambia antes del test, la
   reconstrucción deja de ser válida y el pre-registro debe reescribirse. Valor
   verificado hoy vía `Settings.load()`: **0,5**.
3. **Deriva del calibrador.** `cal()` se reentrena periódicamente, así que
   `p_cal` no proviene de una función fija a lo largo de la ventana. Es
   inevitable —refleja lo que realmente se sirvió— pero significa que el test
   evalúa **el sistema tal como opera**, no un modelo congelado.
4. **Acumulación no garantizada.** Si el flujo diario se interrumpe, N no se
   alcanza. En ese caso el test **no se ejecuta**; no se rebaja el umbral.

## Compromiso de ejecución

- Script: `scripts/model_vs_market_report.py`, con `model_col` apuntando a la
  `p_cal` reconstruida.
- Semilla **42**, `n_boot=10.000`, fijados aquí.
- El test se ejecuta **una vez**. Sin miradas intermedias, sin re-corridas con
  otra ventana, sin cambiar la métrica después de ver el resultado.
- Lo que se declara hoy y queda como registro: **eventos por segmento y DE de la
  diferencia pareada, nada más.**

---

Relacionado: [[2026-08-16-preregistro-regla-de-salida]],
[[2026-08-25-preregistro-suelo-de-precio]],
[[2026-07-02-calibrar-pmodel-puro-vs-blend]].
