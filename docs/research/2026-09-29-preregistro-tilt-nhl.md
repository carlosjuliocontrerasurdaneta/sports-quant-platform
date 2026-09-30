# Pre-registro — ¿bajar `tilt_scale` corrige la sobreconfianza del modelo NHL?

**Fecha:** 2026-09-29. Escrito **antes** de evaluar ningún valor de `tilt_scale`
contra resultados. Lo único consultado es el código, la documentación, los
precedentes y **distribuciones de la probabilidad del modelo sin marcadores**
(sección 9: cómo cambian la media y la dispersión de `p` con el tilt, sin
compararlas con ningún resultado). Código de referencia: `main` en `50aee46`.

**Orden del operador (2026-09-29):** medir y ajustar `tilt_scale` de la NHL
**antes** que el portero, porque la base NHL es sobreconfiada
(`2026-09-26-preregistro-portero-nhl.md`, decisiones del 2026-09-29: «El portero
se medirá sobre la base que resulte de ese test»).

Precedentes que se siguen: `2026-09-27-preregistro-descanso-nhl.md` (misma liga,
mismas particiones, misma paridad) con su resultado
`2026-09-29-resultado-descanso-nhl.md`, `2026-09-26-preregistro-descanso-basket.md`
y el precedente MLB del tilt (0,8 → 0,4, `scripts/tune_mlb_pitcher.py`, etapa 2;
KI-006 y la decisión del 2026-06-12 en `.claude/memory/`). Vienen incorporados
desde el principio:

- particiones temporales con selección solo en el entrenamiento (rolling origin);
- controles, incluido uno **constante** y uno **recalibrado**;
- bootstrap por días;
- paridad exacta con el motor;
- ejecución única con regla de re-ejecución;
- ningún umbral sin origen (el margen es `IMPROVEMENT_MARGIN`);
- potencia calculada antes de medir.

---

## 1. La pregunta y el mecanismo

**Pregunta.** Sustituir el `tilt_scale` de la familia hockey (0,9, sin ajustar
nunca para la NHL) por un valor estimado en el entrenamiento, ¿mejora la
probabilidad del modelo puro NHL frente al resultado, **y** deja un modelo que
aporta algo sobre no saber nada más que la tasa de victorias del local?

### 1.1 Dónde vive `tilt_scale` (verificado)

- `src/sqp/sports/registry.py:43`: `FAMILY_PARAMS["hockey"]` =
  `avg_total 6.1, tilt_scale 0.9, max_score 15, home_scoring_bonus 0.10,
  elo_k 10, elo_home_adv 33`.
- `configs/leagues/ratings.yaml`, `nhl:` solo sobrescribe `elo_home_adv: 15.0`.
  No hay `tilt_scale` para la NHL: rige el 0,9 de la familia.
- MLB sí lo sobrescribe (`tilt_scale: 0.4`; la familia béisbol tiene 0,8).
- Parámetros resueltos hoy (consulta del 2026-09-29 con `_league_meta("nhl")` +
  `get_adapter`): `avg_total 6.1`, `tilt_scale 0.9`, `max_score 15`,
  `home_scoring_bonus 0.1`, `elo_k 10`, `elo_home_adv 15.0`; sin `elo_mov`,
  `dc_rho`, `dispersion_k` ni `score_rho`; `rest_elo_per_day` ausente (0).

### 1.2 Cómo lo usa `PoissonAdapter._rates` (`src/sqp/sports/adapters.py`)

    p_home = 1 / (1 + 10^(−diff/400))                  diff = rating_diff (+ descanso, hoy 0)
    tilt   = clip((p_home − 0,5) · tilt_scale, −0,30, +0,30)
    λ_home = avg · (0,5 + tilt) + home_scoring_bonus
    λ_away = avg · (0,5 − tilt)                        (suelo 0,1 en ambas)

`elo_k` y `elo_home_adv` actúan **antes**: fijan la trayectoria de los ratings
(`observe`) y, por tanto, `diff`. `home_scoring_bonus` suma goles al local fuera
del tilt. `tilt_scale` es la **pendiente** con la que la probabilidad Elo se
convierte en reparto de goles.

### 1.3 Propiedad clave: `tilt_scale` no realimenta nada

El Elo y `TeamScoringRates` se actualizan con los **marcadores** en `observe`, no
con las probabilidades. `tilt_scale` solo entra en `_rates`. Por tanto:

- `diff` y `avg` de cada partido son **los mismos para cualquier tilt**: basta
  **un único walk-forward** de la base;
- cada valor de tilt es una función determinista y analítica de `(diff, avg)`.
  Es la misma estructura que el brazo T del descanso NHL, con las funciones
  vectorizadas ya validadas por paridad a 1e-12 en `measure_rest_nhl.py`
  (`_lambda_split`, `home_win_vec`, `cover_vec`, `over_vec`, que ya reciben
  `tilt_scale` como argumento).

Esto **no** vale para `elo_k` ni `elo_home_adv`: cambiarlos cambia la trayectoria
del Elo y exige un walk-forward por valor (sección 2).

### 1.4 Qué hace un tilt más bajo (cálculo sin resultados, `avg` 6,1)

| diff (Elo) | P(local), tilt 0,9 | tilt 0,4 | tilt 0 |
|---:|---:|---:|---:|
| 0 | 0,5157 | 0,5157 | 0,5157 |
| 15 (ventaja de campo) | 0,5527 | 0,5322 | 0,5157 |
| 60 | 0,6590 | 0,5807 | 0,5157 |
| 120 | 0,7780 | 0,6402 | 0,5157 |
| 200 | 0,8839 | 0,7057 | 0,5157 |

