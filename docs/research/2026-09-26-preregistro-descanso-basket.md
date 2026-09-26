# Pre-registro — ¿el descanso diferencial mejora el margen esperado en basket?

**Fecha:** 2026-09-26. Escrito **antes** de calcular ninguna relación entre descanso
y resultados. Lo único consultado es el código, la documentación y la
**distribución de los días de descanso sin marcadores** (recuentos por partición,
sección 9). Orden del operador: «re-medir el factor de descanso/back-to-back en
basket, que hoy está apagado». Código de referencia: `main` en `ac36d91`.

Sigue el precedente de `2026-09-26-preregistro-clima-mlb.md`, con las enmiendas
E1–E13, y su resultado `2026-09-26-resultado-clima-mlb.md`. Las exigencias de
aquella revisión independiente vienen incorporadas desde el principio: control de
intercepto, criterio sobre los partidos afectados, bootstrap por bloques de fecha,
particiones temporales, ejecución única y ningún umbral nuevo sin origen.

---

## 1. La pregunta y el mecanismo que se mide

Hay dos mecanismos de descanso en el código, los dos a 0:

| | (a) `RestModel` | (b) `rest_days_coef` |
|---|---|---|
| Dónde | `src/sqp/models/rest.py`, usado por `NormalMarginAdapter.estimate` (`src/sqp/sports/adapters.py:38-55`) | `src/sqp/features/rest_form.py::rest_form_p_adjustment`, sumado en `src/sqp/pipeline/probabilities.py::adjust_model_probability` |
| Espacio | puntos de **margen** esperado del local | puntos de **probabilidad** |
| Forma | `μ += rest_points_per_day · (r_home − r_away)`, con `r` acotado a `[0, rest_max_days]` = `[0, 4]` | `p += signo · (r_home − r_away) · rest_days_coef`, **sin acotar** |
| Alcance | parámetro de liga (`league_params` / `LEAGUE_OVERRIDES`) | parámetro **global** de `RiskConfig` (`configs/default.yaml:43`): se aplicaría a **todas** las ligas de todos los deportes |
| Mercados | moneyline y spread (mismo μ); no toca totales | h2h y spreads de todos los deportes |
| Replicable en `walk_forward_backtest` | sí, exacto | no: vive en la capa de ajustes, que solo reproduce `roi_engine` con cuotas |

**Se mide (a) y solo (a).** Medir los dos a la vez sería multiplicidad sobre la
misma señal. Además, (b) no es una hipótesis de basket:

- es un coeficiente global. Activarlo movería MLB, fútbol, NHL, NFL y tenis, que
  este pre-registro no evalúa;
- no acota los días. En el primer partido de cada temporada, `team_rest_days`
  devuelve la distancia al último partido de la temporada anterior, así que un
  finalista frente a un equipo eliminado en abril da diferencias de ~60 días.
  Con cualquier coeficiente distinto de 0, eso es un ajuste de varios puntos de
  probabilidad sin base;
- está en la probabilidad servida, no en el modelo puro. Su ajuste interactúa con
  calibración y shrink de maneras que el arnés walk-forward no reproduce.

`rest_days_coef` **sigue en 0** pase lo que pase aquí. Si (a) se activara, (b)
tendría que seguir en 0 para no contar el descanso dos veces. Medir (b) exigiría
su propio pre-registro, con todas las ligas y una forma acotada.

**Se mide la forma funcional de (a) tal como está programada**: lineal en la
diferencia de días, con el tope de 4 días de `rest_max_days` fijo. El tope no se
ajusta. Buscar el tope después de ver los datos sería buscar una señal a medida.
Un solo parámetro libre: `rest_points_per_day` (en adelante, `c`).

## 2. Lo que ya se sabe

- **Rechazo del 2026-06-22** (`.claude/memory/project-decisions.md:180-184`): se
  midió con **ROI en spreads de la WNBA** sobre cuotas capturadas, con 22–25
  eventos (7–10 en held-out). El resultado no era monótono en el parámetro. Era
  una muestra demasiado pequeña para decidir en cualquier sentido. **Nunca se ha
  hecho un walk-forward de log loss sobre el histórico grande de NBA**, que es lo
  que se hace aquí. Esto no contradice aquella decisión: responde a otra pregunta
  (calidad de la probabilidad frente al resultado) con una muestra ~400 veces
  mayor.
