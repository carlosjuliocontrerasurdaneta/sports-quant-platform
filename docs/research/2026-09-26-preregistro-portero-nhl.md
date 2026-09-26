# Pre-registro — ¿el portero titular y su calidad mejoran el modelo NHL?

**Fecha:** 2026-09-26. Escrito **antes** de descargar ningún dato de porteros y
antes de calcular ninguna relación entre porteros y resultados. Lo único
consultado es:

- el código y la documentación;
- la forma de las APIs, con seis llamadas de prueba a ESPN y cuatro a la API
  pública de la NHL, todas con timeout;
- el **calendario** del histórico NHL, sin marcadores: recuentos por partición
  y back-to-backs (sección 10).

Orden del operador: «añadir, por prioridad, las features por deporte que faltan;
la primera es portero titular + calidad del portero en NHL, porque la temporada
empieza en octubre». Código de referencia: `main` en `3648b17`.

Sigue los precedentes `2026-09-26-preregistro-clima-mlb.md` (enmiendas E1–E13)
y `2026-09-26-preregistro-descanso-basket.md` (enmiendas, contraste de `--pre` y
nota de re-ejecución), con sus resultados. Incorpora desde el principio las
exigencias de las revisiones de Fable:

- control de intercepto;
- criterio sobre los partidos afectados;
- particiones temporales;
- bootstrap por días;
- paridad con el motor;
- ejecución única con regla de re-ejecución;
- ningún umbral sin origen;
- potencia calculada antes de medir.

---

## 1. La pregunta y el problema de información

**Pregunta.** Sumar al `PoissonAdapter` de la NHL un factor acotado sobre la
lambda del rival, en función de la calidad del portero que se espera que juegue,
¿mejora la probabilidad del modelo puro frente al resultado?

**El problema central.** El histórico solo permite saber qué portero **jugó**, un
dato que se conoce después del partido. El pick se genera a las 12:00 de Uruguay
(~15:00 UTC), y los partidos NHL empiezan casi siempre entre las 23:00 y las
02:00 UTC. Los equipos suelen confirmar al titular tras el entrenamiento
matinal, así que a las 15:00 UTC el titular muchas veces **no** es oficial. ESPN
publica `probables` en el scoreboard, pero sin marca de hora del anuncio, y no
guarda un histórico de anuncios. Si el backtest usara el titular real, mediría
un efecto con información que el pick de las 12:00 no tiene.

**Decisión: combinación de (a), (b) y (c), con una jerarquía fija.**

| Brazo | Identidad del portero | Disponible a las 12:00 | Papel |
|---|---|---|---|
| **M2: proxy** | el **titular del partido anterior del equipo** (fecha UTC estrictamente anterior) | sí: solo usa partidos ya jugados | **Decide la activación** |
| **M1: titular real** | el portero con `starter = true` en el boxscore oficial | no | **Cota superior declarada.** No activa nada. Decide si merece la pena la fase 2 |
| **Fase 2: híbrido** | titular real con la probabilidad π medida en la captura prospectiva; proxy en el resto | sí, por construcción | Decide si producción puede usar los `probables` de ESPN. Fórmula fijada aquí y ejecución posterior (sección 12) |

**Por qué este orden.**

- **M2 es el único brazo cuya información existe con certeza a la hora del pick.**
  No necesita ningún anuncio. Si M2 acepta, producción puede activar el factor
  con el proxy aunque ESPN no publique nada. Usar después los `probables` solo
  puede acercar la identidad a la real, siempre que la captura demuestre que
  aciertan más que el proxy (sección 12).
- **M1 no es leakage de resultado.** El titular se decide antes del saque
  inicial, y que lo retiren a mitad de partido no cambia quién fue titular. Pero
  **sí** es información que el pick no tiene. Además arrastra la **selección del
  entrenador**, que da la titularidad al suplente en back-to-backs y contra
  rivales débiles. Por eso es una cota superior y no una estimación de lo que
  obtendría producción.
- **Proxy sin parámetros.** El proxy es «el titular del partido anterior», sin
  ventanas ni reglas de rotación. Una regla de back-to-back («el suplente juega
  el segundo día») o una moda sobre los últimos N partidos serían reglas
  inventadas: N no tiene origen en el proyecto, y probar varias sería
  multiplicidad. El proxy falla justo en los back-to-backs, así que es
  conservador: atenúa el efecto y no lo infla.
- **Lo que se espera.** Es probable que M2 rechace. El Elo (`elo_k 10`) ya recoge
  la fuerza reciente de cada equipo con su portero habitual, y el proxy apenas
  añade información en los partidos del suplente. La señal, si existe, estará
  en M1, y ahí solo se puede llegar por la fase 2. Se declara antes de medir,
  para que un rechazo de M2 no se lea como «el portero no importa».

## 2. Lo que ya se sabe

- El modelo NHL no tiene ninguna feature de portero. `features/research.py`
  lista `goalie_gsax_per60`, que depende de xG, y el proyecto no tiene xG. Queda
  fuera.
- **El mercado ya incorpora el portero.** Las líneas se mueven cuando se anuncia
  un suplente. Con `market_shrink = 0,5`, la probabilidad servida recibiría como
  mucho la mitad del ajuste.
