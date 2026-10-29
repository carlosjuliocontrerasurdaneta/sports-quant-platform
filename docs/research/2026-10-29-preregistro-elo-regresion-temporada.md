# Pre-registro — ¿regresar el Elo a la media entre temporadas mejora el moneyline NBA al principio de temporada?

**Fecha:** 2026-10-29. Escrito **antes** de calcular ninguna relación entre la
regresión entre temporadas y los resultados: no se ha ejecutado ningún Elo con
λ ≠ 0, ni calculado ningún log loss, Brier, ECE o acierto con o sin regresión. Lo
único consultado es:

- el código (`src/sqp/models/elo.py`, `src/sqp/sports/base.py`,
  `src/sqp/sports/adapters.py`, `src/sqp/sports/registry.py`,
  `src/sqp/backtesting/engine.py`, `src/sqp/pipeline/daily.py:750-772`) y la
  configuración (`configs/leagues/ratings.yaml`);
- los pre-registros en curso y sus addenda (sección 13);
- el **calendario** del histórico NBA, **sin marcadores**: fechas, huecos entre
  fechas, recuentos por temporada y por partición (sección 10). Los marcadores se
  descartaron al cargar.

Código de referencia: `main` en `7616893`, árbol limpio. Sigue la estructura y las
exigencias de `2026-09-26-preregistro-descanso-basket.md` y
`2026-09-26-preregistro-portero-nhl.md`:

- control de constante;
- particiones temporales con test posterior;
- criterios todos a la vez y ningún umbral sin origen;
- bootstrap por días;
- paridad con el motor;
- potencia razonada antes de medir;
- ejecución única con regla de re-ejecución.

---

## 1. La pregunta y el mecanismo

**Hoy.** `EloRatings` (`src/sqp/models/elo.py`) no tiene regresión entre temporadas.
`SportAdapter.fit_results` (`src/sqp/sports/base.py:40-44`) consume el histórico en
orden y `EloRatings.update` solo mira marcadores. El rating de fin de temporada
pasa **intacto** a la siguiente, aunque entre medias haya ~110 días de verano,
draft, agencia libre, traspasos y lesiones.

**Hipótesis.** Al cruzar el límite de temporada (sección 4), cada rating se encoge
hacia la base:

    r_nuevo = base + (1 − λ) · (r − base),     λ ∈ [0, 1)

Esto mejora el log loss del moneyline NBA en los primeros partidos de la temporada
y no lo empeora en el resto.

- **λ = 0 es el modelo actual, sin cambios.**
- **La base no importa entre franquicias NBA.** Para dos equipos con rating,
  r_nuevo(h) − r_nuevo(a) = (1 − λ)(r_h − r_a), sea cual sea la base. La base solo
  afecta a los partidos contra clubes de exhibición. Se fija en
  `EloRatings.base = 1500`.
- **El efecto no es una función analítica del modelo base**, a diferencia del
  descanso o del portero. La regresión cambia el estado del Elo, y cada
  actualización posterior depende de él: la esperanza y el multiplicador de margen
  de `update` usan `rating_diff`. **Cada valor de λ exige un walk-forward completo
  del motor.** No se reconstruye nada a mano (sección 6).
- **Qué mercados cambia.** En `NormalMarginAdapter` el margen sale del Elo, así que
  cambian el moneyline y el spread, que usan el mismo μ. El total sale de
  `TeamScoringRates` (`adapters.py:66-68`): **el total NBA no cambia
  numéricamente**. Esto importa para la sección 13.

**Por qué se espera algo.** El Elo con `elo_k 20` y multiplicador de margen
necesita del orden de una decena de partidos para corregir un error de nivel
(sección 7.2). Durante ese tiempo, el rating de junio es una estimación
sobreconfiada del equipo de octubre. Como referencia externa, la metodología
pública de FiveThirtyEight para su Elo NBA conservaba 3/4 del rating entre
temporadas (λ = 0,25). **No se ha verificado hoy contra una fuente viva ni se usa
como umbral ni como valor por defecto**: solo explica por qué la rejilla cubre ese
entorno.

**Lo que ya se sabe y va en contra:**

- **El mercado ya incorpora los cambios de plantilla.** Con `market_shrink = 0,5`,
  la probabilidad servida recibiría como mucho la mitad del ajuste.
- Siete mediciones previas no encontraron ventaja sobre el feed público de cuotas
  (encompassing del 2026-09-07). **Aceptar aquí significaría que el modelo estima
  mejor, no que gane dinero.** Ningún resultado de este documento es una
  afirmación de rentabilidad: probabilidad estimada ≠ probabilidad implícita ≠
  edge ≠ hit rate observado ≠ ROI esperado ≠ ROI realizado.

## 2. Liga que decide

**Solo la NBA puede producir un ACEPTA.**

- Es la liga con la hipótesis en juego ahora, con 25 temporadas completas y el
  arnés de paridad ya probado en el descanso.
- WNBA, NCAAB y WNCAAB no se miden aquí. NCAAB y WNCAAB tienen una sola temporada
  en el histórico, y sin límite de temporada no hay nada que medir.
- NHL, NFL y MLB se tratan en la sección 15: pre-registros separados.

