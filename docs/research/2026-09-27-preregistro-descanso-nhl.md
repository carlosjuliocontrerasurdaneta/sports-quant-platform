# Pre-registro — ¿el descanso diferencial mejora el modelo NHL?

**Fecha:** 2026-09-27. Escrito **antes** de calcular ninguna relación entre descanso
y resultados. Lo único consultado es el código, la documentación, los precedentes
y el **calendario** del histórico NHL, sin marcadores: recuentos, distribución de
Δr y la sensibilidad del modelo evaluada en lambdas típicas (sección 9). Código de
referencia: `main` en `386f316`.

**Orden del operador (2026-09-27):** «medir el descanso en NHL (y después MLB) con
el `RestModel` acotado, como se hizo en NBA». El ajuste global `rest_days_coef` de
la capa de features se descartó porque no está acotado
(`2026-09-27-preregistro-bateria-ajustes.md`, §2.1 y decisión 3 del operador).

Precedentes que se siguen, con sus enmiendas y resultados:
`2026-09-26-preregistro-descanso-basket.md` → `2026-09-26-resultado-descanso-basket.md`
(ACEPTA con c ≈ 0,8 puntos por día; el criterio 1 pasó por 0,00024 y parte del
efecto era ventaja de campo), `2026-09-26-preregistro-portero-nhl.md` (misma liga,
mismas particiones) y `2026-09-26-preregistro-clima-mlb.md`. Vienen incorporados
desde el principio:

- control de intercepto;
- criterio sobre los partidos afectados;
- particiones temporales;
- bootstrap por días;
- paridad exacta con el motor;
- ejecución única con regla de re-ejecución;
- ningún umbral sin origen (el margen es `IMPROVEMENT_MARGIN`);
- potencia calculada antes de medir.

---

## 1. La pregunta y la forma funcional

**Pregunta.** Sumar al `PoissonAdapter` de la NHL el ajuste de descanso acotado de
`RestModel` (`src/sqp/models/rest.py`), ¿mejora la probabilidad del modelo puro
frente al resultado?

### 1.1 El problema: en Poisson no hay un margen al que sumar

En `NormalMarginAdapter` (basket, NFL) el ajuste es directo:
`μ += c · (r_home − r_away)`, con `μ = points_per_elo · diff`. En el
`PoissonAdapter` (`src/sqp/sports/adapters.py:96-105`) el margen no es un
parámetro:

    p_home = 1 / (1 + 10^(−diff/400))                 (Elo, diff = rating_diff)
    tilt   = clip((p_home − 0,5) · tilt_scale, −0,30, +0,30)
    λ_home = avg · (0,5 + tilt) + home_scoring_bonus
    λ_away = avg · (0,5 − tilt)                        (suelo 0,1 en ambas)

El Elo decide el **reparto** y `TeamScoringRates` decide la **escala** (`avg`).

### 1.2 Decisión: desplazamiento de la diferencia de Elo

    diff_eff = rating_diff(home, away) + c · Δr ,   Δr = r_home − r_away,  r ∈ [0, 4]

con `c` en **puntos Elo por día** de diferencia de descanso. El resto de la cadena
(logística, tilt acotado, lambdas, suelo, rejilla de Poisson) queda intacto.

**Por qué esta forma y no otra:**

1. **Es la traducción literal del `RestModel`.** En la familia Normal,
   `μ = ppe · diff + c · Δr = ppe · (diff + (c/ppe) · Δr)`: el ajuste de basket
   **ya es** un desplazamiento de la diferencia de Elo expresado en puntos. Aquí se
   expresa en Elo porque es la única unidad de reparto que tiene la familia. Es la
   misma clase de hipótesis (el descanso cambia la fuerza relativa), no una nueva.
2. **El control queda en la misma unidad que el confusor.** El brazo de control
   (sección 5) es `diff + a`, es decir, un desplazamiento de `elo_home_adv` que no
   realimenta el Elo. El confusor que hay que batir es justo ese: la NHL sirve con
   `elo_home_adv 15` (`configs/leagues/ratings.yaml`, frente a 33 de la familia en
   `registry.py`) y el local llega más descansado más a menudo (sección 9). Con la
   misma unidad, T y C compiten en igualdad.
3. **Respeta las cotas del modelo.** El tope de 4 días de `RestModel` (el valor por
   defecto de `rest_max_days`, sin ajustar), el recorte del tilt a ±0,30 y el suelo
   de lambda siguen actuando después del ajuste. No hace falta ningún tope nuevo.
4. **Un solo parámetro libre**, `c`. No hay que repartir el efecto entre ataque y
   defensa.

**Alternativas descartadas:**

- **Desplazar el tilt** (`tilt += c · Δr`). En primer orden es equivalente
  (dtilt/dElo ≈ 0,9 · p(1 − p) · ln10/400 ≈ 0,0013 por punto Elo cerca de
  p = 0,5), pero obliga a una unidad nueva y el control ya no sería la ventaja de
  campo del modelo. Medir las dos sería multiplicidad sobre la misma señal.