Tres consecuencias que se declaran ahora:

1. **El límite tilt → 0 es un modelo casi constante**, p ≈ 0,516, que solo
   recoge `home_scoring_bonus`. **No es** el modelo constante con la tasa
   observada del local (sección 5): un tilt bajo «aplana hacia 0,516», no hacia
   la tasa real.
2. **Bajar el tilt también baja el nivel.** `elo_home_adv` (15 Elo) pasa por el
   tilt, así que aplanar recorta la ventaja de campo. Media de `p` en el test
   combinado (sección 9): 0,5456 con 0,9; 0,5339 con 0,5; 0,5306 con 0,4. Un tilt
   estimado solo por log loss negocia a la vez pendiente y nivel. Por eso se
   añade la estimación conjunta con un desplazamiento de nivel (brazo T2,
   criterio 7).
3. **`tilt_scale` es, en esencia, una recalibración de pendiente dentro del
   adaptador.** Para `avg` fijo, `p` es monótona en `diff` con cualquier tilt > 0.
   Solo `avg` puede reordenar partidos, y apenas lo hace. El tilt **no puede añadir
   discriminación**: solo deja de exagerarla. Aceptarlo significaría que el
   modelo deja de sobreafirmar, no que sepa más (sección 5.2 y criterio 3).

### 1.5 Qué implica para cada mercado

| Mercado | Efecto | Motivo |
|---|---|---|
| Moneyline (h2h) | **se mueve** (métrica principal) | cambia el reparto de goles |
| Puck line (±1,5) | **se mueve mucho** | mismo reparto. Desviación típica de P(local −1,5) en el test combinado: 0,161 con 0,9 y 0,073 con 0,4; media 0,321 → 0,291 |
| Totales | **no se mueve** (salvo truncamiento) | `λ_home + λ_away = avg + home_scoring_bonus` no depende del tilt, y con Poisson independiente el total solo depende de la suma. Máximo \|Δ P(over)\| entre 0,9 y 0,4 en el test combinado: 1,8·10⁻⁵ (5,5) y 2,4·10⁻⁵ (6,5), por la rejilla truncada a 15 goles y el suelo de 0,1 |

**Los totales no llevan criterio.** Se informa el máximo \|Δ\| con el tilt de C
(sección 10). El calibrador y el corte `nhl|totals` no se ven afectados por una
activación.

## 2. Parámetros: solo `tilt_scale`

**Decisión: un solo parámetro libre, `tilt_scale`.** `elo_k` y `elo_home_adv` no
se ajustan en este pre-registro.

Motivos:

1. **Es el parámetro de la patología diagnosticada.** El diagnóstico del
   orquestador (sección 3) dice que el problema es la **dispersión** (desviación
   típica de `p` 0,15–0,20, sesgo medio ≈ 0), no el nivel. La revisión del
   2026-08-17 (`Obsidian/Bitácora/2026-08-17.md`) clasifica `tilt_scale` como
   parámetro de dispersión y `elo_home_adv`/`home_scoring_bonus` como parámetros
   de nivel, con correcciones opuestas.
2. **No realimenta** (sección 1.3): un walk-forward, paridad exacta y una sola
   trayectoria para todos los brazos. Con `elo_k` cada valor es otro modelo.
3. **`elo_k` y `tilt_scale` están confundidos.** Los dos escalan la dispersión
   final de `p`: un `elo_k` menor comprime los ratings y un tilt menor comprime
   su traducción. Ajustarlos juntos da una cresta casi plana en la que la
   partición entre ambos no se identifica, y cada combinación mueve de forma
   distinta la memoria del Elo. `elo_k` es otra hipótesis (cuánto recuerda el
   Elo), no la pendiente. Se reserva para reabrir (sección 15).
4. **`elo_home_adv` es un parámetro de nivel,** y el nivel no es el problema
   declarado (sesgo ≈ 0). Pero la sección 1.4.2 muestra que bajar el tilt mueve el
   nivel. Se controla con el brazo diagnóstico **T2** (tilt + desplazamiento
   analítico de nivel, sin realimentación) y con el criterio 7, **no** ajustando
   `elo_home_adv`, que realimenta el Elo y exigiría un walk-forward por valor.
5. **Grados de libertad.** Con 15.827–26.799 partidos de entrenamiento, el
   sobreajuste de un parámetro es del orden de 1/(2n) ≈ 2–3·10⁻⁵ de log loss,
   despreciable frente al margen de 0,002. El riesgo real de añadir parámetros no
   es el sobreajuste, sino la **multiplicidad de caminos** (probar combinaciones
   hasta que una pase). Un solo parámetro, declarado ahora, lo cierra.

**Una observación sin resultados que refuerza el punto 3.** La desviación típica
de `diff` en los tests crece partición a partición: 74,8 (A), 83,6 (B) y 94,7 (C)
Elo. El Elo de la NHL no regresa a la media entre temporadas (no hay regresión
en `src/sqp/models/elo.py`) y los ratings se dispersan con el tiempo. Un tilt
constante estimado sobre un entrenamiento con menos dispersión **aplanará menos
de lo necesario** en el test siguiente. Es un sesgo conservador para los
criterios 1 y 2 (juega en contra de aceptar) y una pista de que la causa de fondo
puede estar en el Elo (memoria y regresión entre temporadas). Esa hipótesis no se
mide aquí (sección 15).

**Optimizador.** Nelder-Mead de `scipy.optimize.minimize` sobre el log loss medio
del moneyline en el entrenamiento, **punto de partida 0,9** (el valor actual),
`xatol=1e-7`, `fatol=1e-10`, `maxiter=2000` (los `NM_OPTS` de los precedentes),
sin límites. Si no converge, aborta y se trata como defecto de código. No se usa
una rejilla para decidir: la rejilla discretizaría el valor que se activaría. La
rejilla 0,00–1,20 con paso 0,05 se usa solo para el perfil de entrenamiento
(informe 3) y para el procedimiento canónico de `tuning.py` (informe 4).

