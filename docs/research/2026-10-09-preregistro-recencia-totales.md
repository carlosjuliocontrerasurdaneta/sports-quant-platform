# Pre-registro — recencia de la anotación en el adaptador de totales (`scoring_half_life_days`, NBA, NFL y NHL)

**Fecha:** 2026-10-09. Redactado por Fable **antes** de emparejar con un desenlace
ninguna μ calculada con un valor candidato de media vida. Lo consultado:

- el código y la configuración (`src/sqp/models/team_scoring.py`,
  `src/sqp/sports/adapters.py`, `src/sqp/sports/registry.py`,
  `src/sqp/backtesting/{tuning,roi_engine}.py`, `src/sqp/pipeline/probabilities.py`,
  `configs/leagues/ratings.yaml`, `configs/default.yaml`);
- los documentos de la sección 2 (exposición previa);
- **agregados sin desenlaces** sobre la instantánea
  `C:\dev\3\snapshots\bateria-ajustes-20261008`: cobertura de cuotas de totales por
  mes y antigüedad del último snapshot, la distribución de μ_h − μ_base para la
  rejilla de la sección 4 (sin el marcador del propio partido, solo el estado al
  cierre del día anterior), y μ_base frente a la línea capturada **solo para la
  base** (sección 9). Ninguna de esas cifras empareja una μ candidata con un total
  realizado ni con una línea del mercado.

Orden del operador (2026-10-09): «Sí, que Fable redacte el pre-registro de
recencia». Sale de la recomendación de `2026-10-09-resultado-bateria-ajustes.md`
(sección «Qué se deriva», punto 4, y «Recomendación de esta revisión»).

Sigue la forma y el rigor de los precedentes:
`2026-09-27-preregistro-bateria-ajustes.md` (y sus Enmiendas 1–3),
`2026-09-29-preregistro-tilt-nhl.md`, `2026-09-27-preregistro-descanso-nhl.md` y
`2026-09-26-preregistro-descanso-basket.md`.

**Esto no mide ventaja sobre el mercado.** Se distinguen probabilidad estimada,
probabilidad implícita, edge, hit rate observado, ROI esperado y ROI realizado, y
**solo se mide la primera** frente al desenlace. La línea y el no-vig del mercado
entran como **referencia de semántica**, no como objetivo a batir: la medición del
2026-09-07 (modelo *encompassed* por el consenso) sigue en pie, y un modelo menos
desfasado no es un modelo con ventaja.

---

## 1. La pregunta y el mecanismo

**Pregunta.** En NBA, NFL y NHL, ¿un decaimiento temporal de las tasas de anotación
(`scoring_half_life_days`), elegido en entrenamiento, mejora la distribución del
total que sirve el modelo, **y no la empeora en la línea que el mercado cotiza**?

### 1.1 Dónde vive (verificado en `a405995`)

- `TeamScoringRates` (`src/sqp/models/team_scoring.py:19-101`) acumula puntos a favor
  y en contra por equipo, regresados con `prior_games` (6) partidos ficticios a la
  media de la liga. Con `half_life_days > 0`, `_decay` (l. 40-61) multiplica por
  0,5^(Δdías/h) todas las sumas **y** `league_points` / `league_team_games` cada vez
  que avanza la fecha. Solo usa fechas pasadas: es incremental y sin fuga.
- Los dos adaptadores lo construyen con
  `half_life_days=params.get("scoring_half_life_days", 0.0)` y
  `prior_games=params.get("scoring_prior_games", 6.0)`
  (`src/sqp/sports/adapters.py:34-37` y 86-89).
- Valor vigente: **NBA 180** (`LEAGUE_OVERRIDES`, `registry.py:92`, elegido «por el
  precedente de wnba, no por minimizar», l. 87-89); **NFL 0** y **NHL 0** (sin
  clave); WNBA 60 (fuera de alcance, sección 3).
- Precedencia: `FAMILY_PARAMS` → `LEAGUE_OVERRIDES` → `league_params`
  (`configs/leagues/ratings.yaml`) (`registry.py:7-10`, `get_adapter` l. 125-129).
  Una activación iría en `ratings.yaml`.

### 1.2 Qué mercados mueve, por familia

- **NBA y NFL (`NormalMarginAdapter.estimate`, l. 50-70):** μ_total =
  `scoring.expected_total(...)`, P(Over L) = Φ((μ − L)/`total_sigma`). El margen sale
  del Elo y del descanso: **h2h y spreads no cambian** con h (lo confirma la rejilla
  del 2026-08-18: «spreads y moneyline IDÉNTICOS»).
- **NHL (`PoissonAdapter._rates`, l. 107-124):** `avg` = `expected_total`, y
  λ_home = avg·(0,5 + tilt) + bonus, λ_away = avg·(0,5 − tilt). El total esperado es
  avg + 0,10 y no depende de `tilt_scale` (Enmienda 1(c) de la batería). Pero la
  **escala** sí mueve las probabilidades de victoria y de la puck line: h cambia
  **h2h, spreads y totales** NHL. Es el motivo por el que el 2026-08-18 no se cambió
  (sección 2).

### 1.3 La semántica de producción

En producción, P(Over) se evalúa en la línea principal del consenso
(`_pick_main_lines`, `src/sqp/pipeline/probabilities.py:153-164`), no en una línea
fijada por el modelo. Es la lección del informe 7 de la batería: un término que
corrige μ **frente a la propia μ** puede empeorar frente a una línea que ya incorpora
la recencia. Aquí la situación es distinta en un punto clave —un cambio de h mueve
μ, y P(Over L_m) = Φ((μ − L_m)/σ) depende directamente de la calidad de μ, no de
una diferencia «ventana − línea»—, pero eso es un argumento, no una medición. Por
eso el diseño tiene dos fases (sección 7): una histórica con potencia y una de
mercado que vigila la semántica de producción.

## 2. Lo que ya se sabe y exposición previa (declarada)

El histórico **no es virgen** para esta hipótesis. Quien redacta conoce:

1. **2026-07-04 (WNBA):** 180 días corrigió un sesgo Under; **2026-08-18:** 180 → 60
   con `tune_market_param`, medido en la línea real del mercado (mejora OOS +0,0289,
   4 folds) (`registry.py:61-75`; Bitácora 2026-08-18).
2. **2026-08-18 (NBA):** rejilla evaluada desde 2024 en una línea fija de 227
   (Bitácora 2026-08-18): Brier de totales 0,3567 (h = 0), **0,2367 (90)**, 0,2383
   (180), 0,2405 (365). Se eligió 180 por precedente, no por argmin. **Quien redacta
   conoce, por tanto, que 90 tuvo un Brier algo menor que 180 en esa evaluación.**
3. **2026-08-18 (NHL):** con 90 días, el Brier de totales mejoró −0,0029 y empeoraron
   spreads (+0,0014) y moneyline (+0,0011). Después, `tune_market_param` lo
   **rechazó** (argmin 0, mejora OOS 0,0000 frente a 0,002, 4 folds; `1d14d31`,
   `Obsidian/Tareas.md:101`). Aquel tuner puntuaba una **línea fija** sobre todo el
   histórico 2002-2026: la Enmienda 2(f) de la batería explica por qué eso mide sobre
   todo el **nivel** del total y no la recencia. Este pre-registro es, para la NHL,
   **una reapertura** de una decisión cerrada, justificada por un instrumento
   distinto (puntuación sin línea, sección 7.3) y por la evidencia nueva del punto 4.
   Se declara como tal (decisión 3 del operador).