- Siete mediciones previas no encontraron ventaja sobre el feed público de
  cuotas. **Aceptar aquí significaría que el modelo estima mejor, no que gane
  dinero.** Ningún resultado de este documento es una afirmación de rentabilidad
  (probabilidad estimada ≠ probabilidad implícita ≠ edge ≠ hit rate observado ≠
  ROI esperado ≠ ROI realizado).

## 3. Datos

### 3.1 Resultados

- `ResultsStore(ROOT).load("nhl")`: 32.888 filas, del 2002-01-01 al 2026-09-26.
  Columnas: `date`, `game_id`, `home`, `away`, marcadores y `neutral`.
- `date` es el día **UTC** del inicio (la misma semántica ESPN que en el
  descanso). Las 51 filas del 2026-09-19 al 26 son **pretemporada**: el
  histórico incluye pretemporada, temporada regular y playoffs (82 «equipos»
  distintos). Se estiman ~110 partidos por temporada de pretemporada o
  exhibición: ~1.425 filas por temporada, frente a 1.230 de temporada regular
  y ~85 de playoffs en la época de 30 equipos. `--pre` lo confirma con
  `gameType`.
- `game_id` es de ESPN, con tres formatos: 9 dígitos `2YYMMDD…` hasta 2010-11,
  `400…` de 2011-12 a 2017-18 y `401…` desde 2017-18 (11.416 filas).

### 3.2 Porteros: fuente elegida, la API pública de la NHL, no ESPN

Resultado de las llamadas de prueba (2026-09-26):

| | ESPN `summary?event=` | NHL `api-web.nhle.com/v1/gamecenter/{id}/boxscore` |
|---|---|---|
| Responde a `requests.get` simple | sí, en las cuatro épocas de `game_id` (2002, 2009, 2014, 2022) | sí (2008 y 2022) |
| Marca de titular | **no**: `starter` no existe; solo `athlete` y `stats` | **sí**: `starter: true/false` por portero, también en 2007-08 |
| Porteros completos | **no siempre**: en 2014-01-10 (`400484910`) solo aparece un portero de BOS, con 21:45 de TOI | sí en las dos pruebas (incluye a los suplentes que no jugaron) |
| Campos útiles | GA, SA, SV, SV%, TOI | `playerId`, `starter`, `toi`, `shotsAgainst`, `saves` |
| Tamaño | 150–400 KB por partido | menor |

**Se usa la API de la NHL.** Es la única fuente probada que dice quién fue
titular sin tener que deducirlo. Deducirlo por TOI sería un sesgo: el titular
retirado tras encajar mucho tiene poco TOI, y el suplente se llevaría la
titularidad justo en los partidos malos.

**Enlace con el histórico.** Para cada fecha D del histórico se pide
`/v1/score/{D}` y `/v1/score/{D−1}`: la NHL agrupa por fecha local y el
histórico por fecha UTC, así que los partidos nocturnos caen en el día local
anterior. Se empareja por `startTimeUTC[:10] == date` y por los nombres de los
dos equipos, normalizados con `sqp.sports.team_names.normalize_key` y
`configs/leagues/team_aliases.yaml`. Casos conocidos que hay que cubrir:

- Phoenix/Arizona/Utah;
- Atlanta Thrashers;
- Mighty Ducks of Anaheim;
- Montréal con tilde.

En la NHL no hay dos partidos del mismo equipo el mismo día.

**Campos que se guardan:**

- por partido: `gameId`, `gameType` (1 pretemporada, 2 regular, 3 playoffs) y
  `startTimeUTC`;
- por portero: `playerId`, nombre, equipo, `starter`, `toi`, `shotsAgainst` y
  `saves`;
- el JSON bruto comprimido (gzip), para preservar los datos brutos.

`decision` y `goalsAgainst` **no** se leen en ningún paso del modo `--pre`.

### 3.3 Backfill

- **Alcance: de la temporada 2005-06 a la 2025-26, más la pretemporada en
  curso.** 2005-06 es la primera temporada tras el cierre patronal y la
  primera con tanda de penaltis, lo que deja 9 temporadas de historial de
  porteros antes del primer test (A, octubre de 2014). Las filas de 2002 a
  2004 (~3.600) se quedan sin datos de portero y reciben factor 1 en todos los
  brazos. Solo sirven para calentar el Elo, igual que hoy. No se acota a
  temporadas recientes: una calificación de carrera necesita la carrera, y
  acortar el historial haría que el test A arrancara con porteros sin muestra.
- **Volumen:** ~29.200 boxscores y ~4.700 días × 2 consultas de `score`
  (con caché: cada día local se pide una sola vez). En total, **~34.000
  llamadas**.
- **Ritmo y cortesía:**
  - una petición por segundo (~9,5 h);
  - `timeout=20`;
  - hasta 3 reintentos que respetan `Retry-After`, reutilizando
    `sqp.providers.espn_results.retry_wait_seconds`;
  - para tras 3 fallos seguidos;
  - reanudable por punto de control;
  - un solo hilo;
  - fuera de la ventana del run diario de las 12:00.

  Es una API pública, sin documentar y gratuita. No gasta créditos de The Odds
  API.
- **Destino:** `data/historical/nhl_goalies/`: brutos en gzip y una tabla
  extraída `goalie_games_nhl.csv`, con el SHA-256 registrado en `--pre`. El
  backfill es un script aparte (`scripts/research/fetch_goalies_nhl.py`) y se
  commitea antes de ejecutarse.
