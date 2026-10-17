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

## Addendum 2026-09-26 — cambio de régimen del modelo MLB (antes de ejecutar)

Desde el run del 2026-09-26, MLB sirve con `pitcher_bound: 0.05` (commit `49a6181`, orden del operador); hasta el 25/09 era 0.0. Las filas MLB servidas desde el 26/09 salen de ese modelo. Se registra **antes** de mirar ningún resultado del test. **No altera ningún criterio de este documento** y queda prohibido usarlo después para recortar o re-segmentar la ventana: el test evalúa el sistema tal como operó. Revisión independiente (Fable, 2026-09-26): no invalida el test; en `mlb|totals`, como mucho ~13 de 300 filas vendrán del modelo nuevo.

## Addendum 2026-09-26 (2) — descanso NBA activado (antes de ejecutar)

Desde el commit que activa `nba.rest_points_per_day: 0.795` (2026-09-26), el modelo NBA suma 0,795 puntos por día de diferencia de descanso (tope de 4) al margen esperado. Hasta entonces era 0. Pre-registro y resultado: `docs/research/2026-09-26-preregistro-descanso-basket.md` y `docs/research/2026-09-26-resultado-descanso-basket.md` (ACEPTA, dictamen de Fable: APTO CON CONDICIONES). Las filas NBA servidas desde ese commit salen de este modelo; hoy el gate no tiene cortes NBA y la temporada empieza a finales de octubre. Se registra **antes** de mirar ningún resultado del test. **No altera ningún criterio**, y queda prohibido usarlo después para recortar o re-segmentar la ventana.

## Addendum 2026-09-26 (3) — alias de nombres de equipo (antes de ejecutar)