4. **Batería (2026-10-09):** adj4 y adj10 aceptan en NBA y NFL en L_i = ⌊μ⌋ + 0,5;
   adj4 NHL queda en −0,00198. El punto 8 del dictamen (exploratorio, posterior)
   midió RMSE(μ) frente a RMSE(media de 10 partidos) en los tests combinados: NBA
   19,35 frente a 18,76; NFL 14,08 frente a 13,86; NHL 2,30 frente a 2,31. El informe
   8 midió que quitar los 180 días de la NBA empeora la base en +0,20 en L_i. El
   informe 7 midió, en la línea capturada, Δ > 0 para el **término aditivo** (no para
   h) en las cuatro ligas, con n = 237 / 33 / 238 en NBA / NFL / NHL.
5. **Agregados calculados para este documento** (sección 9, sin desenlaces): el
   tamaño de μ_h − μ_base por h, y que la μ de la **base** queda, en la muestra con
   línea capturada, de media **+3,43 puntos por encima** de la línea en la NBA
   (RMS 9,13), −1,40 en la NFL (RMS 3,46, n = 33) y **−0,21 goles** en la NHL
   (RMS 0,46). En la NHL, cualquier h > 0 sube μ en ≈ +0,43 goles de media sobre
   el periodo 2022-2026 (sección 9.1). **Quien redacta puede, por tanto, intuir el
   signo de la distancia al mercado de algunos candidatos.** No se ha calculado
   para ningún candidato, ni ninguna pérdida.

**Cómo se trata.** Ninguna elección de este documento sale de esos números: la
rejilla es de valores redondos fijada por escala temporal (sección 4), la regla de
selección es mecánica en entrenamiento, las particiones son las de la batería, el
margen y α son los de los precedentes, y la fase de mercado (la única cuya muestra
está parcialmente expuesta por el informe 7) solo puede **vetar**, no aceptar. Un
ACEPTA sobre esta muestra es una evidencia algo más débil que sobre una virgen, como
en la batería.

## 3. Ligas y mercados

| Liga | Familia | h vigente | Rol | Motivo |
|---|---|---:|---|---|
| **NBA** | basketball | 180 | **decide** | 25 temporadas; revisar el 180 (elegido por precedente) |
| **NFL** | football | 0 | **decide** | media acumulada desde 2002; potencia de mercado baja (sección 9.3) |
| **NHL** | hockey | 0 | **decide** | media acumulada desde 2002; reapertura declarada (sección 2.3); mueve h2h y puck line |
| MLB | baseball | 0 | excluida | adj4 MLB nulo en la batería; 4 temporadas en el store (el arrastre lo limita el propio store); la escala interactúa con abridor y parque; temporada regular terminada |
| WNBA | basketball | 60 | excluida | ya ajustada contra el mercado el 2026-08-18; temporada terminada; n pequeño |
| NCAAB / WNCAAB / NCAAF | — | 0 | excluidas | una o tres temporadas en el store: con una sola temporada el decaimiento casi no cambia los pesos; sin test posterior |

**Mercado de decisión:** totales en las tres ligas. **Restricción** (NHL): h2h y
puck line ±1,5 no pueden empeorar (sección 7.4).

## 4. Parámetro, rejilla y selección (sin *snooping*)

- **Un solo parámetro por liga:** `scoring_half_life_days`. `scoring_prior_games`
  (6), `total_sigma` (NBA 22, NFL 13,5), `home_scoring_bonus`, `tilt_scale` y el Elo
  **no cambian**. Ajustar a la vez σ o el prior sería un grado de libertad más; si la
  μ mejora, la reestimación de `total_sigma` es un paso posterior y aparte
  (sección 16.4).
- **Rejilla, igual para las tres ligas (11 valores, en días naturales):**
  **{0, 30, 45, 60, 90, 120, 180, 270, 365, 540, 730}**. Incluye el 0 (sin
  decaimiento), el 180 vigente en la NBA y el 60 de la WNBA; cubre de ≈ 1 mes a 2
  años con espaciado aproximadamente geométrico. Se usa rejilla y no un optimizador
  continuo porque el objetivo es escalonado en la práctica y el valor desplegado
  debe ser legible; con 11 puntos no hay un grado de libertad relevante (la
  diferencia 90/180 del 2026-08-18 fue de 0,0016 de Brier).
- **Regla de selección:** en cada partición, **h_P = argmin de la pérdida media de
  entrenamiento** (sección 7.3) sobre la rejilla, con los partidos evaluados desde el
  warmup hasta el día anterior al test. Empate exacto: el h más cercano al vigente;
  si persiste, el mayor. **El test nunca interviene en la selección.**
- **Valor que se evaluaría en el mercado y que se activaría:** **h_C**, el elegido en
  el entrenamiento de la última partición (C), **sin reestimar** con todo el
  histórico. Es el precedente del descanso, el tilt y la batería. h_C se fija con
  entrenamiento hasta 2022-09-30 (NBA, NHL) o 2022-06-30 (NFL), así que toda la
  muestra de mercado (2026-03 en adelante) es fuera de muestra para él.
- Si h_P coincide con el valor vigente en alguna partición, en esa partición T ≡
  base, Δ = 0 y el criterio H2 falla: la liga **RECHAZA** (se declara ahora para que
  no se lea como defecto).

## 5. Base vigente exacta

- **Commit de referencia:** `a405995` (`a405995cf330…`, `main`, árbol limpio al
  redactar). `git log ee0ab19..a405995 -- configs src scripts/research` está vacío:
  la base es **la misma que midió la batería**.
- **SHA-256:** `configs/leagues/ratings.yaml` `7b904e4c…b483`;
  `configs/default.yaml` `fc2f9520…eed8f`.
- **Parámetros resueltos que el script aserta (aborta si difieren)**, los de la
  Enmienda 1(b) de la batería:
  - NBA (`BasketballAdapter`): `avg_total 224.0`, `elo_home_adv 70`, `elo_k 20`,
    `elo_mov True`, `margin_sigma 13.0`, `points_per_elo 0.028`,
    `rest_points_per_day 0.795`, **`scoring_half_life_days 180.0`**,
    `total_sigma 22.0`, y ninguna otra clave;
  - NFL (`FootballAdapter`): `avg_total 44.0`, `elo_home_adv 55`, `elo_k 24`,
    `elo_mov True`, `margin_sigma 13.5`, `points_per_elo 0.025`, `total_sigma 13.5`,
    y ninguna otra clave (**sin** `scoring_half_life_days`: 0 por defecto);
  - NHL (`HockeyAdapter`): `avg_total 6.1`, `elo_home_adv 15.0`, `elo_k 10`,
    `home_scoring_bonus 0.1`, `max_score 15`, `tilt_scale 0.439`, y ninguna otra
    clave.
  - `_league_meta(liga)["league_params"]`: NBA `{"rest_points_per_day": 0.795}`,
    NFL `None`, NHL `{"elo_home_adv": 15.0, "tilt_scale": 0.439}`.
- **Trampas** (las de la batería): `get_adapter("nhl", "hockey")` sin `league_params`
  devuelve el tilt viejo (0,9); el candidato se construye **siempre** como
  `league_params ∪ {"scoring_half_life_days": h}` sobre los parámetros resueltos.
- Si entre la redacción y el `--pre` se commitea cualquier cambio en `configs/` o
  `src/sqp/` que toque la base de estas ligas, se enmienda esta sección y se repite
  el `--pre` (precedente de la Enmienda 1 de la batería).

## 6. Datos, corte e instantáneas

**Fase H (histórica).** `ResultsStore.load(liga)` con `date ≤ 2026-09-26`, el filtro
de `game_id` repetido de la Enmienda 3(c) de la batería (0 descartes esperados en
estas tres ligas; se aserta) y la **misma instantánea** de la batería
(`C:\dev\3\snapshots\bateria-ajustes-20261008`), cuyos hashes ya están registrados.
Reutilizarla elimina un grado de libertad (los recuentos son los del resultado de la
batería: tests NBA 19.332, NHL 16.950, NFL 4.604). `--data-root` obligatorio; aborta
si resuelve a los datos vivos.

