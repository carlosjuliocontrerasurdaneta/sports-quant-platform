# Pre-registro — `park_bound` de MLB revalidado con datos deportivos (log loss y Brier, sin cuotas)

**Fecha:** 2026-11-10. Escrito **antes** de comparar ningún valor de `park_bound`
con ningún resultado por log loss o Brier. Para este documento solo se han leído
código, configuración, pre-registros y resultados anteriores y las notas de
memoria del proyecto. **No se ha abierto ningún CSV ni Parquet y no se ha
calculado ninguna cifra sobre los datos**: todas las tablas de recuentos y
potencia las produce el modo `--pre` del script (sección 9), nunca este texto.
Código de referencia: `main` en `858a13f`. Autorización del operador: 2026-11-10.

**Por qué ahora.** `configs/leagues/ratings.yaml:25-30` fija `park_bound: 0.10`
para MLB con esta justificación: «ENABLED 2026-06-22: on captured odds it flips
MLB totals from -17.1% to +2.8% ROI (held-out -15.9% -> +3.8%/+7.0%) … 0.10
chosen over 0.20». Commit `3301e4a` (2026-06-22); decisión registrada en
`.claude/memory/project-decisions.md:174-178`. Es decir, un **parámetro que entra
en λ** se eligió por ROI realizado sobre cuotas capturadas. Eso viola el principio
del operador de que las probabilidades salen solo de datos deportivos y el mercado
solo se compara después: `docs/prompts-audit/05-informe-de-riesgos.md` (R2,
CRÍTICA), `07-independencia-del-mercado.md` (M15, «ENTRADA PROHIBIDA en la
optimización») y `09-principios-fundamentales.md` (P8, estado PARCIAL). La
auditoría dejó dicho que la revalidación «por log loss/Brier frente a resultados
en walk-forward» es la salida, y que un cambio del valor es un cambio de régimen
que debe esperar a la medición de «el modelo manda» (sección 13). El candado
`tests/test_market_independence.py::test_roi_justified_values_are_only_the_declared_legacy_ones`
mantiene `park_bound` en `LEGACY_ROI_JUSTIFIED` «pendiente de revalidación por
log loss»: este documento es esa revalidación.

Precedentes que se siguen: `2026-09-29-preregistro-tilt-nhl.md` (un parámetro de
adaptador que no realimenta; un solo walk-forward; brazos analíticos; control de
nivel), `2026-09-27-preregistro-bateria-ajustes.md` (particiones MLB, corte de
datos, deduplicación por `gamePk`, línea por partido ⌊μ⌋ + 0,5, `--data-root`
sobre instantánea), `2026-10-09-preregistro-recencia-totales.md` (rejilla legible
en lugar de optimizador; regla de selección sin *snooping*; pérdida del total sin
línea como informe) y `2026-08-26-resultado-correlacion-marcadores.md` (regla de
«ambos mercados a la vez» y rechazo del argmin en el borde sin apoyo).

---

## 1. La pregunta y el mecanismo

**Pregunta.** Con datos deportivos solamente, ¿el factor de parque acotado por
`park_bound` mejora la probabilidad del modelo MLB en los **totales** frente al
desenlace, **y** qué valor de la cota elige un procedimiento que solo mira el
pasado? Las tres respuestas posibles son: el parque no se sostiene (la cota debe
ser 0, el valor de la familia); se sostiene y el valor coincide con el 0,10
heredado; se sostiene con otro valor.

### 1.1 Dónde vive (verificado en `858a13f`)

- `src/sqp/models/park.py:22-58`: `ParkFactors(prior_games=20.0, bound=0.0)`.
  `update` acumula, **solo con marcadores**, las carreras totales de los partidos
  en casa y fuera de cada equipo. `factor(home)` devuelve
  `clamp(1 + w·(raw − 1), 1 − bound, 1 + bound)` con
  `raw = media_total_en_casa / media_total_fuera` del equipo local y
  `w = min(n_casa, n_fuera) / (min(n_casa, n_fuera) + prior_games)`; 1,0 si falta
  alguna de las dos muestras o si la media fuera es ≤ 0.
- `src/sqp/sports/adapters.py:190-195`: el `BaseballAdapter` lo construye con
  `park_prior_games` (sin override: 20) y `park_bound` (sin override: 0 = no-op).
  `adapters.py:199`: `observe` lo actualiza con `home_score + away_score`.
  `adapters.py:213-224`: `_rates` devuelve
  `max(0,1, λ_h · f_abridor_rival · pf)` y `max(0,1, λ_a · f_abridor_local · pf)`,
  con `pf = park.factor(event.home)`: **el mismo factor multiplica las dos λ**.
- `src/sqp/sports/registry.py:40-42`: familia `baseball` = `avg_total 8.7,
  tilt_scale 0.8, max_score 25, dispersion_k 3.8, home_scoring_bonus 0.10,
  elo_k 6, elo_home_adv 25`. Overrides MLB en `ratings.yaml:16-30`:
  `pitcher_bound 0.05, pitcher_prior_starts 5.0, tilt_scale 0.4, park_bound 0.10`.
  Sin `pitcher_signal` (rige `"ra"`), sin `rest_elo_per_day`, sin
  `scoring_half_life_days` (0), sin `park_prior_games`.
- `src/sqp/models/distributions.py:204-262`: `poisson_match_probs` con
  `dispersion_k` (binomial negativa por equipo), rejilla 0..25 por equipo,
  `tie_adds_goal=False` en béisbol.

### 1.2 Propiedad clave: `park_bound` no realimenta nada

El Elo, `TeamScoringRates`, `StarterRatings` y el propio `ParkFactors` se
actualizan en `observe` con **marcadores**, nunca con probabilidades ni con el
factor aplicado. La cota solo entra en `factor()` como recorte final de un valor
`f_i = 1 + w·(raw − 1)` que **no depende de la cota**. Por tanto:

- la trayectoria del modelo (ratings, tasas, abridores, `f_i`) es **la misma para
  cualquier `park_bound`**: basta **un único walk-forward** de la base;