**Rango.** Sin límites en el optimizador. El recorte del tilt a ±0,30 y el suelo
de λ siguen actuando. Con el 0,9 actual, solo el 0,09 % de los partidos del test
combinado tienen el tilt recortado (0 % en A, 0,08 % en B y 0,20 % en C). Un tilt
≤ 0 significaría que el Elo no aporta o es contraproducente: lo recoge el
criterio 5.

## 3. Lo que ya se sabe y exposición previa de la muestra

**El histórico NO es virgen para esta pregunta.** Exposición declarada:

1. **Diagnóstico del orquestador (2026-09-29)** con `walk_forward_backtest` NHL y
   la configuración canónica: log loss global 0,6928 (ln 2 = 0,6931), peor que un
   modelo constante con la tasa del local (≈ 0,6887); varias temporadas por
   encima de 0,70; ECE 0,068; desviación típica de `p` 0,15–0,20; sesgo medio
   ≈ 0. **Estas cifras ya contienen información sobre el tilt óptimo**: dicen que
   está claramente por debajo de 0,9. No se ha calculado a partir de ellas ningún
   valor de tilt, y este documento no fija ninguno.
2. **Resultado del descanso NHL (2026-09-29):** en el test combinado, la base
   tiene log loss 0,69393, ECE 0,0723 y sesgo +0,0037 (A −0,0017, B +0,0079,
   C +0,0052). El sesgo positivo interactúa con la sección 1.4.2: aplanar baja el
   nivel y podría **corregir** ese pequeño exceso, o pasarse. El criterio 7 y el
   informe 1 separan las dos cosas.
3. **Precedente MLB:** 0,8 → 0,4 con una rejilla **en muestra** de tres valores
   (`TILTS = (0.4, 0.6, 0.8)`), validada después con `validate_oos.py` en ROI
   (memoria del proyecto: KI-006 y `known-issues.md`). Aquel procedimiento fue más
   débil que este. No fija ningún valor para la NHL, que es otra liga y otra
   familia.
4. **Revisión del modelo por deporte (2026-08-17,**
   `audit/reproductions/model_review_by_sport.py`**):** midió pendientes de
   calibración por deporte. No se ha comprobado qué dijo de la NHL y no se ha
   consultado para este documento.
5. **Distribuciones sin resultados de la sección 9,** calculadas para este
   documento: solo `p` en función del tilt, nunca comparada con `y`.

**Por qué el pre-registro sigue teniendo valor a pesar de la exposición.** La
pregunta no es si el tilt óptimo es menor que 0,9 (la exposición ya lo sugiere),
sino **si un valor elegido solo con el pasado generaliza al futuro** en las tres
particiones, con margen sobre la base, **batiendo a la constante** y sin estropear
la puck line. La exposición no permite ajustar nada de eso, porque los criterios
se fijan aquí.

**Lo que no se afirma.** Siete mediciones previas no encontraron ventaja sobre el
feed público de cuotas. **Aceptar significaría que el modelo estima mejor, no que
gane dinero.** Probabilidad estimada ≠ probabilidad implícita ≠ edge ≠ hit rate
observado ≠ ROI esperado ≠ ROI realizado. Nada de este documento es una
afirmación de rentabilidad.

## 4. Datos

- **Fuente:** `ResultsStore(ROOT).load("nhl")`, todas las filas: 32.902 al
  2026-09-29, SHA-256 `6163a66f…7a81` (el mismo de la Enmienda 1 del descanso).
  El `--pre` registra el hash vigente al ejecutarse, y el modo completo aborta si
  cambia (sección 14).
- **Orden y warmup:** los del motor (`walk_forward_backtest`, diferido por días
  UTC, `warmup = 60`).
- **Semántica temporal:** `date` es el día UTC del inicio. `diff` y `avg` de cada
  partido se calculan con el estado **al cierre del día anterior**, igual que en
  el motor y en producción. El tilt no introduce ninguna información nueva: no hay
  riesgo de fuga más allá del que ya controla la paridad con el motor.
- **Moneyline:** sin empates (anteriores a 2005, fuera de todos los tests), como
  en `binary_probs`. **Puck line y totales:** todas las filas tras el warmup
  (vista `df_all` del descanso).
- **Pretemporada, temporada regular, playoffs y neutrales:** todos, como ve
  producción y como en el descanso NHL.
- **Los partidos que el portero excluye** (fechas fallidas del backfill,
  Enmienda 2 del portero) **no se excluyen aquí**. Esta medición no usa porteros.

## 5. Brazos, controles y paridad

### 5.1 Brazos

| Brazo | Probabilidad | Parámetros (estimados en entrenamiento) |
|---|---|---|
| **Base** | `home_win_vec(diff, avg, 0,9)` | — |
| **Tratamiento T** | `home_win_vec(diff, avg, t)` | `t` |
| **Constante K** | `k` = tasa de victorias del local (sin empates) en el entrenamiento | `k` (media, sin optimizador) |
| **Platt P** | σ(α + β · logit(p_base)) | α, β (Nelder-Mead, partida (0, 1)) |
| **T2 (diagnóstico)** | `home_win_vec(diff + a, avg, t)` | `t`, `a` (Nelder-Mead, partida (0,9, 0)) |

- `a` está en puntos Elo y se suma a `diff` **sin realimentar** el Elo: es el
  brazo de control del descanso NHL, en la misma unidad que `elo_home_adv`. **No
  es activable**: T2 solo sirve para saber si el `t` de T depende del nivel.