## 3. Datos

- `ResultsStore(ROOT).load("nba")` (con la deduplicación por `game_id` de
  AUD-003), sobre una **instantánea** del fichero tomada en `--pre`. En la
  instantánea se registran el SHA-256 y el número de filas.
- Estado al redactar:
  - SHA-256 de `data/historical/results_nba.csv`:
    `0e11c37589102c2fcd1b8d33573f93b165fe27cc58b3d63faa47313ebfac9ff8`;
  - 34.188 filas tras deduplicar, del 2002-01-01 al 2026-10-28;
  - 5.557 fechas distintas.

  El fichero crece cada día con la temporada 2026-27. Por eso el hash de `--pre`
  será otro, y lo que se exige es que las filas con fecha ≤ 2026-06-30 den los
  recuentos de la sección 10.
- **Corte de la medición:** filas con `date ≤ 2026-06-30`, que son **34.065**,
  las mismas que leyeron el descanso y la fase H de la recencia. La temporada
  2026-27 en curso (123 partidos hasta el 2026-10-28) **queda fuera** de toda
  partición.
- `date` es el día **UTC** del inicio, con la semántica ESPN
  (`espn_results.py:224`). Producción usa `str(event.start_time)[:10]`, también en
  UTC.
- **El histórico incluye pretemporada.** Las temporadas empiezan entre el 28 de
  septiembre y el 10 de octubre, mientras que la temporada regular arranca a
  finales de octubre. También hay exhibiciones contra clubes no NBA: 65 «equipos»
  con ≤ 25 apariciones, el que más tiene 21, frente a un mínimo de 179 de las
  franquicias. El fichero no marca el tipo de partido. **No se filtra nada:**
  producción observa las mismas filas, y el Elo se actualiza con ellas.

## 4. Límite de temporada (fijado ahora, sin resultados)

**Regla:** hay un límite de temporada antes del primer partido de la fecha D si el
hueco entre D y la **fecha anterior con algún partido de la liga** es de **≥ 30
días naturales UTC**.

**Por qué 30, con el calendario y sin marcadores.** Distribución de los 5.556
huecos entre fechas consecutivas:

| Hueco (días) | 1 | 2 | 3 | 4–6 | 7–13 | 14–29 | 30–59 | ≥ 60 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Casos | 5.085 | 281 | 125 | 36 | 3 | 0 | 0 | 26 |

- El mayor hueco dentro de una temporada es de **8 días** (2015-05-28 → 2015-06-05,
  la espera de la final).
- El menor hueco entre temporadas es de **62 días** (2020-10-11 → 2020-12-12).
- **Cualquier umbral entre 9 y 62 días detecta exactamente los mismos 26
  límites.** El 30 queda en mitad de un hueco vacío. El resultado no depende de él.

**Casos especiales, declarados antes de medir:**

- **2011-12 (cierre patronal):** hueco de 187 días (2011-06-13 → 2011-12-17). Es un
  límite normal.
- **2020 (suspensión por COVID):** el hueco de **140 días** (2020-03-12 →
  2020-07-30) **es un límite por la regla**. La reanudación en la burbuja
  (`s19`: 172 partidos, 22 equipos) recibe una regresión, y la temporada 2020-21
  (`s20`, desde 2020-12-12) recibe otra. **No se añade ninguna excepción:**
  - la regla tiene que ser la misma en el histórico y en producción;
  - una lista de excepciones elegida a mano es un grado de libertad;
  - una pausa de 4,5 meses con plantillas alteradas es, de hecho, un reinicio
    plausible.

  Se informa aparte (informe secundario 5).
- **Primera temporada del histórico** (`s00`, desde el 2002-01-01): empieza a
  mitad de temporada y no tiene límite previo. La primera regresión es la del
  2002-10-06.
- **Producción:** la misma regla con la misma fecha UTC. Con fallos de ingesta, un
  hueco artificial de ≥ 30 días a mitad de temporada dispararía una regresión
  espuria (riesgo de la sección 12.4).

Con la regla hay **27 temporadas** en el histórico (`s00`–`s26`). `s26` es la
2026-27 en curso, fuera de la medición.

## 5. Ventana temprana (métrica primaria)

**Partido temprano:** un partido del día D en el que **al menos uno** de los dos
equipos ha jugado **menos de N = 20** partidos de la temporada en curso, contando
solo partidos con fecha **estrictamente anterior** a D dentro de la misma temporada
(sección 4). Cuentan todas las filas del histórico, pretemporada y exhibiciones
incluidas, como las observa el Elo. Se define solo con el calendario, sin
resultado, así que no hay leakage.

**Por qué N = 20, derivado de parámetros del proyecto:**

- El error de nivel de un rating decae a una tasa por partido de aproximadamente
  κ ≈ k · m · (ln 10 / 400) · p(1 − p).
- Con:
  - `elo_k = 20`;
  - p ≈ 0,5;
  - un multiplicador de margen m ≈ ln(E|margen| + 1) · 2,2/(0,001 · |Δelo| + 2,2) ≈
    2,3, con E|margen| ≈ 13 · √(2/π) ≈ 10,4 tomado de `margin_sigma 13.0` y
    |Δelo| ≈ 100;

  sale κ ≈ 0,066 por partido, es decir, una **semivida de ≈ 10,5 partidos**.