- para cada partido y cada cota b, `pf_i(b) = max(1 − b, min(1 + b, f_i))`, la
  expresión literal de `park.py:58`, y las λ de cada brazo son
  `λ_h^0 · pf_i(b)` y `λ_a^0 · pf_i(b)`, donde `λ^0` es la λ **antes** del parque
  (Elo, tasas, tilt, bono y abridor incluidos). Es la misma estructura que el tilt
  NHL (§1.3 de aquel pre-registro).

El suelo `max(0,1, ·)` no puede actuar con λ ≈ 4 y factores en [0,5; 1,5]; la
paridad con el motor (sección 5.3) lo comprueba igualmente.

### 1.3 Qué mercados mueve

| Mercado | Efecto | Motivo |
|---|---|---|
| **Totales** | **se mueve** (mercado de decisión) | escala μ = λ_h + λ_a por `pf` |
| Run line (±1,5) | se mueve poco | con la misma proporción de λ, más carreras separan más; segundo orden |
| Moneyline | casi no se mueve | la proporción λ_h/λ_a no cambia; con binomial negativa y empates repartidos 50/50 el efecto es de segundo orden |

Los dos últimos no deciden, pero llevan restricción de signo (criterio 7): la
regla de «ambos a la vez» del precedente de correlación de marcadores dice que
un parámetro que arregla un mercado y estropea otro no se despliega.

### 1.4 Qué significa cada cota (sin datos)

- **b = 0:** el parque no existe (valor de la familia; el «no-op» de `park.py`).
- **b pequeña:** solo los parques extremos quedan recortados; con la regresión
  `prior_games = 20`, un equipo con una temporada completa (81/81) tiene w ≈ 0,80,
  así que un `raw` de 1,15 (parque bateador) da f ≈ 1,12 y un b = 0,10 lo recorta
  a 1,10.
- **b no vinculante:** si ningún `f_i` del histórico sale de [1 − b, 1 + b], la
  cota no hace nada y el parque entra entero con la única regularización del
  prior. **Todas las cotas que no recorten ningún partido son el mismo modelo.**
  El `--pre` informa la fracción de partidos recortados por cota y por partición
  (sección 9), y la regla de desempate de la sección 2 resuelve las equivalencias
  antes de medir.

## 2. Parámetro, rejilla y selección (sin *snooping*)

- **Un solo parámetro:** `park_bound`. `park_prior_games` (20) **no se ajusta**:
  cota y prior son dos regularizaciones del mismo factor y ajustarlas juntas abre
  una cresta no identificable (el argumento del tilt frente a `elo_k`). Reabrir el
  prior exige otro pre-registro.
- **Rejilla (7 valores):** **{0; 0,05; 0,10; 0,15; 0,20; 0,30; 0,50}**. 0 es el
  valor de la familia; 0,10 el vigente; 0,20 la alternativa que la decisión de
  junio descartó «por menos sobre-corrección»; 0,05 y 0,15 rodean el vigente;
  0,30 y 0,50 cubren el tramo hasta la cota **no vinculante**. El `--pre` debe
  mostrar **0 partidos recortados con 0,50** en todo el histórico; si no, se añade
  por enmienda, antes del modo completo, un valor superior que lo sea. Así el
  borde superior de la rejilla significa «sin tope», y un argmin ahí es legible,
  no un síntoma (precedente de correlación de marcadores: un argmin en un borde
  que *pide ir más allá* se rechaza; aquí el borde superior no pide nada).
- **Rejilla y no optimizador** (precedente recencia §4): el objetivo es
  escalonado (la cota solo cambia la pérdida cuando cruza un `f_i`) y el valor
  desplegado debe ser legible; con 7 puntos no hay un grado de libertad relevante.
- **Regla de selección:** en cada partición, **b_P = argmin de la pérdida
  primaria media de entrenamiento** (sección 4) sobre la rejilla, con los partidos
  evaluados desde el warmup hasta el día anterior al test. **Empate exacto** (dos
  cotas que no recortan ningún partido distinto): la más cercana a 0,10, el valor
  vigente; si persiste, la **menor** (el modelo es el mismo y se declara la cota
  más pequeña que lo produce). **El test nunca interviene en la selección.**
- **Valor que se desplegaría:** **b_C**, el elegido en el entrenamiento de la
  última partición, **sin reestimar** con todo el histórico (precedente del
  descanso NBA, el tilt NHL y la recencia). Sin redondeo: los valores de la
  rejilla ya son el valor escrito.

## 3. Lo que ya se sabe y exposición previa de la muestra (declarada)

1. **Decisión de junio de 2026** (`3301e4a`; `project-decisions.md:175-178`;
   `architecture-log.md:138-142`): 0,10 y 0,20 se compararon por **ROI realizado
   sobre cuotas capturadas de 2026** (hasta el 22/06, con un *held-out* desde el
   2026-05-09). Ninguna comparación por log loss consta. **La partición C (test
   2026) está expuesta a este parámetro** en otra métrica y a través de dos de los
   siete valores de la rejilla; la exposición favorece a 0,10 y 0,20 en C. Las
   particiones A (test 2024) y B (test 2025) **no se han usado nunca para elegir
   `park_bound`**: en junio las cuotas capturadas solo cubrían 2026.
2. **Clima MLB** (`2026-09-26-resultado-clima-mlb.md`) y **batería**
   (`2026-10-09-resultado-bateria-ajustes.md`): midieron sobre tests 2025 y 2026
   con `park_bound 0,10` **en la base**, sin comparar cotas. Dejan escrito el log
   loss de la base en totales con líneas fijas y con ⌊μ⌋ + 0,5. La batería
   concluyó que en MLB «los totales dependen del abridor y del parque, que la base
   ya incorpora» (línea 278): es una lectura, no una medición del parque.
3. **Abridor** (`ratings.yaml:17-21`, activado el 2026-09-26): el walk-forward
   sobre 9.629 juegos se hizo con el parque en 0,10. Expone el log loss de la base,
   no el del parque.