- **Factor sobre las lambdas**, análogo al abridor MLB (`λ_rival · f`). Exige
  decidir si el cansancio baja el ataque propio, sube el del rival o las dos cosas
  (dos parámetros o un reparto inventado), y mueve los totales. Además, el
  pre-registro del portero ya ocupa el canal «factor sobre la lambda del rival»
  (§5 de aquel documento). Poner el descanso en el canal del reparto mantiene los
  dos mecanismos separados en el código (aunque no en los datos: sección 11).
- **Indicadores de back-to-back**, **viajes** o **descanso en horas.** Son formas
  funcionales distintas, que el precedente reserva para reabrir tras un rechazo
  (§12 del pre-registro de basket). No se miden aquí.

### 1.3 Qué implica para cada mercado

| Mercado | Efecto | Motivo |
|---|---|---|
| Moneyline (h2h) | **se mueve** | cambia `p_home` → tilt → reparto |
| Puck line (±1,5) | **se mueve** | mismo reparto; la sensibilidad es asimétrica entre −1,5 y +1,5 (sección 9) |
| Totales | **no se mueve** (salvo truncamiento) | `λ_home + λ_away = avg + home_scoring_bonus` no depende del tilt. Con Poisson independiente, el total solo depende de la suma. Lo único que cambia es el truncamiento de la rejilla a 15 goles y el suelo de 0,1: del orden de 1e-7 por 10 puntos Elo (sección 9) |

Consecuencias que se declaran ahora:

- **La hipótesis no incluye un efecto del descanso sobre los goles totales.** Si
  existe (por ejemplo, equipos cansados que encajan más), esta forma no lo recoge.
  Medirlo sería otra hipótesis, con su propio pre-registro.
- El calibrador `nhl_totals` y el corte `nhl|totals` del gate **no** se ven
  afectados por una activación.
- Como en basket, se mide la forma **tal como quedará programada**: lineal en Δr,
  con el tope de 4 días fijo. El tope no se busca.

## 2. Lo que ya se sabe y exposición previa de la muestra

- La NHL **no tiene** ningún mecanismo de descanso: `PoissonAdapter` no instancia
  `RestModel`, y `rest_days_coef` vale 0 y sigue en 0.
- **El mercado ya incorpora el descanso:** las casas saben quién juega un
  back-to-back. Con `market_shrink = 0,5`, la probabilidad servida recibiría como
  mucho la mitad de lo que se mida aquí.
- Siete mediciones previas no encontraron ventaja sobre el feed público de cuotas.
  **Aceptar significaría que el modelo estima mejor, no que gane dinero.**
  Probabilidad estimada ≠ probabilidad implícita ≠ edge ≠ hit rate observado ≠ ROI
  esperado ≠ ROI realizado. Nada de este documento es una afirmación de
  rentabilidad.

**Exposición previa, declarada** (el histórico no es virgen para esta idea):

1. **2026-09-01:** `scripts/measure_features.py` imprimió correlaciones brutas de
   `rest_diff` con el resultado en diez ligas (§4 de la batería). No se ha
   comprobado si incluía la NHL, y la cifra no se ha consultado para este
   documento.
2. **2026-09-15:** `scripts/evaluate_feature_blocks.py` evaluó el bloque
   `schedule` (con `schedule_*_rest_days`, sin tope, `features/research.py:225`).
   En `audit/feature_candidates_20260915.json` no hay ningún candidato
   `nhl|schedule`: el bloque no pasó aquella selección en la NHL. Es un indicio
   débil en contra. No se han consultado sus números.
3. **2026-09-26:** el pre-registro del portero contó back-to-backs por partición,
   solo con el calendario.
4. **2026-09-26:** el resultado de basket (c ≈ 0,8 puntos por día en NBA) sí se
   conoce. Es otra liga, y aquí no fija ningún valor.

La forma, el tope, las particiones, los criterios y el optimizador vienen fijados
por los precedentes, no elegidos a la vista de esa exposición.

## 3. Datos y definición de «días de descanso»

- **Fuente:** `ResultsStore(ROOT).load("nhl")`, todas las filas: 32.888, del
  2002-01-01 al 2026-09-26, SHA-256 `98b0eb7d…bbb1` (consulta del 2026-09-27).
  Incluye pretemporada, temporada regular y playoffs, que es lo que ve producción.
  El script registra el hash y el número de filas, y aborta si el fichero cambia
  entre `--pre` y el modo completo.
- **Semántica de la fecha:** `date` es el día **UTC** del inicio (ESPN), sin hora.
  En producción, `estimate` usa `str(event.start_time)[:10]`, también en UTC. «Día»
  = día natural UTC del inicio.
- **Regla, idéntica a basket:** `r = min(max(D − L, 0), 4)`, donde L es la fecha
  del último partido del equipo con fecha **estrictamente anterior** a D, en el
  orden diferido por días de `engine.walk_forward_backtest`. El script **no
  reimplementa** la regla: sondea `RestModel(points_per_day=1.0, max_rest=4,
  normalize=get_team_normalizer("nhl"))` con `margin_adjustment` (enmienda E4 de
  basket).