- Todos los parámetros se estiman por partición y **solo con su entrenamiento**.
  La pérdida es el log loss binario con recorte 1e-12, la expresión de
  `tuning._binary_nll_series`.

### 5.2 El control relevante: por qué la constante además de la base

La base es un comparador **débil**: según el diagnóstico, ya es peor que la
constante. Batir a la base por 0,002 podría conseguirse solo con **aplanar**:
cualquier `t` entre la base y el óptimo gana log loss aunque el Elo no aporte nada,
porque acerca `p` a 0,5. Si el Elo NHL no llevara información útil, el óptimo
sería `t` ≈ 0 y T sería el modelo casi constante de 0,516. Eso pasaría el
criterio 1 y dejaría en producción un modelo que no sabe nada.

Por eso se exige **además batir a K** (criterio 3), la constante con la tasa real
del local en el entrenamiento, que es lo mínimo que sabe cualquiera:

- si T < K, el Elo aporta algo **después** de corregir su pendiente;
- si T ≥ K, el Elo no aporta ni corregido. La conclusión es entonces que el
  problema no es el tilt, sino el Elo, y se rechaza aunque T bata a la base.

**P (Platt) no es criterio, es la referencia de techo.** Con dos parámetros en
el espacio de probabilidad, es la mejor recalibración monótona posible de la base.
T no puede, en principio, batirla por mucho (solo por la forma de Poisson). Se
informa **qué fracción de la ganancia de Platt captura T**:
(ll_base − ll_T)/(ll_base − ll_P). Una fracción baja indicaría que falta un
término de nivel (α), que es lo que mide T2. Exigir T ≈ P obligaría a fijar una
tolerancia que el proyecto no tiene, así que no se exige.

**AUC (informe 2).** T y la base deberían tener prácticamente la misma AUC
(sección 1.4.3). Se informa para dejar constancia de que el tilt no cambia la
ordenación.

### 5.3 Paridad (aserciones; aborta si falla; tolerancia 1e-12)

1. Las probabilidades del brazo base coinciden con `binary_probs` y con
   `markets["spreads@-1.5"|"spreads@1.5"|"totals@5.5"|"totals@6.5"]` del motor
   ejecutado con la configuración canónica.
2. Las del brazo T con el `t` de la partición C coinciden con el motor ejecutado
   con `params["tilt_scale"] = t_C`, en el moneyline y en esos cuatro mercados.
   Esto comprueba que el tilt entra por `league_params` igual que lo haría en
   producción (la cadena `FAMILY_PARAMS → LEAGUE_OVERRIDES → league_params`).
3. `--parity-only` repite la aserción 2 con un tilt de prueba fijo en el script
   (0,5) y comprueba que `diff` y `avg` del walk-forward son idénticos con 0,9 y
   con 0,5 (sección 1.3).

## 6. Particiones y estimación

Las mismas del descanso y del portero NHL, con cortes a 30 de septiembre:

| Partición | Entrenamiento | Test | Test n (moneyline) | Días de test | Entrenamiento n |
|---|---|---|---:|---:|---:|
| A | tras el warmup – 2014-09-30 | 2014-10-01 – 2018-09-30 | 5.780 | 957 | 15.827 |
| B | tras el warmup – 2018-09-30 | 2018-10-01 – 2022-09-30 | 5.192 | 872 | 21.607 |
| C | tras el warmup – 2022-09-30 | 2022-10-01 – 2026-06-30 | 5.978 | 952 | 26.799 |
| **Combinado** | | | **16.950** | **2.781** | |

- Es un **rolling origin** con entrenamiento expansivo: cada `t` se elige solo con
  el pasado de su test y se evalúa en un bloque que esa selección nunca vio.
- **Test combinado:** unión de los tres tests (sin solapes), media por partido.
- Las filas de septiembre de 2026 quedan fuera de todos los entrenamientos y
  tests.
- **El procedimiento canónico del proyecto** (`tuning.rolling_origin_improvement`,
  4 bloques, `HOLDOUT_MIN_TRAIN_FRAC` 0,4, sobre la rejilla del informe 3 con 0,9
  como valor por defecto) se ejecuta también, como informe 4. **No decide.** Sus
  bloques no coinciden con las particiones, y su selección está limitada a la
  rejilla.

## 7. Criterios de aceptación (todos a la vez)

1. **Δ log loss moneyline (T − base) ≤ −0,002** en **todo** el test combinado.
   Aquí no hay subconjunto de afectados: el tilt actúa en todos los partidos.
2. **Δ < 0 en cada partición** (A, B y C).
3. **ll(T) < ll(K)** en el test combinado **y** en cada partición: el modelo
   corregido debe batir a la constante con la tasa del local de su entrenamiento
   (sección 5.2).
4. **ECE(T) ≤ ECE(base)** en todo el test combinado (moneyline), con
   `expected_calibration_error` por defecto (10 bins).
5. **0 < t < 0,9 en las tres particiones.** Es la dirección de la hipótesis
   (sobreconfianza → aplanar) y la condición de que el Elo conserve peso. No es un
   umbral: 0 y 0,9 son el límite sin información (sección 1.4.1) y el valor actual.
6. **La puck line no empeora:** Δ log loss medio de `spreads@-1.5` y
   `spreads@+1.5` (línea del local) ≤ 0 en todo el test combinado, con el `t` del
   moneyline de cada partición. Es el criterio 6 del descanso NHL. Aquí pesa más,
   porque el tilt mueve la puck line con más fuerza que el moneyline
   (sección 1.5).