- **N = 20 ≈ dos semividas:** al final de la ventana queda ≈ 1/4 del desfase
  inicial. Más allá, la regresión apenas cambia nada y diluiría la métrica.
- Además, N = 20 rebasa la pretemporada (unos pocos partidos por equipo) y entra en
  la temporada regular. Con N = 10, buena parte de la ventana serían partidos de
  pretemporada, con titulares en reposo.

Es una aproximación declarada. **N no se cambia después de medir**, y los perfiles
N = 10 y N = 41 son solo secundarios.

«Al menos uno» y no «los dos»: la regresión cambia el rating de los dos equipos, y
basta con que uno esté desfasado para que la probabilidad lo esté. Los recuentos
con «los dos» se informan (sección 10).

## 6. Modelo base, tratamiento, control y paridad

- **Base (λ = 0):** la configuración de producción NBA en `7616893`, tomada con
  `_league_meta("nba").get("league_params")` (`{"rest_points_per_day": 0.795}`) y
  `get_adapter("nba", "basketball", params)`. Parámetros resueltos que el script
  **aserta** (aborta si difieren):
  - `points_per_elo 0.028`;
  - `margin_sigma 13.0`;
  - `elo_k 20`;
  - `elo_home_adv 70`;
  - `elo_mov True`;
  - `rest_points_per_day 0.795`;
  - `scoring_half_life_days 180.0`;
  - `avg_total 224.0`;
  - `total_sigma 22.0`.

  Se evalúa con `walk_forward_backtest(results, "nba", "basketball", params,
  warmup=60)`: el día D se estima con el estado al cierre de D−1. Los empates (1
  fila) salen del moneyline, como en el motor.
- **Tratamiento T(λ):** el mismo motor con `params ∪ {"elo_season_regression": λ}`.
  Necesita la implementación con valor por defecto sin efecto (sección 12.1),
  commiteada **antes** de `--pre`.
- **Control C:** μ_base + a, **solo en los partidos tempranos**. a es una constante
  estimada en la ventana temprana de cada entrenamiento.
  - **Motivo:** la regresión podría ganar log loss en la ventana temprana sin que
    importe el estado del Elo, solo porque al principio de temporada la ventaja de
    campo o el nivel medio del local están mal estimados (pretemporada, partidos
    neutrales de exhibición). C absorbe ese desplazamiento de nivel. Es el control
    de intercepto del clima, el descanso y el portero.
  - μ_base se obtiene de la probabilidad del motor como μ = σ · Φ⁻¹(p), con
    σ = 13. El script aserta que Φ(μ/σ) reproduce p con tolerancia 1e-12.
- **Paridad (aserciones; el script aborta si fallan):**
  1. el motor con `elo_season_regression = 0.0` y la clave **ausente** da
     probabilidades **idénticas** (tolerancia 0) a las del motor en `7616893`.
     Esto prueba que la implementación no hace nada por defecto. La referencia
     de `7616893` se obtiene ejecutando el motor en un `git worktree` de ese
     commit sobre la misma instantánea. El script guarda el SHA-256 del vector
     de probabilidades serializado (repr de cada float) y la paridad compara ese
     hash (Enmienda E5);
  2. con un λ arbitrario (0,3), un día de inicio de temporada estimado **antes**
     de observar ningún partido de la nueva temporada recibe ya los ratings
     regresados. Es la paridad entre el entrenamiento y el servicio de la sección
     12.1;
  3. la reconstrucción de μ del control (arriba).
- **Pérdida:** log loss binario con recorte 1e-12, la expresión de
  `tuning._binary_nll_series`.

## 7. Particiones, rejilla y estimación

### 7.1 Particiones por temporadas completas

Los tests son temporadas enteras según la regla de la sección 4, para que ninguna
ventana temprana quede partida entre el entrenamiento y el test. Por ejemplo, la
`s22` empieza el 2022-09-30, y un corte en fecha el 30 de septiembre la habría
partido.

| Partición | Entrenamiento | Límites en el entrenamiento | Test (temporadas) | Fechas del test |
|---|---|---|---|---|
| A | tras el warmup – fin de `s10` | 10 (`s01`–`s10`) | `s11`–`s15` | 2012-10-05 – 2017-06-13 |
| B | tras el warmup – fin de `s15` | 15 | `s16`–`s21` (incluye la burbuja `s19` y `s20`) | 2017-10-01 – 2022-06-17 |
| C | tras el warmup – fin de `s21` | 21 | `s22`–`s25` | 2022-09-30 – 2026-06-14 |

**Test combinado** = unión de los tres tests, sin solapes, con media por partido.

### 7.2 Rejilla y selección (sin snooping)

- **Rejilla de λ (13 valores):** {0; 0,05; 0,10; …; 0,60}. Incluye el 0 (el modelo
  vigente) y el entorno de la referencia externa. Se usa rejilla y no un
  optimizador porque cada punto es un walk-forward completo y el valor desplegado
  debe ser legible.