- **Partido afectado:** los dos r conocidos y Δr ≠ 0. Se define solo con el
  calendario, antes del resultado.

**Consecuencias de la definición, declaradas antes de medir:**

1. **Back-to-backs con partido de tarde (específico de la NHL).** Un partido a las
   19:00 ET cae en el día UTC siguiente, y un partido de tarde del día siguiente
   (por ejemplo, a las 17:00 ET) cae en **el mismo** día UTC. Como el motor estima
   el día completo con el estado del día anterior, la segunda mitad de ese
   back-to-back se ve con el descanso de la primera (r ≥ 2) y no como r = 1. En el
   histórico hay **740 pares equipo-fecha con dos partidos el mismo día UTC**
   (168 en el test A, 115 en B y 120 en C; 45/17/22 en septiembre, sobre todo
   pretemporada con plantillas divididas). Otros 22 son **filas idénticas**
   (fecha, local, visitante), el defecto ya documentado en la enmienda 1 del
   portero. Es ruido de medida que **atenúa** `c` y no lo infla. En el histórico
   hay 0 casos de r = 0.
   **Esto crea un desajuste con producción** (sección 13.4): a las ~15:00 UTC, el
   partido de las 00:00 UTC del mismo día ya terminó, y si está en el histórico,
   `RestModel` devolvería r = 0, un valor que el entrenamiento nunca vio.
2. **Primer partido de un equipo en el histórico:** `rest_days = None` → ajuste 0.
   Son 44 partidos tras el warmup (exhibiciones y franquicias con nombre nuevo).
3. **Entre temporadas y parones de 4 días o más:** los dos equipos quedan en r = 4
   y Δr = 0, salvo que uno venga de jugar pretemporada. El tope evita regla aparte.
   Antes del tope hay 4.065 descansos de equipo de 5 días o más (máximo 3.653).
4. **Neutrales:** 310 partidos tras el warmup, tratados como en producción (el
   motor no pasa `neutral` al `Event`).
5. **Empates** (anteriores a 2005): salen del moneyline, como en el motor; entran
   en la puck line con la vista **con** empates (lección de la re-ejecución de
   basket).

## 4. Implementación previa a la medición, sin efecto en producción

Hace falta para la paridad con el motor (sección 5) y para una eventual
activación. Se commitea **antes** del modo completo. Es código en `src/`, así que
debe estar commiteado antes del run de las 12:00 (guarda KI-036).

- `PoissonAdapter.__init__`: `self.rest = RestModel(points_per_day=params.get(
  "rest_elo_per_day", 0.0), max_rest=params.get("rest_max_days", 4),
  normalize=self.normalize)`. `observe` llama a `self.rest.observe`.
- `PoissonAdapter._rates`: `diff = self.elo.rating_diff(home, away) +
  self.rest.margin_adjustment(home, away, str(event.start_time)[:10])` y
  `p_home = 1/(1 + 10**(−diff/400))`, en lugar de `expected_home_win`.
- **Clave nueva `rest_elo_per_day`**, no `rest_points_per_day`: en la NBA esa
  clave está en puntos de margen (0,795). Compartirla mezclaría unidades.
- El mecanismo vive en `PoissonAdapter`, así que `BaseballAdapter` (incluido
  `f5_rates`) y `SoccerAdapter` lo heredan con valor 0. **Solo la NHL** puede
  activarse con este documento. MLB tendrá su propio pre-registro.
- **Tests obligatorios:**
  - con `rest_elo_per_day = 0`, salida idéntica bit a bit a la actual en hockey,
    béisbol (incluido F5) y fútbol;
  - back-to-back conocido → Δr correcto;
  - primer partido → ajuste 0;
  - solo usa días anteriores;
  - los totales no cambian con `c ≠ 0` (hasta el truncamiento).

## 5. Modelo base, brazos, control y paridad

- **Base:** la configuración de producción de la NHL en `386f316`, con
  `_league_meta("nhl").get("league_params")` + `get_adapter("nhl", "hockey",
  params)`: `avg_total 6.1`, `tilt_scale 0.9`, `max_score 15`,
  `home_scoring_bonus 0.10`, `elo_k 10`, `elo_home_adv 15`, `elo_mov` apagado,
  sin `dispersion_k`, `dc_rho` ni `score_rho`. Walk-forward de
  `walk_forward_backtest` sobre todo el histórico, `warmup = 60`. El script aborta
  si `rest_elo_per_day` ≠ 0 en la configuración, o si hay un `goalie_beta` ≠ 0,
  salvo que una enmienda previa diga otra cosa (sección 11).
- El ajuste **no realimenta** el Elo ni las tasas. `rating_diff` y `avg` se
  calculan una sola vez por partido, y cada brazo es una función determinista de
  (diff_base, avg, Δr).
