# Pre-registro — ¿un peso del mercado por segmento mejora al 0,5 global?

**Fecha:** 2026-10-13.
**Estado:** APROBADO por el operador el 2026-10-13 (§14). El commit que añade este fichero es **H**. Diseño: Fable (rol de pre-registro de `.claude/automation/MODEL_ROUTING.md`).
**Escrito antes de mirar ningún efecto.** Sobre los datos solo se han calculado **parámetros de nuisance** (§7.1): recuentos, tasas de acumulación, magnitud del desacuerdo modelo-mercado (sin resultado) y **desviaciones típicas** por evento. Ninguna media que dependa del resultado, ningún signo, ningún `s` óptimo.

Precedentes de forma y método: `2026-08-26-preregistro-el-modelo-manda.md` (en adelante **MM**), `2026-10-02-preregistro-brecha-tier-a.md` (registro de `--contar`, T1 por addendum, veto a enmiendas) y `2026-09-25-repreregistro-gate-k52.md` (addenda de régimen).

---

## 1. La pregunta

Hoy la probabilidad servida es

    p = (1 − s)·cal(p_adj) + s·fair        s = risk.market_shrink = 0,5, GLOBAL

- `configs/default.yaml:17` (`market_shrink: 0.5`, sin cambios desde 2026-06-21, commit `70c21f9`).
- Se aplica en `src/sqp/pipeline/probabilities.py:191` (`_decision_probability`, llamada desde `src/sqp/pipeline/daily.py:898-899`) y en `src/sqp/backtesting/roi_engine.py:374`.
- `fair` = `implied_probability_novig`. Sin `fair` no hay mezcla (`p_decision = p_cal`).
- Verificado hoy con `Settings.load()`: `market_shrink` 0,5; `min_edge` 0,02; `max_plausible_edge` 0,075.
- No existe ningún override de `market_shrink` por liga en `configs/`.

**Pregunta:** ¿un peso del mercado **por segmento** `s_k ∈ [0,1]`, estimado con un procedimiento fijado aquí sobre una ventana de ajuste y aplicado **fuera de tiempo**, mejora la precisión probabilística (Brier; log loss como control) frente a `s = 0,5` global?

**Qué no es.** No es un test de rentabilidad. Una probabilidad mejor no implica ROI positivo: hay que batir al mercado por más que el vig (`.claude/rules/betting-output-rules.md`). Nada se activa con este documento.

---

## 2. Lo que ya está publicado (y orienta, no decide)

- `audit/model_vs_market_20261001.md`: Brier de la probabilidad calibrada servida frente al no-vig, **+0,0038** IC95 [+0,0022, +0,0055] (mercado mejor); probabilidad bruta **+0,0141**.
- Por segmento, mercado claramente mejor en ncaaf h2h/spreads, wnba h2h/totals, tenis WTA US Open, ATP/WTA Canadian y ligamx h2h. «Modelo MEJOR» en tennis_atp_cincinnati h2h, brasileirao totals y epl spreads: con ~60 segmentos, esperable por azar.
- Escalera de `min_edge` invertida (2026-08-25): edge alto = error del modelo.
- Séptima medición (2026-09-07): el modelo está **encompassed** por el consenso (coeficiente condicional ≈ 0).

**Lectura.** La evidencia apunta a que el peso óptimo del mercado es **mayor** que 0,5 en muchos segmentos. Eso es una hipótesis, no un resultado de este test. La pregunta propia de este documento es si **ajustar** ese peso, por segmento y fuera de muestra, mejora lo que se sirve.

---

## 3. Coordinación con «el modelo manda» (MM)

MM compara `s = 0` frente a `s = 1` global, **una sola vez**, cuando el stream graduado alcance **3.402 eventos**. Hoy hay **2.796** (§7.1). A ~31,8 eventos/día, MM se dispara **hacia el 2026-11-01**.

Las dos preguntas actúan sobre el mismo parámetro (`market_shrink`). Si evaluaran las mismas filas, serían dos contrastes correlacionados sobre la misma acción. Este diseño lo evita así:

1. **T0 = fecha del resultado de MM.** T0 es el committer date (UTC) del commit que **añade** el fichero `docs/research/*-resultado-el-modelo-manda.md`. Se resuelve con `git log --diff-filter=A --format="%H %cI" -- "docs/research/*resultado-el-modelo-manda*.md"`. Si hay cero o más de un fichero así, el script aborta.
2. **Ventana de ajuste = eventos con `start_time ≤ T0`.** Contiene toda la muestra de MM. Usarla para **ajustar** no es un segundo contraste: es entrenamiento.
3. **Ventana de evaluación = eventos con `start_time > T0`.** Ningún evento de la muestra de MM puede estar aquí: un partido que empieza después de T0 no podía estar graduado cuando se midió MM. **Las filas de evaluación son disjuntas de las de MM.**
4. **Nada de `s_k` se calcula antes de T0.** Calcular `s_k` sobre la ventana de ajuste antes de que MM se publique sería mirar la muestra de MM (un `s_k` cercano a 0 o a 1 anticipa su resultado). El modo `--ajustar` (§11) aborta si T0 no existe.
5. **Multiplicidad.** Muestras de evaluación disjuntas y procedimientos fijados antes de ver ninguno de los dos resultados. Cada test conserva su α = 0,05. Si sus recomendaciones chocan (§9.3), ninguna se aplica sola: decide el operador, y una decisión que combine ambos exige un pre-registro nuevo.
6. **Si MM sale «modelo PEOR»,** su documento pide un pre-registro propio para subir `s` por encima de 0,5. Este documento lo cubre: `s_k` puede ser > 0,5.
7. **Si MM no se ejecuta antes del 2026-12-31,** el operador fija T0 por addendum. Ese addendum se escribe sin haber calculado ningún `s_k` ni ningún Brier de la ventana.