- **Regla de selección:** λ_P es el argmin del **log loss medio del moneyline sobre
  todos los partidos de entrenamiento** de la partición P (tras el warmup). Se usan
  todos y no solo los tempranos porque λ es un parámetro global del Elo: el valor
  desplegable es el que mejor estima la temporada entera.
  - Empate exacto: el λ menor.
  - **El test nunca interviene en la selección.**
- **Borde:** si λ_P = 0,60, se informa como «solución en el borde» y el veredicto
  se aplica igual. **No se amplía la rejilla después de mirar.**
- Si λ_P = 0 en alguna partición, T ≡ base en ella, el criterio 5 falla y el
  resultado es **RECHAZA**. Se declara ahora para que no se lea como defecto.
- **Control C:** a_P = argmin del log loss medio en los partidos **tempranos** del
  entrenamiento de P. Se usa Nelder-Mead de `scipy.optimize.minimize`, con punto
  de partida 0, `xatol=1e-7`, `fatol=1e-10` y `maxiter=2000`, sin límites. Si no
  converge, el script aborta y se trata como defecto de código.

## 8. Criterios de aceptación (NBA; todos a la vez)

Con T = T(λ_P) en el test de cada partición:

1. **Δ log loss moneyline (T − base) ≤ −0,002** en los partidos **tempranos** del
   test combinado.
2. **Δ < 0** en los partidos tempranos de **cada** partición (A, B y C).
3. **Δ ≤ 0 en todos los partidos** del test combinado. La regresión no puede
   empeorar el resto de la temporada, que es donde vive la mayor parte de la
   muestra.
4. **ECE(T) ≤ ECE(base)** en todo el test combinado, con
   `sqp.calibration.metrics.expected_calibration_error` por defecto (10 bins).
5. **λ_P > 0 en las tres particiones.** Es la convención de la forma funcional
   (regresar hacia la media, no alejarse); la rejilla no admite valores negativos.
6. **log loss(T) < log loss(C)** en los partidos tempranos del test combinado. El
   estado del Elo regresado debe batir a un simple desplazamiento constante de la
   ventana temprana.

**Origen de los umbrales.**

- 0,002 es `IMPROVEMENT_MARGIN` (`src/sqp/backtesting/tuning.py:38`), el margen del
  abridor, el clima, el descanso y el portero.
- Aplicarlo a la ventana temprana es el análogo de «solo afectados» (E6 del clima,
  confirmado por el operador para el descanso el 2026-09-26). La ventana es donde
  la regresión actúa con fuerza; en el resto el efecto decae hacia 0 por
  construcción. El criterio 3 cubre el resto sin margen.
- N = 20: sección 5.
- Criterios 2–6: signos y comparaciones, sin constantes nuevas.

**Si falla cualquiera: RECHAZA.** La clave no se añade a la configuración, y el
resultado se commitea igual.

**Multiplicidad.** Decide una liga, un parámetro y una métrica primaria. λ se elige
solo en el entrenamiento y la rejilla nunca se contrasta en el test. Los criterios
son conjuntivos, y los secundarios (sección 11) no deciden nada. No hay familia de
contrastes que corregir, así que no se aplica Holm, y queda declarado.

## 9. Incertidumbre

Bootstrap por **bloques de fecha**: días UTC completos del test combinado, 10.000
réplicas, semilla 42. Se informan el IC95 percentil y el error estándar de:

- el Δ del criterio 1 (remuestreando los días con partidos tempranos);
- el Δ del criterio 3;
- T − C del criterio 6.

**No es puerta de aceptación:** exigir que el extremo superior sea < 0 sería un
umbral que el operador no ha fijado (E8 del clima).

## 10. Potencia (calendario, sin resultados)

**Recuentos** del 2026-10-29, regla de la sección 4 y warmup 60, con un script de
consulta que descartó los marcadores al cargar. El `--pre` debe reproducirlos. Si
no coinciden, se documenta la diferencia **antes** de medir.

| Partición | Test n | Tempranos (N = 20, «alguno») | Tempranos sin exhibición | Días de test con tempranos | Entrenamiento n | Tempranos en entrenamiento |
|---|---:|---:|---:|---:|---:|---:|
| A | 7.134 | 1.573 | 1.526 | 269 | 14.673 | 3.342 |
| B | 6.620 | 1.735 | 1.692 | 310 | 21.807 | 4.915 |
| C | 5.578 | 1.263 | 1.230 | 216 | 28.427 | 6.650 |
| **Combinado** | **19.332** | **4.571** | **4.448** | **795** | | |

- **«Los dos» equipos tempranos, N = 20** (recuento previo, con cortes por fecha
  idénticos salvo un partido en B/C): A 1.479, B 1.630, C 1.178.
- **Perfil de la ventana temprana, solo secundario:**
  - N = 10: A 802, B 916, C 646;
  - N = 41: A 3.164, B 3.328, C 2.524.
- **En B**, `s19` (la burbuja) aporta 159 partidos tempranos y `s20`, 312.
- **Temporada en curso** `s26`: 123 partidos hasta el 2026-10-28, todos tempranos.
  Queda fuera de la medición.