- **Brazos:**

  | Brazo | diff efectiva | Parámetros |
  |---|---|---|
  | Base | diff | — |
  | **Tratamiento T** | diff + c · Δr | c |
  | **Control C** | diff + a | a, constante |

  **Motivo del control:** el local llega más descansado más a menudo (media de Δr
  en entrenamiento ≈ +0,18; en los afectados del test, +0,39 / +0,32 / +0,33), y
  `elo_home_adv 15` es la mitad del valor de la familia. Un `c > 0` puede ganar log
  loss solo por corregir una infraestimación de la ventaja de campo. En basket,
  con el intercepto controlado, `c` bajaba de ≈ 0,8 a ≈ 0,5–0,6, y el control ganó
  en la partición A.
- **Paridad (aserción, aborta si falla, tolerancia 1e-12):**
  1. las probabilidades del brazo base coinciden con `binary_probs` y con
     `markets["spreads@-1.5"|"spreads@1.5"|"totals@5.5"|"totals@6.5"]` del motor;
  2. las del brazo T con el `c` de la partición C coinciden con el motor ejecutado
     con `params["rest_elo_per_day"] = c_C`, en los mismos cuatro mercados y en el
     moneyline. Esto comprueba que el Δr reconstruido es el de `RestModel`.
  - `--parity-only` las comprueba con un `c` arbitrario fijado en el script.
  - Si el script vectoriza la rejilla de Poisson en lugar de llamar a
    `poisson_match_probs` partido a partido, estas aserciones son las que lo
    validan.
- **Pérdida:** log loss binario con recorte 1e-12, la expresión de
  `tuning._binary_nll_series`.

## 6. Particiones y estimación

Las mismas del portero NHL y de la batería, con cortes a 30 de septiembre:

| Partición | Entrenamiento | Test | Contenido del test |
|---|---|---|---|
| A | tras el warmup – 2014-09-30 | 2014-10-01 – 2018-09-30 | 4 temporadas normales |
| B | tras el warmup – 2018-09-30 | 2018-10-01 – 2022-09-30 | burbuja de 2020 y 2020-21 divisional sin público |
| C | tras el warmup – 2022-09-30 | 2022-10-01 – 2026-06-30 | 4 temporadas actuales |

- El modelo base es **un único walk-forward**. Por partición solo se estiman `c`
  (T) y `a` (C), con el entrenamiento, minimizando el log loss medio del
  **moneyline**.
- **Optimizador:** Nelder-Mead de `scipy.optimize.minimize`, punto de partida 0,
  `xatol=1e-7`, `fatol=1e-10`, `maxiter=2000`, sin límites ni restricción de
  signo (E9 del clima). Si no converge, aborta y se trata como defecto de código.
- **Test combinado:** unión de los tres tests (sin solapes), media por partido.
- **Estimación conjunta** diff + a + c·Δr en cada entrenamiento (mismo
  optimizador, partida (0, 0)): da `c_conj`, el `c` con el intercepto controlado.

## 7. Criterios de aceptación (todos a la vez)

1. **Δ log loss moneyline (T − base) ≤ −0,002** en los partidos **afectados** del
   test combinado.
2. **Δ < 0** en los afectados de **cada** partición (A, B y C).
3. **ECE(T) ≤ ECE(base)** en **todo** el test combinado (moneyline), con
   `expected_calibration_error` por defecto (10 bins).
4. **`c > 0` en las tres particiones.** Es la convención de la forma (el equipo
   descansado rinde más), no un umbral.
5. **log loss(T) < log loss(C)** en **todo** el test combinado: el descanso debe
   batir a un desplazamiento constante de la ventaja de campo.
6. **La puck line no empeora:** Δ log loss medio de `spreads@-1.5` y
   `spreads@+1.5` (línea del local) ≤ 0 en todo el test combinado, con el `c` del
   moneyline de cada partición. Se toma del criterio 6b del portero. Los totales
   no llevan criterio: no se mueven por construcción (sección 1.3).
7. **`c_conj > 0` en las tres particiones** (estimación conjunta con intercepto).
   **Propuesta nueva, decisión del operador (sección 16.2).** El motivo es la
   lección de basket: el criterio 5 se cumplió en el combinado, pero no en A, y una
   parte del `c` era sesgo de nivel. En la NHL el confusor es mayor
   (`elo_home_adv 15`). Es una condición de signo, sin constantes nuevas. Si el
   operador la rechaza, pasa a informe secundario y lo demás queda igual.

**Origen de los umbrales.**
- 0,002 es `IMPROVEMENT_MARGIN` de `src/sqp/backtesting/tuning.py:38`, el margen del
  abridor, el clima, el descanso NBA, el portero y la batería.
- **Solo afectados:** decisión del operador heredada (E6 del clima, confirmada
  para el descanso NBA y el portero el 2026-09-26). Aquí sí importa: f ≈ 0,48, así
  que sobre el universo el margen equivaldría a exigir ≈ −0,0042 en los afectados.
- Las líneas ±1,5 son la puck line que cotiza el mercado. 5,5 y 6,5 (solo para la
  paridad y los informes) rodean `avg_total 6.1`. Son líneas de evaluación.