4. **Recencia de totales:** MLB **excluida** (su §3, línea 137, cita justo la
   interacción con abridor y parque). No hay exposición.
5. Este documento no ha calculado nada sobre los datos.

**Por qué el pre-registro conserva valor.** La pregunta no es si el parque
existe en el béisbol (el conocimiento previo dice que sí para dos o tres estadios),
sino si **un factor estimado como lo hace `park.py`, acotado por un valor elegido
solo con el pasado, generaliza en tres tests sucesivos con el margen del proyecto
y sin estropear la run line**. Dos de los tres tests nunca han visto el parámetro.

**Lo que no se afirma.** Las cifras de ROI de junio **no son evidencia** en este
documento y no se reproducen. Aceptar significaría que el modelo estima mejor el
total, no que gane dinero. Probabilidad estimada ≠ probabilidad implícita ≠ edge
≠ hit rate observado ≠ ROI esperado ≠ ROI realizado. **El script no lee cuotas
en ningún modo** (sección 14): el único mercado que aparece es una línea teórica
derivada del propio modelo (sección 4), que el informe `07` clasifica como UMBRAL
LEGÍTIMO.

## 4. Métricas

**Línea por partido, común a todos los brazos y fijada sin desenlace:**
**L_i = ⌊μ_i^0⌋ + 0,5**, con μ_i^0 = λ_h^0 + λ_a^0 el total esperado del brazo
**sin parque** (b = 0). Es la línea de la batería (§7.3) y de la recencia (H4),
tomada del modelo nulo para que **no dependa del candidato**; con medio punto no
hay empujes. Limitación declarada (batería, punto 8): en su propia línea la base
queda en P(Over) ≈ 0,5, donde un cambio de escala tiene el máximo efecto; por eso
se añaden la línea fija canónica y la pérdida sin línea como informes.

- **Primaria (criterios 1-2, selección):** log loss **binario** de P(Over L_i),
  recorte 1e-12, la expresión de `tuning._binary_nll_series` (`tuning.py:66-72`).
  Es la métrica en la que está definido el margen del proyecto.
- **Brier** de P(Over L_i) (criterio 4), `sqp.calibration.metrics.brier_score`.
- **ECE** de P(Over L_i) (criterio 5), `expected_calibration_error` por defecto
  (10 bins).
- **Moneyline y run line** (criterio 7): log loss binario de P(local) sin
  empates, y de P(local cubre −1,5) y P(local cubre +1,5), desenlace del marcador
  como en `walk_forward_backtest` (`engine.py:115-125`).
- **Informes (no deciden):** pérdida del total **sin línea**
  −log P(T = T_i) con la rejilla conjunta del adaptador (binomial negativa,
  `max_score` 25, P(T = k) = P(Over k − 0,5) − P(Over k + 0,5); precedente
  recencia §7.3); y el procedimiento canónico `tune_market_param` sobre la línea
  fija 8,5 (sección 10).

Todas las probabilidades salen de `dist.poisson_match_probs` con los parámetros
resueltos del adaptador (`three_way=False`, `max_goals=25`, `dispersion_k=3.8`,
`score_rho=0`, `dc_rho=0`, `tie_adds_goal=False`), nunca de una reimplementación.

## 5. Brazos, control y paridad

### 5.1 Brazos

| Brazo | λ | Parámetros (estimados solo en entrenamiento) |
|---|---|---|
| **Nulo N** | `λ^0` (b = 0) | — |
| **Tratamiento T(b)** | `λ^0 · pf_i(b)` para cada b de la rejilla | b_P por selección (sección 2) |
| **Control de nivel C** | `λ^0 · (1 + a)` | a (Nelder-Mead desde 0, `NM_OPTS` de los precedentes: `xatol 1e-7, fatol 1e-10, maxiter 2000`, sin límites) |
| **T2 (diagnóstico)** | `λ^0 · pf_i(b) · (1 + a_b)` | para cada b, a_b por Nelder-Mead; (b_T2, a) = argmin conjunto |

- **C** es el intercepto de escala: un factor constante para todos los partidos.
  Existe porque un brazo de parque podría ganar log loss solo si corrigiera un
  sesgo global de μ (clima E5, batería brazo C, recencia control C). El parque
  **no debería** tener ese canal (los cocientes casa/fuera promedian ≈ 1 entre
  equipos), y por eso C es una cota de cordura barata: si T no bate a C, lo que se
  estaba midiendo era nivel, no parque.
- **T2** dice si b_P sobrevive con el nivel controlado. Es informe (sección 10),
  no criterio; su elevación a criterio es decisión del operador (sección 16.3),
  como en el tilt.
- Si el optimizador de a no converge, el script aborta (defecto de código, E9).

### 5.2 Paridad (aserciones; aborta si falla; tolerancia 1e-12)

1. Las probabilidades del brazo **T(0,10)** coinciden, partido a partido, con
   `binary_probs` y con `markets["spreads@-1.5"|"spreads@1.5"|"totals@8.5"]` de
   `walk_forward_backtest("mlb", "baseball", params_resueltos)` ejecutado con la
   configuración canónica (`_league_meta("mlb")["league_params"]`).
2. Las de **T(0)** y **T(0,20)** coinciden con el motor ejecutado con
   `params["park_bound"] = 0.0` y `= 0.20`. Comprueba que la cota entra por
   `league_params` igual que en producción.
3. `--parity-only` repite 1 y 2 y comprueba además que `λ^0`, `f_i` y las λ de
   abridor del walk-forward son **idénticos** bajo las tres cotas (sección 1.2).

Como en la batería (Enmienda 1(b)), **todo** parámetro se lee de
`_league_meta("mlb")` y se asierta por igualdad exacta con la sección 1.1: si
`park_bound` ≠ 0,10, `pitcher_bound` ≠ 0,05, `tilt_scale` ≠ 0,4,
`pitcher_prior_starts` ≠ 5,0, o aparece `pitcher_signal`, `rest_elo_per_day`,
`scoring_half_life_days` ≠ 0 o `park_prior_games`, el script aborta y hace falta
una enmienda de base.