Una recuenta independiente (revisión del 2026-10-29) da +1 en los tempranos de A
y C, +1/+2/+1 en «los dos» y +1/+2/+2 en los tempranos de entrenamiento. Antes de
fijar, se declara la definición operativa exacta: clave de equipo (nombre
normalizado o crudo), recuento por fecha anterior a D dentro de la temporada de
D, y si el warmup se aplica por índice de fila en el orden de
`ResultsStore.load`. El `--pre` debe reproducir los recuentos así definidos.
(Enmienda E6.)

**Qué efecto hace falta para el criterio 1** (la misma derivación que en el
descanso):

- Cerca de p = 0,5, corregir un error de δ gana ≈ 2δ² de log loss. Para 0,002 hace
  falta δ_RMS ≈ 3,2 pp en la ventana temprana.
- Con σ = 13 y `points_per_elo 0,028`, dp/dElo ≈ 0,031 · 0,028 ≈ 0,00087. Eso pide
  un desplazamiento RMS de rating **correcto** de ≈ 37 puntos Elo, de media en la
  ventana.
- Con un decaimiento de semivida ≈ 10,5 partidos, la media en 20 partidos es
  ≈ 0,55 veces el desplazamiento inicial. Hace falta, por tanto,
  λ · RMS(Δelo al inicio) ≈ 65–70 puntos de información nueva que el Elo de junio
  no tenga. Con λ = 0,25, eso es un RMS de la diferencia de ratings de ≈ 270 al
  inicio de temporada. No se ha medido la dispersión real de los ratings, porque
  exige ejecutar el Elo con marcadores; el `--pre` la informa. Si resulta bastante
  menor, el margen pide un λ grande y que casi todo el desplazamiento sea correcto.
- **Es plausible que un efecto real no llegue al margen.** Se deja dicho para que un
  rechazo no se lea como «la regresión no existe».
- El `--pre` informa, **sin compararlo con ningún desenlace**, el RMS de
  (p_T(λ) − p_base) en la ventana temprana y en todo el test, para cada λ de la
  rejilla y por partición. Con él se lee, antes de medir, el tamaño del cambio que
  produce cada λ.

**Ruido:** con δ ≈ 3 pp, la desviación típica del Δ por partido es ≈ 0,063. Con
4.571 partidos tempranos, el error estándar sale ≈ 0,0009 sin agrupar; el bootstrap
de la sección 9 da el valor bueno, con 795 días de ~5,7 partidos. El margen queda a
~2 errores estándar: **potencia justa, no holgada.** Un N mayor bajaría el error
estándar, pero diluiría el efecto más deprisa de lo que baja el ruido (el perfil
N = 41 es solo secundario).

El criterio 1 es un umbral sobre la estimación puntual: si el efecto real fuera
exactamente −0,002, la probabilidad de superarlo sería ≈ 50 %. Un 80 % exige
≈ −0,0028 sin agrupar, y más con el agrupamiento por días. El criterio 2 (Δ < 0 en
cada partición, con error estándar ≈ 0,0017 en C) añade exigencia: con un efecto
de −0,002 la probabilidad de que se cumpla en las tres es ≈ 0,68. La potencia
conjunta en el margen es inferior al 40 %. Un RECHAZA con un Δ combinado negativo
se lee como «no demostrado con este margen», no como «la regresión no existe».
(Enmienda E1, revisión de Fable del 2026-10-29.)

## 11. Informes secundarios (no deciden)

1. λ_P de las tres particiones, y perfil del log loss de **entrenamiento** en la
   rejilla (todos los partidos y solo los tempranos), para ver si es monótono a
   ambos lados del mínimo. Se informa también el argmin de entrenamiento sobre los
   partidos tempranos solamente.
2. Δ en el test por partido de la temporada (1–5, 6–10, 11–20, 21–41, 42+, según
   el menor de los dos recuentos), para ver el decaimiento.
3. Perfil N ∈ {10, 41} del criterio 1 con el mismo λ_P, y la variante «los dos
   equipos tempranos» con N = 20.
4. Sin exhibiciones: el criterio 1 sin los partidos con algún equipo de ≤ 25
   apariciones, la regla del descanso (informe 8).
5. Δ en la ventana temprana por temporada (`s11`–`s25`), marcando `s19` (burbuja,
   regresión tras la suspensión) y `s20`. Además, el criterio 1 sin `s19`.
6. **Control D (encogimiento constante):** μ_base · (1 − b) solo en los partidos
   tempranos, con b estimado como a. **Si D bate a T**, la mejora sería un exceso
   de confianza general al principio de temporada y no el estado del Elo. Se
   informa así, y cualquier uso de D exigiría su propio pre-registro. Si D debe
   decidir es una decisión del operador (sección 14).
7. Spreads con líneas fijas (−q25, −q50 y −q75 de μ_base en el test, redondeadas
   al medio punto en el modo completo, como en E2 del descanso). En la familia
   Normal no es una prueba independiente.
8. `bias` del brazo base (probabilidad media − tasa observada del local) en la
   ventana temprana y en el resto, por partición.