- **Cobertura, no umbral:** todo partido NHL contra NHL de temporada regular o
  playoffs en las particiones de test debe quedar emparejado. Los que falten
  son un defecto de datos que se corrige antes del modo completo, y se listan
  por nombre en `--pre`. Las exhibiciones contra clubes que no son de la NHL
  pueden no existir en la API. Esos partidos se quedan con factor 1 y se
  cuentan.

## 4. La métrica de calidad del portero (solo con datos anteriores)

Sin xG no hay paradas sobre las esperadas. Se usa el **% de paradas sobre la
media de la liga, regresado a la media**. Todas las apariciones cuentan
(titular y relevo, pretemporada, regular y playoffs, las del mismo universo
que observa el adaptador), y solo con fecha **estrictamente anterior** al día
estimado, en el mismo orden diferido por días de
`engine.walk_forward_backtest`.

- **Referencia de liga** `L_g` para la aparición g, del día D: el % de paradas
  de la liga ponderado por tiros, sobre todas las apariciones de la **misma
  temporada** con fecha < D. La temporada va del 1 de agosto al 31 de julio. El
  primer día de cada temporada se usa la temporada anterior completa. Así el
  exceso no mezcla épocas: el % de paradas de la liga ha cambiado de nivel entre
  2005 y 2026.
- **Exceso por aparición:** `e_g = SV_g − SA_g · L_g`.
- **Calificación del portero i antes del día D:**

      q_i(D) = Σ_{g<D} e_g / (Σ_{g<D} SA_g + k)

  Son puntos de % de paradas por encima de la liga, encogidos hacia 0 con `k`
  tiros de prior. Un portero sin tiros previos, o sin identificar, tiene q = 0.
  Es una calificación de carrera acumulada, sin semivida, como
  `StarterRatings`. Una semivida sería un parámetro libre más. Limitación
  declarada: no recoge la edad ni las rachas.
- **`k` no se inventa. Se deriva en cada entrenamiento** por el método de
  momentos beta-binomial, solo con las apariciones de ese entrenamiento. La
  unidad es la temporada de un portero, con `SA_j` tiros y tasa `r_j`:

      V  = Σ_j SA_j (r_j − L̄_j)² / Σ_j SA_j       (varianza observada)
      B  = Σ_j L̄_j (1 − L̄_j)   / Σ_j SA_j       (parte binomial esperada)
      τ² = V − B                                   (varianza del talento)
      k  = L̄ (1 − L̄) / τ²

  `L̄_j` es la referencia de liga de esa temporada. Si τ² ≤ 0, no hay
  varianza de talento medible: el script lo informa y el veredicto es
  **RECHAZA**, porque sin señal no hay calificación. Suponer que el talento es
  estable a lo largo de la carrera es una aproximación declarada.

## 5. Cómo entra en el modelo

Es el análogo exacto del abridor MLB (`BaseballAdapter._rates`,
`src/sqp/models/starters.py`): un factor multiplicativo acotado sobre la lambda
**del rival**.

    f(i) = clip(1 − β · q_i / (1 − L̄_D),  1 − 0,35,  1 + 0,35)
    λ_home ← λ_home · f(portero visitante)
    λ_away ← λ_away · f(portero local)

- `1 − L̄_D` pasa de puntos de % de paradas a fracción de goles. Con β = 1, un
  portero con q = +0,005 sobre una liga de 0,905 reduce los goles esperados del
  rival en un 5,3 %: es el valor «físico». β es el **único parámetro libre**.
  Absorbe lo que el Elo y las tasas de ataque y defensa ya cuentan del portero
  habitual. Se informa junto a 1.
- **El tope de 0,35 no es nuevo.** Es la regla de auditoría del docstring de
  `starters.py` («max ±35 %») y el valor por defecto de `StarterRatings.bound`.
  Con q típicos del orden de ±0,01, casi nunca actuará.
- Se aplica **después** del reparto de Elo y la escala de `TeamScoringRates`, y
  **antes** del suelo `max(0,1, ·)`, como el abridor.
- **Mercados afectados:** los tres del `PoissonAdapter`.
  - **Moneyline (h2h):** cambia el reparto.
  - **Puck line (spreads ±1,5):** cambia el reparto.
  - **Totales:** si los dos porteros están por encima o por debajo de la media,
    los dos factores mueven el total en el mismo sentido.

  No hay mercados derivados NHL en el pipeline.
- **Portero desconocido:** f = 1 y **no** bloquea candidatos. En MLB, un
  abridor desconocido bloquea candidatos. Aquí eso vaciaría la NHL de picks
  cada vez que no hubiera anuncio a las 12:00, y la regla fundamental es
  generar picks de todos los deportes y mercados. El proxy existe justo para
  no depender del anuncio.