- **El mercado ya incorpora el descanso**: las casas publican las líneas sabiendo
  quién juega back-to-back. Con `market_shrink = 0,5`, la probabilidad servida
  recibiría como mucho la mitad de lo que se mida aquí.
- Siete mediciones previas no encontraron ventaja sobre el feed público de cuotas.
  **Aceptar aquí significaría que el modelo estima mejor, no que gane dinero.**
  Ningún resultado de este documento es una afirmación de rentabilidad.

## 3. Ligas

| Liga | Partidos | Rol | Motivo |
|---|---:|---|---|
| **NBA** | 34.065 (2002-01-01 a 2026-06-14) | **decide** | 25 temporadas, tres particiones con test posterior y 9.109 partidos afectados en test (sección 9) |
| WNBA | 1.160 (2023-06-15 a 2026-09-25) | secundaria, no decide | 365 afectados en test: el error estándar (~0,003) es mayor que el margen de 0,002 (sección 9) |
| NCAAB | 6.331 (solo 2025-26) | secundaria, no decide | una sola temporada: no hay test en una temporada posterior. El Elo arranca en frío dentro de la misma temporada que se evaluaría. 728 «equipos», 250 con un solo partido (rivales fuera de la División I) |
| WNCAAB | 6.125 (solo 2025-26) | secundaria, no decide | mismas razones que NCAAB (666 «equipos», 212 con un solo partido) |

**Solo la NBA puede producir un «ACEPTA».** Un resultado positivo en NBA no activa
el factor en WNBA, NCAAB ni WNCAAB: cada una necesitaría su propio pre-registro
con muestra suficiente (**decisión del operador**, sección 13).

## 4. Datos y definición de «días de descanso»

- **Fuente:** `ResultsStore(ROOT).load(liga)`, todas las filas: temporada
  regular, playoffs y lo que el histórico traiga de pretemporada, All-Star o
  exhibiciones. Es lo mismo que ve producción al ajustar el adaptador. El script
  registra el SHA-256 de cada fichero leído y el número de filas.
- **Semántica de la fecha:** `date` son los 10 primeros caracteres del campo
  `date` de ESPN (`src/sqp/providers/espn_results.py:224`), que es la hora de
  inicio en **UTC**. En producción, `estimate` usa `str(event.start_time)[:10]`,
  también en UTC (The Odds API). Por tanto, **«día» = día natural UTC del inicio
  del partido**. No hay hora en el histórico.
- **Días de descanso de un equipo en un partido del día D:**

      r = min(max(D − L, 0), 4)

  donde `L` es la fecha (UTC) del último partido **de ese equipo** en el
  histórico con fecha **estrictamente anterior** a D. Es exactamente
  `RestModel.rest_days`, alimentado en el orden de
  `engine.walk_forward_backtest`: el día D completo se estima con el estado al
  cierre del día D−1. El script **no reimplementa** la regla: instancia
  `RestModel(points_per_day=0.0, max_rest=4, normalize=adapter.normalize)` y lo
  alimenta con el mismo `observe` diferido por días que usa el motor.
- **Consecuencias de la definición**, declaradas antes de medir:
  - `r = 1` es un back-to-back **en calendario UTC**. Un back-to-back real con el
    primer partido antes de las 00:00 UTC y el segundo después aparece como
    `r = 2`. Es ruido de medida, y es el mismo en el histórico y en producción,
    porque las dos usan UTC. En el histórico hay 0 casos de `r = 0`.
  - **Primer partido de un equipo en el histórico:** `L` no existe, así que
    `rest_days = None` y el ajuste es 0 (`margin_adjustment`). Eso afecta a 86
    partidos de la NBA, en su mayoría rivales de exhibición.
  - **Entre temporadas, parón del All-Star y cualquier parón de 4 días o más:**
    los dos equipos quedan en `r = 4`, así que Δr = 0 salvo que uno haya jugado
    en los 3 días anteriores (por ejemplo, pretemporada si está en el
    histórico). El tope de 4 hace que los cortes de temporada **no necesiten
    una regla aparte**. No se añade ninguna.
  - Los partidos en campo neutral (NBA 301) se tratan igual que el resto, como
    en producción.
- **Δr = r_home − r_away ∈ {−3, …, +3}.** «Partido afectado» = los dos `r`
  conocidos y Δr ≠ 0. Se define solo con el calendario, antes del resultado, así
  que no hay leakage.