9. Línea capturada del mercado: el log loss de T(λ_C) y de la base frente al
   resultado en los partidos NBA con cuotas (`roi_engine.load_closing_odds`),
   informando n. Mide log loss frente al resultado en esa submuestra, **no ventaja
   sobre el mercado**.

## 12. Si se acepta: lo que haría falta para activarlo

No se toca producción en esta medición. Activar es un cambio aparte, con
aprobación y revisión de Fable antes del commit (`MODEL_ROUTING.md`: parámetro de
modelo, clase de escalado).

### 12.1 Implementación previa a la medición (sin efecto en producción)

**Interfaz:**

- `EloRatings` gana `season_regression: float = 0.0` y
  `season_gap_days: int = 30`, más el estado interno de la última fecha observada
  y del último límite ya regresado.
- `SportAdapter.__init__` pasa `params.get("elo_season_regression", 0.0)`.
- Con `season_regression = 0.0` el comportamiento es idéntico byte a byte.
- La clave `elo_season_regression` no se añade a `LEAGUE_OVERRIDES` ni a ningún
  valor por defecto de familia en `registry.py`. Se lee solo con
  `params.get(..., 0.0)` en `SportAdapter.__init__`, para que los parámetros
  resueltos que asertan otros pre-registros (fase M de la recencia, «y ninguna
  otra clave») no cambien. (Enmienda E4.)

**Dónde se aplica la regresión:**

- **Al observar:** antes de actualizar con un resultado cuya fecha diste ≥ 30 días
  de la última observada.
- **Al estimar:** cuando la fecha del evento dista ≥ 30 días de la última
  observada. Es imprescindible. En producción, el día de apertura se estima con un
  histórico cuya última fila es la final de junio, y en el motor el primer día de
  temporada se estima antes de observarlo. Sin esto, el primer día iría sin
  regresión en el histórico y en producción.
- **Idempotente:** una sola regresión por límite.
- Se aplica a `ratings`, `ratings_home` y `ratings_away` (estos dos, por si alguna
  liga usa `elo_home_away_split`).
- `games_played` no se reinicia.
- La fecha se toma siempre como `str(...)[:10]` (UTC), tanto en `r["date"]`, que
  en las filas recientes es un ISO completo, como en `Event.start_time`. El hueco
  se calcula como fecha del evento − última fecha observada. Solo regresa si es
  ≥ 30. Un evento con fecha anterior o igual nunca regresa. La idempotencia se
  liga a la fecha del primer día de la nueva temporada: estimar D y observar
  después D aplica exactamente una regresión. (Enmienda E3.)

**Tests obligatorios:**

- el valor por defecto no tiene efecto (identidad con el motor actual en NBA);
- detección del límite con el umbral de 30 días;
- regresión al estimar antes de observar, e idempotencia;
- invarianza de las diferencias frente a la base;
- un hueco < 30 días (All-Star) no regresa;
- fila con fecha ISO completa; estimar y luego observar el mismo día da una sola
  regresión; estimar un evento pasado no regresa (Enmienda E3).

Se commitea **antes** de `--pre` y del run de las 12:00 (guarda KI-036). Sin la
clave en ninguna configuración, no cambia ningún parámetro resuelto: no aborta el
`--fase M --pre` de la recencia ni afecta a ningún test en curso.

### 12.2 Activación

- **Clave:** `elo_season_regression: λ_C` bajo `nba:` en
  `configs/leagues/ratings.yaml`, con un comentario que remita al resultado. λ_C
  es el de la **partición C**, sin re-estimar con todo el histórico.
- El umbral de 30 días queda como valor por defecto del código, sin clave.
- Un test fija el valor resuelto por `get_adapter` y comprueba que el resto de
  ligas no cambia.

### 12.3 Pasos posteriores, cada uno con su propia medición

- **Volver a medir `margin_sigma` NBA.** Es el residuo del camino real del modelo
  (`registry.py:26-28`), y la regresión lo cambia.
- **`rest_points_per_day 0,795`** se estimó con λ = 0. No se re-estima en la
  activación. Si se quiere, va con un pre-registro aparte.
- **Calibradores:** si al activar existe algún calibrador NBA h2h o spreads, se
  recalibra en staging (`controlled-recalibration`) con filas de un solo régimen.
  La promoción exige aprobación humana.

### 12.4 Riesgos operativos

- **Activar es retroactivo.** `daily.py` reconstruye el Elo con todo el histórico en
  cada run (`fit_results`, `daily.py:753-765`), así que la regresión se aplica a
  todos los límites pasados. **Los ratings de hoy cambian el mismo día de la
  activación**: el residuo decaído de la regresión de octubre de 2026 se arrastra
  toda la temporada. No hay forma de activarla «solo desde la próxima temporada»
  sin código adicional.
- **Hueco espurio:** si la ingesta de resultados NBA se cae ≥ 30 días a mitad de
  temporada, la regla dispararía una regresión falsa. Con cobertura diaria esto no
  debería pasar, pero hay que vigilarlo. La guarda solo puede **registrar** (un
  aviso en el log cuando se detecte un límite fuera del 1 de junio al 31 de
  octubre). No puede suprimir, retrasar ni alterar la regresión. La regla de la
  sección 4 es la única que decide, en el histórico y en producción. (Enmienda
  E2, revisión de Fable del 2026-10-29.)