- **Implementación previa a la medición, sin efecto en producción:**
  - `HockeyAdapter` con `goalie_beta` (por defecto 0,0, que no hace nada, como
    `park_bound`) y `goalie_prior_shots`;
  - campos `home_goalie` / `away_goalie` en `Event`;
  - `walk_forward_backtest` pasa `r.get("home_goalie_announced")` al `Event`.

  El adaptador observa en cada fila las apariciones (`playerId`, SA, SV) y el
  titular, y usa `event.home_goalie` si viene informado. Si no, usa **el último
  titular observado del equipo** (el proxy). Un solo camino de código sirve
  para M1 (la fila trae `…_announced` = titular real), M2 (la fila no lo trae) y
  producción (`Event` sin portero hasta la fase 2). Tests obligatorios:
  - con `goalie_beta = 0`, salida idéntica a hoy;
  - portero desconocido → f = 1;
  - el proxy usa solo días anteriores.

  Se commitea antes de ejecutar el modo completo.

## 6. Modelo base, brazos y control

- **Base:** configuración de producción de la NHL en `3648b17`:
  `_league_meta("nhl").get("league_params")` + `get_adapter("nhl", "hockey",
  params)`.
  - Familia: `avg_total 6.1`, `tilt_scale 0.9`, `max_score 15`,
    `home_scoring_bonus 0.10`, `elo_k 10`.
  - Liga: `elo_home_adv 15` (`ratings.yaml`).

  Walk-forward de `walk_forward_backtest` sobre todo el histórico,
  `warmup = 60`. En los dos sentidos, el empate de la rejilla se reparte
  50/50 (`poisson_match_probs`). Los empates reales anteriores a 2005 salen del
  moneyline, como en el motor.
- El factor **no realimenta** el Elo ni las tasas, que se actualizan con los
  marcadores. Las lambdas base se calculan una vez, y cada brazo es una función
  analítica de ellas y de (q_home, q_away).
- **Brazos (se calculan para M1 y para M2):**

  | Brazo | Lambdas | Parámetros |
  |---|---|---|
  | Base | λ_h, λ_a | — |
  | **Tratamiento T** | λ_h · f(q_away; β), λ_a · f(q_home; β) | β |
  | **Control C** | λ_h · e^{a}, λ_a · e^{−a} | a (constante) |

  **Motivo del control:** los suplentes juegan más a menudo el segundo partido
  de un back-to-back, y en el histórico el visitante está en back-to-back mucho
  más a menudo que el local (sección 10: 1.506 frente a 882 en el test A). La
  diferencia q_home − q_away tendrá, por tanto, media positiva. Un β > 0 podría
  ganar log loss solo por corregir una infraestimación general de la ventaja de
  campo (`elo_home_adv 15` es bajo). Es el confusor que el intercepto absorbió
  en el clima y que infló `c` en el descanso.
- **Paridad (aserción, aborta si falla):**
  1. las probabilidades base coinciden con `binary_probs` y con
     `markets["totals@5.5"|"totals@6.5"|"spreads@-1.5"|"spreads@1.5"]` del motor
     (tolerancia 1e-12). Los spreads usan la vista **con** empates, por la
     lección de la re-ejecución del descanso;
  2. las del brazo T (M1 y M2) con `β_C` y `k_C` coinciden con el motor
     ejecutado con `goalie_beta = β_C` y `goalie_prior_shots = k_C`, con las
     filas de M1 y de M2 respectivamente (tolerancia 1e-12). Esto comprueba que
     q y el proxy reconstruidos son los del adaptador, y no una copia.
- **Pérdida:** log loss binario con recorte 1e-12, la expresión de
  `tuning._binary_nll_series`.

## 7. Particiones y estimación

Cortes a 30 de septiembre, antes de la temporada regular:

| Partición | Entrenamiento (fechas) | Test (fechas) | Contenido del test |
|---|---|---|---|
| A | tras el warmup – 2014-09-30 | 2014-10-01 – 2018-09-30 | 4 temporadas normales |
| B | tras el warmup – 2018-09-30 | 2018-10-01 – 2022-09-30 | incluye la burbuja de 2020 y 2020-21 (divisional, sin público) |
| C | tras el warmup – 2022-09-30 | 2022-10-01 – 2026-06-30 | 4 temporadas actuales |

- **Por partición se estiman k (sección 4), β (brazo T) y a (brazo C)**, solo con
  el entrenamiento, minimizando el log loss medio del **moneyline**. Para M1 y
  M2 se estiman por separado, cada uno con sus identidades.
- **Optimizador:** Nelder-Mead de `scipy.optimize.minimize`, punto de partida 0,
  `xatol=1e-7`, `fatol=1e-10`, `maxiter=2000`, sin límites ni restricción de
  signo (E9 del clima). Si no converge, el script aborta y se trata como
  defecto de código.
- **Test combinado:** unión de los tests de A, B y C, sin solapes, con media
  por partido.
- **Partido afectado:** f(home) ≠ 1 o f(away) ≠ 1 con los q del estado antes
  del día. Se define sin resultado, así que no hay leakage. Casi todos los
  partidos tras el calentamiento de porteros serán afectados; `--pre` informa
  la fracción f.

## 8. Criterios de aceptación (se aplican a M2; todos a la vez)

1. **Δ log loss moneyline (T − base) ≤ −0,002** en los partidos **afectados**
   del test combinado.
2. **Δ < 0** en los afectados de **cada** partición (A, B y C).
3. **ECE(T) ≤ ECE(base)** en todo el test combinado (moneyline), con
   `expected_calibration_error` por defecto (10 bins).
4. **β > 0 en las tres particiones.** Es la convención de la forma funcional (un
   portero mejor reduce los goles del rival), no un umbral nuevo.