7. **t2 < 0,9 en las tres particiones,** donde t2 es el tilt de la estimación
   conjunta T2 (tilt + nivel). El aplanamiento debe sobrevivir con el nivel
   controlado: si solo aparece sin `a`, lo que se estaba corrigiendo era nivel y no
   dispersión. Es una condición de signo sin constantes nuevas, la analogía del
   criterio 7 del descanso NHL (`c_conj > 0`). **Decisión del operador**
   (sección 16.2).

**Origen de los umbrales.**
- 0,002 es `IMPROVEMENT_MARGIN` de `src/sqp/backtesting/tuning.py:38`, «required
  log-loss gain vs the family default». Aquí se aplica exactamente a eso: el valor
  de la familia (0,9) frente a uno ajustado, sobre todos los partidos, como en
  `tune_home_advantage` y `tune_dc_rho`.
- El criterio 3 es de **signo**, sin margen. El margen existe para no cambiar la
  configuración por ruido, y K no es un candidato a producción, sino una cota de
  cordura. Exigirle también 0,002 es una alternativa más dura, que queda como
  **decisión del operador** (sección 16.1).
- Las líneas ±1,5 son la puck line que cotiza el mercado. 5,5 y 6,5 (paridad e
  informes) rodean `avg_total 6.1`.
- Los criterios 2 a 7 son signos y comparaciones, sin constantes.

Si falla cualquiera: **RECHAZA**. `tilt_scale` sigue en 0,9 para la NHL y el
resultado se commitea igual.

## 8. Incertidumbre

Bootstrap por **bloques de fecha**: días UTC completos del test combinado, 10.000
réplicas, semilla 42. Se informan el IC95 percentil y el error estándar de:

- el Δ del criterio 1;
- T − K del criterio 3;
- el Δ del criterio 6;
- T − P (referencia de techo).

**No es puerta de aceptación** (E8 del clima, como en los precedentes). El
informe da también la fracción de réplicas con Δ ≤ −0,002 y con T − K < 0, para
que un «ACEPTA por poco» se lea como tal.

## 9. Potencia (distribuciones del modelo, sin resultados)

Calculadas el 2026-09-29 con el walk-forward de la base (el Elo y las tasas se
actualizan con marcadores, como en producción) y el tilt aplicado de forma
analítica. **No se ha calculado ninguna pérdida ni se ha leído `y`.** El `--pre`
debe reproducir estas cifras.

### 9.1 Dispersión de `p` según el tilt (moneyline)

| tilt | A: media / d.t. | B: media / d.t. | C: media / d.t. | Combinado: media / d.t. | Combinado p5–p95 |
|---:|---|---|---|---|---|
| 0,9 (actual) | 0,547 / 0,158 | 0,545 / 0,174 | 0,545 / 0,191 | 0,546 / 0,175 | 0,246–0,823 |
| 0,7 | 0,541 / 0,126 | 0,540 / 0,140 | 0,539 / 0,155 | 0,540 / 0,141 | 0,301–0,765 |
| 0,5 | 0,535 / 0,092 | 0,534 / 0,102 | 0,534 / 0,114 | 0,534 / 0,103 | 0,359–0,700 |
| 0,4 | 0,531 / 0,074 | 0,530 / 0,083 | 0,530 / 0,092 | 0,531 / 0,083 | 0,390–0,666 |
| 0,3 | 0,528 / 0,056 | 0,527 / 0,062 | 0,527 / 0,070 | 0,527 / 0,063 | 0,421–0,629 |
| 0,0 | 0,516 / 0,000 | 0,516 / 0,000 | 0,516 / 0,000 | 0,516 / 0,000 | 0,516–0,517 |

Esto confirma la desviación típica de 0,15–0,20 del diagnóstico. Para comparar,
un 0,4 dejaría la dispersión de la NHL en 0,07–0,09.

### 9.2 Escenarios: ganancia esperada si la verdad fuera el modelo con tilt t\*

Si las probabilidades verdaderas fueran las del modelo con t\*, la ganancia
esperada de pasar de 0,9 a t\* es E[KL(p_t\* ‖ p_0,9)]. La «ventaja sobre la
constante» es H(E p_t\*) − E[H(p_t\*)], el máximo que el modelo puede aportar
sobre una constante bien calibrada. Todo se calcula en el test combinado
(16.950 partidos). El error estándar es por partido y sin agrupar (en los
precedentes, el bootstrap por días lo multiplicó por ≈ 1,05–1,1):

| t\* | Ganancia esperada vs 0,9 | EE del Δ | Ventaja sobre la constante |
|---:|---:|---:|---:|
| 0,7 | 0,0034 | 0,0007 | 0,041 |
| 0,6 | 0,0078 | 0,0010 | 0,031 |
| 0,5 | 0,0142 | 0,0013 | 0,022 |
| 0,4 | 0,0226 | 0,0017 | 0,014 |
| 0,3 | 0,0330 | 0,0021 | 0,008 |
| 0,2 | 0,0456 | 0,0025 | 0,004 |

**Lectura:**

- **Criterio 1:** si el tilt verdadero fuera 0,7 o menos, la ganancia esperada
  supera el margen: en 0,7, por ≈ 2 errores estándar; en 0,6, por ≈ 6. Por encima
  de ≈ 0,75, la ganancia esperada ya no llega a 0,002. **Por debajo de 0,7 hay
  potencia de sobra.** El riesgo no es de potencia, sino de generalización: el tilt de un
  entrenamiento largo puede no servir en el test (sección 2, dispersión creciente
  de `diff`).