## 5. Modelo base, tratamiento y control

- **Base:** configuración de producción de la NBA en `ac36d91`, tomada con
  `_league_meta("nba").get("league_params")` y `get_adapter("nba", "basketball",
  params)` (`points_per_elo 0.028`, `margin_sigma 13.0`, `elo_k 20`,
  `elo_home_adv 70`, `elo_mov True`; `rest_points_per_day 0.0`). Walk-forward de
  `walk_forward_backtest` sobre todo el histórico, `warmup = 60`.
- **Probabilidad evaluada:** `P(home win) = 1 − Φ(0; μ, σ)`, la de
  `normal_margin_probs`, con σ = `margin_sigma`. El ajuste de descanso **no
  realimenta el Elo** (`SportAdapter.observe` actualiza con marcadores, no con μ).
  Por eso μ_base se calcula una sola vez y cada brazo es una función analítica de
  μ_base.
- **Brazos:**

  | Brazo | μ | Parámetros |
  |---|---|---|
  | Base | μ_base | — |
  | **Tratamiento T** | μ_base + c · Δr | `c` |
  | **Control C** | μ_base + a | `a` (constante para todos los partidos) |

  **Motivo del control:** Δr tiene media positiva, porque el local llega más
  descansado más a menudo (media de Δr en los afectados: 0,44 en A, 0,19 en B y
  0,12 en C). Un `c > 0` puede ganar log loss solo por corregir una
  **infraestimación general de la ventaja de campo**, sin que el descanso
  importe. Es el confusor que en el clima absorbió el intercepto (resultado del
  clima, partición A). Que la media de Δr cambie entre épocas lo hace aún más
  peligroso: el sesgo de nivel se mezclaría con el calendario de cada época.
- **Paridad (aserción, aborta si falla):**
  1. las probabilidades del brazo base coinciden con `binary_probs` de
     `walk_forward_backtest(results, "nba", "basketball", params)` con tolerancia
     1e-12;
  2. las del brazo T con el `c` estimado en C coinciden con el motor ejecutado
     con `params["rest_points_per_day"] = c` (tolerancia 1e-12). Esto comprueba
     que el Δr reconstruido es el de `RestModel`, y no una copia.
- **Pérdida por partido:** log loss binario con recorte 1e-12, la misma
  expresión que `tuning._binary_nll_series`.

## 6. Particiones y estimación

Cortes en fechas de pretemporada (ninguna coincide con la burbuja de 2020 ni con
el cierre patronal de 2011):

| Partición | Entrenamiento (fechas) | Test (fechas) |
|---|---|---|
| A | tras el warmup – 2012-09-30 | 2012-10-01 – 2017-09-30 |
| B | tras el warmup – 2017-09-30 | 2017-10-01 – 2022-09-30 |
| C | tras el warmup – 2022-09-30 | 2022-10-01 – 2026-06-30 |

- El modelo base es **un único walk-forward** sobre todo el histórico: μ_base de
  cada partido solo usa partidos anteriores. Lo único que se estima por
  partición es `c` (brazo T) y `a` (brazo C), **solo con los partidos de
  entrenamiento**, minimizando el log loss medio.
- **Optimizador:** `scipy.optimize.minimize`, Nelder-Mead, punto de partida 0,
  `xatol=1e-7`, `fatol=1e-10`, `maxiter=2000`, sin límites ni restricción de
  signo (el mismo que E9 del clima). Con un parámetro no hay que elegir rango. Si
  el optimizador no converge, el script aborta y se trata como defecto de código
  (sección 12).
- **Test combinado** = unión de los partidos de test de A, B y C (no se solapan),
  con media por partido.
- WNBA (secundaria): A = entrenamiento 2023–2024, test 2025; B = entrenamiento
  2023–2025, test 2026 hasta 2026-09-25. Mismo optimizador.

## 7. Criterios de aceptación (NBA; todos a la vez)

1. **Δ log loss (T − base) ≤ −0,002** en los **partidos afectados** del test
   combinado.
2. **Δ log loss (T − base) < 0** en los partidos afectados de **cada** partición
   (A, B y C).
3. **ECE(T) ≤ ECE(base)** en **todo** el test combinado, con
   `sqp.calibration.metrics.expected_calibration_error` por defecto (10 bins).