5. **log loss(T) < log loss(C)** en todo el test combinado: el portero debe
   batir a un desplazamiento constante del reparto.
6. **No empeorar los otros dos mercados que mueve el factor**, en todo el test
   combinado y con el β del moneyline:
   - (a) Δ log loss medio de `totals@5.5` y `totals@6.5` ≤ 0;
   - (b) Δ log loss medio de `spreads@-1.5` y `spreads@+1.5` (línea del local)
     ≤ 0.

**Origen de los umbrales.**
- 0,002 es `IMPROVEMENT_MARGIN` de `src/sqp/backtesting/tuning.py:38`, el margen
  del abridor, el clima y el descanso.
- **Solo afectados** hereda la decisión del operador E6 del clima, que confirmó
  para el descanso el 2026-09-26. Aquí casi no cambia nada: con f ≈ 1, afectados
  ≈ universo, y el argumento de dilución de E6 apenas actúa. Se mantiene por
  coherencia y se marca para confirmación (sección 15).
- Las líneas 5,5 y 6,5 son los medios puntos que rodean `avg_total 6.1` de la
  familia (`registry.py`); con medio punto no hay empujes. La línea ±1,5 es la
  puck line que cotiza el mercado NHL. Son líneas de evaluación, no umbrales
  de decisión.
- Criterios 2–6: signos y comparaciones con 0, sin constantes nuevas.

**Veredictos posibles:**

| M2 | M1 | Veredicto | Consecuencia |
|---|---|---|---|
| acepta | cualquiera | **ACEPTA** | se puede activar con el proxy (sección 13) |
| rechaza | acepta (mismos 6 criterios) | **RECHAZA, con señal en la cota superior** | no se activa; la fase 2 decide si los `probables` bastan |
| rechaza | rechaza | **RECHAZA** | no se activa; ni siquiera el titular real ayuda con esta forma; la fase 2 no se ejecuta |

El resultado se commitea en todos los casos.

## 9. Incertidumbre

Bootstrap por **bloques de fecha**: días UTC completos del test combinado, 10.000
réplicas, semilla 42. Se informan el IC95 percentil y el error estándar de:

- el Δ del criterio 1;
- T − C del criterio 5;
- los dos Δ del criterio 6;

para M2 y para M1. **No es puerta de aceptación:** exigir que el extremo superior
sea < 0 sería un umbral que el operador no ha fijado (E8 del clima).

## 10. Potencia (calendario y modelo, sin resultados)

**Recuentos de calendario** (2026-09-26, sin marcadores ni porteros, warmup 60,
back-to-back = el equipo jugó el día UTC anterior). El modo `--pre` debe
reproducirlos. Si no coinciden, se documenta la diferencia **antes** de medir.

| Partición | Test n | Días de test | Algún equipo en back-to-back | Local en b2b | Visitante en b2b | Neutral | Entrenamiento n |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 5.780 | 957 | 1.889 | 882 | 1.506 | 74 | 15.827 |
| B | 5.192 | 872 | 1.629 | 892 | 1.309 | 118 | 21.607 |
| C | 5.978 | 952 | 1.882 | 953 | 1.486 | 65 | 26.799 |
| **Combinado** | **16.950** | **2.781** | **5.400** | | | | |

32.828 partidos tras el warmup; 51 (pretemporada 2026-27) quedan fuera de las
particiones.

**Sensibilidad del modelo** (`poisson_match_probs`, λ típicas 3,15 / 3,05): un
±5 % en la lambda del visitante mueve P(local) en ±2,4 pp y P(Over 5,5) en
∓2,4 pp; un ±10 %, en ±4,8 pp.

**Qué efecto hace falta para el criterio 1** (la misma derivación que en el clima
y el descanso). Cerca de p = 0,5, corregir un error δ gana ≈ 2δ² de log loss, así
que para 0,002 hace falta δ_RMS ≈ 3,2 pp. Eso son ≈ 6,6 % de diferencia RMS
entre los dos factores que **el Elo no capture ya**. Con 1 − L ≈ 0,09–0,095 y
β = 1, equivale a una diferencia RMS de calidad q_home − q_away de **≈ 0,006
(6 milésimas de % de paradas) de información nueva**. En M2 casi toda la
diferencia de q entre porteros habituales ya está en el Elo, así que es poco
probable llegar. En M1 los partidos del suplente pueden aportarla. `--pre`
informa el RMS de (q_home − q_away)/(1 − L̄) en el test de cada partición, para
M1 y para M2, con los k de cada entrenamiento. Con él se lee, antes de medir, el
β que haría falta.

**Ruido:** con δ ≈ 3 pp, la desviación típica del Δ por partido es ≈ 0,064. Con
~16.950 partidos afectados, el error estándar sale ≈ 0,0005 sin agrupar (el
bootstrap da el valor bueno). El margen queda a ~4 errores estándar: **el
histórico tiene potencia**. La temporada 2026-27 sola (~1.300 partidos) daría
≈ 0,0018, casi el margen entero. Por eso la fase 2 **no** re-mide el efecto con
datos prospectivos (sección 12).

## 11. Informes secundarios (no deciden)

1. `bias` del brazo base (probabilidad media − tasa observada del local) por
   partición.