### 12.5 Vigilancia

Si la primera ventana temprana activa (2027-28) empeora el log loss frente a λ = 0,
se revisa con un pre-registro nuevo, no ajustando λ a mano.

## 13. Interacciones con los tests en curso

**La medición no interfiere con ninguno.** Solo lee una instantánea del histórico y
no toca:

- el stream servido;
- `data/bets/prediction_gate.json`;
- los calibradores;
- la configuración.

La implementación con valor por defecto 0 tampoco interfiere: no cambia ningún
parámetro resuelto ni ninguna probabilidad.

**Una activación sí interferiría.** Cambia la `d` de `nba|h2h` y `nba|spreads` (el
total NBA no cambia, sección 1), con efecto retroactivo e inmediato (12.4).

| Test | Qué evalúa | Activar antes de su fecha | Qué hace falta |
|---|---|---|---|
| **«El modelo manda»** (`2026-08-26-preregistro-el-modelo-manda.md`; disparo por recuento, N = 3.402 eventos con margen de 14 días, ≈ mediados o finales de noviembre de 2026) | `p_cal`, que hereda el adaptador; las filas NBA desde octubre caen en su ventana | **Lo contaminaría**: mezcla dos regímenes NBA en la muestra. La regla vigente es activar solo con un addendum de cambio de régimen previo, que no altera criterios | **No activar antes de que su resultado esté commiteado.** Si por algún motivo no se hubiera ejecutado al activar, addendum previo |
| **Recencia de totales, fase M** (`2026-10-09-preregistro-recencia-totales.md`; D = 2027-01-31, ejecución en los 7 días siguientes; prórroga única a 2027-04-20 si la NBA no llega a 800) | totales NBA con `model_probability`; el `--fase M --pre` aserta los parámetros resueltos NBA «y ninguna otra clave» (§5; Enmienda 1(f)5) | **Numéricamente no la contamina** (el Elo no entra en el total NBA). Pero añadir la clave cambia los parámetros resueltos: el `--fase M --pre` **aborta**, y hace falta una enmienda que fije la base de M antes de mirar | **Activar después de ejecutada la fase M de la NBA** (≥ 2027-02-07, o tras el 2027-04-20 si la NBA va a prórroga). Si se activa antes: enmienda previa en la recencia, que declare que el total NBA no cambia |
| **Peso del mercado por segmento** (`2026-10-13-preregistro-peso-mercado-por-segmento.md`, tag `prereg-peso-mercado-h`; T0 = commit del resultado de MM; ≈ marzo de 2027 a N = 3.300) | `p_cal` por segmento; la NBA se ajusta en `basketball\|mercado` | Antes de T0, el cambio cae en la ventana de ajuste. Después de T0, es un cambio de régimen en la evaluación | Addendum de régimen previo (§10 de aquel documento). Solo afecta al informe S4, no a los criterios. Recomendado: activar **después** de su `--medir` o, si no, con addendum |
| **Brecha tier A** (`2026-10-02-preregistro-brecha-tier-a.md`; medición ≈ julio de 2027 a n ≥ 2.100) | el tier A tal como opera | Cambio de régimen dentro de su ventana, que es larga por diseño | Addendum A2 previo (solo afecta a S4) |
| **Gate K = 52** (`2026-09-25-repreregistro-gate-k52.md`) | `model_probability` pura por corte | Cambia la `d` de `nba\|h2h` y `nba\|spreads`; K y el techo 63 no cambian | Addendum de régimen previo, como el del descanso NBA del 2026-09-26 |

**Fecha y condición de activación propuestas (sin contaminar nada):**

1. **Condición necesaria:** el resultado de «el modelo manda» commiteado y la fase M
   de la recencia ejecutada para la NBA (o la NBA declarada no medida o no
   concluyente en ella); y, si la medición de brecha tier A o el `--medir` de
   peso del mercado no se hubieran ejecutado en la fecha de activación, se
   registra antes su addendum de régimen (A2 / §10). El addendum del gate K = 52
   se registra siempre. (Enmienda E7.)
2. **Momento recomendado:** **el parón de verano de 2027.** Después del último
   partido NBA de la temporada 2026-27 (mediados de junio de 2027) y antes del
   primero de la 2027-28 (~1 de octubre de 2027). Así:
   - la activación retroactiva (12.4) no cambia ninguna fila NBA servida dentro de
     una temporada, porque en verano no hay partidos NBA;
   - el primer uso real es justo el límite de temporada, donde la hipótesis
     importa;
   - los addenda del gate, de tier A y de peso del mercado (este, ya pasado T0)
     registran un cambio de régimen limpio, en una fecha sin filas NBA.
3. **Por qué no ahora:** la ventana temprana de 2026-27 (unos 20 partidos por
   equipo, pretemporada incluida desde el 2026-10-03) se cierra hacia finales de
   noviembre de 2026. Para entonces faltarían la implementación, la medición, la
   revisión de Fable y los addenda, y MM aún estaría en curso o recién ejecutado.
   Activar a mitad de temporada aportaría poco (el efecto que queda es el residuo
   decaído) y contaminaría la ventana de MM y el régimen de la fase M.