4. **`c > 0` en las tres particiones.** Es la convención de la forma funcional
   (`rest.py`: el equipo descansado rinde más). No es un umbral nuevo. Se exige en
   las tres, no solo en la última, porque la inestabilidad entre ventanas fue
   justo el motivo del rechazo del 2026-06-22.
5. **log loss(T) < log loss(C)** en **todo** el test combinado: el descanso debe
   batir a un simple desplazamiento de la ventaja de campo.

**Origen de los umbrales.**
- 0,002 es `IMPROVEMENT_MARGIN` de `src/sqp/backtesting/tuning.py`, el mismo
  margen de las decisiones del abridor (2026-06-12 y 2026-06-16) y del clima.
- Aplicarlo **solo a los afectados** copia la enmienda E6 del clima, que decidió
  el operador el 2026-09-26 («Solo afectados»). El motivo es el mismo: un margen
  pensado para un parámetro que actúa en todos los partidos, aplicado a partidos
  donde el ajuste vale 0 por construcción, rechaza por diseño. **Aplicarlo aquí
  es una decisión del operador heredada de aquella medición; se deja marcada para
  que la confirme** (sección 13). Si la rechaza, el criterio 1 pasa a medirse
  sobre todo el test combinado, que es más exigente (f ≈ 0,47), y todo lo demás
  queda igual.
- Criterios 2–5: signos y comparaciones, sin constantes nuevas.

Si falla cualquiera: **RECHAZA**. `rest_points_per_day` sigue en 0 y el resultado
se commitea igual.

## 8. Incertidumbre

Bootstrap por **bloques de fecha** sobre el Δ del criterio 1: se remuestrean días
UTC completos del test combinado (con todos sus partidos afectados), 10.000
réplicas, semilla 42. Se informan el IC95 percentil y el error estándar. **No es
puerta de aceptación:** exigir que el extremo superior sea < 0 sería un umbral que
el operador no ha fijado (igual que E8 del clima). También se informa el IC95 del
Δ del criterio 5 (T − C), con el mismo procedimiento.

## 9. Potencia (con la distribución de Δr, sin resultados)

Recuentos con la regla de la sección 4, en el orden del motor y con warmup 60,
calculados el 2026-09-26 con un script de consulta que no leyó marcadores. El
modo `--pre` del script definitivo debe reproducirlos. Si no coinciden, se
documenta la diferencia **antes** de medir.

**Toda la NBA:** 33.979 partidos con los dos descansos conocidos, 15.930 afectados
(f = 0,469). Δr: −3: 282 · −2: 1.496 · −1: 4.403 · 0: 18.049 · +1: 6.465 ·
+2: 2.362 · +3: 922. Días de descanso por equipo y partido: 1 día: 16.838 ·
2: 31.018 · 3: 12.966 · 4: 3.728 · 5 o más: 3.408 (antes del tope).

| Partición | Test n | Afectados | \|Δr\| = 1 / 2 / 3 | Local más descansado | Media Δr | RMS Δr | Entrenamiento n |
|---|---:|---:|---|---:|---:|---:|---:|
| A | 7.134 | 3.422 | 2.330 / 857 / 235 | 2.208 | 0,440 | 1,517 | 14.673 |
| B | 6.621 | 3.171 | 2.307 / 717 / 147 | 1.795 | 0,187 | 1,432 | 21.807 |
| C | 5.577 | 2.516 | 1.857 / 554 / 105 | 1.358 | 0,120 | 1,412 | 28.428 |
| **Combinado** | **19.332** | **9.109** | | | | **1,459** | |

WNBA: test A (2025) 327 partidos y 179 afectados; test B (2026) 350 y 186.

**Qué efecto hace falta para aprobar el criterio 1** (la misma derivación que en el
clima): cerca de p = 0,5, corregir un error de δ en la probabilidad gana ≈ 2δ² de
log loss. Para 0,002 hace falta δ_RMS ≈ 3,2 pp en los afectados. Con σ = 13,
dp/dμ ≈ φ(0)/13 ≈ 0,031 por punto (≈ 0,027 con p = 0,7). Eso pide un
desplazamiento RMS de ≈ 1,0–1,2 puntos. Con RMS Δr = 1,46, equivale a un
**efecto real de c ≳ 0,7–0,8 puntos por día de diferencia** que el Elo no capture
ya. Un efecto menor puede ser real y aun así no llegar al margen. Se deja dicho
para que un rechazo no se lea como «el descanso no existe».