- Criterios 2–7: signos y comparaciones, sin constantes.

Si falla cualquiera: **RECHAZA**. `rest_elo_per_day` sigue en 0 y el resultado se
commitea igual.

## 8. Incertidumbre

Bootstrap por **bloques de fecha**: días UTC completos del test combinado, 10.000
réplicas, semilla 42. Se informan el IC95 percentil y el error estándar de:

- el Δ del criterio 1 (afectados);
- T − C del criterio 5;
- el Δ del criterio 6.

**No es puerta de aceptación:** exigir que el extremo superior sea < 0 sería un
umbral que el operador no ha fijado (E8 del clima). Como en el resultado de basket,
el informe dará también la probabilidad aproximada de que el Δ real supere el
margen, para que un «ACEPTA por poco» se lea como tal.

## 9. Potencia (calendario y modelo, sin resultados)

Recuentos del 2026-09-27 con la regla de la sección 3, en el orden del motor y con
warmup 60, sin leer marcadores. El modo `--pre` debe reproducirlos. Si no
coinciden, se documenta la diferencia **antes** de medir.

**Toda la NHL tras el warmup:** 32.828 partidos, 32.784 con los dos descansos
conocidos y **15.982 afectados (f = 0,487)**.

- Δr: −3: 297 · −2: 1.481 · −1: 4.463 · 0: 16.802 · +1: 6.406 · +2: 2.493 ·
  +3: 842. Con el tope de 4 días y r ≥ 1, |Δr| ≤ 3.
- Descanso por equipo y partido (con tope): 1 día: 14.037 · 2: 30.241 ·
  3: 12.933 · 4: 8.357.

| Partición | Test n | Días | Afectados | Días con afectados | \|Δr\| 1 / 2 / 3 | Local más descansado | Media Δr (afect.) | RMS Δr (afect.) | Local b2b | Visit. b2b | Ambos b2b | Entrenamiento n |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| A | 5.780 | 957 | 2.824 | 737 | 1.910 / 726 / 188 | 1.741 | 0,390 | 1,518 | 882 | 1.507 | 499 | 15.827 |
| B | 5.192 | 872 | 2.376 | 657 | 1.607 / 612 / 157 | 1.416 | 0,316 | 1,517 | 892 | 1.309 | 572 | 21.607 |
| C | 5.978 | 952 | 2.900 | 734 | 2.044 / 683 / 173 | 1.732 | 0,326 | 1,478 | 953 | 1.489 | 558 | 26.799 |
| **Combinado** | **16.950** | **2.781** | **8.100** | **2.128** | | | | **1,503** | | | | |

Las cifras de test n, días, back-to-backs y entrenamiento coinciden con la tabla
§10 del portero, salvo el visitante en back-to-back de A (1.507 aquí y 1.506
allí). `--pre` explicará esa diferencia de una unidad.

**Sensibilidad del modelo** (cadena de §1.1 con `avg` 6,1, sin resultados):

| diff base (Elo) | P(local) | dP / 10 Elo | puck −1,5 / 10 Elo | puck +1,5 / 10 Elo | Over 5,5 / 10 Elo |
|---:|---:|---:|---:|---:|---:|
| 15 | 0,553 | 0,0244 | 0,0227 | 0,0187 | −4,5·10⁻⁸ |
| 60 | 0,659 | 0,0220 | 0,0240 | 0,0142 | −1,7·10⁻⁷ |
| 120 | 0,778 | 0,0166 | 0,0221 | 0,0085 | −5,6·10⁻⁷ |

El tilt se recorta a partir de |diff| ≈ 280 Elo. En esos partidos el ajuste vale 0
aunque cuenten como afectados, lo que diluye el criterio 1 y es conservador. El
modo completo informa cuántos hay.

**Qué efecto hace falta para el criterio 1** (la derivación de los precedentes).
Cerca de p = 0,5, corregir un error δ gana ≈ 2δ² de log loss, así que para 0,002
hace falta δ_RMS ≈ 3,2 pp en los afectados. Con dP/dElo ≈ 0,0022–0,0024, eso es un
desplazamiento RMS de ≈ 13–15 Elo. Con RMS Δr = 1,50, equivale a un **efecto real
de c ≈ 9–10 puntos Elo por día** que el Elo no capture ya: **≈ 2,2 pp de
probabilidad por día de diferencia**, o ≈ 0,6 veces la ventaja de campo actual
(15 Elo) por cada día. Como comparación, en la NBA el `c` sin control equivalía a
≈ 2,5 pp por día y el conjunto a ≈ 1,8 pp. El hockey tiene más azar por partido,
así que un efecto de descanso de la misma naturaleza debería pesar menos en
probabilidad. **Es probable que no llegue al margen.** Se deja dicho antes de
medir, para que un rechazo no se lea como «el descanso no existe en la NHL».