Por qué no T0 = hoy: adelantaría el test unas tres semanas, a cambio de solapar la evaluación con la cola de la muestra de MM y de tener que repartir α entre dos contrastes sobre la misma acción. No compensa.

---

## 4. Población, unidad y reconstrucción

### 4.1 Fuente y filtros (iguales en ajuste y evaluación)

- `data/calibration/graded_*.csv`, solo `data_label == "real"`. Lectura **sin** la cuarentena de `ServedStore._load`, que renombra ficheros (Addendum 1 de tier A, punto 4): medir no puede mutar `data/`.
- `result ∈ {win, loss}`. `void`, `push`, `half_win` y `half_loss` fuera y contados.
- `calibrated_probability` e `implied_probability_novig` presentes.
- Identidad completa (`event_id`, `market`, `selection`). Si falta alguna, la fila se excluye y se cuenta.
- **Pregame:** se excluye la fila de decisión con `generated_at ≥ start_time` o con `start_time` ilegible.

### 4.2 Unidad: una fila por pick

El stream guarda una fila por día de horizonte. Hoy son 46.009 filas graduadas para 17.250 picks (2,67x). Se colapsa con `one_row_per_pick` (`src/sqp/evaluation/edge_information.py:55`, clave `PICK_KEY = (event_id, market, line, selection)`): **la primera servida** de cada pick. Es lo que hace hoy `score_model_vs_market` (`src/sqp/evaluation/model_vs_market.py:143`) antes de puntuar. Orden: `data_label`, resultado e identidad se filtran antes de colapsar (son iguales en todas las servidas de un pick). Pregame y probabilidades presentes se comprueban **sobre la primera servida**: si no los pasa, el pick queda fuera y no se busca otra servida. Es más estricto que `score_model_vs_market`, que descarta las filas sin probabilidad antes de colapsar; se declara.

- **Inferencia:** el evento es la unidad. El estadístico es la media por pick; el IC remuestrea **eventos** enteros.
- **Sensibilidad S1:** todas las servidas, sin colapsar.

### 4.3 Segmento y familia

- **Segmento** `k = liga|mercado`. Excepción: los torneos de tenis se agrupan por circuito (`tennis_atp_*` y `atp` → `tennis_atp`; `tennis_wta_*` y `wta` → `tennis_wta`). Cada torneo es un id nuevo y efímero: sin agruparlo, casi todo el tenis de la evaluación sería un segmento sin ajuste.
- **Familia** `F = familia|mercado`, con `familia = _league_meta(liga)["family"]` (`src/sqp/pipeline/daily.py:75`) tal como está en H. Hoy: baseball, basketball, football, hockey, soccer, tennis. Liga sin familia legible → su padre es el global.

### 4.4 Reconstrucción de `p_cal` (amenaza 2 de MM)

Ninguna columna guarda `cal(p_adj)`. Se reconstruye:

    calibrated_probability = (1 − s_t)·p_cal + s_t·fair   ⇒   p_cal = (calibrated_probability − s_t·fair) / (1 − s_t)

- Con `s_t = 0,5`: `p_cal = 2·calibrated_probability − implied_probability_novig`. Es la fórmula de MM. **Solo vale mientras el `s` servido sea 0,5.**
- Verificado hoy: 0 de 17.250 picks fuera de [0,1]. Las columnas van a 4 decimales: error ≤ 1,5·10⁻⁴ con `s_t = 0,5`.
- **Si `s` cambia** (por ejemplo, porque MM pasa y se sirve `s = 0` en shadow), `s_t` es el valor vigente para **esa fila**, tomado de la tabla de régimen de los addenda (§10). Con `s_t = 0`, `p_cal = calibrated_probability`. Con `s_t = 1`, `p_cal` es irrecuperable: la fila se excluye y se cuenta. Con `s_t` desconocido, igual.
- `p_cal` reconstruida fuera de [0,1] → se excluye y se cuenta (no se recorta).
- **Precondición recomendada (fuera de este documento):** persistir `market_shrink` en cada fila servida. Elimina la dependencia de la tabla de régimen y del `.env`, que no está versionado (§14).

---

## 5. Procedimiento de `s_k`, fijado aquí

### 5.1 Estimador por nodo

Para un nodo `X` (global, familia o segmento), sobre los picks de la ventana de ajuste:

    d_i = p_cal,i − fair_i
    g_e = Σ_{i∈e∩X} d_i·(p_cal,i − y_i)        D_e = Σ_{i∈e∩X} d_i²
    ŝ_X = Σ_e g_e / Σ_e D_e
    v_X = Σ_e (g_e − ŝ_X·D_e)² / (Σ_e D_e)²     (sándwich por evento)

`ŝ_X` minimiza el Brier de `p(s) = p_cal − s·d` en la ventana: es la forma cerrada. `n_X` = eventos distintos del nodo.

### 5.2 Encogimiento jerárquico (global → familia → segmento)