## 6. Datos

- **Fuente:** `ResultsStore(data_root).load("mlb")` con la deduplicación por
  `game_id` **por defecto** (`results_store.py:32-47`: una fila por `gamePk`, la
  última por `(date, ingested_at)`; es la regla de la Enmienda 3(c) de la batería,
  hoy en el store). Después, `StartersStore(data_root).attach("mlb", results)`
  como `scripts/tune_ratings.py:63-64` (el abridor almacenado; AUD-012: es el que
  lanzó, no el probable; afecta igual a todos los brazos).
- **Corte: `date ≤ 2026-09-26`**, el de la batería y la recencia (Enmienda 1(f)).
  Deja fuera la postemporada 2026 y hace comparables los recuentos: tras el
  filtro, la batería registró **9.704 filas**, test 2025 **2.430 partidos / 184
  días**, test 2026 **2.415 / 183 días**, 9.644 evaluados tras el warmup. El
  `--pre` informa la diferencia de filas con esas referencias (ingesta tardía con
  `date ≤ corte`) y el recuento de filas descartadas por la deduplicación (15 en
  la instantánea de la batería). Una diferencia dentro de un test se documenta en
  una enmienda antes del modo completo; no se corrige ni se excluye nada.
- **Instantánea:** `--data-root` obligatorio, apuntando a una copia fuera del
  repositorio (`C:\dev\3\snapshots\park-bound-mlb-<AAAAMMDD>`), con SHA-256 de
  `results_mlb.csv` y del fichero de abridores en el JSON; aborta si resuelve a
  `sqp.config.ROOT` (batería, Enmienda 2(h)).
- **Orden y warmup:** los del motor (`engine.py:42-150`): por bloques de día UTC,
  estado al cierre del día anterior, `warmup = 60`.
- **Universo:** todos los partidos del store tras el warmup, como ve producción
  (temporada regular y postemporada 2023-2025 si están). Moneyline sin empates.
- **Limitación declarada: el parque se proxea por el equipo local**
  (`park.py:1-9`). En 2025 los Athletics (Sacramento) y los Rays (Steinbrenner
  Field) cambiaron de estadio: su `f_i` mezcla dos recintos en B y C, en **todos**
  los brazos de parque por igual (juega contra aceptar). El `--pre` lista las
  claves de equipo local por temporada y marca las que aparecen solo en algunas;
  el informe 7 repite el Δ sin los partidos en casa de esos dos equipos.

## 7. Particiones y estimación

| Partición | Entrenamiento (selección de b_P y de a) | Test |
|---|---|---|
| A | tras el warmup – 2023-12-31 | 2024-01-01 – 2024-12-31 |
| B | tras el warmup – 2024-12-31 | 2025-01-01 – 2025-12-31 |
| C | tras el warmup – 2025-12-31 | 2026-01-01 – 2026-09-26 |
| **Combinado** | | unión de los tres tests, media por partido |

- *Rolling origin* con entrenamiento expansivo: cada b_P se elige solo con el
  pasado de su test. B y C son exactamente los tests MLB de la batería y la
  recencia; **A es nueva**: se añade porque es un test **no expuesto** (sección
  3) y porque con cuatro temporadas dos tests dejan solo 2026, expuesto, como
  último. Su entrenamiento es una temporada (w ≈ 0,80 al final de 2023 para todo
  equipo); es la partición más débil y se declara.
- Los años naturales son cortes limpios: MLB no juega entre noviembre y febrero.
- Pérdida de selección y de C: la primaria (sección 4), media sobre los partidos
  de entrenamiento.

## 8. Criterios de aceptación (todos a la vez)

Con b_P de cada partición aplicado a **su** test, y T = T(b_P):

1. **Δ log loss primario (T − N) ≤ −0,002** en el test combinado, sobre **todos**
   los partidos (el parque actúa en todos los que tienen factor conocido; los de
   factor 1,0 por falta de muestra se cuentan e informan, no se excluyen).
2. **Δ < 0 en cada partición** (A, B y C).
3. **b_P > 0 en las tres particiones.** Si una partición elige 0, T ≡ N allí,
   Δ = 0 y el 2 falla igualmente; se enuncia para que un «RECHAZA» por este motivo
   se lea como «el pasado no elegía el parque», no como ruido.
4. **Brier(T) ≤ Brier(N)** en P(Over L_i), test combinado.
5. **ECE(T) ≤ ECE(N)** en P(Over L_i), test combinado.
6. **ll(T) < ll(C)** en el test combinado (signo; decisión del operador del
   2026-09-30 en el tilt: el margen se exige frente a la base, no frente al
   control).
7. **Ni el moneyline ni la run line empeoran:** Δ log loss de P(local) ≤ 0 **y**
   Δ medio de `spreads@-1.5` y `spreads@+1.5` ≤ 0 en el test combinado (regla de
   «ambos a la vez»; criterio 6 de la batería; H5 de la recencia).

**Origen de los umbrales.** 0,002 es `IMPROVEMENT_MARGIN`
(`src/sqp/backtesting/tuning.py:38`, «required log-loss gain vs the family
default»), aplicado exactamente a eso: el valor de la familia (0) frente a uno
ajustado, en log loss binario por partido, como `tune_market_param`. El n mínimo
es `MIN_EVAL_MARKET = 200` partidos evaluados (`tuning.py`, gate de
`tune_market_param`): cada test lo supera con holgura y el `--pre` lo registra.
Los criterios 2-7 son signos y comparaciones sin constantes nuevas. **No hay
corrección de multiplicidad entre celdas porque hay una sola celda** (una liga,
un parámetro, un mercado de decisión); la multiplicidad de la rejilla se controla
con la selección solo en entrenamiento y el signo en cada partición. Se informa
el p unilateral p = Φ(Δ̂/EE) con el EE del bootstrap, sin poder de decisión.

**Veredictos (sección 12 dice qué se hace con cada uno):**