**Fase M (mercado).** Instantánea **nueva**, creada el día de ejecución de la fase M
(sección 8.2) con el mismo mecanismo (Enmienda 1(g) de la batería):
`results_{nba,nfl,nhl}.csv` y todos los `odds_{nba,nfl,nhl}_*.csv`, en
`C:\dev\3\snapshots\recencia-totales-M-<AAAAMMDD>`. Corte de la fase M: resultados y
eventos con `date ≤ D` (fecha de corte de la sección 8.2).

**Semántica temporal.** `date` es el día UTC de inicio. El estado del adaptador que
estima un día es el del cierre del día anterior (bucle de `walk_forward_backtest`).
La línea es la del último snapshot **estrictamente anterior** al `commence_time`
(`load_closing_odds`, con el `commence_time` más reciente reportado, KI-019).

## 7. Fase H: walk-forward histórico (decide existencia y valor)

### 7.1 Particiones (las de la batería, sin cambios)

| Liga | A: test | B: test | C: test |
|---|---|---|---|
| NBA | 2012-10-01 – 2017-09-30 | 2017-10-01 – 2022-09-30 | 2022-10-01 – 2026-06-30 |
| NHL | 2014-10-01 – 2018-09-30 | 2018-10-01 – 2022-09-30 | 2022-10-01 – 2026-06-30 |
| NFL | 2012-07-01 – 2017-06-30 | 2017-07-01 – 2022-06-30 | 2022-07-01 – 2026-06-30 |

Entrenamiento: desde el warmup (60 partidos) hasta el día anterior al test. El modelo
base y cada candidato son **un walk-forward completo** por valor de h (11 recorridos
por liga); lo único que se elige por partición es h_P.

### 7.2 Brazos

| Brazo | Qué es |
|---|---|
| Base | producción en `a405995` (h vigente) |
| **T** | producción con `scoring_half_life_days = h_P` (partición P) |
| **C** (control de nivel) | base con la μ desplazada por una constante a_P, estimada en el entrenamiento de P minimizando la misma pérdida; en la NHL, `avg_i + a_P` dentro de las mismas fórmulas de λ |

**Por qué C.** En NFL y NHL, la base es una media acumulada desde 2002 y su sesgo de
nivel cambia con la era (informe 1 de la batería). Un h > 0 corrige ese nivel **y**
sigue el entorno de cada equipo. C separa la parte que un desplazamiento constante
ya captura. Como en la batería, C no controla un nivel que **cambia con el tiempo**:
esa parte es recencia legítima de la liga y se acepta como tal (limitación 6 de la
batería, declarada).

### 7.3 Métrica de la fase H: pérdida del total sin línea

La pérdida por partido es el **log loss de la distribución del total del propio
adaptador** en el total realizado T_i:

- NBA y NFL: −log[φ((T_i − μ_i)/σ)/σ], con σ = `total_sigma`. Con σ fijo, ordena
  igual que el error cuadrático de μ.
- NHL: −log P(T = T_i) con la rejilla conjunta de Poisson de
  `poisson_match_probs` (truncada en `max_score` 15 y renormalizada, como hace el
  adaptador), es decir, P(T = k) = P(Over k − 0,5) − P(Over k + 0,5) en el código de
  producción. Partidos con T_i fuera de la rejilla: se cuentan y se excluyen de
  todos los brazos (no se esperan con 15 por equipo).

**Por qué esta métrica y no una línea fija.** En L_i = ⌊μ_h⌋ + 0,5 la línea depende
del candidato y la base queda en p ≈ 0,5 por construcción (punto 8 de la batería);
en una línea fija sobre 25 años se mide el nivel de la era (Enmienda 2(f)). La
pérdida de la distribución completa es una regla de puntuación propia, independiente
de la línea, y es la que mide directamente lo que h cambia: la calidad de μ. La
semántica de línea queda para la fase M y para el criterio H4.

### 7.4 Criterios de aceptación de la fase H (por liga, todos a la vez)

1. **H1.** Δ pérdida (T − base) en el **test combinado** ≤ **−0,002**.
2. **H2.** Δ < 0 en **cada** partición.
3. **H3.** pérdida(T) < pérdida(C) en el test combinado (signo; decisión del
   operador del 2026-09-30 en el tilt).
4. **H4.** Log loss **binario** de P(Over) en L_i^base = ⌊μ_base,i⌋ + 0,5 (la línea
   de la batería, fijada por la base y común a los brazos): Δ (T − base) ≤ 0 en el
   test combinado. Conecta la fase H con el log loss binario canónico.
5. **H5 (solo NHL).** Δ log loss de h2h (P(local), sin empates) ≤ 0 y Δ medio de
   `spreads@-1.5` y `spreads@+1.5` ≤ 0 en el test combinado, con el h_P de cada
   partición (lectura de la Enmienda 1(e) de la batería).
6. **H6.** Holm sobre **K = 3** (una celda por liga), α de familia 0,05: la liga debe
   estar entre las rechazadas por Holm, con p = Φ(Δ̂_H1/EE) y EE del bootstrap de la
   sección 10.

Si falla cualquiera, la liga **RECHAZA** en la fase H y no pasa a activación.

**Origen de los umbrales.** 0,002 es `IMPROVEMENT_MARGIN` (`tuning.py:38`), un
margen en log loss por partido; aquí se aplica a otro log loss por partido (el de la
distribución del total). Es una extensión y se marca para el operador (decisión 4).
α = 0,05 y Holm: decisión del operador del 2026-09-27 en la batería. K = 3 es un
hecho de diseño (tres ligas), fijado ahora. H2–H5: signos y comparaciones con 0.

## 8. Fase M: semántica de producción en la línea capturada (puede vetar, no aceptar)

### 8.1 Muestra, línea y métrica

- **Muestra:** todos los partidos con `date` en [2026-03-01, D] de la liga,
  emparejados con un evento de cuotas por `roi_engine._match_index` /
  `_match_result` con `get_team_normalizer(liga)` (ambigüedades omitidas, como en el
  informe 7), con línea principal de totales (`_pick_main_lines`) y no-vig completo
  (`_consensus_lines` + `_novig_probs(cons, "totals", L)`). Se excluyen los empujes
  (T = L) en la evaluación. El 2026-03-01 es posterior al entrenamiento de h_C en las
  tres ligas.
- **Línea:** la del último snapshot anterior al inicio (`load_closing_odds` sin
  `max_age_min`), que es la que usa `roi_engine` y el informe 7. La submuestra con
  `CLOSE_MAX_AGE_MIN = 90` (`src/sqp/audit/clv.py:42`) se informa aparte, sin
  decidir.
- **Probabilidad del modelo:** `model_probability` pura (la del gate), P(Over L_m),
  sin capa de ajustes (todos los coeficientes valen 0), sin calibrador (no hay
  calibradores NBA, NFL ni NHL en el registro vivo ni en staging, verificado hoy) y
  sin shrink. En la NHL, con línea entera, P = P(Over)/(P(Over) + P(Under)), la
  probabilidad condicionada a no empuje.
- **Métrica primaria:** Δ_M = log loss binario (T con h_C − base) en la muestra.

### 8.2 Fecha de ejecución y muestra mínima (fijadas ahora)

- **Fecha de corte D = 2027-01-31** (UTC) para las tres ligas. Se ejecuta **una
  vez**, en los 7 días siguientes, con la instantánea nueva.