Normal-normal con varianza a priori **fija** `τ² = 0,25²` entre hijos de un mismo padre:

    s̃_G = clip(ŝ_G, 0, 1)
    s̃_F = (τ²·ŝ_F + v_F·s̃_G) / (τ² + v_F)        si n_F ≥ 30; si no, s̃_F = s̃_G
    s̃_k = (τ²·ŝ_k + v_k·s̃_F) / (τ² + v_k)        si n_k ≥ 30; si no, s̃_k = s̃_F
    s_k = clip(s̃_k, 0, 1)

- **Umbral mínimo:** 30 eventos de ajuste. Por debajo, `v_X` no es fiable y el nodo hereda el de su padre. Si `Σ D_e = 0`, el nodo se trata como si `n < 30`.
- **τ = 0,25, fijo y no estimado.** Es el efecto en escala de `s` por debajo del cual no merece la pena un parámetro propio (§7.2). Estimar τ con 16 familias sería inestable. Sensibilidad S2: τ ∈ {0,10; 0,50}.
- **Por qué hace falta encoger.** Con los datos de hoy, el error típico de `ŝ_k` es de 0,08 a 0,30 en los segmentos más profundos y de 0,6 a 4 en los demás (§7.1). Sin encogimiento, la mayoría de los `s_k` serían ruido, y el ruido se paga en Brier fuera de muestra.

### 5.3 Segmentos nuevos

Un segmento sin eventos en la ventana de ajuste (o con menos de 30) usa **`s̃_F` de su familia**. Si la familia tampoco llega a 30, usa `s̃_G`.

- **NBA** usa `basketball|mercado`, ajustada sobre WNBA. Comparte adaptador y familia de modelo, así que su desacuerdo con el mercado se parece más al de la WNBA que al promedio global. Si al llegar a T0 la NBA ya tiene ≥ 30 eventos, tiene ajuste propio, encogido hacia esa familia.
- **NHL** ya tiene 86 eventos: ajuste propio, encogido hacia `hockey|mercado` (que hoy es la propia NHL) y de ahí al global.
- No se usa `s = 0,5` para los segmentos nuevos. Eso mezclaría dos políticas en el test primario y diluiría el efecto sin razón.

### 5.4 Congelación

- `--ajustar` se ejecuta **una vez**, con fecha ≥ T0 + 14 días (margen de liquidación de la ventana de ajuste, igual que en tier A), y siempre antes de `--medir`. Solo lee eventos con `start_time ≤ T0`. Que se ejecute más tarde no filtra nada de la evaluación.
- Escribe `docs/research/2026-10-13-preregistro-peso-mercado-por-segmento.sk.json`: `s_k`, `s̃_F`, `s̃_G`, `ŝ`, `v`, `n` de cada nodo, H, T0 y el SHA-256 de los picks de ajuste. Se commitea en un addendum. **Ese fichero manda** en la evaluación. Si al medir el recálculo no coincide, se informa y se usa el commiteado.

---

## 6. Test

Para cada pick de la ventana de evaluación:

    p_k   = (1 − s_k)·p_cal + s_k·fair
    p_0,5 = 0,5·p_cal + 0,5·fair              (= calibrated_probability servida cuando s_t = 0,5)
    diff  = (p_k − y)² − (p_0,5 − y)²         NEGATIVO = s_k gana

### 6.1 Primario (H1)

- Estadístico: media de `diff` sobre los picks de la ventana (§8).
- IC95: `cluster_bootstrap_ci(diff, event_id, n_boot=10_000, seed=42)`. Está en `src/sqp/evaluation/bootstrap.py:22`. Firma: `cluster_bootstrap_ci(values, clusters, *, n_boot=1000, seed=42, alpha=0.05, stat=None) -> (lo, hi)`. IC bilateral por percentiles, remuestreando eventos enteros.
- **PASA** si `hi < 0`. **PEOR** si `lo > 0`. **FALLA** en otro caso.
- Contraste bilateral, decisión unilateral: solo PASA cambia algo (§9).
- **Control de log loss** (con el recorte de `log_loss_safe`): mismo IC. Si H1 PASA pero el log loss empeora con IC (`lo > 0`), el resultado es **frágil** y no se actúa sin revisión de Fable.

### 6.2 Contrastes que solo se abren si H1 pasa (Holm)

Si H1 pasa, se contrasta, con **Holm a α = 0,05** sobre la familia completa:

- **H2 — ¿aporta la segmentación?** `p_k` frente a `p_G = (1 − s̃_G)·p_cal + s̃_G·fair`. Si H1 pasa y H2 no, la ganancia es de **nivel**, no de segmento: un único `s̃_G` global la explica.
- **Segmentos:** cada segmento con **≥ 200 eventos** en la evaluación, `p_k` frente a `p_0,5` dentro del segmento. El número de segmentos elegibles se decide por el recuento real al medir.

Para ordenar Holm se usa el p-valor bilateral de un z con error estándar por clúster de evento (CR1, como en tier A §3.1). El IC bootstrap de cada uno se informa al lado.

Esta secuencia (H1 primero; luego Holm sobre H2 y los segmentos) controla el error de familia al 5 %. Un segmento **no** puede pasar si H1 falla. Es más estricto que MM, a propósito: aquí `s_k` se ajustan muchos parámetros y el riesgo de ganar por azar en un segmento es mayor.

**H2 tiene poca potencia.** Con los errores típicos de §7.1 solo detecta heterogeneidad grande entre segmentos. Si falla, se lee «sin evidencia de que segmentar aporte», no «no hay heterogeneidad».

---

## 7. Potencia, N y fecha

### 7.1 Nuisance medidos hoy (sin resultado medio)