- **ACEPTA:** pasan los siete. El valor validado es **b_C**.
- **RECHAZA:** falla cualquiera. El parque **no queda validado por datos
  deportivos**; el único valor con origen legítimo es el de la familia, 0.

Un RECHAZA con Δ entre −0,002 y 0 y signo coherente en las tres particiones se
describe como «efecto en la dirección esperada por debajo del margen» y sigue
siendo RECHAZA: la regla del proyecto ya resolvió ese caso con el abridor v2
(−0,0007, no activado) y, por orden expresa, con el abridor 0,05 (sección 12.3).

## 9. Potencia y lo que calcula `--pre` (sin desenlaces)

**Aritmética del modelo, sin datos** (se declara para que el resultado no
sorprenda). Con μ ≈ 8,7-9 y `dispersion_k 3.8`, la desviación típica del total
del modelo es ≈ 4,4 carreras, y en su mediana dP(Over)/dμ ≈ 0,09 por carrera. Un
factor f = 1,05 mueve μ ≈ 0,45 carreras y P(Over L_i) ≈ 0,04; f = 1,10, ≈ 0,08.
Si la probabilidad verdadera fuera la del brazo con parque, la ganancia esperada
por partido sería ≈ KL(p_T ‖ p_N) ≈ 2·Δp² nats: 0,0008 con Δp = 0,02, 0,0034 con
0,04, 0,013 con 0,08. Con la regresión del prior, la mayoría de los parques
quedan en |f − 1| ≤ 0,03 y solo dos o tres estadios superan 0,05. **La ganancia
media alcanzable con un parque perfectamente estimado es del orden de
0,001-0,003: el margen es una valla real y «efecto real por debajo del margen»
es un desenlace plausible.** Error estándar ingenuo del Δ (aproximación de la
batería, 0,063/√n): ≈ 0,0007 en un combinado de ≈ 7.300 partidos (el margen son
≈ 2,7 EE) y ≈ 0,0013 por partición (el criterio 2 es de signo, pero con un EE de
ese tamaño una partición puede fallar por ruido con un efecto real de 0,002). El
agrupamiento por días (≈ 13 partidos/día) inflará esos EE.

**El `--pre` produce, sin leer ningún desenlace** (los marcadores solo entran por
`observe`, como en el tilt §9):

1. hashes, filas, `git rev-parse HEAD`, `git status --porcelain` (debe estar
   vacío), parámetros resueltos y su aserción (sección 5.2);
2. recuentos por partición (entrenamiento, test, días de test, evaluados) y
   diferencia con las referencias de la sección 6;
3. distribución de `f_i` (percentiles 1, 5, 25, 50, 75, 95, 99, mínimo y máximo)
   por partición y en el combinado; fracción de partidos con factor 1,0 por falta
   de muestra;
4. **fracción de partidos recortados por cada b de la rejilla**, por partición;
   la aserción «0 con b = 0,50» (sección 2); y las clases de equivalencia que
   resultan (qué cotas producen exactamente el mismo modelo en cada
   entrenamiento);
5. distribución de Δp_i(b) = P(Over L_i | b) − P(Over L_i | 0) por b; media de
   P(Over L_i) por brazo;
6. la tabla de escenarios E[KL(p_b ‖ p_0)] por b en el test combinado, el máximo
   posible si la verdad fuera T(b);
7. claves de equipo local por temporada (sección 6).

Las cifras de este punto son las que el informe de resultado compara con la
aritmética anterior.

## 10. Informes secundarios (no deciden)

1. Δ por partición y combinado de **todos** los brazos de la rejilla (no solo
   b_P), para ver la forma del perfil en el test.
2. **Perfil de entrenamiento** de la pérdida primaria sobre la rejilla, por
   partición: si el mínimo es interior, en 0 o en el borde no vinculante.
3. **Procedimiento canónico:** `tune_market_param(results, "mlb", "baseball",
   param="park_bound", grid=rejilla, market="totals", line=8.5,
   default_value=0.0, league_params=base sin park_bound, n_splits=4)`, con
   `DEFAULT_HOLDOUT_SPLITS 4` y `HOLDOUT_MIN_TRAIN_FRAC 0,4`
   (`tuning.py:25-26, 196, 201-269`), y sus `oos_selections` por bloque. Conecta el
   resultado con la herramienta de `scripts/tune_ratings.py` (que hoy solo
   gestiona `elo_home_adv` y `dc_rho`, `TUNABLE_KEYS`) y con la línea fija 8,5
   de la batería. **No decide**: sus bloques no son las particiones y su línea
   mide también el nivel de la era.
4. **Pérdida del total sin línea** (sección 4) de N, T, C y T2, por partición y
   combinado, con los T_i > 50 contados y excluidos de todos los brazos.
5. **Sesgo** (media de P(Over L_i) − tasa de Over observada) de N y T por
   partición; a de C y (b_T2, a) de T2; fracción de la ganancia de T2 que T
   captura.
6. **Tabla de fiabilidad** (10 bins) de N y T en el combinado; Δ por quintil de
   |f_i − 1| (la ganancia debería concentrarse en los parques extremos).
7. Δ **sin** los partidos en casa de los dos equipos con cambio de estadio
   (sección 6).
8. Δ por temporada y por mes; Δ en temporada regular frente a postemporada.
9. Run line por línea (−1,5 y +1,5 por separado) y moneyline: Δ y ECE.
10. **Sensibilidad al prior**, solo descriptiva: el perfil del informe 2 con
    `park_prior_games` 10 y 40, para saber si la pregunta del prior merece otro
    pre-registro. No se usa para elegir nada.

## 11. Incertidumbre

Bootstrap por **bloques de fecha** (días UTC completos del test combinado),
10.000 réplicas, semilla 42 (E8 del clima y todos los precedentes). IC95 percentil
y EE de: Δ del criterio 1; T − C; Δ Brier; Δ moneyline; Δ medio de run line;
Δ(b_C) − Δ(0,10) cuando b_C ≠ 0,10 (sección 12.2). **No es puerta.** Se informa la
fracción de réplicas con Δ ≤ −0,002 y con T − C < 0.