2. Estimación conjunta base + a + β: el β que queda con el intercepto controlado.
3. Perfil del log loss de entrenamiento en la rejilla β ∈ {−1,0, −0,5, …, +3,0}
   por partición, para ver si es monótono a los dos lados del mínimo.
4. Δ en test **según los back-to-backs**: ningún equipo en b2b / alguno. Si el
   efecto de M1 vive solo en los b2b, parte de lo que se atribuye al portero es
   fatiga de los jugadores de campo, que el modelo NHL no tiene.
5. Δ en test de M1 en los partidos donde **titular real ≠ proxy**, y fracción de
   esos partidos por partición y por lado (local/visitante).
6. Δ por temporada (2014-15 a 2025-26), marcando 2019-20 y 2020-21.
7. β estimado sobre los **totales** (entrenamiento) frente al β del moneyline.
   Una diferencia grande avisa de que el factor mezcla canales.
8. Sin pretemporada (`gameType` 1): criterio 1 repetido.
9. Línea capturada del mercado: β_C de M2 en h2h, spread y total del consenso
   (`roi_engine.load_closing_odds`, `_pick_main_lines`) sobre la muestra NHL con
   cuotas. Se informa n. Mide log loss frente al resultado en esa submuestra,
   **no ventaja sobre el mercado**.
10. Cobertura: partidos con portero conocido por lado, apariciones sin `starter`
    (partidos con 0 o con 2 titulares por equipo), porteros distintos, y
    distribución de k y de q.

## 12. Fase 2: captura prospectiva e híbrido (pre-registrada aquí, se ejecuta después)

**Captura (c): empieza en cuanto se apruebe, con independencia del resultado
histórico.** Cuesta cero créditos (ESPN es gratuito) y no toca el modelo. Si no
arranca con la temporada, que empieza hacia el 7 de octubre, esos datos se
pierden para siempre.

- **Módulo nuevo** (patrón de `team_totals_capture.py` y de
  `log_pitcher_confirmation`): en cada pase de `CAPTURE_CLOSE` (cada 30 min) y en
  el propio run diario NHL, pide `scoreboard?dates=` de hoy y de mañana y
  **añade** una fila por (evento, equipo) **solo cuando cambia** el portero o su
  estado:
  - `captured_at_utc`;
  - `event_id` (ESPN);
  - `commence_time`;
  - equipo;
  - `goalie_espn_id` y nombre;
  - estado (`Probable`/`Confirmed`: lo reporta la viabilidad y hay que
    verificarlo al implementar; la llamada de prueba de hoy lo cortó);
  - `source_run` (`daily`|`capture`).

  Solo eventos no comenzados (`captured_at < commence_time`). Destino propuesto:
  `data/historical/goalie_probables_log_nhl.csv`. La marca de hora es la
  **nuestra**, con resolución de 30 min. ESPN no da la del anuncio.
- En el run diario, la fila `source_run = daily` lleva el `generated_at` del run.
  Es **exactamente** la información que tenía el pick.
- Titular real: boxscore de la NHL del día siguiente, como en el backfill.
  Cruce ESPN ↔ NHL por nombre normalizado + equipo + fecha, informando los que
  no casan.
- **El resultado de los partidos no se lee en la captura.**

**Qué se mide con la captura**, solo identidades y nunca resultados:

- **cobertura a la hora del pick:** fracción de lados con `probable` en la fila
  del run diario;
- **acierto del probable:** fracción de esos lados en que coincide con el
  titular real;
- **acierto del proxy** sobre los **mismos** lados;
- **π_s**, la fracción de lados en que el probable a la hora del pick existe y
  acierta, por estrato s ∈ {equipo en back-to-back, no}.

**Regla para usar los `probables` en producción** (solo si la sección 8 dio
ACEPTA o «señal en la cota superior»):
1. el acierto del probable a la hora del pick es **mayor** que el del proxy en
   los mismos lados (comparación, sin umbral); y
2. el **híbrido** acepta: se re-ejecuta la medición de la sección 8 con las
   particiones, criterios, bootstrap y optimizador de este documento. En cada
   lado del test histórico, la identidad es el titular real con probabilidad
   π_s de su estrato y el proxy en el resto (sorteo con semilla 42). β, a y k se
   re-estiman en cada entrenamiento con esas identidades.

   La fórmula queda fijada hoy y solo entra π_s de la captura, así que no es
   una búsqueda a posteriori. Limitación declarada: supone que los anuncios
   tempranos son aleatorios dentro de cada estrato. Si los suplentes se
   anuncian más tarde, el híbrido sobreestima; por eso se estratifica por
   back-to-back.
3. **Tamaño mínimo de la captura antes del híbrido:** decisión del operador
   (sección 15). Como referencia, con ~600 lados (~300 partidos, unas 3
   semanas) el error estándar binomial de π ronda 0,02.

Si el híbrido acepta, producción pasa `event.home_goalie` = probable a la hora del
pick cuando exista, con el proxy de respaldo, y el mismo β (sección 13).

## 13. Si se acepta: lo que haría falta para activarlo

No se toca producción en esta medición. Activar sería un cambio aparte, con
aprobación:

1. **Addenda previos**: en `2026-09-25-repreregistro-gate-k52.md` y en
   `2026-08-26-preregistro-el-modelo-manda.md`, antes de tocar la
   configuración, como con el abridor MLB y el descanso NBA. Cada uno lleva la
   fecha del cambio, no altera los criterios y prohíbe usarlo después para
   recortar la ventana.
2. **Valores:** `goalie_beta` = β de la **partición C de M2** (el proxy).
   `goalie_prior_shots` = k_C. El tope 0,35 queda fijo. Solo `nhl`, en
   `configs/leagues/ratings.yaml`, con un comentario que remita al resultado.
   Motivo: la identidad con ruido del proxy atenúa β, así que β_M2 ≤ β_M1.
   Usarlo con identidades mejores (fase 2) queda del lado conservador. No se
   re-estima con todo el histórico.
3. **Almacén de porteros e ingesta diaria:** los boxscores de ayer tienen que
   estar guardados **antes** de generar, como los resultados en el orden
   `SETTLE_ALL` → `RUN_DIARIO_ALL`. Hay que verificarlo, no suponerlo.
   - Si falta el partido anterior de un equipo, su proxy sería el de dos
     partidos atrás, y en los back-to-backs eso invierte el sentido del
     ajuste. Regla: si el último partido del equipo en el histórico no tiene
     datos de portero, f = 1 para ese equipo (sin adivinar).
   - Test con un back-to-back conocido.
4. **Guarda de revalidación `goalie_changed`**, análoga a `revalidate_pitchers`
   (`src/sqp/pipeline/revalidation.py:355`). Si el portero `Confirmed` en ESPN
   dentro de la ventana difiere del que usó el pick (proxy o probable), marca o
   revoca. Solo baja stakes y nunca revoca a ciegas. Bajo shadow mode es
   medición. Si revoca o solo marca: decisión del operador (sección 15). El
   pase de revalidación **no re-estima** (revalida precio): el portero no puede
   actualizar la probabilidad después de las 12:00. Un pase de re-estimación
   intradía sería otro cambio, con su propio pre-registro.
5. **Recalibrar en staging** (`controlled-recalibration`) los calibradores NHL
   de h2h, spreads y totales, entrenados sin portero. La promoción necesita
   aprobación humana.
6. **Paridad entre entrenamiento y servicio:** `event.start_time` en UTC y el
   cruce de nombres ESPN (cuotas) ↔ NHL (porteros) con `team_aliases.yaml`.
   Hay un test por cada franquicia renombrada.
7. **Vigilancia:** si la primera temporada activa empeora el log loss NHL, se
   revisa con un pre-registro nuevo, no ajustando β a mano.

## 14. Compromisos de ejecución

- **Scripts:**
  - `scripts/research/fetch_goalies_nhl.py` (backfill, sección 3.3);
  - `scripts/research/measure_goalie_nhl.py`, con tres modos:
    - `--pre`: recuentos de la sección 10, cobertura, sanidad de `starter`,
      tasa de titular real ≠ proxy, f, k por entrenamiento, RMS de la
      diferencia de q y hashes. **Sin marcadores ni `goalsAgainst`/`decision`**;
    - `--parity-only`: comprueba las paridades de la sección 6 con valores
      arbitrarios de β y k;
    - completo: produce el JSON (`--out`).

  El informe `docs/research/2026-09-XX-resultado-portero-nhl.md` se redacta a
  partir del JSON.
- Los scripts y la implementación con valor por defecto sin efecto (sección 5)
  se commitean **antes** del modo completo.
- **Una sola ejecución** del modo completo para M1 y M2 juntos. Sin miradas
  intermedias al efecto y sin cambiar particiones, métrica, tope, proxy, fuente
  o ligas después de ver el resultado.
- **Regla de re-ejecución (E10):** solo se repite si aparece un defecto de
  **código o datos** demostrable sin mirar el resultado: paridad rota, filas mal
  unidas u ordenadas, emparejamiento incompleto, ficheros distintos de los del
  hash de `--pre`, o que el optimizador no converja. Se documenta el defecto,
  a ser posible diagnosticado a ciegas (solo longitudes e índices, como en el
  descanso), y se commitean las dos salidas. Un resultado adverso no es motivo
  para repetir.
- Las enmiendas, por ejemplo tras la revisión independiente del script, se
  añaden al final **antes** del modo completo, y mandan sobre el texto.
- **Reabrir tras un rechazo exige una forma distinta y pre-registrada**, por
  ejemplo: calificación con semivida, % de paradas a igualdad numérica
  (`evenStrength…`), un proxy de rotación con parámetros de origen declarado, o
  xG si se incorpora. Repetir esta con otro tope, otro k u otras particiones
  sería buscar una señal a medida.

## 15. Interacciones con los tests en curso y decisiones del operador

**La medición no interfiere con ningún test:** solo lee el histórico y escribe
el backfill en `data/historical/nhl_goalies/`. No toca el stream servido,
`data/bets/prediction_gate.json`, los calibradores ni la configuración.

**Una activación sí interferiría:**

- **Gate K = 52.** El gate evalúa `model_probability`, el modelo **puro**. El
  factor vive en el adaptador, así que **cambia la `d` de `nhl|h2h`,
  `nhl|spreads` y `nhl|totals`**. Hoy el registro no tiene cortes NHL: la
  temporada está parada y no se ha gastado ningún test de entrada. Activar no
  cambia el número de cortes: K = 52 y el techo 63 no se tocan. Exige el
  addendum previo (sección 13.1).