**Ruido:** con δ ≈ 3 pp, la desviación típica del Δ por partido es ≈ 0,063. Con
8.100 afectados, el error estándar sale ≈ 0,0007 sin agrupar (en basket, el
bootstrap por días dio 0,00075 con 9.109). El margen queda a ~3 errores estándar:
**hay potencia**, la misma que en la NBA. Por partición (2.376–2.900 afectados) el
error estándar es ≈ 0,0012–0,0013. Aunque el efecto real estuviera justo en el
margen, el criterio 2 fallaría por ruido en alguna partición con probabilidad
≈ 10–15 %. Es el coste declarado de exigir las tres.

## 10. Informes secundarios (no deciden)

1. `bias` del brazo base (probabilidad media − tasa observada del local) por
   partición y en el combinado. Evolución de `a` entre particiones.
2. `c_conj` y `a_conj` por partición (si el criterio 7 no se adopta, vive aquí).
3. Perfil del log loss de **entrenamiento** en la rejilla c ∈ {−10; −7,5; …; +30}
   Elo por partición, para ver si es monótono a los dos lados del mínimo.
4. Δ en test por |Δr| (1, 2, 3) y por signo de Δr. Residuo medio (y − p_base) por
   valor de Δr: separa pendiente (descanso) de desplazamiento (ventaja de campo),
   como en el resultado de basket.
5. Δ en test según los back-to-backs: ninguno, solo el local, solo el visitante,
   los dos.
6. Δ por temporada (2014-15 a 2025-26), marcando 2019-20 (burbuja) y 2020-21.
7. **Totales:** máximo de |Δp_over| en `totals@5.5` y `totals@6.5` con `c_C`
   (se espera del orden de 1e-6). Confirma la sección 1.3.
8. Sin exhibiciones: criterio 1 repetido excluyendo los partidos con algún equipo
   de **≤ 11 apariciones** en el fichero. No es un umbral de decisión: cae en el
   hueco observado de la NHL, entre 11 apariciones (el club ajeno a la NHL con más
   partidos) y 89 (la franquicia con menos).
9. Sin los 740 pares equipo-fecha dobles (sección 3.1): criterio 1 repetido
   excluyendo los partidos de esos equipos en esas fechas.
10. **Línea capturada del mercado:** `c_C` en h2h y en la puck line principal del
    consenso (`roi_engine.load_closing_odds`, `_pick_main_lines`) sobre la muestra
    NHL con cuotas. Se informa n. Mide log loss frente al resultado, **no ventaja
    sobre el mercado**.
11. **Solo identidades, sin resultados:** si `data/historical/goalies_nhl.csv`
    existe al ejecutar, fracción de partidos con r = 1 en que el titular difiere
    del titular del partido anterior del equipo, por partición y lado. Solo lee
    `starter` y el identificador del portero: **nunca** `goals_against`, paradas
    ni `decision`, y no cruza porteros con resultados (sección 11). Mide cuánto
    del back-to-back es cambio de portero.

## 11. Interacción con el pre-registro del portero NHL

**El confusor.** Los suplentes juegan mucho más el segundo partido de un
back-to-back. Con los datos de hoy:

- el descanso (solo calendario) recoge el cansancio de los jugadores de campo
  **y** la parte esperada del cambio a suplente;
- el brazo M1 del portero (titular real) recoge la calidad del suplente **y**,
  a través de la selección del entrenador, parte del cansancio (el propio
  pre-registro lo anticipa en su informe 4);
- el proxy M2 (titular del partido anterior) casi no ve el cambio en el
  back-to-back: ahí suele ser el titular habitual, que hoy descansa.

**Qué se mide primero: el descanso** (**decisión del operador**, sección 16.3). Motivos:

1. **Es información cierta a la hora del pick.** El calendario se conoce siempre.
   El portero depende de un proxy (M2) o de anuncios que aún se están capturando
   (fase 2).
2. **No necesita datos nuevos.** La medición del portero espera al backfill y a su
   script. `scripts/research/measure_goalie_nhl.py` no existe todavía.
3. **Da al portero una base más limpia.** Con el descanso dentro, el portero mide
   lo que aporta **además** del calendario, que es la atribución que su informe 4
   intentaba reconstruir.
4. La temporada regular empieza hacia el 7 de octubre. Si el descanso se acepta,
   activarlo desde el primer partido evita un cambio de régimen a mitad de
   temporada en las filas NHL.

**Cómo se evita contar dos veces: anidamiento con base actualizada.** Regla,
válida en los dos órdenes:

- **La medición que se ejecute en segundo lugar usa como base el modelo con el
  primer mecanismo si fue ACEPTADO**, esté o no activado ya en producción, con su
  valor de partición C. Si fue rechazado, la base no cambia.
- Así, el segundo parámetro se estima **condicionado** al primero: solo puede
  ganar con la información que el primero no recoge. El reparto entre los dos
  depende del orden, pero el modelo combinado no cuenta nada dos veces.
- **Si el descanso va primero y acepta**, el pre-registro del portero necesita una
  **enmienda previa a su modo completo**: base = producción + `rest_elo_per_day =
  c_C`, paridad del motor con ese parámetro, y M1, M2 y el control C sobre esa
  base. Los criterios no cambian.