## 12. Qué se hace con cada resultado

Nada de esto ocurre en la medición. Cualquier cambio de configuración es un
commit aparte, con aprobación, con la cronología de la sección 13.

### 12.1 ACEPTA con b_C = 0,10

El valor heredado queda **revalidado por datos deportivos**. Producción no cambia
(no hay cambio de régimen). En un mismo commit: el comentario de
`ratings.yaml:25-29` se reescribe citando el resultado y **sin** las cifras de
ROI; `park_bound` sale de `LEGACY_ROI_JUSTIFIED` en
`tests/test_market_independence.py` (el test falla con entradas obsoletas); se
añade un test que fije el valor resuelto por `get_adapter("mlb", "baseball", …)`.
Nota informativa, no addendum, en «el modelo manda» y en el gate.

### 12.2 ACEPTA con b_C ≠ 0,10

El valor pasa a **b_C**: es el único elegido por un procedimiento declarado con
datos deportivos; conservar 0,10 sería conservar el número elegido por ROI. Se
informa Δ(b_C) − Δ(0,10) con IC (sección 11) para que se lea cuánto separa a los
dos. **Decisión del operador** (sección 16.1): la alternativa es mantener 0,10
salvo que b_C lo bata por el margen; la propuesta es b_C. Es un **cambio de
régimen** de `mlb|totals` (y marginal en h2h y run line): sección 13.

### 12.3 RECHAZA

`park_bound` pasa a **0.0**, escrito explícitamente (no se borra la clave:
`tests/test_validate_oos_frozen_params.py:41-46` exige que exista y que
`validate_oos.py` la congele), con comentario que cite este resultado; sale de
`LEGACY_ROI_JUSTIFIED`. Es un **cambio de régimen** (sección 13). **Decisión del
operador** (sección 16.2): el informe `07` (M15) deja abierta la opción de
conservar 0,10 «por orden», como se hizo con `pitcher_bound 0,05`
(`ratings.yaml:17-21`); si la toma, el comentario debe decir «por orden del
operador, medición del <fecha> RECHAZA» y la entrada de `LEGACY_ROI_JUSTIFIED`
sale igualmente, porque la justificación ya no es ROI. El estado de
`paused_markets` para `mlb/totals` (des-pausado junto al parque el 2026-06-22) no
lo decide este documento: lo gobiernan el monitor de degradación y el operador.

En los tres casos el resultado se commitea, `docs/research/2026-11-XX-resultado-park-bound-mlb.md`
se redacta a partir del JSON y se anota en la memoria del proyecto.

## 13. Cuándo puede aplicarse un cambio de valor (12.2 y 12.3)

**La medición no interfiere con nada:** solo lee la instantánea. No toca el
stream servido, `data/bets/prediction_gate.json`, los calibradores ni la
configuración, y no gasta ningún test de entrada.

**Un cambio de `park_bound` sí es un cambio de régimen del modelo MLB** (el
informe `05` R2 y `07` M15 lo dicen expresamente). Reglas, en orden:

1. **No antes de la medición de «el modelo manda»**
   (`2026-08-26-preregistro-el-modelo-manda.md`: N = 3.402 eventos graduados,
   T1 = E − 14 días fijado por addendum, `--medir` una sola vez; último
   `--contar` oficial del 2026-10-13: 2.394 eventos, estimación «mediados o
   finales de noviembre de 2026»). Hoy no hay filas MLB nuevas: la temporada
   terminó, así que esperar no mezcla regímenes en su ventana.
2. **En la pausa invernal, antes del Opening Day de 2027** (finales de marzo),
   para que todas las filas MLB servidas de 2027 salgan de un solo régimen (la
   regla que el operador fijó para el descanso y el tilt NHL: con la temporada
   empezada, esperar a una ventana limpia).
3. **Addenda previos «antes de ejecutar»**, sin alterar criterios y con la
   prohibición de usarlos para recortar o re-segmentar ventanas (precedente: los
   tres addenda del 2026-09-26 en MM), en los pre-registros vivos sobre el stream
   servido que incluirán filas MLB de 2027: el gate K = 69
   (`2026-11-02-repreregistro-gate-k69.md` y su enmienda del 2026-11-03; cambia
   la `d` de `mlb|totals` y de `mlb|team_totals`, no K), el peso del mercado por
   segmento (`2026-10-13-preregistro-peso-mercado-por-segmento.md`, T0 = commit
   del resultado de MM, N = 3.300 ≈ marzo de 2027) y la brecha tier A
   (`2026-10-02-preregistro-brecha-tier-a.md`). Si MM aún no se hubiera medido,
   la regla 1 manda y no se cambia nada.
4. **Calibrador `mlb_totals`** (`data/models/calibration_methods.json`:
   isotónico, vivo): se entrenó con filas servidas bajo 0,10. La regla de un solo
   régimen (tilt NHL §11) impide reentrenarlo mezclando regímenes; con la
   temporada 2027 recién empezada no habrá filas suficientes del nuevo. Qué hacer
   con él (mantenerlo provisionalmente o retirarlo a no-op con el aviso de
   `_warn_if_uncalibrated_accuracy`) es **decisión del operador** (sección 16.4),
   a tomar en el marco de `controlled-recalibration`, no aquí.
5. **Commit antes del run de las 12:00** (guarda KI-036) y test del valor
   resuelto. Revisar `tests/test_pipeline_demo.py`, que menciona `park_bound`.
6. **Vigilancia:** si la primera temporada con el valor nuevo empeora el log loss
   de totales MLB, se revisa con otro pre-registro, no a mano.

**Recencia de totales y batería.** Ninguna de las dos toca la base MLB: MLB está
excluida de la recencia (su fase M del 2027-01-31 es NBA/NFL/NHL) y las seis
celdas MLB de la batería rechazaron y están cerradas (ejecución única). Un cambio
de `park_bound` no exige enmendarlas. A la inversa, **si antes del `--pre` de este
script cambiara algún parámetro resuelto de MLB** (por ejemplo por los
pre-registros del Elo con regresión entre temporadas o del modo de inicio de
temporada, si llegaran a tocar la familia béisbol), la aserción de la sección 5.2
aborta y hace falta una enmienda de base antes de medir.