- **Muestra mínima (partidos emparejados con línea y no-vig, antes de excluir
  empujes):** **NBA 800, NHL 800, NFL 250.**
- **Si una liga no llega:** **una única prórroga** de esa liga a D' = 2027-04-20.
  Si tampoco llega, la liga queda **NO CONCLUYENTE** en M y **no se activa** (sección
  15). No hay más miradas ni más prórrogas.
- **Conteo sin desenlaces:** el `--pre` de la fase M cuenta los emparejados (con
  línea y no-vig) sin leer marcadores salvo para el emparejamiento. Si no llega al
  mínimo, no se ejecuta el modo completo de M para esa liga.

### 8.3 Criterios de la fase M (por liga que haya aceptado H)

1. **M1.** n ≥ mínimo de la sección 8.2.
2. **M2.** Δ_M ≤ 0 (estimación puntual) en totales.
3. **M3 (solo NHL).** Δ log loss de h2h (P(local), en los mismos emparejados) ≤ 0.

**Por qué un veto y no un criterio de aceptación con margen.** Con la cobertura de
cuotas disponible, un criterio con margen 0,002 y Holm exigiría varios miles de
partidos con línea por liga (sección 9.3): temporadas 2027-28 o posteriores. La
existencia y el valor ya los decide la fase H, con potencia. Lo que la fase M debe
detectar es el **modo de fallo** del informe 7: un cambio que mejora frente al
desenlace pero empeora en la línea del mercado. Aquel daño fue de +0,05 a +0,11,
detectable con estos n casi con certeza (sección 9.3). Un M2 que se cumple **no** es
evidencia de mejora en el mercado; se informa el IC, sin presentarlo como tal.

## 9. Potencia y tamaño de muestra (sin desenlaces)

### 9.1 Cuánto mueve h la μ (test C, estado al cierre del día anterior)

RMS(μ_h − μ_base) y media(μ_h − μ_base), test C de cada liga (NBA 5.577, NFL
1.339, NHL 5.978 partidos):

| h | NBA (base 180) | NFL (base 0) | NHL (base 0), goles |
|---:|---|---|---|
| 0 | −20,90 · RMS 21,40 | — | — |
| 30 | +1,08 · 3,33 | −0,53 · 3,70 | +0,43 · 0,53 |
| 60 | +0,96 · 2,30 | −0,35 · 2,99 | +0,44 · 0,51 |
| 90 | +0,72 · 1,52 | −0,11 · 2,63 | +0,45 · 0,51 |
| 120 | +0,46 · 0,90 | +0,06 · 2,44 | +0,45 · 0,51 |
| 180 | — | +0,28 · 2,24 | +0,45 · 0,50 |
| 365 | −1,26 · 1,72 | +0,67 · 1,99 | +0,43 · 0,46 |
| 730 | −4,31 · 4,82 | +0,91 · 1,72 | +0,34 · 0,37 |

(45, 270 y 540 caen entre sus vecinos.) Lectura: en la NBA, cualquier valor de 60 a
365 mueve μ entre 1 y 2,3 puntos RMS frente a σ = 22; en la NFL, 1,7–3,7 puntos
frente a σ = 13,5, sobre todo por equipo (la media apenas cambia); en la NHL,
≈ +0,45 goles, casi todo **nivel** (la media acumulada desde 2002 va por debajo de la
era actual). Por eso el control C (sección 7.2) es especialmente relevante en la NHL.

### 9.2 Fase H

Error estándar ingenuo del Δ por partido (sin agrupar por días; el bootstrap da el
bueno):

- Normal: DE(Δ_i) ≈ RMS(d)·RMSE(μ)/σ², con d = μ_h − μ_base y el RMSE(μ) del punto 8
  de la batería (exposición declarada). NBA: 0,036–0,13 → **EE 0,0003–0,0009** con
  19.332 partidos. NFL: 0,13–0,29 → **EE 0,0019–0,0042** con 4.604.
- NHL (Poisson): DE(Δ_i) ≈ RMS(d)/√μ ≈ 0,5/2,5 ≈ 0,2 → **EE ≈ 0,0015** con 16.950.

NBA y NHL tienen potencia holgada para el margen. La NFL solo aprueba si el efecto es
de varias veces el margen; el informe 4 de la batería no se usa para estimarlo. Holm
con K = 3 pide p ≤ 0,05/3, es decir, z ≥ 2,13, en el primer escalón: NBA y NHL,
sobrados; NFL, Δ ≈ −0,004 a −0,009 (más si el agrupamiento por jornadas infla el EE).

### 9.3 Fase M

**Cobertura capturada hasta la instantánea** (eventos con línea de totales, último
snapshot antes del inicio):

| Liga | Por mes de inicio | Antigüedad mediana del último snapshot | Libros (mediana) |
|---|---|---|---|
| NBA | 2026-03 48 · 04 146 · 05 40 · 06 6 (239 emparejados) | 2,2 h | 11 |
| NHL | 2026-03 51 · 04 167 · 05 42 · 06 6 · 09 7 · 10 59 (258 emparejados hasta 2026-06) | 2,1–2,7 h | 11 |
| NFL | 2026-09 48 (33 emparejados hasta el corte del 26/09); 10–01 ya capturados con días de antelación | 1,0 h (sept.) | 3 |

En marzo de 2026 la NBA tuvo 48 eventos capturados frente a 237 partidos jugados:
la captura cubría solo parte del mes; desde abril cubre casi todo. **Hoy no hay
muestra de mercado útil para decidir**: la NFL tiene 33 partidos y NBA y NHL un solo
tramo de fin de temporada y playoffs.

**Muestra esperada en D = 2027-01-31,** con captura completa: NBA ≈ 239 + ≈ 730
(temporada desde finales de octubre) ≈ 970; NHL ≈ 258 + ≈ 800 ≈ 1.050; NFL ≈ 33 +
≈ 280 ≈ 310. De ahí los mínimos de la sección 8.2 (con holgura por huecos de
captura).

**Error estándar del Δ_M:** DE(Δ_i) ≈ 2·δ_RMS, con δ_RMS el cambio de probabilidad
en la línea. Normal: δ_RMS ≈ φ(z)·RMS(d)/σ; en la muestra capturada la base queda
lejos de 0,5 (RMS(p_base − 0,5) = 0,156 en la NBA, 0,099 en la NFL y 0,092 en la
NHL), así que φ(z) < φ(0) y estas cifras son cotas superiores:

| Liga | δ_RMS (rango de la rejilla) | DE(Δ_i) | EE con el n de D | EE con 239/258/33 (hoy) |
|---|---|---|---|---|
| NBA | 0,016–0,06 | 0,03–0,12 | 0,001–0,004 (n 970) | 0,002–0,008 |
| NHL | ≈ 0,075 | ≈ 0,15 | ≈ 0,005 (n 1.050) | ≈ 0,009 |
| NFL | 0,05–0,11 | 0,10–0,22 | 0,006–0,013 (n 310) | 0,017–0,038 |

- **Detectar daño del tamaño del informe 7** (Δ de +0,05 a +0,11): probabilidad de
  veto ≈ 1 en NBA y NHL; en la NFL, ≥ 0,99 para +0,05 incluso con EE 0,013.
- **Si el cambio es neutro en el mercado** (Δ verdadero 0), M2 pasa con probabilidad
  ≈ 0,5: el veto no protege contra un cambio inútil, solo contra uno dañino. Lo que
  descarta lo inútil es la fase H.
- **Un criterio con margen** (Δ_M ≤ −0,002 y z ≥ 2,13, primer escalón de Holm con
  K = 3) pediría, para un efecto igual al margen, n ≈ (2,13 · DE/0,002)²: NBA
  1.000–16.000, NHL ≈ 25.000, NFL ≥ 11.000. No es alcanzable con la captura actual
  en ningún plazo razonable. De ahí el diseño de veto.