**Ruido:** con δ ≈ 3 pp, la desviación típica del Δ por partido es ≈ 2δ ≈ 0,063.
Con 9.109 afectados, el error estándar sale ≈ 0,0007 (sin agrupar por fecha; el
bootstrap de la sección 8 da el valor bueno). El margen queda a ~3 errores
estándar: **la NBA tiene potencia**. En la WNBA, con 365 afectados en test, sale
≈ 0,003, mayor que el propio margen. Por eso es solo secundaria.

## 10. Informes secundarios (no deciden nada)

1. `bias` del brazo base (probabilidad media − tasa observada del local) por
   partición y en el test combinado.
2. Estimación conjunta μ_base + a + c·Δr en cada entrenamiento: el `c` que queda
   con la ventaja de campo controlada.
3. Perfil del log loss de **entrenamiento** en la rejilla c ∈ {−1,00, −0,75, …,
   +3,00} (paso 0,25) por partición, para ver si es monótono a ambos lados del
   mínimo (el rechazo de junio fue no-monótono).
4. Δ log loss en test por |Δr| (1, 2, 3) y por signo de Δr; residuo medio
   (y − p_base) por valor de Δr en test.
5. Δ log loss en test por temporada (de 2012-13 a 2025-26), marcando 2019-20
   (burbuja) y 2020-21 (calendario comprimido).
6. **Spreads con líneas fijas.** Handicap del local en −q25, −q50 y −q75 de
   μ_base del test combinado, cada uno redondeado al x,5 más próximo. Las líneas
   salen de la salida del modelo, no de los resultados, y se fijan en `--pre`. Se
   evalúa `home_cover` con el `c` de cada partición (vía `spread_lines` del
   motor, con la paridad de la sección 5). En la familia Normal el spread mueve el
   mismo μ, así que no es una prueba independiente.
7. **Línea capturada del mercado:** el mismo `c` (partición C) evaluado en h2h y
   en la línea principal de spread del consenso (`roi_engine.load_closing_odds`,
   `_pick_main_lines`) sobre la muestra NBA con cuotas disponible. Se informa su n.
8. Sin exhibiciones: el criterio 1 repetido excluyendo los partidos con algún
   equipo que tenga **≤ 25 apariciones** en el fichero de la liga. El 25 no es un
   umbral de decisión: cae en el hueco observado de la NBA, entre 21 apariciones
   (el club de exhibición con más partidos) y 179 (la franquicia con menos).
9. **WNBA** con sus propias particiones (sección 6): `c`, Δ en afectados y
   IC95 por días.
10. **Transferencia:** el `c` de la partición C de la NBA, en puntos por día,
    aplicado sin reajustar a WNBA 2025–26, NCAAB y WNCAAB (con su propio
    `margin_sigma`). Δ log loss en afectados. En NCAAB y WNCAAB se evalúa toda la
    temporada tras el warmup, sin estimar nada.

## 11. Si se acepta: lo que haría falta para activarlo

No se toca producción en esta medición. Activar sería un cambio aparte, con
aprobación y con estas condiciones:

- `rest_points_per_day` = `c` de la **partición C** (el último entrenamiento
  validado), solo para `nba`, en `configs/leagues/ratings.yaml`.
  `rest_max_days` sigue en 4. No se re-estima con todo el histórico: ese valor no
  estaría validado fuera de muestra.
- `rest_days_coef` sigue en 0 (sección 1).
- **Paridad entre entrenamiento y servicio:** comprobar en un día real que
  `event.start_time` llega en UTC a `estimate`, y que el run diario ya tiene los
  resultados del día anterior al generar. Si falta el partido de ayer, un
  back-to-back se ve como descanso largo. El orden `SETTLE_ALL` →
  `RUN_DIARIO_ALL` debe garantizarlo, y hay que verificarlo, no suponerlo. Añadir
  un test con un back-to-back conocido.
- Volver a medir `margin_sigma` de la NBA: su comentario en `registry.py` ya
  cuenta el ajuste de descanso en el residual.
- Recalibrar en staging (`controlled-recalibration`) los calibradores
  `nba_h2h` / `nba_spreads`, entrenados sin descanso.
- Addenda previos en los dos tests en curso (sección 13).

## 12. Compromisos de ejecución