## 14. Contrato del script (lo implementa Sonnet; lo revisa Fable antes del commit)

**Fichero:** `scripts/research/measure_park_bound_mlb.py`. **Tests:**
`tests/research/test_measure_park_bound_mlb.py`. **Sin dependencias nuevas**
(numpy, pandas, scipy ya se usan en los precedentes). **No importa
`sqp.backtesting.roi_engine` ni lee `data/odds` en ningún modo** (candado P8(a)
del informe `09`); un test lo fija.

**Modos y CLI** (patrón de la batería y la recencia):

    python scripts/research/measure_park_bound_mlb.py --pre --data-root <inst> --out pre.json
    python scripts/research/measure_park_bound_mlb.py --parity-only --data-root <inst> [--parity-stride N]
    python scripts/research/measure_park_bound_mlb.py --data-root <inst> --pre-json pre.json --out res.json [--n-boot 10000] [--seed 42]

- `--data-root` obligatorio; aborta si resuelve a `sqp.config.ROOT`.
- `--pre` exige `git status --porcelain` vacío en todo el repositorio; el modo
  completo aborta si el HEAD, los hashes de datos, los SHA-256 de `configs/` o los
  parámetros resueltos difieren del `pre.json`; registra el SHA-256 del `pre.json`.
- Constantes del módulo: `GRID = (0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50)`,
  `CUTOFF = "2026-09-26"`, `WARMUP = 60`, `FOLDS` de la sección 7, `MARGIN =
  tuning.IMPROVEMENT_MARGIN` (importado, no copiado), `MIN_EVAL =
  tuning.MIN_EVAL_MARKET`, `NM_OPTS` de los precedentes, `SEED = 42`,
  `N_BOOT = 10_000`, `TOL = 1e-12`.

**Carga** (`load_mlb(data_root)`): `ResultsStore(data_root).load("mlb")` con la
deduplicación por defecto; informar también `len(load("mlb", dedupe_game_id=False))`;
filtrar `date ≤ CUTOFF`; `StartersStore(data_root).attach("mlb", results)`;
`_league_meta("mlb")` para familia y `league_params`; aserción de parámetros
resueltos (sección 5.2) en dos niveles (`league_params` y `get_adapter(...).params`).

**Walk-forward único** (`walk_components(results, league_params)`), copia del
bucle de `walk_forward_backtest` (`engine.py:78-125`: orden por `date`, bloque
diario, `observe` al cambiar de día, `Event` con `home_starter`/`away_starter`,
`i >= warmup`), que por partido evaluado guarda: `date`, `home`, `away`,
`lam_h0`, `lam_a0` (= `PoissonAdapter._rates(adapter, ev)` multiplicadas por
`adapter.starters.factor(ev.away_pitcher)` y `(ev.home_pitcher)` respectivamente,
las operaciones de `adapters.py:214-216` **sin** `pf`), `f` (factor **sin
recortar**: una instancia sombra `ParkFactors(prior_games=20.0, bound=1e9,
normalize=adapter.normalize)` actualizada en el mismo `observe`; con esa cota
`max(1 − b, min(1 + b, f))` devuelve `f` exacto), `pf_prod` =
`adapter.park.factor(ev.home)` (para la paridad), `known` =
`adapter.park.is_known(ev.home)`, y los desenlaces `home_score`, `away_score`
**en una estructura aparte** que `--pre` no recibe (`read_outcomes`, patrón de la
recencia). Para `b` de la rejilla: `pf(b) = max(1 − b, min(1 + b, f))`,
`lam_h(b) = max(0.1, lam_h0 · pf(b))`, `lam_a(b) = max(0.1, lam_a0 · pf(b))`; para
C y T2 se multiplica además por `(1 + a)` antes del suelo.

**Probabilidades:** `dist.poisson_match_probs(lam_h, lam_a, spread, total,
three_way=False, max_goals=25, dispersion_k=3.8, score_rho=0.0, dc_rho=0.0,
tie_adds_goal=False)`, con los valores tomados de `adapter.params` y
`adapter.TIE_ADDS_GOAL`, no literales. `L_i = floor(lam_h0 + lam_a0) + 0.5`.
P(T = k) por diferencias de P(Over) como en la recencia (`hockey_pt`).

**Selección y brazos:** por partición, máscaras de entrenamiento y test sobre
`date`; `select_b(train_loss, b_vigente=0.10)` con el desempate de la sección 2
(tolerancia de empate: igualdad exacta de la pérdida media; se informa también la
diferencia mínima entre cotas); `fit_level(lam_h0, lam_a0, L, y, train)` para C y
`fit_level` por cada b para T2.

**Criterios, bootstrap y salida:** los siete criterios de la sección 8 como
booleanos con sus cifras; `bootstrap_dias` por días del combinado con `SEED` y
`N_BOOT`; p unilateral; los informes 1-10 envueltos en `_safe_informe` (un fallo
en un informe no invalida los criterios; la batería, Enmienda 2(d)); **ningún
criterio pasa por `_safe_informe`**. JSON con: HEAD, hashes, parámetros resueltos,
recuentos de la sección 6, resultados del `--pre` (sección 9) en el modo `--pre`,
y en el completo b_P por partición, tabla de pérdidas por brazo y partición,
criterios, veredicto, bootstrap, informes, versiones de Python/numpy/pandas/scipy
y tiempos. Determinista: dos ejecuciones sobre la misma instantánea deben dar
criterios y bootstrap idénticos bit a bit.