- **«El modelo manda»:** se ejecuta una sola vez al llegar a 3.402 eventos
  graduados (≈ 2026-11-24). Evalúa `p_cal`, que hereda el adaptador. Las filas
  NHL desde octubre caen en su ventana. Activar antes exige el mismo addendum.
  El test evalúa el sistema tal como operó.
- **La captura (sección 12) no interfiere con ninguno:** solo registra
  identidades, no cambia probabilidades ni stakes.

**Decisiones del operador que quedan marcadas:**

1. **Criterio 1 sobre los afectados** (heredado de E6). Aquí afectados ≈
   universo; la alternativa es medirlo sobre todo el test combinado.
2. **Autorizar el backfill:** ~34.000 llamadas a la API pública, sin documentar,
   de la NHL, a 1 por segundo (~9,5 h), temporadas 2005-06 a 2025-26, con
   escritura en `data/historical/nhl_goalies/`.
3. **Arrancar la captura prospectiva antes del inicio de la temporada regular**
   (~7 de octubre). Es un cambio de código en producción: módulo nuevo,
   enganche en `CAPTURE_CLOSE` y en el run diario, y escritura en `data/`. Debe
   estar commiteado antes del run de las 12:00 (KI-036).
4. **Tamaño mínimo de la captura** antes de ejecutar el híbrido de la fase 2.
5. **Guarda `goalie_changed`:** revocar (como el abridor MLB) o solo marcar.
6. **Momento de una eventual activación** respecto al gate y a «el modelo
   manda». El precedente del operador es activar con nota previa.
7. **Si M1 también rechaza:** mantener o apagar la captura. Por diseño, la fase
   2 no se ejecutaría.

---

Relacionado: [[2026-09-26-preregistro-descanso-basket]],
[[2026-09-26-resultado-descanso-basket]], [[2026-09-26-preregistro-clima-mlb]],
[[2026-09-26-resultado-clima-mlb]], [[2026-08-22-resultado-timing-starters]],
[[2026-09-25-repreregistro-gate-k52]], [[2026-08-26-preregistro-el-modelo-manda]].

**Decisiones del operador resueltas el 2026-09-26, antes de implementar:**
1. Backfill **completo** de porteros titulares, de 2005-06 a 2025-26, contra la API pública de la NHL (~34.000 llamadas a 1/s): autorizado.
2. **Captura diaria prospectiva** de los probables de ESPN con marca de hora: arrancar **ya**, antes del inicio de la temporada. Solo captura; no toca probabilidades ni picks.
3. Guarda `goalie_changed`, si se activa: **marcar y poner el stake a 0**. El pick se conserva en la lista.
4. Si M1 también rechaza: **mantener** la captura.
Criterio 1 sobre los afectados (≈ universo) y activación con nota previa: como en los precedentes del 26/09.

---

## Enmienda 1 (2026-09-26, antes de ejecutar el backfill y `--pre`; texto propuesto por la revisión de Fable)

(a) **Emparejamiento (§3.2).** En lugar de alias estáticos, se usa coincidencia exacta de `normalize_key`, o el nombre corto de la NHL como palabra final completa del nombre ESPN. Se exige que casen local y visitante y que haya un único candidato en la fecha UTC; los ambiguos quedan sin emparejar y se listan. Se corrige la afirmación «no hay dos partidos del mismo equipo el mismo día»: en fecha UTC hay 22 enfrentamientos duplicados desde 2005-09 (p. ej. playoffs 2016-04-15 NYI@FLA). El backfill no los desempata: quedan con `matched=False`, sin `espn_game_id`, y se listan como sin emparejar. `--pre` los desempatará por orden (`startTimeUTC` de la NHL frente al orden del `game_id` de ESPN), sin leer marcadores, y listará los que queden.

(b) **Rutas (§3.3, §14, §15).** El backfill es `scripts/backfill_goalies_nhl.py` (módulo `sqp.pipeline.goalie_backfill`). La tabla es `data/historical/goalies_nhl.csv` y los brutos, `data/historical/nhl_goalies_raw/{gameId}.json.gz`. El SHA-256 de `--pre` se registra sobre esa tabla. La tabla incluye `goals_against`, que `--pre` no lee.

(c) **Captura (§12).** Destino: `data/historical/goalie_probables_nhl.csv`, una fila por evento y lado. Los estados observados en ESPN son «Confirmed» y «Expected» (no «Probable») y se guardan tal cual. La fila `source_run=daily` se añade sin deduplicar para cada lado con probable, con el `captured_at` del momento en que se recibe la respuesta. Que se ejecute antes de la generación depende de conectarla al run diario, cosa aún no aplicada. La retirada de un probable se registra como fila sin portero (`status=none`). Las filas con `commence_time` que no se puede parsear se descartan.

(d) **Titulares.** Solo se ingieren boxscores con `gameState` OFF o FINAL. Un partido sin terminar deja el día como incompleto, y el checkpoint no avanza más allá del primer día incompleto (fallo del `score`, fallo del boxscore o partido sin terminar). `--end` se recorta como mucho a ayer (UTC). El script sale con código distinto de 0 si se detiene por fallos consecutivos.