- **Criterio 3:** la ventaja posible sobre la constante se encoge rápido al
  bajar t\*. Si la verdad fuera t\* ≈ 0,2, el Elo apenas aportaría 0,004 sobre la
  constante, antes de descontar el error de estimación y la diferencia de nivel
  entre 0,516 y la tasa real. **El criterio 3 es el que discrimina** entre
  «corregir la pendiente de un Elo útil» y «aplanar un Elo inútil».
- **Criterio 2 por partición:** con los mismos escenarios, el EE por partición es
  ≈ √3 veces el combinado. Con t\* ≤ 0,6, el Δ esperado supera 4 EE en cada
  partición (A 4,1; B 4,3; C 5,1 con t\* = 0,6). Con t\* ≈ 0,7, la partición A (Δ esperado 0,0027 frente a un EE
  ≈ 0,0010) es la más frágil.
- Son escenarios bajo un modelo supuesto, no predicciones del resultado.

### 9.3 Puck line y totales

| | tilt 0,9 | tilt 0,4 |
|---|---|---|
| P(local −1,5): media / d.t. | 0,321 / 0,161 | 0,291 / 0,073 |
| P(local +1,5): media / d.t. | 0,757 / 0,144 | 0,761 / 0,068 |
| Máx. \|Δ P(over 5,5)\| | — | 1,8·10⁻⁵ |
| Máx. \|Δ P(over 6,5)\| | — | 2,4·10⁻⁵ |

## 10. Informes secundarios (no deciden)

1. **Sesgo** (media de `p` − tasa observada del local) de base, T, T2 y P por
   partición y en el combinado. Evolución de `t`, `t2` y `a` entre particiones.
2. **AUC** de base y T (y de P, que por construcción es igual a la base).
3. **Perfil del log loss de entrenamiento** en la rejilla t ∈ {0,00; 0,05; …;
   1,20} por partición, para ver si el mínimo es interior y único.
4. **Procedimiento canónico:** `tuning.rolling_origin_improvement` sobre esa
   rejilla (0,9 como valor por defecto, 4 bloques, 0,4 de semilla), con sus
   selecciones por bloque. Conecta el resultado con la herramienta de
   `tune_ratings.py`.
5. **Pendiente de calibración** (regresión logística de y sobre logit(p)) de base
   y T por partición. En T debería acercarse a 1.
6. **Tabla de fiabilidad** (10 bins) de base, T y P en el combinado, y **Δ por
   quintil de \|diff\|**. La ganancia debería concentrarse en los extremos.
7. **Δ por temporada** (2014-15 a 2025-26), marcando 2019-20 (burbuja) y
   2020-21. Tilt óptimo **de entrenamiento** por temporada solo como descripción
   de la deriva, sin usarlo para nada.
8. **Puck line por línea:** Δ de −1,5 y de +1,5 por separado, y su ECE.
9. **Totales:** máximo de \|Δ P(over)\| en 5,5 y 6,5 con `t_C`. Se espera del
   orden de 10⁻⁵ (sección 9.3).
10. **Fracción de la ganancia de Platt que captura T**, con IC por bootstrap.
11. **Línea capturada del mercado:** en la muestra NHL con cuotas de cierre
    (`roi_engine.load_closing_odds`), log loss de base, T y el no-vig del
    consenso, con n. Es una referencia frente al resultado, **no una medida de
    ventaja sobre el mercado**. **Antes** de reutilizar código de
    `measure_rest_nhl.py`, hay que corregir el defecto de `_informe_linea_capturada`
    documentado en el resultado del descanso (falta `float(lam[0])`) y cubrirlo
    con un test de humo.
12. **Sensibilidad al redondeo:** Δ log loss en el test entre `t_C` exacto y `t_C`
    redondeado a 3 decimales (el valor que se escribiría, sección 13).

## 11. Interacción con los calibradores NHL

**Verificado el 2026-09-29: hoy no hay ningún calibrador NHL en producción ni en
staging.**

- El registro vivo (`data/models/calibration_methods.json`, que lee
  `_load_method_registry()`) solo tiene `mlb_spreads`, `mlb_totals` y
  `wnba_spreads`.
- El registro de staging (`data/models/staging/`) no tiene entradas NHL.
- No existe ningún `nhl_*_calibration_*.joblib`. `nhl_moneyline_model.joblib` y
  `nhl_totals_model.joblib` son artefactos antiguos que solo mira
  `monitoring/health.py`.
- Sin entrada en el registro, `calibrate_probability` es un **no-op**
  (`daily._warn_if_uncalibrated_accuracy` lo avisa). La probabilidad NHL servida
  es la mezcla del modelo puro con el no-vig (`market_shrink = 0,5`).

Corrige dos supuestos previos: la orden de este pre-registro («los calibradores
NHL de producción, entrenados sobre la base actual») y la frase del resultado del
descanso («que en producción corrige el calibrador `nhl_h2h`»). **Ninguno de los
dos se sostiene hoy.** Consecuencias:

1. **Una activación no exige recalibrar nada**, porque no hay nada que
   recalibrar. Esto hace que el tilt importe **más**: la sobreconfianza del modelo
   puro llega sin corregir a la mitad de la probabilidad servida, al ranking por
   probabilidad y al gate.
2. **Si se entrena un calibrador NHL en el futuro** (`controlled-recalibration`),
   debe entrenarse **solo con filas servidas bajo un único régimen de tilt**. El
   stream `served_nhl.csv` tiene filas desde el 2026-09-23 (pretemporada, 744 al
   2026-09-29) generadas con 0,9. Las filas anteriores a la activación no pueden
   mezclarse con las posteriores en un mismo entrenamiento del calibrador.
3. **Si antes de la activación apareciera un candidato NHL en staging** entrenado
   sobre la base de 0,9, se descarta. No se promueve un calibrador de un modelo
   que ya no se sirve.