Script de un solo uso en el scratchpad de la sesión (no versionado): lee los `graded_*.csv`, filtra `real` y win/loss, aplica `one_row_per_pick`, reconstruye `p_cal` con `s = 0,5` e imprime solo recuentos, `D` medio por evento y la **DE** por evento de `g_e = Σ d_i·(calibrated_probability_i − y_i)`. Datos hasta `start_time` 2026-10-12 05:20Z. Sin el filtro pregame ni el orden estricto de §4.2: diferencia despreciable para la potencia.

| métrica | valor |
|---|---:|
| picks / eventos | 17.250 / 2.796 (6,17 picks por evento) |
| `p_cal` fuera de [0,1] | 0 |
| eventos/día, desde 2026-07-07 | 28,5 |
| eventos/día, desde 2026-09-15 | 31,8 (football 10,3; tenis 7,0; soccer 5,7; baseball 4,0; hockey 3,1; basketball 1,6) |
| `D` medio por evento (Σd²), global | 0,0762 (0,0123 por pick) |
| DE por evento de `g_e`, global | 0,2793 |
| error típico de `ŝ_G` | 0,069 |

Error típico de `ŝ` por segmento, los más profundos: ncaaf h2h 0,08; tennis_wta 0,14; ncaaf spreads 0,16; tennis_atp 0,17; mlb spreads 0,22; mlb totals 0,26; wnba h2h 0,26; ncaaf totals 0,27; mlb h2h 0,30; nhl h2h 0,34. Por familia: tennis|h2h 0,11; football|h2h 0,08; football|spreads 0,15; soccer|h2h 0,20. El resto de segmentos, entre 0,35 y 4.

### 7.2 Efecto mínimo de interés

Sea `Δ = |s* − 0,5|` la distancia entre el peso óptimo y el vigente. Si `s*` fuera igual en todos los segmentos, la ganancia esperada por pick es

    ganancia = (Δ² − m)·D_pick        D_pick = 0,0123,  m = 0,0145

`m` es el error cuadrático medio de `s_k` por el ruido de ajuste bajo esa hipótesis, calculado con los errores típicos de §7.1 y el encogimiento de §5.2. **Techo:** con `s ∈ [0,1]`, `Δ ≤ 0,5`, y la ganancia no puede pasar de ~0,0031 por pick. El δ = 0,0025 de MM queda casi en el techo (exigiría `s*` ≈ 0,03 o 0,97). No sirve aquí.

Se fija **Δ = 0,40**, es decir **δ = 0,0018** de Brier por pick:

- Es `s*` ≤ 0,10 o ≥ 0,90: uno de los dos (casi siempre el mercado) se lleva casi todo el peso. Un ajuste más fino no justifica un parámetro por segmento.
- La evidencia publicada (§2, encompassing con coeficiente ≈ 0) apunta a `s*` cerca de 1. Si es cierto, el test tiene potencia ≥ 0,9. No se ancla en ese extremo para no diseñar un test que solo vea lo que ya se cree.
- Δ = 0,25 exigiría ~11.400 eventos: más de un año y varios cambios de temporada.

### 7.3 N

`N = ((z_0,975 + z_0,80)·2Δ·DE(g) / ((Δ² − m)·D_e))²`, α = 0,05 bilateral, potencia 0,80.

| Δ | δ por pick | N eventos |
|---:|---:|---:|
| 0,30 | 0,0009 | 6.660 |
| 0,35 | 0,0013 | 4.431 |
| **0,40** | **0,0018** | **3.189** |
| 0,45 | 0,0023 | 2.418 |
| 0,50 | 0,0029 | 1.902 |

**N = 3.300 eventos** de evaluación (redondeo al alza). Potencia con N = 3.300: Δ 0,30 → 0,50; 0,35 → 0,68; **0,40 → 0,81**; 0,45 → 0,91; 0,50 → 0,96.

Aproximaciones declaradas: `s*` uniforme; DE y `D` de la mezcla de verano y otoño. La composición de la evaluación será más de fútbol americano, NBA y NHL. Football tiene `D` por pick unas dos veces el global, lo que tiende a **subir** la potencia.

### 7.4 Fecha y disparo

- T0 ≈ 2026-11-05 (MM ≈ 2026-11-01 más su ejecución y commit).
- Entre noviembre y febrero sale el tenis (mediados de noviembre a enero) y el MLB; entran NBA y NHL completas. Se estima **27 eventos/día** (rango 22-32).
- 3.300 / 27 ≈ 122 días → T1 ≈ 2027-03-07; medición ≈ **2027-03-21** (rango: mediados de febrero a mediados de abril de 2027).
- **El disparo es por recuento, no por calendario.** `--contar` (§11) cuenta los eventos con `start_time ∈ (T0, E − 14 d]` y al menos un pick que pasa §4.1. Nunca imprime resultados, `p` ni `s_k`. Cada ejecución añade una línea a `docs/research/2026-10-13-preregistro-peso-mercado-por-segmento.contar.jsonl` (append-only, commiteado). Se recomienda mensual, y semanal a partir de 2.800.
- La **primera** línea con `n ≥ 3.300` fija **T1 = E − 14 días**, que se escribe en un addendum (`T1 fijado = <ISO>` y `commit del registro = <sha>`) antes de `--medir`. Población de evaluación: eventos con `start_time ∈ (T0, T1]`.
- **Una sola ejecución** de `--medir`. Sin miradas intermedias. Re-ejecutar solo por fallo técnico que impida producir el informe. Si tras publicarlo aparece un error que cambie la población, se publican ambos, con revisión de Fable.
- **Δ, N, τ, el umbral de 30 eventos, la jerarquía y los criterios no se cambian después de H**, salvo fallo técnico documentado, revisado por Fable y sin haber visto ningún `s_k` ni Brier de la evaluación. El resultado de MM, que se conocerá antes de T0, también cuenta como información: una enmienda posterior a él no podría demostrar que no la motivó.