- **Si el portero se ejecutara antes** (por ejemplo, si su script está listo
  primero), este documento se enmienda igual: base con `goalie_beta = β_C (M2)` y
  `goalie_prior_shots = k_C`.
- **Fase 2 del portero (híbrido con probables):** si el descanso está aceptado, el
  híbrido se mide sobre la base con descanso. Como informe secundario, `c` se
  re-estima conjuntamente con β usando las identidades del híbrido. Cualquier
  cambio de `c` que se quiera aplicar exige un pre-registro nuevo: no se reajusta a
  mano.

**Protección del pre-registro del portero.** Esta medición **no lee** marcadores de
porteros, goles encajados ni `decision`, y no cruza porteros con resultados. Solo
el informe 11 cuenta identidades, lo mismo que calcula el `--pre` del portero. El
resultado del descanso (en particular, el informe 5 por back-to-backs) sí será
exposición previa para el portero. Se declarará en su enmienda. No le permite
ajustar nada, porque sus criterios ya están fijados.

## 12. Interacción con la batería de ajustes

Las celdas NHL de la batería (`2026-09-27-preregistro-bateria-ajustes.md`) usan
como base la NHL de producción. Por su §16, si el portero se activa antes de su
ejecución, la base se enmienda y `--pre` se repite. **Se aplica lo mismo al
descanso:** si se acepta antes de que la batería ejecute su modo completo, la
base NHL de la batería se enmienda (con `rest_elo_per_day = c_C`) y se repite su
`--pre`. Las features de la batería son ventanas de resultados, no calendario, así
que el solapamiento de señal es pequeño. La regla existe para que la base sea la
del sistema que operará.

## 13. Si se acepta: lo que haría falta para activarlo

No se toca producción en esta medición. Activar es un cambio aparte, con
aprobación y en este orden:

1. **Addenda previos** en `2026-09-25-repreregistro-gate-k52.md` y en
   `2026-08-26-preregistro-el-modelo-manda.md`, antes de tocar la configuración,
   como los tres del 2026-09-26: fecha del cambio, sin alterar criterios y con la
   prohibición de usarlo luego para recortar la ventana. Además, las enmiendas del
   portero y de la batería (secciones 11 y 12).
2. **Valor:** `rest_elo_per_day` = `c` de la **partición C** (brazo T, como en
   basket), solo para `nhl`, en `configs/leagues/ratings.yaml`, con un comentario
   que remita al resultado. `rest_max_days` sigue en 4. No se re-estima con todo el
   histórico ni se usa `c_conj`: los dos serían valores no pre-registrados. Se
   declara que `c_C` incluye el desplazamiento medio a favor del local (media de Δr
   ≈ 0,33 en los afectados de C).
3. **`rest_days_coef` sigue en 0.**
4. **Paridad entre entrenamiento y servicio**, verificada y no supuesta:
   - que `event.start_time` llega en UTC a `estimate`;
   - que el run diario tiene los resultados del día anterior al generar (orden
     `SETTLE_ALL` → `RUN_DIARIO_ALL`). Si falta el partido de ayer, un
     back-to-back se ve como descanso largo y el ajuste se invierte. Test con un
     back-to-back conocido;
   - **el caso de la sección 3.1:** si a las ~15:00 UTC el histórico ya contiene
     un partido del mismo día UTC (inicio a las 00:00–03:00 UTC), producción vería
     r = 0 donde el entrenamiento vio r ≥ 2. **Decisión del operador**
     (sección 16.5): (a) servir con la misma regla que el motor, ignorando para el
     descanso los partidos del mismo día UTC (paridad exacta, pierde esa
     información), o (b) aceptar r = 0 (lo que dice el calendario, pero fuera del
     soporte del entrenamiento y con un ajuste mayor que el de un back-to-back).
     Este documento recomienda (a): el `c` se midió con esa definición. Medir el
     descanso en horas (con `startTimeUTC`, que la tabla de porteros trae desde
     2005) sería una forma distinta con su propio pre-registro.
5. **Recalibrar en staging** (`controlled-recalibration`) `nhl_h2h` y
   `nhl_spreads`, entrenados sin descanso. `nhl_totals` no se toca (sección 1.3).
   La promoción necesita aprobación humana.
6. **Vigilancia:** si la primera temporada activa empeora el log loss NHL, se
   revisa con un pre-registro nuevo, no ajustando `c` a mano.
7. **MLB no hereda nada.** Tiene su propio pre-registro (el siguiente en la cola).
   El mismo código, con `rest_elo_per_day` = 0 hasta entonces.

## 14. Compromisos de ejecución

- **Script único:** `scripts/research/measure_rest_nhl.py`, con tres modos:
  - `--pre`: recuentos de la sección 9, distribución de Δr, pares equipo-fecha
    dobles, apariciones por equipo y hash. **Sin marcadores**;
  - `--parity-only`: aserciones de la sección 5 con un `c` arbitrario fijado en el
    script, más el test de totales invariantes;
  - completo: produce el JSON (`--out`) y aborta si el hash no coincide con el de
    `--pre`. El informe `docs/research/2026-09-XX-resultado-descanso-nhl.md` se
    redacta a partir del JSON.