## 10. Incertidumbre

Bootstrap por **bloques de día UTC**: 10.000 réplicas, semilla 42 por liga y fase, un
único generador compartido por todos los estadísticos de la liga (lectura de la
Enmienda 2(b).7 de la batería), con todos los días del test combinado (fase H) o de
la muestra (fase M), aunque no tengan partidos válidos en algún mercado. Se informan
IC95 percentil y EE de: Δ H1, Δ por partición, T − C, Δ H4, Δ H5 (NHL), Δ_M y Δ M3.
El EE de H1 alimenta el p de Holm (aproximación normal, como en la batería). Fuera de
Holm, ningún IC es puerta.

## 11. Paridad con producción (aserciones; aborta si fallan; tolerancia 1e-12)

1. **Motor.** Para la base y para **cada** h de la rejilla,
   `walk_forward_backtest(results, liga, familia, params_h)` en las líneas fijas de la
   batería (NBA `totals@220.5`, NFL `totals@44.5`, NHL `totals@5.5`, y además
   `spreads@±1.5` y h2h en la NHL) coincide con la P que calcula el script para ese
   partido. `params_h` = parámetros resueltos de la sección 5 con
   `scoring_half_life_days = h`.
2. **μ.** En cada partido evaluado, la μ del script coincide con la que implica
   `adapter.estimate` del adaptador de producción construido con
   `get_adapter(liga, familia, league_params ∪ {scoring_half_life_days: h})`, para la
   base y para un h de prueba fijado en el script (90). En la NHL, además,
   |λ_home + λ_away − (μ_scoring + 0,10)| ≤ 1e-12 (Enmienda 1(c) de la batería).
3. **Distribución del total (NHL).** Σ_k P(T = k) = 1 ± 1e-12 y P(Over L) de la
   rejilla del script = `poisson_match_probs(...)["over"]` en L ∈ {4,5; 5,5; 6,5;
   7,5}.
4. **Fase M.** La línea, el no-vig y la P(Over L_m) del script coinciden con
   `_pick_main_lines`, `_novig_probs` y `build_model_map` del run diario para cada
   emparejado (la orientación local/visitante se resuelve como en el informe 7).
5. **Base sin cambios.** Las líneas L_i^base y los recuentos por partición del
   script coinciden con los registrados en el `--pre` de la batería
   (`pre_ee0ab19.json`, SHA-256 `173a5c1c…66c14be`), que no contiene desenlaces.

## 12. Fugas a vigilar

- **Temporal:** el decaimiento usa solo fechas pasadas; el estado que estima un día
  es el del cierre del anterior; el partido entra en las tasas **después** de su
  estimación. Los partidos del mismo día no se ven entre sí.
- **Selección:** h_P y a_P solo con entrenamiento; h_C, el valor de mercado y de
  activación, se fija con datos hasta 2022 y no se reestima.
- **Copias del mismo partido:** filtro de `game_id` de la Enmienda 3(c) (0 descartes
  esperados) y los 2 pares NBA de mismo local, visitante y marcador a 1–3 días del
  dictamen de la batería (irrelevantes frente a 19.332).
- **Cuotas:** `captured_at` comparado como instante (M-30), `commence_time` más
  reciente (KI-019), solo snapshots anteriores al inicio; ninguna cuota en vivo. Los
  emparejamientos ambiguos se omiten, sin fabricar etiquetas.
- **Ingesta tardía:** el corte es por `date`; las filas añadidas después se informan
  por partición y no se excluyen (Enmienda 1(f) de la batería).
- **Exhibiciones:** `ResultsStore` no distingue pretemporada (Enmienda 2(g)); entran
  en las tasas como en producción. Se informa el recuento por mes (agosto NFL,
  septiembre NHL).
- **Contaminación entre fases:** la fase H **no lee cuotas**. La fase M no puede
  cambiar h_C: lee el JSON de la fase H por hash.

## 13. Informes secundarios (no deciden)

1. Perfil de la pérdida de **entrenamiento** en la rejilla, por liga y partición, y
   h_A / h_B / h_C. Si h_C cae en un extremo de la rejilla, se dice.
2. Sesgo del total (media de μ − T) y DE del residuo por partición y brazo: informa
   si `total_sigma` quedaría desajustado con h_C (no se reestima aquí).
3. Δ por temporada, con las marcas de la burbuja 2019-20 y el calendario 2020-21.
4. Δ H1 con el h de **cada** valor de la rejilla en el test combinado (descriptivo:
   no cambia h_C).
5. Fase M: log loss del **no-vig** en la misma muestra (referencia de mercado);
   brecha log loss(modelo) − log loss(no-vig) para base y T; RMS(p − p_fair) para
   base y T; Δ de la mezcla de producción 0,5·p + 0,5·p_fair (`market_shrink` 0,5,
   `configs/default.yaml:17`), sin calibrador.
6. Fase M: submuestra con `CLOSE_MAX_AGE_MIN` 90; por mes; temporada regular frente
   a playoffs; spreads ±1,5 NHL en línea capturada.
7. Fase M: comparación con el término aditivo adj4 de la batería **no** se hace (está
   rechazado como activable; repetirlo no informa la decisión).

## 14. Contrato del script

Script único: `scripts/research/measure_totals_recency.py`. Reutiliza de
`measure_adjustment_battery.py`, importándolas, `load_league`,
`dedupe_by_game_id`, las aserciones de parámetros y el manifiesto (con las
constantes de esta sección 5), o las copia con paridad.

**Modos:**

- `--pre --data-root <inst. H> --out pre_H.json`: HEAD y `git status --porcelain`
  (vacío en todo el repo), manifiesto SHA-256/filas, hashes de configuración,
  parámetros resueltos (aserción), recuentos por partición, descartes por `game_id`,
  ingesta tardía, y la tabla de la sección 9.1 (debe reproducirla). **No empareja
  ninguna μ con su total ni calcula ninguna pérdida.** No lee cuotas.
- `--parity-only --data-root <inst. H>`: aserciones 1–3 de la sección 11 para la
  base, h = 90 y, en la aserción 1, todos los h de la rejilla. No estima nada.
- `--fase H --data-root <inst. H> --pre-json pre_H.json --out H.json`: aborta si el
  HEAD, los hashes o la tabla 9.1 difieren del `--pre`. Escribe
  `{procedencia, parametros_resueltos, rejilla, por_liga: {h_por_particion,
  a_por_particion, perdidas: {base, T, C} por partición y combinado, delta_H1,
  delta_por_particion, T_menos_C, delta_H4, delta_H5 (NHL), bootstrap: {IC95, EE,
  n_replicas}, p, criterios: {H1..H5: bool}, veredicto_H}, holm: {orden, umbrales,
  p_ajustados, rechazadas}, paridad: {desviacion_max por aserción y n},
  informes: {1..4}}`.
- `--fase M --pre --data-root <inst. M> --h-json H.json --out pre_M.json`:
  verifica el SHA-256 de `H.json` (commiteado), lee h_C, cuenta emparejados por
  liga y mes (sin desenlaces salvo para emparejar) y decide por la sección 8.2 qué
  ligas se miden.
- `--fase M --data-root <inst. M> --h-json H.json --pre-json pre_M.json --out
  M.json`: `{procedencia, h_C, por_liga: {n, n_empujes, n_ambiguos_omitidos,
  delta_M, IC95, EE, delta_M3 (NHL), criterios: {M1..M3}, veredicto_M},
  paridad_M, informes: {5, 6}}`.