---

## 8. Segunda puerta: ROI (necesaria, no suficiente)

Solo cuenta para algo que toque el **stake**. Sobre la ventana de evaluación, una fila por pick, cuota `price_decimal`:

- Política P ∈ {`p_k`, `p_0,5`}: stake plano de 1 unidad si `0,02 ≤ p_P·cuota − 1 ≤ 0,075` (`edge` de `src/sqp/risk/kelly.py:11`; literales congelados aquí, iguales a `min_edge` y `max_plausible_edge` de hoy).
- PnL: `cuota − 1` si gana, `−1` si pierde.
- **Puerta:** `ΔPnL = (PnL(p_k) − PnL(p_0,5)) / nº de eventos` (cero en los eventos sin apuesta), con IC95 bootstrap por evento (seed 42, 10.000). **Pasa si `lo > 0`.**

Lectura obligada:

- Pasar significa «pierde menos o gana más que la política vigente en esta ventana». **No** significa rentabilidad. Con `s_k` cerca de 1 la política casi no apuesta (el no-vig nunca supera la cuota con vig), y puede pasar solo por apostar menos.
- Es una aproximación: no replica la penalización de incertidumbre (`adjusted_edge`), el `prediction_gate` ni el Kelly.

Se informan **por separado**, para cada política y nunca como promesa: nº de apuestas; acierto observado frente a probabilidad prometida media; probabilidad implícita media (`1/cuota`); edge medio (`p − fair`); ROI esperado medio (`p·cuota − 1`); ROI realizado. Si hay `execution_price`, sus ROI van aparte y no sustituyen a los de la mediana.

---

## 9. Qué se hace con cada resultado

### 9.1 Tabla

| resultado | condición | acciones permitidas |
|---|---|---|
| **PASA** | H1 `hi < 0` y log loss no peor | Registrar. **Proponer** al operador una columna shadow con `p_k` en cada fila servida, sin tocar la probabilidad servida ni el stake, durante ≥ 30 días. Si H2 falla, la propuesta es el `s̃_G` global y no los `s_k`. Solo los segmentos que pasen Holm pueden llevar `s_k` propio. |
| **PASA + ROI** | además la puerta de §8 | Lo anterior. Para tocar el stake hace falta además la regla de salida vigente (`2026-08-16-preregistro-regla-de-salida.md`, gate K = 52) y aprobación expresa del operador. |
| **FALLA** | IC contiene 0 | Registrar con su IC. `s = 0,5` sigue. No se reabre con otro τ, otra jerarquía u otra ventana sobre estos datos. |
| **PEOR** | H1 `lo > 0` | Registrar. Es evidencia de que ajustar por segmento sobreajusta con esta muestra. `s = 0,5` sigue. |
| frágil | PASA con log loss peor, o S1 cambia el veredicto | Registrar. Nada sin revisión de Fable. |

En **ningún** caso:

- se promueve nada automáticamente;
- se cambia `market_shrink` sin aprobación expresa del operador;
- se presenta el resultado como evidencia de rentabilidad.

El resultado, sea cual sea, se commitea en `docs/research/<fecha>-resultado-peso-mercado-por-segmento.md`.

### 9.2 Sensibilidades (descriptivas, sin poder de decisión)

- S1: todas las servidas, sin colapsar.
- S2: τ = 0,10 y τ = 0,50.
- S3: reajuste sin las filas anteriores a cada cambio de régimen de §10 en los segmentos afectados.
- S4: partición de la evaluación antes y después de cada addendum de régimen posterior a T0.
- S5: comparación con el `s` vigente por fila cuando difiera de 0,5.
- S6: desglose por familia.
- S7: marca de los segmentos con calibrador aplanado en la ventana (`flattened_segments`, `src/sqp/evaluation/model_vs_market.py:58`). Su `p_cal` es casi constante: el ajuste aprende a sustituirla por el mercado, que es lo que haría la política, pero se informa.

### 9.3 Si MM y este test chocan

- MM PASA (modelo mejor, `s → 0`) y aquí PASA con `s_k` altos: recomendaciones opuestas. No se aplica ninguna sola. Decide el operador; una decisión conjunta exige pre-registro nuevo.
- MM FALLA o PEOR: no hay conflicto. Este test es la vía para un `s` distinto de 0,5.

Este test **no** toca la población ni el criterio del gate K = 52 ni de tier A. Si algún día `p_k` pasa a ser la probabilidad servida, se registra como addendum de régimen en esos dos documentos y en MM.

---

## 10. Cambios de régimen

**Antes de T0, dentro de la ventana de ajuste:** `pitcher_bound` MLB 0,05 (2026-09-26), descanso NBA 0,795 (2026-09-26), alias de equipo (2026-09-26), `tilt_scale` NHL 0,439 (2026-09-30), y los reentrenos del calibrador.

- El ajuste usa **todas** las filas ≤ T0, sin recortar. Es la política tal como se habría aplicado: con todo lo disponible en T0.
- S3 mide, solo como dato, cuánto cambiaría el resultado ajustando MLB y NHL con filas posteriores a su cambio.