- La implementación de la sección 4 y el script se commitean **antes** del modo
  completo, tras la revisión independiente del script (como en basket).
- **Una sola ejecución.** Sin miradas intermedias al efecto y sin cambiar
  particiones, métrica, tope, líneas ni forma después de ver el resultado.
- **Regla de re-ejecución (E10):** solo se repite si aparece un defecto de
  **código o datos** demostrable sin mirar el resultado: paridad rota, filas mal
  ordenadas o unidas, hash distinto del de `--pre`, o que el optimizador no
  converja. El diagnóstico se hace a ciegas (solo longitudes e índices, como en
  basket), se documenta el defecto y se commitean las dos salidas. Un resultado
  adverso no es motivo para repetir.
- Las enmiendas (por ejemplo, tras la revisión del script) se añaden al final
  **antes** del modo completo y mandan sobre el texto.
- **Reabrir tras un rechazo exige una forma distinta y pre-registrada:**
  indicadores de back-to-back, descanso en horas, viajes o un efecto sobre
  totales. Repetir esta con otro tope, otras particiones u otra unidad sería
  buscar una señal a medida.

## 15. Interacciones con el gate K = 52 y «el modelo manda»

**La medición no interfiere con ninguno:** solo lee el histórico de resultados. No
toca el stream servido, `data/bets/prediction_gate.json`, los calibradores ni la
configuración, y no gasta ningún test de entrada.

**Una activación sí:**

- **Prediction gate (K = 52).** El gate usa `model_probability`, el modelo puro. El
  mecanismo vive en el adaptador, así que cambia la `d` de **`nhl|h2h` y
  `nhl|spreads`**, pero **no** la de `nhl|totals` (sección 1.3). Al 2026-09-26 el
  registro no tenía cortes NHL con test de entrada gastado, porque la temporada
  está parada. Activar no cambia el número de cortes: K = 52 y el techo 63 no se
  tocan. Exige el addendum previo (sección 13.1).
- **«El modelo manda»** (≥ 3.402 eventos graduados, ≈ 2026-11-17/24). Evalúa
  `p_cal`, que hereda el adaptador. Las filas NHL desde octubre caen en su
  ventana. Las opciones son activar con addendum previo (lo que se hizo con el
  abridor MLB y el descanso NBA) o esperar a que se ejecute (lo que la batería
  recomienda para sus términos). **Decisión del operador** (sección 16.4). Este
  documento se inclina por el precedente del descanso NBA, activar con nota
  previa: el mecanismo es el mismo, no toca los totales, y activarlo antes del
  inicio de la temporada deja todas las filas NHL de la ventana en un solo
  régimen. Si la activación llegara con la temporada ya empezada, recomienda
  esperar.

## 16. Decisiones del operador que quedan marcadas

1. **Criterio 1 sobre los afectados** (heredado de E6 y confirmado en el descanso
   NBA y el portero). La alternativa, sobre todo el test combinado, es más
   exigente (f ≈ 0,48).
2. **Criterio 7 (`c_conj > 0` en las tres particiones):** incluirlo como criterio
   (propuesta de este documento) o dejarlo como informe secundario.
3. **Orden descanso → portero** y **regla de anidamiento** de la sección 11,
   incluida la enmienda previa al pre-registro del portero si el descanso acepta.
4. **Momento de una eventual activación** respecto a «el modelo manda» (sección
   15). El precedente es activar con nota previa.
5. **Partidos del mismo día UTC en producción** (sección 13.4): paridad con el
   motor (recomendado) o r = 0.

Decisiones técnicas tomadas en este documento, no del operador (se pueden
revisar en la revisión independiente):

- la forma de Elo (sección 1.2);
- el nombre de la clave `rest_elo_per_day`;
- la rejilla del informe 3;
- el corte de exhibiciones en el hueco 11–89.

---

Relacionado: [[2026-09-26-preregistro-descanso-basket]],
[[2026-09-26-resultado-descanso-basket]], [[2026-09-26-preregistro-portero-nhl]],
[[2026-09-27-preregistro-bateria-ajustes]], [[2026-09-26-preregistro-clima-mlb]],
[[2026-09-25-repreregistro-gate-k52]], [[2026-08-26-preregistro-el-modelo-manda]].

**Decisiones del operador resueltas el 2026-09-27, antes de implementar:**
1. **Criterio 7 exigido:** `c_conj > 0` en las tres particiones.
2. **Orden: primero el descanso y después el portero**, con la regla de anidamiento: la medición que va segunda usa como base el mecanismo aceptado en la primera.
3. **Activación, si se acepta:** con nota previa si llega antes del inicio de la temporada (~7 oct). Si llega con la temporada empezada, se espera a una ventana limpia.
4. **Partidos del mismo día UTC en producción:** la misma regla que el motor, para que lo servido coincida con lo medido.
Criterio 1 solo sobre los afectados, como en los precedentes.