Los informes `docs/research/AAAA-MM-DD-resultado-recencia-totales-{H,M}.md` se
redactan a partir de los JSON; el script no los genera. Las salidas viven en las
instantáneas y se fijan por hash, como en los precedentes.

## 15. Compromisos de ejecución

- Script, tests (paridad, rejilla, selección con empates, conteo sin desenlaces) y
  revisión de Fable **antes** del commit, y el commit **antes** del `--pre` de la
  fase H. Fase H completa justo después del `--pre`, sin commits en medio y lejos de
  las 12:00 de Uruguay.
- **Una sola ejecución por fase.** Sin miradas intermedias; sin cambiar rejilla,
  particiones, métrica, brazos, líneas, ligas, D ni mínimos después de ver nada.
- **E10:** solo se repite por un defecto de código o datos demostrable sin mirar el
  resultado (paridad rota, hashes distintos, filas mal ordenadas o unidas), con
  diagnóstico a ciegas y las dos salidas commiteadas. Un resultado adverso no es
  motivo para repetir.
- `H.json` y su informe se commitean **antes** de crear la instantánea M. Entre la
  fase H y D no se cambia nada de lo que fija este documento.
- Las enmiendas se añaden al final, antes de la ejecución a la que afectan, y mandan
  sobre el texto.
- **Reabrir tras un rechazo exige otra hipótesis**, no otra rejilla: por ejemplo, una
  ventana de recencia por número de partidos dentro de `TeamScoringRates`,
  `scoring_prior_games`, o separar el nivel de la liga del de cada equipo (dos medias
  vidas). Con datos nuevos y pre-registro propio.

## 16. Qué se deriva en cada desenlace

**Nada de este documento toca producción.** Para cada liga:

1. **H RECHAZA:** el h vigente se mantiene (NBA 180, NFL 0, NHL 0). La fase M se
   ejecuta igualmente para esa liga (si alcanza n) con valor solo descriptivo. Si en
   la NHL fallan solo H5, se documenta como el empate del 2026-08-18, ahora medido.
2. **H ACEPTA y M NO CONCLUYENTE (n insuficiente tras la prórroga):** no se activa.
   Queda abierta la decisión 5 del operador (históricos de cuotas) o esperar a la
   temporada siguiente con una enmienda que fije la nueva fecha **antes** de mirar.
3. **H ACEPTA y M veta (M2 o M3 fallan):** **no se activa.** Se documenta como
   contradicción entre la mejora frente al desenlace y la semántica de mercado, al
   estilo del informe 7, y se analiza con un pre-registro nuevo.
4. **H ACEPTA y M no veta:** **candidata a activación**, en este orden:
   1. **Addendum previo** en `2026-09-25-repreregistro-gate-k52.md`: el gate usa
      `model_probability`, y h cambia la `d` de `nba|totals`, `nfl|totals` y
      `nhl|totals`, y en la NHL también `nhl|h2h` y `nhl|spreads`. No cambia K ni el
      techo de 63 (el número de cortes no depende de h). Prohibición de recortar o
      re-segmentar la ventana después.
   2. **«El modelo manda»:** su ejecución está prevista hacia el 2026-11-24, antes de
      la fecha D. Si por cualquier motivo no se hubiera ejecutado, se espera a que se
      ejecute o se registra antes un addendum de cambio de régimen en
      `2026-08-26-preregistro-el-modelo-manda.md` (regla vigente).
   3. **Valor:** h_C de la liga, en `configs/leagues/ratings.yaml` (`nfl:` es una
      entrada nueva; en la NBA, el valor de `ratings.yaml` prevalece sobre el 180 de
      `LEAGUE_OVERRIDES`, que se deja con un comentario o se retira en el mismo
      commit), con un test que fije el valor resuelto por `get_adapter` y que la
      familia y el resto de ligas no cambien.
   4. **`total_sigma`:** si el informe 2 muestra que el residuo con h_C difiere del σ
      vigente, su reestimación es un paso **aparte** con su propia medición; no se
      ajusta en la misma activación.
   5. **Calibradores:** hoy no hay ninguno NBA, NFL ni NHL (verificado). Cualquier
      entrenamiento futuro usa filas de un solo régimen de h.
   6. **Commit antes del run de las 12:00** (guarda KI-036) y revisión de Fable antes
      del commit (`MODEL_ROUTING.md`: parámetro de modelo, clase de escalado).
   7. **Vigilancia:** si la primera temporada activa empeora el log loss de totales en
      la línea servida, se revisa con un pre-registro nuevo, no ajustando h a mano.
5. **Lectura obligatoria de cualquier ACEPTA:** el modelo se acercaría a una línea que
   ya incorpora la recencia. Mejora la probabilidad estimada; **no** crea edge, no
   cambia la conclusión de *encompassing* y no autoriza ninguna afirmación sobre hit
   rate ni ROI.

## 17. Decisiones del operador

1. **Diseño en dos fases (H decide; M solo veta).**
   - Opción A (**recomendada**): fase H histórica con criterios y Holm; fase M en la
     línea capturada como veto (sección 8). Es la única que da una decisión
     defendible esta temporada.
   - Opción B: la fase M como criterio de aceptación con margen 0,002 y Holm. Exige
     miles de partidos con línea por liga (sección 9.3): 2028 o después.
   - Opción C: solo la fase H. Repetiría el defecto del informe 7: decidir sin mirar
     la semántica de producción.
2. **Fecha D y mínimos.** Recomendado: **D = 2027-01-31**, mínimos **NBA 800 / NHL 800
   / NFL 250**, una prórroga única a 2027-04-20. Alternativa: D al final de la
   temporada regular (2027-04-20) sin prórroga, con más muestra y la activación
   aplazada a la temporada 2027-28.
3. **NHL como liga que decide, aunque su h se rechazó el 2026-08-18.** Recomendado:
   **incluirla**, declarando la reapertura (sección 2.3): aquel tuner medía el nivel en
   una línea fija, y la batería aporta evidencia nueva. El coste es K = 3 en Holm y el
   criterio H5. Alternativa: excluirla (K = 2) y dejar la NHL con 0.
4. **Margen 0,002 aplicado a la pérdida de la distribución del total (criterio H1).**
   Recomendado: **sí**: es un log loss por partido como el de `tuning.py:38`, y cerca
   de p = 0,5 una corrección de μ gana algo más en esta pérdida que en la binaria, así
   que es un margen de la misma escala. Alternativa: aplicar el margen al log loss
   binario en L_i^base (criterio H4), que es la métrica canónica pero solo usa el
   signo de μ_h − μ_base.
5. **Históricos de cuotas (gasto o integración de proveedor).** Para que la fase M
   tuviera potencia de aceptación haría falta comprar o integrar líneas de cierre
   históricas de varias temporadas. El precio y la licencia no están verificados en
   este documento. Recomendado: **no ahora**; reconsiderarlo solo si una liga acaba
   NO CONCLUYENTE o si se quiere la opción B.
6. **Momento de una activación.** Si la fase M no veta (≈ febrero de 2027), las
   temporadas NBA y NHL estarán en curso. Recomendado: **activar en cuanto se cumpla
   la sección 16.4**, con el addendum del gate: «el modelo manda» ya se habrá
   ejecutado, el gate evalúa el sistema tal como operó y la regla de la ventana limpia
   se fijó para no contaminar ese test, no el gate. Alternativa: esperar al final de la
   temporada regular (abril de 2027) para no mezclar regímenes dentro de una
   temporada.

Decisiones técnicas tomadas en este documento (revisables en la revisión del
script, no del operador): un solo parámetro; la rejilla de 11 valores y su regla de
empate; h_C sin reestimar; la pérdida de la distribución del total; el control C de
nivel constante; la reutilización de la instantánea de la batería en la fase H; la
línea sin `max_age_min`; la probabilidad condicionada a no empuje en líneas enteras
NHL; las aserciones de paridad.