**Tests mínimos** (liga sintética pequeña, sin datos reales): (1) paridad de
`T(0)`, `T(0,10)` y `T(0,20)` con `walk_forward_backtest` a `TOL` en h2h,
`spreads@±1.5` y `totals@8.5`; (2) `f` sombra es idéntico bajo las tres cotas y
`pf(0.10)` coincide con `pf_prod`; (3) dos cotas que no recortan ningún partido
dan pérdidas exactamente iguales y el desempate elige la más cercana a 0,10 y
después la menor; (4) `--pre` no accede a desenlaces (los `home_score` del frame
que recibe `--pre` se sustituyen por un centinela y el modo no falla ni los usa
salvo en `observe`); (5) el script no importa `roi_engine` (inspección de
`sys.modules` tras importar el script); (6) humo del JSON del modo completo con
`--n-boot 50`.

## 15. Compromisos de ejecución

- El script se commitea **antes** del modo completo, tras revisión de Fable
  (APTO o APTO CON CAMBIOS aplicados), como en el tilt y la batería.
- Instantánea creada el día de la ejecución; `--pre`, revisión de sus recuentos
  frente a la sección 6 y, si hace falta, enmienda; después `--parity-only`; el
  **modo completo justo después**, con el mismo HEAD, sin commits ni liquidación
  en medio (`SETTLE_ALL`, run de las 12:00, tareas `SQP_*`), en una ventana lejos
  de las 12:00 de Uruguay.
- **Una sola ejecución.** Sin miradas intermedias y sin cambiar rejilla,
  particiones, línea, métrica ni brazos después de ver el resultado.
- **Regla de re-ejecución (E10):** solo por un defecto de **código o datos**
  demostrable sin mirar el resultado (paridad rota, filas mal ordenadas o unidas,
  hash distinto del `--pre`, optimizador sin converger). Diagnóstico a ciegas,
  defecto documentado, las dos salidas commiteadas. Un resultado adverso no es
  motivo para repetir. Un defecto en un informe secundario no justifica repetir.
- Las enmiendas se añaden al final, **antes** del modo completo, y mandan sobre
  el texto.
- **Reabrir tras un rechazo exige otra hipótesis pre-registrada**, no otra
  rejilla: si falla el 6 (no bate al nivel), el problema es el nivel de μ, no el
  parque; si falla el 7, el parque no es «solo total» y hay que medir la forma
  (p. ej. factor sobre el total con la proporción fija); si el perfil del
  informe 2 sugiere que el prior importa (informe 10), se pre-registra
  `park_prior_games`; si el parque por equipo falla donde hubo cambio de estadio
  (informe 7), la hipótesis siguiente es un parque por `venue_id`
  (`configs/venues.yaml`), que es otra implementación.

## 16. Decisiones del operador que quedan marcadas

1. **Valor si ACEPTA con b_C ≠ 0,10:** b_C (propuesta) o conservar 0,10 salvo que
   b_C lo bata por el margen.
2. **Valor si RECHAZA:** 0,0 (propuesta: es el único valor con origen en datos
   deportivos) o conservar 0,10 «por orden», como `pitcher_bound`, con el
   comentario que lo diga.
3. **T2 (parque + nivel)** como criterio adicional (b_T2 = b_P en las tres
   particiones) o como informe (propuesta: informe).
4. **Calibrador `mlb_totals`** ante un cambio de régimen: mantener provisional o
   retirar a no-op; a resolver en `controlled-recalibration`.
5. **Momento de un cambio:** después de MM y antes del Opening Day 2027
   (propuesta); la alternativa es esperar al resultado del peso por segmento
   (≈ marzo de 2027) y activar con la temporada 2027 empezada, en una ventana
   limpia posterior.

Decisiones técnicas tomadas aquí, revisables en la revisión independiente: un
solo parámetro (`park_prior_games` fijo); rejilla de 7 valores con borde superior
no vinculante; línea L_i del modelo nulo; tres particiones por año natural con A
nueva; corte 2026-09-26; control de nivel multiplicativo; ninguna corrección de
multiplicidad entre celdas; cuotas fuera de todos los modos.

---

Relacionado: [[2026-09-29-preregistro-tilt-nhl]], [[2026-09-27-preregistro-bateria-ajustes]],
[[2026-10-09-resultado-bateria-ajustes]], [[2026-10-09-preregistro-recencia-totales]],
[[2026-08-26-resultado-correlacion-marcadores]], [[2026-08-26-preregistro-el-modelo-manda]],
[[2026-11-02-repreregistro-gate-k69]], [[2026-10-13-preregistro-peso-mercado-por-segmento]],
[[2026-09-26-preregistro-clima-mlb]], [[2026-09-26-preregistro-clima-parque-mlb]].

---

## Addendum 1: 2026-11-11, antes de ejecutar y sin datos vistos

Redacción de Fable en la revisión del script `scripts/research/measure_park_bound_mlb.py`. Ninguno de estos puntos cambia un criterio; precisan lo que el texto anterior dejaba ambiguo.

1. **Δ(b_C) − Δ(0,10)** (§11 y §12.2). Se calcula sobre todas las filas del test combinado con dos brazos fijos, T(b_C) y T(0,10), no con el b_P de cada partición; equivale a ll(T(b_C)) − ll(T(0,10)). Si b_C = 0,10, no se informa.
2. **Universo del informe 8.** El store MLB solo contiene partidos con `gameType=R` (`src/sqp/providers/mlb_statsapi.py:56-58`). El universo es la temporada regular, así que el apartado «regular frente a postemporada» del informe 8 no aplica. Se mantienen Δ por temporada y Δ por mes.
3. **Claves de equipo local del informe 7.** Son las que el `--pre` liste para los Athletics («Oakland Athletics» o «Athletics») y para «Tampa Bay Rays». Corrección de §6: si las claves de los Athletics cambian según la temporada, su factor no mezcla recintos, sino que se reinicia en 2025 con muestra corta. El informe 7 excluye igualmente sus partidos en casa.
4. **«Δ medio de run line»** = (Δ_{−1,5} + Δ_{+1,5}) / 2.
5. **Duración y paridad.**
   - El modo completo tarda varias horas; T2 es lo que domina.
   - El JSON se escribe con criterios y bootstrap antes de los informes, y se reescribe al final.
   - La paridad del modo completo corre siempre con stride 1; `--parity-stride` solo se aplica a `--parity-only`.