Desde el commit que añade 69 alias en `configs/leagues/team_aliases.yaml` (13 ligas: ncaaf, brasileirao, bundesliga, chile, epl, laliga, ligamx, ligue1, mls, nba, seriea, ucl, uwcl), los partidos de equipos cuyo nombre en el feed de cuotas no casaba con el histórico (Hawai'i, LA Clippers, Internazionale, Atlético-MG, etc.) dejan de descartarse y entran en el stream servido y graduado. **El modelo no cambia; cambia la población de eventos.** K no cambia: los 52 cortes `liga|mercado` son los mismos y todos siguen en `muestra_insuficiente`. Revisión de Fable: no invalida el test. Se registra **antes** de mirar ningún resultado. **No altera ningún criterio**, y queda prohibido usarlo después para recortar o re-segmentar la ventana.

## Addendum 2026-09-30 — tilt_scale NHL activado (antes de ejecutar)

Desde el commit que activa `nhl.tilt_scale: 0.439` (2026-09-30; hasta entonces 0,9 de la familia hockey), el modelo NHL reparte las probabilidades con mucha menos dispersión: pendiente de calibración 0,45 → 0,97. Pre-registro y resultado: `docs/research/2026-09-29-preregistro-tilt-nhl.md` y `docs/research/2026-09-30-resultado-tilt-nhl.md` (ACEPTA 7/7; dictamen de Fable: APTO CON CONDICIONES). Cambian las `d` de `nhl|h2h` y `nhl|spreads`; `nhl|totals` no cambia. K no cambia. Los cortes NHL van por n = 5, graduados con 0,9: las filas NHL servidas desde este commit salen del modelo nuevo. Se registra **antes** de mirar ningún resultado del test. **No altera ningún criterio**, y queda prohibido usarlo después para recortar o re-segmentar la ventana.

## Addendum 2026-10-13 — unidad de puntuación (antes de ejecutar)

El texto original no fija la unidad de forma inequívoca. La verificación de la reconstrucción («13.999 de 13.999») se hizo sobre **filas servidas**, y el stream guarda una fila por día de horizonte (2,19x el 2026-08-27; 2,67x el 2026-10-12). Desde el 2026-09-04 (`f4e00f1`, KI-026(b), orden del operador), `score_model_vs_market` (`src/sqp/evaluation/model_vs_market.py:143`) colapsa con `one_row_per_pick` **antes** de puntuar y antes del bootstrap, porque sobre el stream inflado el estimador puntual sale sesgado: pondera cada pick por los días que pasó en el horizonte. Se fija, **antes** de mirar ningún resultado del test:

- **Unidad del test primario y de los secundarios:** una fila por pick, la **primera servida** (`one_row_per_pick`, clave `PICK_KEY = (event_id, market, line, selection)`). El estadístico es la media de `diff` por pick; el IC sigue agrupado por **evento** (seed 42, `n_boot = 10.000`).
- **Orden:** `result ∈ {win, loss}` y las dos probabilidades presentes se filtran **antes** de colapsar, igual que en `score_model_vs_market`. La reconstrucción `p_cal = 2·calibrated_probability − implied_probability_novig` se comprueba en [0,1] sobre los picks resultantes; un pick fuera de rango se excluye y se cuenta (no se recorta). Si la primera servida de un pick cae fuera de [0,1], se excluye el pick entero (todas sus filas, por `PICK_KEY`) antes de llamar a `score_model_vs_market`; no se sustituye por una servida posterior. Se informa el recuento.
- **El umbral no cambia:** N = 3.402 eventos. La DE por evento del cálculo de potencia se estimó sobre filas servidas; no se re-estima con la nueva unidad ni se recalcula N por ningún motivo. El MDE resultante es aproximado y así se declara.
- **Sensibilidad descriptiva, sin poder de decisión:** el mismo test sobre todas las filas servidas, sin colapsar. Si el veredicto difiere, se informan ambos y decide la unidad fijada aquí.
- **Ejecución:** `scripts/model_vs_market_report.py` no reconstruye hoy `p_cal`. La columna se añade al frame antes de llamar a `score_model_vs_market`; el cambio de código va aparte y no altera ningún criterio.

Transparencia: el informe periódico (`model_vs_market_report.py`, sección 1, `calibrated_probability`) publica el Brier de la mezcla al 50%, y por convexidad diff(p_cal) ≥ 2·diff(mezcla) fila a fila. Ese informe acota el resultado de este test desde antes de este addendum; la unidad se fija igual con independencia de esa cota y no se reabre por ella.

Mismo día, y sin efecto sobre el test: el párrafo «Unidades» de `scripts/model_vs_market_report.py` decía que la sección 1 puntuaba todas las servidas. Era obsoleto desde `f4e00f1` y se corrige. Las cifras de la sección 1 del informe del 2026-10-01 ya se calcularon por pick.

Coordinación: `2026-10-13-preregistro-peso-mercado-por-segmento.md` toma como T0 la fecha del commit que añade el resultado de este test y evalúa solo eventos posteriores. No altera ningún criterio de este documento. Queda prohibido usar este addendum para recortar o re-segmentar la ventana.

## Addendum 2026-10-13 (2) — especificación de ejecución (antes de ejecutar)

Diseño: Fable (rol de pre-registro). Escrito **antes** de mirar ningún resultado del test. Sobre los datos solo se ha contado (2026-10-13, lector propio sin mutación, sin calcular nada que dependa de `result` salvo el filtro win/loss): 47.341 filas graduadas, **todas** con `data_label == "real"`; 17.250 picks y **2.796 eventos** tras filtrar win/loss y probabilidades presentes y colapsar a la primera servida; 0 picks cuya primera servida tenga `generated_at ≥ start_time`; `event_id` no colisiona entre ligas (2.796 eventos por `event_id` y por `(league, event_id)`).

**No cambia ningún criterio ya fijado:** δ = 0,0025; N = 3.402 eventos; PASA/FALLA del primario por IC bootstrap; seed 42 y `n_boot = 10.000`; unidad por pick (addendum anterior); secundarios con ≥ 800 eventos y Holm; puerta de ROI necesaria. Este addendum solo fija lo que el texto dejaba abierto. Queda prohibido usarlo para recortar o re-segmentar la ventana.

### E1. Vehículo: script dedicado, no el informe periódico

- **Sustituye el vehículo** de «Compromiso de ejecución» y del punto «Ejecución» del addendum de unidad, no ningún criterio. `scripts/model_vs_market_report.py` es un informe periódico: si llevara `p_cal`, cada ejecución rutinaria mostraría el estadístico de este test antes de N, y eso es una mirada intermedia prohibida. **Ese informe no se toca y nunca reconstruye `p_cal`.**
- **Script:** `scripts/research/measure_el_modelo_manda.py`. Tests: `tests/research/test_measure_el_modelo_manda.py`. Lo implementa Sonnet según esta especificación; lo revisa Fable antes de la primera ejecución oficial de `--contar`. La revisión se registra en un addendum de implementación, como el Addendum 1 de tier A.
- Reutiliza, importándolos y sin copiarlos, `one_row_per_pick` y `PICK_KEY` (`src/sqp/evaluation/edge_information.py`), `score_model_vs_market` (`src/sqp/evaluation/model_vs_market.py`) y `cluster_bootstrap_ci` (`src/sqp/evaluation/bootstrap.py`). Registra el hash de blob de esos tres ficheros en HEAD y en disco.

### E2. Lectura sin efectos secundarios

- **Prohibido** llamar a `ServedStore.load_all_graded` o a `ServedStore._load`: ante un `ParserError`, `_load` renombra el fichero (cuarentena, `src/sqp/storage/served_store.py`, `_quarantine` y `_load`). Medir no puede mutar `data/`.
- **Lector propio con la misma semántica** que `load_all_graded`: recorre `data/calibration/graded_*.csv` en orden alfabético (no `demo/`), lee cada uno con `pd.read_csv` y **asigna `league` desde el nombre del fichero** (`graded_<liga>.csv`), sobrescribiendo la columna del CSV, igual que `load_all_graded`. Así los torneos de tenis son ligas distintas, como en la tabla de potencia. Concatena.
- **`data_label`:** se conservan solo las filas con `data_label == "real"` si la columna existe. `load_all_graded` **no** filtra (lo hace cada consumidor; el lector de tier A y los consumidores del gate sí filtran). Hoy el filtro es inerte: 47.341 de 47.341 filas son reales. Se cuentan las excluidas. Si alguna vez hay más de 0, se informa además el primario sin el filtro, como sensibilidad sin poder de decisión.
- Un fichero ilegible, vacío o corrupto **no se toca**: se omite y se informa. `--medir` **aborta** si una liga listada no se puede leer. Una liga que solo trae cabecera se informa como vacía y no aborta (como tier A, Addendum 1 §4).
- El mismo lector, con `served_*.csv`, se usa solo para el recuento informativo de picks sin graduar (E4).

### E3. Qué es un pick válido y qué es un evento

Orden único y vinculante, el del addendum de unidad, sobre el frame del lector:

1. `result ∈ {win, loss}`. Fuera `push`, `void`, `half_win` y `half_loss`, y cualquier otro valor. Todos se cuentan por valor.
2. `calibrated_probability` e `implied_probability_novig` presentes y finitas. Las ausentes se cuentan.
3. Colapso con `one_row_per_pick` (primera servida por `PICK_KEY`).
4. `p_cal = 2·calibrated_probability − implied_probability_novig` sobre la fila resultante. Si `p_cal ∉ [0,1]`, se excluye el pick entero (todas sus filas, por `PICK_KEY`), se cuenta y no se recorta ni se sustituye por otra servida. La comprobación no depende de `result`.
5. **Corte temporal (E4):** el pick entra solo si el `generated_at` de **esa** primera servida es ≤ T1.
6. Lo que queda es la **población medida**. **Evento** = `event_id` distinto con al menos un pick en ella. **n** = número de eventos. El clúster del bootstrap y del SE es `event_id`, el mismo que usa `score_model_vs_market`.

No hay más exclusiones. La lista del texto original es cerrada (resultado binario y las dos probabilidades), así que **no** se añade filtro pregame ni de liga. Las primeras servidas con `generated_at ≥ start_time` o `start_time` ilegible se **cuentan e informan**, sin excluirlas (hoy, 0).

Nota: si una liga o mercado no tiene calibrador, `calibrated_probability` es la mezcla sin calibrar y `p_cal` resulta ser `p_adj`. Es exactamente lo que se serviría con `market_shrink: 0` (`_decision_probability`, `src/sqp/pipeline/probabilities.py`), así que no se excluye.

### E4. Disparo por recuento, margen de liquidación y T1

- El texto original no fijaba margen. Se fija uno de **14 días**, igual que en tier A (2 × p90 de latencia generación → liquidación del graduado, 7,0 días, medido el 2026-10-02). Sin margen, la cola reciente de la muestra estaría sesgada hacia lo que liquida rápido (un partido de MLB frente a un torneo de tenis). El margen solo retrasa el disparo, **no rebaja N**: los 3.402 eventos se exigen dentro de la ventana con margen. Coste: unas dos semanas. Se acepta.
- **`--contar`** (modo por defecto, repetible): instante de ejecución E (UTC), T1 candidato = E − 14 días, aplica E3 con ese T1 y añade **una** línea JSON a `docs/research/2026-08-26-preregistro-el-modelo-manda.contar.jsonl` (append-only; nunca se reescribe ni se borra una línea; se commitea tras cada ejecución). Campos: E, HEAD, H_MM (commit que añadió este documento: `git log --diff-filter=A --format="%H %cI" -- docs/research/2026-08-26-preregistro-el-modelo-manda.md`), T1 candidato, `n` eventos, picks, `n` eventos sin corte (informativo), eventos por segmento `league|market` y lista de segmentos con ≥ 800 eventos, recuentos de cada exclusión de E3, picks servidos con primera servida ≤ T1 y `start_time` ≤ T1 que no aparecen en el graduado («sin graduar»), el chequeo de `s` (E7) y SHA-256 y filas de cada CSV leído. **Nunca** imprime ni escribe Brier, `diff`, aciertos, `p` medias, ROI, z ni p-valores. Admite `--no-log` (diagnóstico, no cuenta para fijar T1).
- Frecuencia recomendada: semanal mientras `n < 3.000`, y cada 2–3 días a partir de ahí.
- **Fijación de T1:** la **primera** línea del registro con `n ≥ 3.402` fija **T1 = E − 14 días** de esa línea. Se escribe en un addendum commiteado a este documento con dos líneas literales: `T1 fijado = <ISO-8601>` y `commit del registro = <sha>`. Ejecuciones posteriores de `--contar` siguen anotándose y no mueven T1.
- **`--medir --t1 <ISO>`**, una sola vez: lee el addendum y el registro con `git show HEAD:`, comprueba que el T1 pasado coincide (como instante) con el del addendum y con la primera línea del registro que cruzó 3.402, que el commit citado contiene esa línea, y que `n(T1) ≥ 3.402` con los datos del momento. Comprueba también E7. Si algo falla, **aborta sin calcular nada** de lo que depende de `result`. Re-ejecutar solo se permite por un fallo técnico que impida producir el informe.

### E5. Primario y secundarios (Holm)

**Primario** (sin cambios, solo su mecánica): se añade al frame de E3 la columna `p_cal` y una constante `_global`, y se llama a `score_model_vs_market(d, by=["_global"], model_col="p_cal", market_col="implied_probability_novig", n_boot=10000, seed=42)`. Como `d` ya está colapsado, el colapso interno es idempotente. **PASA** si `brier_diff_hi < 0`. **FALLA** en otro caso. Si `brier_diff_lo > 0`, se registra además como «modelo PEOR» (párrafo correspondiente del texto original).

**Secundarios.** El texto original fija Holm, pero no cómo se obtienen los p-valores. Se fija:

- **Segmento** = `league|market`, con `league` del nombre del fichero (E2). Es la segmentación de la tabla de potencia y el `by` por defecto de `score_model_vs_market`.
- **Elegible** si tiene **≥ 800 eventos** en la población medida (E3, con T1). m = número de elegibles, decidido por el recuento en `--medir`. Si m = 0, no hay secundarios y se dice.
- **p-valor:** z bilateral con error estándar robusto por clúster de **evento**, CR1, como en tier A §3.1 (que agrupa por día; aquí se agrupa por evento porque es la unidad de remuestreo fijada en este documento). Con `d_i = (p_cal,i − y_i)² − (fair_i − y_i)²` sobre los n picks del segmento y G eventos:

      D̂ = (1/n)·Σ d_i      SE² = G/(G−1) · Σ_g (Σ_{i∈g} (d_i − D̂))² / n²      z = D̂/SE      p = 2·Φ(−|z|)

- **Holm** a α = 0,05 de familia sobre los m elegibles: se ordenan los p ascendentes y se rechaza el j-ésimo (j = 1…m) mientras `p_(j) ≤ 0,05/(m − j + 1)`; al primer no-rechazo se para. Un segmento **pasa la primera puerta** si se rechaza **y** `D̂ < 0`. Si se rechaza con `D̂ > 0`, se registra como «modelo PEOR en el segmento».
- **Independencia del primario:** los secundarios se calculan y se deciden **siempre**, pase o no el primario. Es lo que dice el texto («candidato aunque el global falle»). El primario no entra en la familia de Holm: así lo diseñó el texto original y no se cambia.
- Descriptivo, sin poder de decisión: por cada segmento elegible, también el IC bootstrap de `score_model_vs_market` (seed 42, 10.000). Si su clase (IC < 0, contiene 0, > 0) no coincide con el veredicto de Holm, se marca como frágil en el informe.

### E6. Segunda puerta: ROI

Se aplica **solo** a las unidades que pasaron la primera puerta: la global si pasa el primario, y cada segmento que pase Holm con `D̂ < 0`. Sobre la **misma población** de picks de esa unidad (E3). Si ninguna pasa, no se calcula.

- **Dos políticas sobre los mismos picks:** `p_0,5 = calibrated_probability` (lo servido) y `p_0 = p_cal`. Cuota: `price_decimal` (mediana del consenso guardada en la fila). `execution_price` no decide; si existe, se informa aparte.
- **Regla de apuesta, la del modo `edge` del pipeline** (`src/sqp/pipeline/daily.py`: `adjusted_edge` → `kelly_fraction_stake` → tope de plausibilidad), con **literales congelados aquí** e iguales a `configs/default.yaml` en este commit. El script no los lee de ninguna configuración:
  - `e = p·cuota − 1` (EV bruto);
  - `gap = |p − implied_probability_novig|`; `pen = 0,35·gap + (0,02 si gap > 0,06) + (0,015 si books_count < 2)`; `e_adj = e − max(0, pen)`; `p_eff = (e_adj + 1)/cuota`;
  - **apuesta** si `0 < p_eff < 1`, `cuota > 1`, `e_adj ≥ 0,02` (`min_edge`) **y** `e ≤ 0,075` (`max_plausible_edge`).
  - Las penalizaciones por movimiento de línea, velocidad y dispersión de casas valen 0 en la configuración vigente, así que la regla se reproduce con las columnas guardadas. Si el valor efectivo de alguna difiere de 0 al medir, se informa como dato y no cambia la regla.
- **Stake plano de 1 unidad**, no Kelly: el Kelly depende de la banca y pondera el resultado por el tamaño de la apuesta. PnL por pick apostado: `cuota − 1` si gana, `−1` si pierde. `ROI_s = Σ PnL / nº de picks apostados` con la política `s`.
- **Estadístico:** `Δ = ROI_0 − ROI_0,5`. **IC95 bootstrap por evento:** con `numpy.random.default_rng(42)`, 10.000 réplicas, en cada una se remuestrean los eventos de la unidad con reemplazo y se recalculan los dos ROI y Δ. IC por percentiles 2,5 y 97,5. Las réplicas en las que alguna política no apuesta nada dan Δ indefinido: se descartan y se cuentan.
- **PASA** la segunda puerta si el límite inferior del IC de Δ es > 0. **FALLA** si no, si alguna política no apuesta nada en la muestra observada o si más del 1 % de las réplicas son indefinidas.
- **Walk-forward.** El stream servido ya es fuera de muestra: cada fila guarda la `p` y el calibrador de su momento, entrenado con resultados anteriores a esa servida. Como la calibración actúa **antes** de la mezcla (`p_decision = (1 − s)·cal(p_adj) + s·fair`), `cal(p_adj)` habría sido el mismo con cualquier `s`, y la política `s = 0` se reproduce exactamente con los datos de cada momento. Los literales de la regla son anteriores al stream (fijados en junio de 2026). **Lo que no se reproduce:** límites de exposición diaria y por liga, banca dinámica, precio realmente ejecutable (se usa la mediana del consenso, igual en las dos políticas) y el efecto que `s = 0` habría tenido sobre el `prediction_gate`. Afectan a las dos políticas por igual o no influyen en la comparación de selección. Se declaran.
- Descriptivo, sin poder de decisión: la misma comparación con la regla simple `0,02 ≤ p·cuota − 1 ≤ 0,075`, sin penalización. ROI esperado, ROI realizado, acierto y prob. prometida media de cada política se informan **por separado**. Ninguno es una promesa de rentabilidad.
- **Las dos puertas deben pasar** (sin cambios).

### E7. Comprobaciones previas (sin depender de `result`)

- **`s = 0,5` en las filas** (amenaza 2 del texto original). Sobre las primeras servidas de la población con `|a − fair| ≥ 0,02`, donde `a = adjusted_probability` (con fallback por fila a `model_probability` en filas de esquema antiguo), se calcula `ŝ_i = (a − estimated_probability)/(a − fair)`. `--medir` **aborta** si la mediana de ŝ se aleja de 0,5 más de 0,01, o si más del 1 % de esas filas se aleja más de 0,05. Si aborta, el pre-registro se reescribe según la amenaza 2; no se mide. `--contar` solo informa.
- El valor efectivo de `Settings.load().risk.market_shrink` y de los literales de E6 se registra al medir frente a `configs/default.yaml`, sin usarlo.
- Descriptivo: fracción de primeras servidas con `|calibrated_probability·cuota − 1 − estimated_edge| > 0,001 + 0,0001·cuota`.

### E8. Procedencia y publicación

- **Salida JSON** (`--out`, y resumen en stdout): HEAD; H_MM; commit de este addendum y del addendum de T1; `git status --porcelain -- src configs scripts/research`; hash de blob, en HEAD y en disco, de `edge_information.py`, `model_vs_market.py`, `bootstrap.py`, `probabilities.py` y del propio script; SHA-256 y filas de cada CSV leído; ligas listadas, cargadas, vacías y faltantes; E, T1, seed y `n_boot` (marcados si difieren de 42 y 10.000); versiones de Python, pandas y numpy; recuentos de cada paso de E3; E7; primario; secundarios con `n`, G, `D̂`, SE, z, p, umbral Holm y decisión; segunda puerta por unidad; sensibilidades (todas las servidas sin colapsar, según el addendum de unidad; sin corte T1, con todo lo graduado al medir; regla simple de E6). Las sensibilidades no tienen poder de decisión.
- **Publicación:** `docs/research/<fecha de --medir>-resultado-el-modelo-manda.md`, con el JSON al lado (`…-resultado-el-modelo-manda.json`), en **un solo commit** que contenga solo esos dos ficheros. Ese commit fija T0 de `2026-10-13-preregistro-peso-mercado-por-segmento.md` §3.1, cuyo script aborta si hay cero o más de un `.md` que case con `*resultado-el-modelo-manda*.md`. Por eso **nunca** se crea un segundo `.md` con ese patrón. Una corrección por fallo técnico posterior va como sección añadida al mismo fichero, conservando el resultado original y con revisión de Fable.
- El resultado se commitea en los tres casos (PASA, FALLA, PEOR), como ordena el texto original.

### E9. Tests mínimos (`tests/research/test_measure_el_modelo_manda.py`, solo datos sintéticos)

1. El lector no renombra ni modifica ningún fichero ante un CSV corrupto (mtime y nombre intactos), lo informa y hace abortar `--medir`. Toma `league` del nombre del fichero y filtra `data_label == "real"`.
2. Orden de E3: los filtros de resultado y de probabilidades actúan antes del colapso (si la servida más antigua de un pick no tiene `calibrated_probability`, la primera servida es la siguiente que sí la tiene, igual que en `score_model_vs_market`); un pick con `p_cal` fuera de [0,1] en la primera servida queda fuera entero aunque otra servida esté en rango; un pick con primera servida > T1 queda fuera aunque tenga otras servidas ≤ T1.
3. `n` cuenta eventos, no picks ni filas, y el clúster es `event_id`.
4. `--contar` no emite ningún campo con Brier, diff, acierto, ROI, z ni p (se comprueba por nombre de clave y por contenido) y añade exactamente una línea al registro. Con `--no-log` no añade ninguna.
5. `--medir` aborta sin T1, con un T1 distinto del addendum o del registro, con `n(T1) < 3.402` o con ŝ fuera de tolerancia, y en todos esos casos sin calcular Brier.
6. El primario coincide con `score_model_vs_market` aplicado a mano al frame sintético, y la decisión PASA/FALLA/PEOR sale del IC.
7. CR1 por evento reproduce un cálculo a mano con 3 eventos. Holm se comprueba con p fijados (m = 3: un caso que rechaza los dos primeros y para en el tercero, y otro en que un rechazo con `D̂ > 0` se etiqueta PEOR). Los segmentos con < 800 eventos no entran en m.
8. Regla de E6: casos frontera (`e_adj` = 0,02 apuesta; `e` = 0,0751 no apuesta; `books_count` = 1 aplica 0,015; `gap` > 0,06 aplica 0,02). Δ y su IC con semilla 42 son reproducibles. Una política sin apuestas da FALLA.
9. E7: un frame sintético construido con `s = 0,4` hace abortar `--medir`; uno con `s = 0,5` y redondeo a 4 decimales lo pasa.

## Addendum 2026-10-17 — filas `nhl|h2h` anteriores a `ffc5ad3` (AUD-003, antes de ejecutar)

Diseño y revisión: Fable (rol de pre-registro de `.claude/automation/MODEL_ROUTING.md`). Escrito **antes** de mirar ningún resultado del test: no se ha calculado ningún Brier, `diff`, acierto ni ROI. Lo pendiente lo dejó declarado `docs/research/2026-10-16-enmienda-gate-nhl-h2h-aud003.md` («Fuera de esta enmienda»).

**Hecho.** Hasta el commit `ffc5ad3` (2026-10-16T12:56:03Z), el consenso h2h de la NHL, que es una liga a 2 vías, incluía casas que cotizan el 1X2 reglamentario con Draw. Por eso fair(home)+fair(away) quedaba por debajo de 0,95 en 1.150 de 1.835 snapshots, con una mediana de 0,8477. El `implied_probability_novig` de esas filas es falso. Totales y spreads de la NHL y el resto de ligas no estaban afectados.

**Efecto sobre este test.** `p_cal = 2·calibrated_probability − implied_probability_novig` se sigue reconstruyendo bien, porque la columna guardada es el mismo `fair` que entró en la mezcla. Lo falso es el **rival**: un `fair` rebajado en los dos lados empeora artificialmente `Brier(fair)` y empuja `diff` hacia el negativo. Es un sesgo **permisivo**, a favor de PASA, justo en la dirección que cambia la política. También contamina la regla de E6, porque `gap = |p − fair|` usa el mismo `fair`.

**Regla (nuevo paso 4b de E3, entre el 4 y el 5).** Se excluye el pick entero (todas sus filas, por `PICK_KEY`) si su **primera servida** tras los pasos 1–3 es de `nhl|h2h` y su `generated_at` es anterior a 2026-10-16T12:56:03Z, es ilegible o falta. La liga sale del nombre del fichero (E2). La regla es la misma que `INVALID_BEFORE` del gate. No se sustituye por una servida posterior, igual que en el paso 4. Se cuenta como `picks_mercado_invalido_aud003`. Vale para `--contar`, para `--medir` y para todas las sensibilidades: la población que fija T1 es la misma que se mide.

**Por qué excluir y no recalcular.** El no-vig correcto no se puede reconstruir con las columnas guardadas. Renormalizar el par (`fair/(fair_h + fair_a)`) no es el consenso canónico, que tras `ffc5ad3` descarta esas casas y recalcula la mediana. Sería una fórmula que el proyecto no define. Conservar las filas tampoco vale: el rival sería falso y el sesgo, favorable a la tesis. Igual que en el gate, el corte lo fija un hecho del pipeline, no el signo de ningún resultado.

**Qué no cambia.** δ = 0,0025, N = 3.402 eventos, el margen de 14 días, la unidad, seed 42, `n_boot = 10.000`, Holm con ≥ 800 eventos y las dos puertas. La lista cerrada de exclusiones de E3 gana este único paso, que corrige datos y no añade un criterio. Recuento hecho hoy, sin `result` salvo el filtro win/loss: 236 picks `nhl|h2h` quedan fuera (todas sus primeras servidas son anteriores al corte) y **0 eventos** se pierden. Los 118 eventos NHL graduados conservan sus picks de totales y spreads, así que ni `n` ni T1 ni el calendario se mueven. Ninguna línea del registro `.contar.jsonl` fija T1 todavía. La línea existente no se reescribe. A partir de la siguiente, `exclusiones` incluye el nuevo recuento.

**Código:** `scripts/research/measure_el_modelo_manda.py` (`INVALID_BEFORE` como literal congelado, `invalid_market_mask` y paso 4b de `build_population`). Tests: `tests/research/test_measure_el_modelo_manda.py`, con dos tests nuevos: exclusión del pick entero sin sustitución, y literal igual al del gate. Si el gate añade otra entrada a `INVALID_BEFORE`, el test falla. Eso obliga a decidir por addendum, antes de medir, cómo se trata aquí. Queda prohibido usar este addendum para recortar o re-segmentar la ventana.