**Decisiones del operador resueltas el 2026-10-09, antes de implementar** (respuesta
literal: «Aprobar todas (Recommended)»):

1. **RESUELTA — opción A:** diseño en dos fases; la fase H decide existencia y valor,
   la fase M solo veta (sección 8).
2. **RESUELTA — fecha y mínimos recomendados:** D = 2027-01-31; mínimos NBA 800,
   NHL 800 y NFL 250; prórroga única a 2027-04-20 (sección 8.2).
3. **RESUELTA — NHL incluida como liga que decide.** El operador **acepta
   expresamente la reapertura** de la decisión cerrada el 2026-08-18
   (`1d14d31`, `Obsidian/Tareas.md:101`), con K = 3 en Holm y el criterio H5
   (secciones 2.3 y 7.4).
4. **RESUELTA — margen 0,002 sobre el log loss de la distribución del total**
   (criterio H1); H4 sigue como criterio de signo.
5. **RESUELTA — no se compran ni integran cuotas históricas ahora.** Se reconsidera
   solo si una liga queda NO CONCLUYENTE en la fase M o si se quiere la opción B.
6. **RESUELTA — activación** en cuanto se cumpla la sección 16.4, con el addendum
   previo en `2026-09-25-repreregistro-gate-k52.md`, sin esperar al final de la
   temporada regular.

---

Relacionado: [[2026-10-09-resultado-bateria-ajustes]],
[[2026-09-27-preregistro-bateria-ajustes]], [[2026-09-29-preregistro-tilt-nhl]],
[[2026-09-30-resultado-tilt-nhl]], [[2026-09-26-preregistro-descanso-basket]],
[[2026-09-25-repreregistro-gate-k52]], [[2026-08-26-preregistro-el-modelo-manda]],
[[Bitácora/2026-08-18]].

---

## Enmienda 1 (2026-10-09, antes del commit del script y antes de `--pre`; redactada por Fable)

Revisión del script `scripts/research/measure_totals_recency.py` y de sus pruebas
`tests/research/test_measure_totals_recency.py`, ambos sin commitear al redactar,
sobre `027c019`. **Nada de esta enmienda sale de un resultado**: no se ha ejecutado
`--pre`, `--fase H` ni `--fase M`, y no se ha emparejado ninguna μ candidata con un
total realizado ni con una línea. Lo único ejecutado: las pruebas sintéticas, `ruff`,
`--parity-only` (asertos 1-3, que leen marcadores solo para excluir empujes y empates,
como el motor, y no calculan ninguna pérdida) y un diagnóstico de Sonnet **solo con
μ** (tabla 9.1 y aserto 5, sin desenlaces). Resuelve las 14 marcas `# DECISION:` del
script y los hallazgos de la revisión que exigen texto. **No cambia** criterios,
márgenes, α, K, rejilla, particiones, métrica, brazos, líneas, ligas, fechas ni
mínimos.

### (a) Tabla 9.1: tolerancia de la comparación con el documento (DECISION 1)

La tabla de la sección 9.1 está impresa a dos decimales. El `--pre` la recalcula y
aborta si una celda difiere de la impresa en más de **0,01** (una unidad del último
decimal impreso; en el código, 0,0101 por margen de coma flotante), no 0,005: el
diagnóstico sin desenlaces dio en la NBA, h = 90, una media de 0,7145 frente al 0,72
impreso (redondeo de una cifra intermedia al redactar). Es una comprobación de que el
`--pre` ve los mismos datos que vio quien redactó, no un criterio. La comparación
`--fase H` frente a `--pre` sigue en 1e-12.

### (b) Partidos con T_i fuera de la rejilla NHL (DECISION 2)

«Se excluyen de todos los brazos» (sección 7.3) se lee como: se excluyen de **todas
las métricas que puntúan el total** —H1, Δ por partición, T − C, H4 y los informes
2-4—. H5 (h2h y puck line) no puntúa el total y usa todos los partidos del test (h2h
sin los empates de marcador). La validez depende solo de T_i, así que la muestra es la
misma para todos los brazos. Se esperan 0 casos; `n_fuera_de_rejilla` se informa.

### (c) Lectura de H5 (DECISION 3)

«Δ medio de `spreads@-1.5` y `spreads@+1.5` ≤ 0» = media, sobre los partidos del test
combinado, de (Δ@−1,5 + Δ@+1,5)/2 por partido; con las dos líneas sobre los mismos
partidos es idéntico a la media de los dos Δ. H5 exige **además**, por separado,
Δ log loss de h2h ≤ 0 (partidos con margen ≠ 0). Las dos condiciones a la vez.

### (d) Ajuste de a_P en el control C (DECISION 4)

NBA y NFL: a_P = media del residuo T_i − μ_i en el entrenamiento de P, que es el
mínimo **exacto** de la pérdida normal con σ fijo (no hace falta optimizador). NHL:
Nelder-Mead con las opciones de la batería (sección 9 de aquel documento), punto de
partida 0, abortando si no converge; λ con el mismo suelo de 0,1 que
`PoissonAdapter._rates`.

### (e) SHA-256 de `H.json` (DECISION 5)

`H.json` vive en la instantánea, fuera del repositorio; lo que se commitea es su hash.
El informe `AAAA-MM-DD-resultado-recencia-totales-H.md` **debe imprimir** el SHA-256
de `H.json`, y ese es el valor que se pasa a `--fase M --pre` con `--h-sha256`. El
script aborta si el fichero no lo reproduce. Además (corrección de código F4), `pre_H`,
`H.json`, `pre_M` y `M.json` registran el SHA-256 de `measure_totals_recency.py` y de
`measure_adjustment_battery.py`; si en la fase M difieren de los de `H.json`, el
`--fase M --pre` aborta y solo puede continuar tras una enmienda, redactada antes de
mirar nada de la fase M, que justifique el cambio de código (p. ej., un defecto
demostrado sin desenlaces, E10).

### (f) Prórroga, ventana y una sola ejecución en la fase M (DECISIONES 6 y 7)

1. La fecha de corte se pasa con `--m-cutoff ∈ {2027-01-31, 2027-04-20}`. La ventana
   de «los 7 días siguientes» es disciplina operativa: el informe M registra la fecha
   de creación de la instantánea y la de ejecución.
2. **Ninguna liga se mide dos veces.** En D' = 2027-04-20 solo se miden las ligas que
   el `--fase M --pre` de D marcó como `prorroga`; las medidas en D no se vuelven a
   medir (corrección de código F1: el `--pre` de D' recibe el `pre_M` de D y deja
   fuera las demás).
3. **Ligas con H RECHAZA (sección 16.1):** la fase M se mide en D si la liga alcanza el
   mínimo, con `valor: descriptivo`; **no tienen prórroga** (no deciden nada, y una
   segunda fecha sería una mirada más sin uso). Si no alcanzan el mínimo en D, quedan
   «no medidas (descriptivo)».
4. Entre `--fase M --pre` y `--fase M` no hay commits (el script exige el mismo HEAD),
   igual que entre `--pre` y `--fase H`.
5. Si entre la fase H y D cambia cualquier parámetro resuelto de NBA, NFL o NHL (por
   ejemplo, una recalibración del descanso NBA), el `--fase M --pre` aborta, como ya
   hace. La fase M no se ejecuta hasta que una enmienda, escrita **antes** de medir,
   fije la base de la fase M (la de producción en D, con el mismo h_C). Abortar ahí no
   es una ejecución.

### (g) n de M1 y empujes (DECISION 8)