**Después de T0:** cada cambio de modelo, calibrador, población o `market_shrink` se registra como **addendum antes de medir**, con fecha y alcance. No altera ningún criterio y queda prohibido usarlo para recortar la ventana. Lo único que se hace con él es S4.

**Tabla de régimen de `s`.** Un addendum por cada cambio del `s` servido: instante UTC, alcance (global o `liga|mercado`) y valor. Hoy: `s = 0,5` global desde antes del 2026-07-07. `--contar` compara el `Settings().risk.market_shrink` efectivo con el último valor de la tabla y avisa si difieren (puede haber un `MARKET_SHRINK` en `.env`, que no está versionado).

---

## 11. Contrato del script (NO escrito todavía)

**Ruta propuesta:** `scripts/research/measure_segment_market_weight.py`. Tests en `tests/research/test_measure_segment_market_weight.py`, solo con datos sintéticos.

**Entradas comunes**
- `--data-root` (por defecto, la raíz del repo). Lee `data/calibration/graded_*.csv` con un lector propio sin efectos secundarios (semántica de `load_all_graded`, sin cuarentena). Nunca vuelca filas.
- H: tag `prereg-peso-mercado-h` si existe; si no, `git log --diff-filter=A` sobre la ruta de este fichero. Si dan commits distintos, aborta.
- T0: §3.1. Sin T0, todos los modos salvo `--contar` abortan (`--contar` imprime n = 0).
- Familia con `_league_meta` de H; segmento con la regla de §4.3.
- Tabla de régimen de `s` leída de los addenda de este fichero en HEAD.

**`--contar`**
- Imprime y anota en el `.contar.jsonl`: instante E, HEAD, H, T0, T1 candidato (E − 14 d), `n` eventos de evaluación, picks de evaluación, picks sin graduar de la ventana, `market_shrink` efectivo frente a la tabla, SHA-256 de cada CSV.
- Ni `y`, ni `p`, ni `s_k`, ni Brier. `--no-log` solo para diagnóstico; no cuenta para fijar T1.

**`--ajustar`** (una vez, §5.4)
- Exige T0 y E ≥ T0 + 14 d. Ventana `start_time ≤ T0`. Aplica §4 y §5.
- Escribe el `.sk.json`: `s_k`, `s̃_F`, `s̃_G`, y `ŝ`, `v` y `n` de cada nodo; H, T0, hash de los picks de ajuste y recuentos de cada exclusión.
- Si el `.sk.json` ya está commiteado, aborta.

**`--medir --t1 <ISO>`** (una vez)
- Exige el T1 del addendum, coherente con la primera línea del registro con `n ≥ 3.300`, y `n(T1) ≥ 3.300` con los datos del momento. Exige el `.sk.json` commiteado. Si algo falla, aborta sin calcular.
- Calcula §6 (H1, log loss, H2 y segmentos con Holm), §8 y §9.2.
- Salida JSON (`--out` y stdout): procedencia (H, T0, T1, HEAD, hashes de blob de `probabilities.py`, `edge_information.py`, `bootstrap.py` y `configs/default.yaml` en H y en HEAD, `git status --porcelain -- src configs scripts/research`, SHA-256 y filas de cada CSV); recuentos de cada filtro; `s_k` usados y discrepancia con el recálculo; H1 (`n` picks, `n` eventos, media de `diff`, IC, etiqueta); log loss; H2 y segmentos (z, p, Holm, IC); ROI; S1-S7.
- `--seed 42` y `--n-boot 10000` congelados; si se pasan otros, se marcan en la procedencia.

**Tests mínimos**
- `ŝ_X` coincide con el mínimo numérico del Brier en un caso pequeño; `v_X` reproduce el sándwich a mano en 3 eventos.
- Encogimiento: con `v → 0` devuelve `ŝ_k`; con `v → ∞`, el padre; `n < 30` hereda; el resultado final está en [0,1].
- Tenis se agrupa por circuito; un segmento nuevo hereda de su familia, y sin familia, del global.
- Reconstrucción de `p_cal` con `s_t` ∈ {0; 0,5}; `s_t = 1` o desconocido excluye y cuenta.
- Ningún evento con `start_time ≤ T0` entra en la evaluación, ni uno posterior en el ajuste.
- `--contar` no emite ningún campo de resultado y añade exactamente una línea.
- `--ajustar` aborta sin T0 o antes de T0 + 14 d; `--medir` aborta sin T1, con un T1 distinto o con `n < 3.300`.

---

## 12. Amenazas a la validez

- **A1 — Composición.** Ajuste en verano y otoño (MLB, WNBA, tenis, fútbol); evaluación en invierno (NFL, NCAAF, NBA, NHL). Es la prueba que importa: si el `s_k` de verano no transfiere, el test lo dirá. S6 lo desglosa.
- **A2 — Deriva del calibrador.** `cal()` se reentrena; `d` cambia con él. El test evalúa el sistema tal como opera.
- **A3 — Dependencia de MM.** Si MM se retrasa, este test también (§3.7).
- **A4 — `.env` no versionado.** Un `MARKET_SHRINK` fuera del yaml cambiaría `s_t` sin dejar rastro en git. Mitigación: aviso de `--contar` y precondición de §4.4.
- **A5 — Aproximación de potencia.** `s*` uniforme y errores de `ŝ` independientes entre niveles. Con heterogeneidad real, H1 puede tener más o menos potencia.
- **A6 — Redondeo.** ≤ 1,5·10⁻⁴ por fila con `s_t = 0,5`; mayor con `s_t` cercano a 1. Diez veces menor que δ.
- **A7 — Visibilidad.** `scripts/model_vs_market_report.py` puede ejecutarse durante la ventana de evaluación y mostrar Brier de modelo frente a mercado. No muestra `p_k`, pero está correlacionado. Por eso está vetada cualquier enmienda posterior a H (§7.4).