## 14. Compromisos de ejecución y decisiones del operador

**Script:** `scripts/research/measure_elo_season_regression.py`, con tres modos:

- `--pre`:
  - imprime los recuentos de la sección 10 por temporada y partición, los huecos y
    los límites;
  - imprime el SHA-256 de la instantánea y los parámetros resueltos;
  - imprime el RMS de (p_T(λ) − p_base) de la sección 10, que es salida del modelo
    sin desenlaces;
  - **no compara ninguna probabilidad con ningún resultado**;
- `--parity-only`: comprueba las paridades 1–3 de la sección 6;
- el modo completo produce el JSON (`--out`).

El informe `docs/research/2026-1X-XX-resultado-elo-regresion-temporada.md` se
redacta a partir del JSON.

**Reglas de ejecución:**

- El script y la implementación con valor por defecto 0 (12.1) se commitean
  **antes** del modo completo, con revisión de Fable del script frente a este
  texto.
- **Una sola ejecución** del modo completo. Sin miradas intermedias al efecto, y
  sin cambiar después de ver el resultado:
  - la regla de límite;
  - N;
  - la rejilla;
  - las particiones;
  - la métrica;
  - los criterios.
- **Regla de re-ejecución (E10):** solo se repite si aparece un defecto de
  **código o datos** demostrable sin mirar el resultado: paridad rota, filas mal
  ordenadas, una instantánea distinta de la del `--pre` o recuentos distintos. Se
  documenta el defecto, diagnosticado a ciegas (solo longitudes e índices), y se
  commitean las dos salidas. Un resultado adverso no es motivo para repetir.
- Las enmiendas se añaden al final, **antes** del modo completo, y mandan sobre el
  texto.
- **Reabrir tras un rechazo exige una forma distinta y pre-registrada.** Por
  ejemplo:
  - un k de Elo mayor solo en los primeros partidos de la temporada;
  - una regresión hacia una media ponderada por la continuidad de la plantilla;
  - un prior de mercado de pretemporada.

  Repetir esta con otro N, otra rejilla u otras particiones sería buscar una señal
  a medida.

**Decisiones del operador que quedan marcadas:**

1. **Criterio 1 sobre la ventana temprana con N = 20 y «al menos un equipo».** La
   alternativa más exigente es medirlo sobre todo el test combinado. En ese caso la
   dilución hace casi seguro el rechazo, porque el efecto decae a 0 tras la
   ventana.
2. **Control D (informe 6):** dejarlo como secundario (propuesta) o convertirlo en
   criterio 7 (T debe batir también a un encogimiento constante de la ventana
   temprana). Hacerlo decisivo reduce la potencia, pero aísla mejor el mecanismo.
3. **Los dos límites de 2020** (suspensión y temporada 2020-21) por la regla pura
   (propuesta) o con una excepción declarada ahora para `s19`.
4. **Autorizar la implementación previa** con valor por defecto 0 (12.1) en
   `src/sqp/models/elo.py` y `src/sqp/sports/base.py`, commiteada antes del run de
   las 12:00.
5. **Momento de una eventual activación:** verano de 2027 (propuesta, sección 13) o
   antes, con todas las enmiendas y addenda de la tabla.

## 15. ¿Generalizar a NHL, NFL y MLB?

**Sí, pero como pre-registros separados.** No se diseñan aquí, y un ACEPTA NBA no
activa nada en otra liga. Cada liga tiene una dinámica de Elo distinta y su propio
paquete de tests en curso:

| Liga | Por qué merece su propio pre-registro | Cuidado específico |
|---|---|---|
| **NHL** (32.900 filas) | `elo_k 10` y un Elo que entra en el reparto con `tilt_scale 0.439`. Con una k baja, el desfase de junio tarda más en corregirse, y la hipótesis podría pesar más | Afecta a h2h, puck line **y** totales a través del reparto. Hay que tener en cuenta la recencia M (NHL decisoria en H5) y el tilt recién activado. Hay un límite especial en 2004-05 (temporada cancelada) |
| **MLB** | `elo_k 6`, el Elo más lento del proyecto | Interactúa con el abridor (`pitcher_bound 0.05`) y con la ventana de MLB en tier A |
| **NFL** (8.046 filas) | 17 partidos: la «ventana temprana» es una fracción grande de la temporada | Potencia mucho menor. NFL está en la recencia M con un mínimo de 250 |

**Orden sugerido por potencia:** NHL, MLB y NFL. WNBA solo tiene tres temporadas, y
NCAAB y WNCAAB una: hoy no se pueden medir.

---

Relacionado: [[2026-09-26-preregistro-descanso-basket]],
[[2026-09-26-resultado-descanso-basket]], [[2026-09-26-preregistro-portero-nhl]],
[[2026-08-26-preregistro-el-modelo-manda]],
[[2026-10-09-preregistro-recencia-totales]],
[[2026-10-13-preregistro-peso-mercado-por-segmento]],
[[2026-10-02-preregistro-brecha-tier-a]], [[2026-09-25-repreregistro-gate-k52]].