## 12. Interacción con el gate K = 52 y «el modelo manda»

**La medición no interfiere con ninguno:** solo lee el histórico de resultados.
No toca el stream servido, `data/bets/prediction_gate.json`, los calibradores ni
la configuración, y no gasta ningún test de entrada.

**Una activación sí:**

- **Prediction gate (K = 52).** El gate usa `model_probability`, el modelo puro
  (`src/sqp/risk/prediction_gate.py`). El tilt cambia la `d` de **`nhl|h2h` y
  `nhl|spreads`**, pero no la de `nhl|totals` (sección 1.5). Estado verificado el
  2026-09-29 (registro generado a las 15:06Z): **52 cortes y ninguno de la NHL**.
  Los cortes NHL aparecerán cuando se gradúen filas NHL. Llevarían el recuento a
  55, dentro del techo de 63, y eso ocurre con o sin tilt. Activar **no cambia K**
  ni el techo, pero exige un **addendum previo** en
  `2026-09-25-repreregistro-gate-k52.md`: fecha del cambio, sin alterar criterios
  y con la prohibición de usarlo después para recortar o re-segmentar la ventana.
  Si alguna fila NHL graduada con 0,9 entra en la ventana del corte, el test
  evalúa el sistema tal como operó, con los dos regímenes, igual que en MLB y NBA.
- **«El modelo manda»** (≥ 3.402 eventos graduados, ≈ 2026-11-17/24). Evalúa
  `p_cal`, que para la NHL es hoy el modelo puro sin calibrar (sección 11). Las
  filas NHL desde octubre caen en su ventana, y este cambio es mayor que el del
  descanso: mueve **todas** las filas h2h y de puck line NHL, no solo las
  afectadas. Hay dos opciones: activar con addendum previo en
  `2026-08-26-preregistro-el-modelo-manda.md` antes del inicio de la temporada
  regular (~7 de octubre), para que todas las filas NHL de temporada regular de la
  ventana queden en un solo régimen, o esperar a que ese test se ejecute. **Decisión
  del operador** (sección 16.3). Este documento recomienda la misma regla que el
  operador fijó para el descanso NHL el 2026-09-27: con nota previa si llega antes
  del ~7 de octubre, y si llega con la temporada empezada, esperar a una ventana
  limpia.
- **Ranking por probabilidad (regla de generar picks).** Un modelo NHL más plano
  produce menos probabilidades altas. Las filas NHL bajarán en el ranking por
  probabilidad frente a otros deportes. Es la consecuencia buscada (dejar de
  prometer lo que el modelo no sabe), no un defecto, pero hay que anotarla en la
  bitácora de la activación para que no se lea como una caída de cobertura.

## 13. Si se acepta: lo que haría falta para activarlo

No se toca producción en esta medición. Activar es un cambio aparte, con
aprobación y en este orden:

1. **Addenda previos** en `2026-09-25-repreregistro-gate-k52.md` y en
   `2026-08-26-preregistro-el-modelo-manda.md`, antes de tocar la configuración
   (sección 12). Además, las enmiendas del portero y de la batería (sección 14).
2. **Valor:** `tilt_scale` = `t` de la **partición C** (brazo T), redondeado a 3
   decimales como en la NBA (0,795) y con el informe 12 como comprobación, solo
   para `nhl`, en `configs/leagues/ratings.yaml`, con un comentario que remita al
   resultado. **No** se re-estima con todo el histórico, ni se usa `t2`, ni la
   media de las particiones: serían valores no pre-registrados. `elo_k`,
   `elo_home_adv` y `home_scoring_bonus` no cambian.
3. **Test** que fije el valor resuelto por `get_adapter("nhl", "hockey", …)` y que
   compruebe que la familia hockey (0,9) no cambia para otras ligas si alguna la
   hereda.
4. **Commit antes del run de las 12:00** (guarda KI-036: código o configuración
   sin commitear aborta el run diario).
5. **Calibradores:** no hace falta recalibrar (sección 11). Sí se aplica la regla
   de un solo régimen para cualquier entrenamiento futuro.
6. **Vigilancia:** si la primera temporada activa empeora el log loss NHL, se
   revisa con un pre-registro nuevo, no ajustando el tilt a mano.

## 14. Interacción con el portero, el descanso y la batería

- **Portero (anotado en su pre-registro, decisión del 2026-09-29).** Si el tilt
  acepta, el portero se mide **sobre la base nueva** (`tilt_scale = t_C`), esté o
  no activado ya. Necesita una **enmienda de base antes de su `--pre`** con:
  - la aserción de parámetros de su enmienda 2(b) actualizada (`tilt_scale t_C`
    en lugar de 0,9);
  - la paridad del motor con ese valor;
  - M1, M2 y su control sobre esa base;
  - **la potencia recalculada**: el portero actúa como factor sobre la λ del
    rival, y con un tilt más bajo la misma variación de λ se traduce en otra
    variación de `p`, así que su sección 10 cambia. Los criterios no cambian.

  Si el tilt rechaza, la base del portero es la actual y no hace falta enmienda de
  base. En los dos casos, el resultado de este test es **exposición** para el
  portero y se declara en su enmienda.
- **Descanso NHL (rechazado el 2026-09-29).** Se midió sobre 0,9 y no se reabre
  aquí. Un aplanamiento reduce dP/dElo, así que el mismo `c` en Elo por día
  pesaría menos en probabilidad. Si se reabre con otra forma (indicador de
  back-to-back, según su resultado), irá sobre la base vigente en ese momento y
  después del portero.