---

## 13. Lo que este pre-registro NO prueba

- Rentabilidad, de ninguna política.
- Que la mezcla lineal sea la mejor forma de combinar modelo y mercado (logit, por precio, por profundidad de consenso: otras preguntas).
- Nada sobre mercados finos (`casas < 10`) por separado.

---

## 14. Decisión del operador

Resuelta el 2026-10-13 (orden del operador: «Sí, házlo», sobre la recomendación de aprobar tal cual con T0 = resultado de MM):

- [x] **Aprobar el pre-registro.** El commit que añade este fichero fija H. Tag anotado `prereg-peso-mercado-h`.
- [x] **Aceptar T0 = resultado de MM** (§3) y el horizonte resultante, con la medición hacia **marzo de 2027**. Descartada la alternativa T0 = H.
- [ ] **Precondición recomendada:** persistir `market_shrink` en cada fila servida (cambio de código aparte, con su revisión). Sin decidir; no es obligatoria mientras `s` siga en 0,5 y pasa a serlo en la práctica si MM cambia `s`.

---

## Addenda

Ninguno todavía. Aquí se añaden, por commits posteriores a H y sin editar lo anterior: la tabla de régimen de `s` y los cambios de régimen (§10), T0 si lo fija el operador (§3.7), el `.sk.json` (§5.4) y T1 (§7.4).

### Addendum 2026-10-13 (1) — formato de la tabla de régimen de `s` y columna `market_shrink` (antes de T0)

No cambia ningún criterio; fija el formato que §10 y §11 dejaban abierto (hallazgo de la revisión de Fable del script).

- **Fuente de `s_t` por fila, en este orden:** (1) la columna `market_shrink` de la fila, si existe y es finita (el stream la guarda desde el commit que la añade a `ServedStore.COLUMNS`; vale 0,0 cuando la fila no tuvo no-vig y no se mezcló); (2) si no, la tabla de régimen de abajo; (3) si ninguna aplica, `s_t` desconocido: la fila se excluye y se cuenta (§4.4).
- **Formato literal de cada entrada de la tabla**, una por línea, al inicio de línea, dentro de la sección «Addenda»:

      s servido = <valor en [0,1] | desconocido> | desde = <ISO-8601 con zona> | alcance = <global | liga|mercado>

  Entrada implícita: `s servido = 0.5 | desde = 2026-06-21T00:00:00+00:00 | alcance = global`. Gana la entrada aplicable con `desde` más reciente, comparada con el `generated_at` de la fila; a igual `desde`, la de alcance `liga|mercado` sobre la global.
- Cualquier línea de la sección «Addenda» que empiece por `s servido` y no cumpla este formato hace **abortar** `--ajustar` y `--medir`. Nunca se ignora en silencio.
- Si la columna y la tabla discrepan en una fila, manda la columna y la discrepancia se cuenta y se informa.

### Addendum 2026-10-13 (2) — precisiones a la tabla de régimen de `s` (antes de T0)

Redactado por Fable en la verificación del script. No cambia ningún criterio; precisa el Addendum 2026-10-13 (1).

- La discrepancia entre la columna `market_shrink` y la tabla se cuenta **después** de los filtros de §4.1 y del colapso de §4.2: solo sobre las filas que llegan a la reconstrucción de §4.4.
- Una columna `market_shrink` finita fuera de [0,1] no se sustituye por la tabla: la fila se excluye y se cuenta en un recuento propio.
- El `alcance` de una entrada `liga|mercado` es el **segmento** de §4.3. Para tenis es el circuito (`tennis_atp|<mercado>` o `tennis_wta|<mercado>`), nunca un torneo ni `atp`/`wta`. Una entrada con alcance de torneo, o con un `desde` sin zona horaria, no cumple el formato y hace abortar `--ajustar` y `--medir`.
- Si la tabla no puede leerse del pre-registro en HEAD, `--ajustar` y `--medir` abortan; `--contar` lo informa.

### Addendum 2026-10-17 (3) — filas `nhl|h2h` anteriores a `ffc5ad3` (AUD-003, antes de T0)

Diseño y revisión: Fable. Es un **fallo técnico documentado** en el sentido de §7.4. Se escribe antes de T0: no existe el resultado de MM, `--ajustar` no se ha ejecutado y no se ha calculado ningún `s_k`, `ŝ`, Brier ni `diff`. Lo pendiente lo dejó declarado `docs/research/2026-10-16-enmienda-gate-nhl-h2h-aud003.md`.

**Hecho.** Hasta `ffc5ad3` (2026-10-16T12:56:03Z), el consenso h2h de la NHL incluía casas del 1X2 con Draw. El `implied_probability_novig` de esas filas es falso: fair(home)+fair(away) quedaba por debajo de 0,95 en 1.150 de 1.835 snapshots, con una mediana de 0,8477. Totales y spreads de la NHL y el resto de ligas no estaban afectados.