- Script único: `scripts/research/measure_rest_basketball.py`, con dos modos:
  - `--pre` solo imprime recuentos, distribución de Δr, líneas fijas y hashes de
    los ficheros, sin leer marcadores;
  - el modo completo produce el JSON (`--out`) y el informe
    `docs/research/2026-09-XX-resultado-descanso-basket.md`.
- Se commitea antes de ejecutar el modo completo.
- **Una sola ejecución.** Sin miradas intermedias al efecto, sin cambiar
  particiones, métrica, tope ni ligas después de ver el resultado.
- **Regla de re-ejecución (igual que E10):** solo se repite si aparece un defecto
  de **código o datos** demostrable sin mirar el resultado: paridad rota, filas
  mal ordenadas o unidas, ficheros distintos de los del hash de `--pre`, o que el
  optimizador no converja. Se documenta el defecto y se commitean las dos
  salidas. Un resultado adverso no es motivo para repetir.
- Las enmiendas, si las hay (por ejemplo, tras una revisión independiente), se
  añaden al final de este documento **antes** del modo completo, y mandan sobre el
  texto de arriba.
- Reabrir tras un rechazo exige una forma funcional **distinta** (por ejemplo,
  indicadores de back-to-back en lugar de lineal, o viajes) y pre-registrada.
  Repetir esta con otro tope u otras particiones sería buscar una señal a medida.

## 13. Interacciones con los tests pre-registrados en curso

**La medición no interfiere con ninguno:** solo lee el histórico de resultados. No
toca el stream servido, `data/bets/prediction_gate.json`, los calibradores ni la
configuración, y no gasta ningún test de entrada del gate.

**Una activación sí interferiría**, y por eso se fija ahora qué haría falta:

- **Prediction gate (K = 52, `2026-09-25-repreregistro-gate-k52.md`).** El gate
  usa `model_probability`, el modelo **puro** (`prediction_gate.py:12`). El
  mecanismo (a) vive en el adaptador, así que activarlo **cambia la `d` de los
  cortes `nba|h2h` y `nba|spreads`**. Hoy el registro (generado el 2026-09-25) no
  tiene cortes de NBA, y los de WNBA están en `muestra_insuficiente` (n = 69, sin
  test de entrada gastado). La NBA empieza hacia finales de octubre. Activar
  exigiría un addendum **previo** al gate, como el del cambio del abridor MLB del
  2026-09-26: fecha del cambio de régimen, sin alterar criterios y con la
  prohibición de usarlo luego para recortar la ventana. Activar no cambia el
  número de cortes, así que K no se ve afectado.
- **«El modelo manda» (`2026-08-26-preregistro-el-modelo-manda.md`).** Se ejecuta
  una sola vez al llegar a 3.402 eventos graduados (≈ mediados o finales de
  noviembre de 2026). Evalúa `p_cal`, que hereda el adaptador. Las filas de la NBA
  desde finales de octubre caerán en su ventana. Activar antes de ejecutarlo
  exigiría el mismo tipo de addendum: el test evalúa el sistema tal como operó.
- **Cuándo activar, si se acepta, es una decisión del operador.** Las opciones
  son activar con addenda en los dos tests, o esperar a que «el modelo manda» se
  ejecute. Este documento no la toma.

## 14. Decisiones del operador que quedan marcadas

1. **Criterio 1 sobre los afectados** (heredado de E6 del clima, 2026-09-26).
   Hay que confirmarlo para esta medición. La alternativa es medirlo sobre todo
   el test combinado.
2. **Extender a WNBA / NCAAB / WNCAAB:** aquí no pueden aceptarse. Cada una
   necesitaría su propio pre-registro cuando haya muestra.
3. **Momento de una eventual activación** respecto al gate y a «el modelo manda»
   (sección 13).

**Resueltas por el operador el 2026-09-26, antes de escribir el script:**
1. Criterio 1 **solo sobre los afectados** («Solo afectados»).
2. Extender a otras ligas exige su propio pre-registro (sin cambio).
3. Si se acepta, se activa **con nota previa**: addendum de cambio de régimen en el
   gate K=52 y en «el modelo manda» antes de sus tests, como con el abridor MLB.

---

Relacionado: [[2026-09-26-preregistro-clima-mlb]], [[2026-09-26-resultado-clima-mlb]],
[[2026-08-26-preregistro-el-modelo-manda]], [[2026-09-25-repreregistro-gate-k52]].