- **Batería de ajustes.** Por su §16 y la regla del §12 del descanso: si el tilt
  se acepta antes del modo completo de la batería, su base NHL se enmienda
  (`tilt_scale = t_C`) y se repite su `--pre`.

## 15. Compromisos de ejecución

- **Script único:** `scripts/research/measure_tilt_nhl.py`, que importa de
  `measure_rest_nhl.py` las funciones ya validadas (`load_league`,
  `resolved_params`, las vectorizadas y `FOLDS`), o las copia con la misma
  paridad. Tres modos:
  - `--pre`: hash y filas, `git rev-parse HEAD`, aserción de los parámetros
    resueltos de la sección 1.1 (aborta si `tilt_scale` ≠ 0,9, si
    `rest_elo_per_day` ≠ 0 o si hay un `goalie_beta` ≠ 0), recuentos de la
    sección 6 y las tablas de la sección 9. **Nunca lee `y`**: ni marcadores ni
    resultados en la ruta de `--pre`, salvo lo que consume el propio `observe`.
  - `--parity-only`: las aserciones de la sección 5.3 con el tilt de prueba 0,5.
    No estima ningún parámetro ni calcula ninguna pérdida.
  - Completo: exige `--pre-json`, aborta si el hash o el HEAD difieren, y escribe
    el JSON (`--out`). El informe
    `docs/research/2026-09-XX-resultado-tilt-nhl.md` se redacta a partir del JSON.
- El script se commitea **antes** del modo completo, tras una revisión
  independiente, como en el descanso.
- **El modo completo se ejecuta justo después del `--pre`,** sin liquidación en
  medio (`SETTLE_ALL`, el run de las 12:00, tareas `SQP_*`), en una ventana lejos
  de las 12:00 de Uruguay (lección de la Enmienda 1 del descanso).
- **Una sola ejecución.** Sin miradas intermedias al efecto y sin cambiar
  particiones, métrica, punto de partida, líneas ni brazos después de ver el
  resultado.
- **Regla de re-ejecución (E10):** solo se repite si aparece un defecto de
  **código o datos** demostrable sin mirar el resultado: paridad rota, filas mal
  ordenadas o unidas, hash distinto del de `--pre` o falta de convergencia del
  optimizador. El diagnóstico se hace a ciegas (solo longitudes e índices), se
  documenta el defecto y se commitean las dos salidas. **Un resultado adverso no
  es motivo para repetir.** Un defecto en un informe secundario que se ejecute
  después del veredicto no justifica repetir (precedente de `linea_capturada`).
- Las enmiendas se añaden al final **antes** del modo completo y mandan sobre el
  texto.
- **Reabrir tras un rechazo exige otra hipótesis pre-registrada,** no otro tilt:
  - si falla el criterio 3 (T no bate a la constante), el problema está en el
    Elo: `elo_k`, `elo_mov` o **regresión a la media entre temporadas**, que la
    sección 2 señala por la dispersión creciente de `diff`;
  - si falla el 7 (el aplanamiento era nivel), se abre un pre-registro de nivel
    (`elo_home_adv`/`home_scoring_bonus`, teniendo en cuenta que el bonus mueve los
    totales);
  - si fallan solo el 1 o el 2 por generalización, el siguiente paso es la misma
    hipótesis de Elo, porque un tilt fijo no puede seguir una dispersión que
    crece.

  Repetir con otra partición, otro punto de partida o una rejilla sería buscar una
  señal a medida.

## 16. Decisiones del operador que quedan marcadas

1. **Criterio 3 (batir a la constante): signo** (propuesta de este documento) o
   **con el margen de 0,002** en el combinado (más duro). La propuesta es el signo,
   por la razón de la sección 7.
2. **Criterio 7 (t2 < 0,9 en las tres particiones):** incluirlo como criterio
   (propuesta, analogía del `c_conj` que el operador exigió en el descanso NHL) o
   dejarlo como informe secundario.
3. **Momento de una eventual activación** respecto a «el modelo manda» y al inicio
   de la temporada regular (~7 de octubre). La propuesta es la regla del descanso
   NHL del 2026-09-27.
4. **Orden tilt → portero con base actualizada.** Ya ordenado el 2026-09-29, se
   deja constancia: si el tilt acepta, el portero exige una enmienda de base
   (sección 14).

Decisiones técnicas tomadas en este documento, no del operador (se pueden revisar
en la revisión independiente):

- un solo parámetro (`tilt_scale`); `elo_k` y `elo_home_adv` fuera (sección 2);
- Nelder-Mead desde 0,9 y la rejilla solo para informes;
- los brazos K, P y T2 y su papel (sección 5);
- valor de la partición C redondeado a 3 decimales;
- no aplicar la exclusión de fechas del portero (sección 4).

---

Relacionado: [[2026-09-27-preregistro-descanso-nhl]],
[[2026-09-29-resultado-descanso-nhl]], [[2026-09-26-preregistro-portero-nhl]],
[[2026-09-26-preregistro-descanso-basket]], [[2026-09-27-preregistro-bateria-ajustes]],
[[2026-09-25-repreregistro-gate-k52]], [[2026-08-26-preregistro-el-modelo-manda]].

**Decisiones del operador resueltas el 2026-09-30, antes de implementar:**
1. **Criterio 3:** solo el signo, ll(T) < ll(constante) en el combinado y en cada partición. El margen de 0,002 se exige frente a la base (criterio 1).
2. **Criterio 7:** cuenta como criterio de aceptación (t2 < 0,9 con el nivel controlado).
3. **Activación, si se acepta:** antes del ~7 de octubre, con nota previa (addenda en el gate K=52 y en «el modelo manda»). Si llega con la temporada empezada, se espera a una ventana limpia.