**Efecto sobre este test.** `fair` es el regresor que `s` pondera. `p_cal` se reconstruye bien (§4.4) porque la columna guardada es el `fair` que entró en la mezcla. Pero `d = p_cal − fair` arrastra en esas filas un desplazamiento positivo en los dos lados, que no existirá en la evaluación (`start_time > T0`, con el consenso ya corregido). Ajustar `ŝ` de `nhl|h2h`, y a través del encogimiento el de `hockey|h2h` y el global, contra un mercado que ya no existe rompe la transferencia ajuste → evaluación en la que se apoya H1. La dirección del sesgo en H1 no se puede fijar a priori. Por eso no se puede aceptar como «conservador».

**Regla.** En las dos ventanas y en todos los modos, se excluye la fila de decisión (la primera servida, §4.2) de `nhl|h2h` con `generated_at` anterior a 2026-10-16T12:56:03Z. La liga sale del nombre del fichero. El filtro se aplica después del de pregame y antes del de probabilidades presentes, y se cuenta como `mercado_invalido_aud003`. El pick no se sustituye por una servida posterior, con la misma regla que §4.2. En S1, sin colapsar, el filtro actúa por fila. La regla es la misma que `INVALID_BEFORE` del gate. Se excluye en lugar de recalcular el no-vig porque el consenso correcto no se reconstruye con las columnas guardadas. La renormalización del par no es la definición canónica.

**No es un recorte por régimen.** §10 manda ajustar con todas las filas ≤ T0 porque son datos válidos de otro modelo. Estas filas no son válidas: su columna de mercado es falsa. S3 no cambia.

**Qué no cambia.** Δ, N = 3.300, τ, el umbral de 30 eventos, la jerarquía, T0, el margen de 14 días, los criterios y la tabla de régimen de `s`. Recuento hecho hoy, sin resultados: el graduado tiene 236 picks `nhl|h2h` win/loss, en 118 eventos, todos con primera servida anterior al corte. En el ajuste, `nhl|h2h` solo tendrá los eventos que empiecen entre el 2026-10-16 y T0. Si no llega a 30, hereda de su familia y, si esta tampoco llega, del global (§5.2–5.3, sin cambios). La evaluación es prácticamente inerte al filtro, porque sus eventos empiezan después de T0. N y el calendario no se mueven.

**Código:** `scripts/research/measure_segment_market_weight.py` (`INVALID_BEFORE` como literal congelado, `invalid_market_mask` y su paso en `prepare_picks`). Tests: `tests/research/test_measure_segment_market_weight.py`, con dos tests nuevos: exclusión sin sustitución con el corte en `>=`, y literal igual al del gate. Se ajustó la fecha de una fila sintética NHL de `test_liga_familia_is_saved_in_sk_and_overrides_live_lookup` para que quede después del corte. Si el gate añade otra entrada a `INVALID_BEFORE`, el test falla y obliga a decidir por addendum. Queda prohibido usar este addendum para recortar la ventana.

### Addendum 2026-10-18 (4) — remediación audit-2026-10-18 (antes de T0)

Desde el commit de la remediación de la ronda `audit-2026-10-18` (2026-10-18): (1) AUD-001: el modelo NHL reparte el empate del tiempo reglamentario en (k+1,k)/(k,k+1) y reescala los ritmos para conservar el total esperado; cambian las p de `nhl|totals` (2-3 pp), `nhl|spreads` (≤0,6 pp) y `nhl|h2h` (≤0,3 pp). (2) AUD-002: el descanso cuenta los partidos programados del run; solo afecta a la NBA (0,795). (3) AUD-008: el gate y el entrenamiento del calibrador excluyen las filas totals/spreads de línea de cuarto con `generated_at` < 2026-09-13T12:36:34Z (c578f52), graduadas sin medias; el corte lo fija el código, no un resultado. Diseño y revisión: Fable (rol de pre-registro de `.claude/automation/MODEL_ROUTING.md`). Se registra **antes** de mirar ningún resultado. **No altera ningún criterio**, y queda prohibido usarlo para recortar o re-segmentar la ventana.

Las filas de (3) se excluyen también de este test: literal congelado `QUARTER_LINE_INVALID_BEFORE` en el script y un test de igualdad con `sqp.settlement.quarter_line_fix`. Código: `scripts/research/measure_segment_market_weight.py` (`quarter_line_mask` en `prepare_picks`, recuento `linea_cuarto_aud008`).

(1) y (2) son cambios del modelo anteriores a T0 y se listan aquí a efectos de §10; `_REGIME_CHANGES_PRE_T0` queda intacto, porque S3 es descriptivo. Cambio de implementación sin efecto sobre la población: `_git_decide` (AUD-017) distingue un fallo o timeout de git de «T0 no existe».

### Addendum 2026-10-20 (5) — `execution.books: [pinnacle]` (antes de T0)

Desde el commit que declara `execution.books: [pinnacle]` (2026-10-20), `execution_price`/`execution_book` dejan de repetir la mediana y toman el precio de Pinnacle cuando cotiza la línea (si no, la mediana). `price_decimal`, edge, selección, stake y liquidación no cambian. Solo afecta a las métricas descriptivas de `execution_price`, que se informarán partidas antes/después de esta fecha. Redactado por Fable (rol de pre-registro de `.claude/automation/MODEL_ROUTING.md`). Corte: `generated_at` ≥ 2026-10-20T13:31:09Z (instante de f92e8e1); sin fecha legible, `sin_fecha`. Desglose en `execution_price_por_regimen` de cada política; el agregado se conserva. No altera ningún criterio y queda prohibido usarlo para recortar o re-segmentar la ventana.