n = emparejados con línea principal de totales y no-vig completo, **antes** de excluir
empujes (como dice la sección 8.2). En Δ_M y M3 los empujes (T = L) y, en h2h, los
empates tienen peso 0; el bootstrap remuestrea todos los días de la muestra. El modo
completo de M aserta que su n y su conteo por mes son **idénticos** a los del
`--fase M --pre` sobre la misma instantánea (corrección de código F3).

### (h) Emparejamientos ambiguos (DECISION 9)

`n_ambiguos_omitidos` cuenta los avisos «AMBIGUO» que `roi_engine._match_result` emite
al omitir una doble jornada. Es descriptivo; no entra en ningún criterio. El orden de
recorrido es la clave de `realized_roi_backtest` (fecha, equipos, `game_id` y, como
último desempate, los marcadores como texto): el `--fase M --pre` lee esas columnas
solo como clave de orden del emparejamiento, nunca las empareja con una μ. Se acepta
como el «salvo para emparejar» de la sección 8.2.

### (i) Líneas de cuarto en la fase M (DECISION 10)

Si la línea principal es de cuarto (x,25 / x,75), P(Over) es la de producción
(`build_model_map`, probabilidad de decisión sobre las dos líneas adyacentes) y no hay
comparación de paridad 4 para ese partido; el JSON informa cuántos hay. La etiqueta es
1{T > L}: en totales de cuarto no hay desenlaces mitad ganados y mitad perdidos, así
que coincide con el signo de la liquidación, y no hay empuje.

### (j) Informe 6 (DECISION 11)

- **Temporada regular frente a playoffs:** se retira del informe 6. `ResultsStore` no
  guarda la fase de la temporada y cortar por fechas sería inventar un umbral.
- **Submuestra `CLOSE_MAX_AGE_MIN` = 90:** emparejados cuyo evento está en
  `load_closing_odds(max_age_min=90)`, sin reemparejar. No decide.

### (k) Paridad en `--fase H` (DECISION 12)

`--fase H` ejecuta las paridades 1-3 completas (los 11 h; ≈ 45 min) y aborta si falla
alguna. Las paridades de **las tres ligas** se ejecutan antes de calcular la primera
pérdida (corrección de código F5). Un aborto de paridad no escribe salida y no es una
ejecución a efectos de la sección 15; tras corregir el defecto se repite según E10.

### (l) Parámetros del aserto 1 (DECISION 13)

`params_h` = los parámetros resueltos de la sección 5 con `scoring_half_life_days = h`,
con la comprobación adicional de que resuelven al mismo adaptador que
`league_params ∪ {scoring_half_life_days: h}`. Aceptado.

### (m) `--data-root` (DECISION 14)

Obligatorio en todos los modos. `--parity-only` admite el árbol vivo, porque no mide
nada; los modos que miden lo rechazan, igual que cualquier ruta dentro de `data/`.

### (n) Salidas no sobrescribibles (E10)

`--pre`, `--fase H` y `--fase M` **abortan si el `--out` ya existe** (corrección de
código F2). Una repetición por E10 escribe en un fichero nuevo, y se commitean las dos
salidas, como exige la sección 15.

### (o) Verificaciones de esta revisión (sin desenlaces)

- `--parity-only` de Sonnet, rejilla completa: asertos 1-3 con desviación máxima
  ≤ 2,3e-15 en NBA (34.005 evaluados), NFL (7.986) y NHL (32.840).
- Repetido por Fable: `--parity-only --leagues nfl,nhl --h-subset 0,90`, PARIDAD OK;
  desviación máxima NFL 0,0 (asertos 1 y 2) y NHL 2,1e-15 / 1,9e-15 / 2,2e-15
  (asertos 1, 2 y 3).
- Diagnóstico solo con μ: aserto 5 frente a `pre_ee0ab19.json` y tabla 9.1 dentro de
  (a).

### (p) Decisiones del operador

Ninguna. Todo lo anterior son lecturas técnicas del contrato, revisables en la
revisión del script (sección 17, último párrafo).

### (q) Addendum a la Enmienda 1(e) (2026-10-09, antes del commit del script)

Los SHA-256 de código de (e) (`codigo_sha256`) se calculan sobre el contenido de
`measure_totals_recency.py` y `measure_adjustment_battery.py` con los finales de línea
normalizados a LF (CRLF → LF), no sobre los bytes de la copia de trabajo: el repositorio
fija `eol=lf` y una copia CRLF reescrita por git no es un cambio de código. Cualquier otra
diferencia sigue abortando como dice (e).

## Enmienda 2 (2026-10-18, antes de mirar nada de la fase M): cambio de código por la remediación audit-2026-10-18

Escrita **antes** de ejecutar `--fase M --pre` y sin ningún desenlace de la fase M: no se ha calculado ningún Brier, ningún `diff` ni ningún acierto de la ventana M. Es la enmienda que exige la Enmienda 1(e) cuando el SHA-256 de `measure_totals_recency.py` o de `measure_adjustment_battery.py` difiere del registrado en `H.json`.

**Qué cambió en producción.** La remediación de la ronda `audit-2026-10-18` introdujo dos cambios que alteran lo que estos scripts leen de producción:
- AUD-001: `HockeyAdapter.TIE_ADDS_GOAL`, que reparte el empate reglamentario de la NHL en (k+1,k)/(k,k+1) y reescala los ritmos;
- AUD-003: `ResultsStore.load`, que ahora descarta las filas con `game_id` repetido.

Sin tocar los scripts, la fase M mediría NHL con un pricing distinto del de la fase H, y la Enmienda 3(c) de la batería dejaría de ver los 15 `gamePk` MLB, que ya descarta `load`, y abortaría.

**Cambio de código, solo para conservar el contrato de la fase H:**
1. El `__main__` de `measure_totals_recency.py` ejecuta `main()` dentro de `sqp.sports.adapters.regulation_tie_without_goal()`. Ese gestor fija `HockeyAdapter.TIE_ADDS_GOAL = False` solo mientras dura la ejecución y lo restaura al salir. Es el pricing con el que se midió la fase H, y lo usan igual el adaptador del script y el motor de producción (`walk_forward_backtest`) contra el que se comprueba la paridad.
2. Los dos scripts leen con `ResultsStore.load(league, dedupe_game_id=False)`, es decir, las mismas filas crudas que en la fase H, y su propia regla 3(c) sigue decidiendo.

Ningún otro byte de lógica cambia. N, ventana, cortes, criterios, asertos de paridad y salidas quedan como estaban.

**Efecto en los hashes.** El `codigo_sha256` de la fase M diferirá del de `H.json` solo por estos dos cambios y por la comprobación que sigue. Esta enmienda es la justificación que exige la Enmienda 1(e). La autorización es verificable y no circular: el fichero versionado `2026-10-09-preregistro-recencia-totales.codigo-M.json`, commiteado después del último cambio de los dos scripts, registra `codigo_sha256_H` (copia literal del de `H.json`; reconstruido desde `f315f4c`, y el script lo contrasta con `H.json` al ejecutarse) y `codigo_sha256_M` (el `code_hashes()` de esa versión final). `--fase M --pre` acepta el código solo si `code_hashes()` coincide con `H.json` o si coincide con `codigo_sha256_M` de un registro cuyo `codigo_sha256_H` es igual al de `H.json`; en cualquier otro caso aborta. pre_M anota cuál de las dos fuentes lo autorizó (`codigo_autorizado_por`), y la comparación de pre_M frente a M no cambia. Cualquier cambio posterior de los scripts invalida el registro y exige una enmienda nueva. Se registra antes de mirar ningún resultado. **No altera ningún criterio**, y queda prohibido usarla para recortar o re-segmentar la ventana.
