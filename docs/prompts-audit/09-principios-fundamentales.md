# 09 — Principios fundamentales a preservar (fase 2)

Fecha: 2026-11-10. Escalón Fable. Reglas metodológicas extraídas de los 21 prompts y del proyecto, cada una con origen (cita verificada), estado en la plataforma, cómo se comprueba y qué test o candado automático la protegería. **La implementación de los candados queda para después**; aquí solo se especifican. Etiquetas: [COMPROBADO] [INFERENCIA] [HIPÓTESIS] [RECOMENDACIÓN].

Convención de estado: CUMPLE (plataforma conforme con candado), CUMPLE SIN CANDADO (conforme, sin test que lo fije), PARCIAL, INCUMPLE (decisión pendiente del operador y de los pre-registros).

## P1 — Independencia del mercado en la estimación

- **Regla.** Ninguna cuota, probabilidad implícita, línea (salvo como umbral), consenso, movimiento o proyección de mercado entra en la generación de probabilidades, en las features ni en la selección de variables.
- **Origen.** Prompts: NHL:6, 36, 592; ATP:37; NFL:24, 446; EPL:27; MLB:14; NBA:19; brief del operador (2026-11-10). Plataforma: `src/sqp/sports/adapters.py` (ningún adaptador recibe precios), `src/sqp/models/*`, `src/sqp/features/*` (grep sin columnas de mercado).
- **Estado.** CUMPLE SIN CANDADO en la estimación; INCUMPLE en la decisión (ver P2 y `07-independencia-del-mercado.md` M1, M3).
- **Cómo se comprueba.** Grep de `implied|novig|price_decimal|odds|consensus` en `src/sqp/sports/`, `src/sqp/models/`, `src/sqp/features/`; lectura de la firma `estimate(event, spread_line, total_line)` (`adapters.py:60, 146`).
- **Candado propuesto.** [RECOMENDACIÓN] (a) Test de contrato estático: ningún módulo bajo `sqp.sports`, `sqp.models`, `sqp.features` importa `sqp.markets`/`sqp.odds` ni nombra columnas de mercado. (b) Test de propiedad: para un evento fijo, `adapter.estimate()` devuelve la misma `EstimatedProbabilities` con cualquier conjunto de cuotas (las cuotas no son argumento, pero el test fija que no lo sean nunca). Alojamiento natural: `tests/test_claude_system_contract.py` o un `tests/test_market_independence.py` nuevo.

## P2 — Congelar antes de mirar el mercado

- **Regla.** La probabilidad del modelo se registra (con `as_of`, versión, parámetros y hash) antes de consultar cuotas y no se reescribe para acercarla a ellas.
- **Origen.** MLB:177-178; ATP:317 («No ajustar `p_A` o `p_B` para acercarse a cuotas»); NBA:248-249; NFL:319; NHL:432-449; EPL:272-274. Plataforma: `model_probability` y `adjusted_probability` persistidas antes de la mezcla (`src/sqp/pipeline/daily.py:1031-1032, 1126`), `market_shrink` por fila (`daily.py:1040-1042`).
- **Estado.** PARCIAL: la columna pura existe y es reconstruible (MM se apoya en ello, `preregistro-el-modelo-manda.md:60-66`), pero la probabilidad que decide y se publica es la mezcla (`probabilities.py:303-305`). La vigencia de la mezcla la decide el operador tras MM.
- **Cómo se comprueba.** Para cada fila servida: `estimated_probability == (1−s)·adjusted_probability + s·implied_probability_novig` con `s` = columna `market_shrink`, y `model_probability` independiente de `fair`.
- **Candado propuesto.** [RECOMENDACIÓN] (a) Test de identidad algebraica sobre filas sintéticas y sobre una muestra del stream (tolerancia 1,5e-4 por redondeo a 4 decimales, como fija peso-mercado §4.4). (b) Test de que `_decision_probability` con `fair=None` o `shrink=0` devuelve `p_decision == cal(p_model)` (ya documentado en `probabilities.py:298`). (c) Si MM pasa y `s` cambia, el test lee `s` de la fila, nunca de la config.

## P3 — Una sola distribución por partido

- **Regla.** ML, spread, total, team totals y medias se derivan de la misma distribución conjunta de marcadores; no de dos modelos incompatibles.
- **Origen.** NFL:36 («Mismo partido, una única distribución conjunta»), NFL:442; NBA:195; ATP individual §6 (mismo espacio de trayectorias para ML, sets y juegos); fútbol: matriz única en los 11. Plataforma: `poisson_match_probs` (una rejilla, `distributions.py:204-266`) cumple; `NormalMarginAdapter` no (`distributions.py:32-70`, `adapters.py:71-72`).
- **Estado.** CUMPLE en fútbol, MLB y NHL; INCUMPLE en baloncesto y fútbol americano (dos Normales independientes).
- **Cómo se comprueba.** Para la familia Normal, `home_win` debe coincidir con `home_cover` en `spread_line = 0` (misma Normal): test rápido; para el total no hay vínculo. Para la malla: `P(home_win) + P(draw) + P(away_win) = 1` y `over + under = 1` tras eliminar push (ya hay tests de líneas asiáticas AUD-001).
- **Candado propuesto.** [RECOMENDACIÓN] (a) Test de coherencia ML/spread@0 en `NormalMarginAdapter`. (b) Marcar en `EstimatedProbabilities` (o en docs) qué familias producen margen y total de distribuciones separadas, de modo que ningún consumidor derive team totals o combinados de ellas. (c) Cualquier challenger conjunto (bootstrap de residuos como NBA:187-195) entra por `model-change` con pre-registro.

## P4 — La localía se aplica una sola vez

- **Regla.** O interceptos propios de local/visitante, o un término HFA explícito; nunca ambos.
- **Origen.** EPL:174, 187; LALIGA:134, 208; BUNDESLIGA:228; WNBA:66 (calibrar, no copiar). Plataforma: dos canales, `elo_home_adv` en `rating_diff` (`src/sqp/models/elo.py:70-77`) y `home_scoring_bonus` en `λ_home` (`adapters.py:141`; `registry.py:41, 44, 46`).
- **Estado.** PARCIAL: dos canales, solo uno validado (`tuning.py:150-158` recorre `elo_home_adv` con el bono fijo).
- **Cómo se comprueba.** Inventario de canales por familia; medir, cuando toque, el log loss walk-forward con el bono a 0 frente al vigente (cambio de régimen: addendum en MM antes de medir).
- **Candado propuesto.** [RECOMENDACIÓN] (a) Test documental: un registro `docs/` o una tabla en `registry.py` que enumere los canales de localía por familia, con un test que falle si aparece un tercer canal (por ejemplo, un `rest`/`form` con sesgo local) sin entrada en el registro. (b) `tune_home_advantage` debe aceptar una rejilla conjunta o, al menos, reportar el bono con el que se tuneó.

## P5 — No trasladar parámetros entre deportes, ligas ni poblaciones

- **Regla.** Sigmas, dispersión, correlación, localía, ritmos, medias vidas y reglas de empate son propios de cada liga y se estiman con sus datos.
- **Origen.** WNCAAB:35; WTA:49; NHL:94, 274 («jamás fijar 0,12 sin validación NHL»); NFL:271; MLB:33. Plataforma: `FAMILY_PARAMS` con overrides por liga (`registry.py:20-98`); `TIE_ADDS_GOAL` solo hockey (`adapters.py:93-96, 288`); descanso solo NBA (`ratings.yaml:35-40`); tilt NHL (`ratings.yaml:45-50`); `rest_elo_per_day` separado de `rest_points_per_day` para no mezclar unidades (`adapters.py:104-112`).
- **Estado.** PARCIAL: la arquitectura lo permite y las activaciones recientes lo respetan; NCAAB/WNCAAB heredan `points_per_elo` y `elo_home_adv` de familia (`registry.py:29-31, 95-96`) y NFL corre con todos los defaults de familia (`ratings.yaml` sin entrada `nfl`).
- **Cómo se comprueba.** Diff de `FAMILY_PARAMS` frente a `LEAGUE_OVERRIDES` + `ratings.yaml` por liga: cada parámetro con efecto en la probabilidad debe tener evidencia por liga o declararse «de familia, no validado».
- **Candado propuesto.** [RECOMENDACIÓN] (a) Test que, para cada liga activa, liste los parámetros heredados de familia y compare con una lista permitida explícita (hoy esa lista sería larga; el test convierte la herencia en decisión visible). (b) Test de que un parámetro activado por pre-registro aparece solo en la liga del pre-registro (ya hay precedente de verificación manual: «Solo NBA», `ratings.yaml:38`).

## P6 — Validación temporal, nunca aleatoria; cutoff de información explícito

- **Regla.** Walk-forward con snapshots pregame; cada feature usa solo información disponible al `as_of`; distinguir fecha del evento de fecha de disponibilidad.
- **Origen.** MLB:261; UCL:365; NCAAF:299; WNBA:43; NHL:43 y 595 (porteros sin titularidad fundamentada); BUNDESLIGA (`available_at`, individual §1). Plataforma: `walk_forward_backtest` en todos los `tune_*`; `AdjustmentContext.ref_date` recorta cada feature (`probabilities.py:319-325`, AUD-LOW-005); `ParkFactors` leakage-safe (`park.py:10-13`); gate fuera de muestra (`prediction_gate.py:28-33`); exclusión `generated_at ≥ start_time` en MM y peso-mercado.
- **Estado.** CUMPLE con candados parciales; residual en priors elegidos con datos del periodo evaluado (`registry.py:56-60, 83`; `05` R7).
- **Cómo se comprueba.** Test de no-anticipación: añadir resultados posteriores a `ref_date` no cambia ninguna feature ni estimación.
- **Candado propuesto.** [RECOMENDACIÓN] (a) Test de propiedad: para un evento con `ref_date = d`, inyectar partidos con fecha ≥ d en `results` y comprobar invariancia de `build_adjustment_context` y de `adapter.estimate` tras `observe` ordenado. (b) Test que falle si un `LEAGUE_OVERRIDES` nuevo cita como evidencia una ventana que solape la de producción posterior sin declararlo (documental).

## P7 — Pre-registro antes de medir; una sola medición; no mirar antes

- **Regla.** Hipótesis, métrica, N, regla de decisión y consecuencias se fijan y commitean antes de ver el efecto; la medición se ejecuta una vez; los cambios de régimen se registran por addendum antes de medir.
- **Origen.** Prompts: «antes de elevar un modo exploratorio a validado, ejecutar backtesting walk-forward» (MLB:261); estados VALIDADO/EXPLORATORIO/INCOMPLETO (los 21). Plataforma: `docs/research/2026-08-26-preregistro-el-modelo-manda.md:1-7, 154-158, 240-254, 328-329`; `2026-10-13-preregistro-peso-mercado-por-segmento.md:3, 43-52, 316, 328`; `prediction_gate.py:28-33` (KI-019: no validar sobre la muestra del hallazgo); `.claude/rules/modeling-rules.md`.
- **Estado.** CUMPLE con candado (scripts que abortan sin T1/T0; `tests/research/test_measure_el_modelo_manda.py` según E9 del pre-registro).
- **Cómo se comprueba.** El script `--medir` exige addendum de T1 y commit del registro; `--ajustar` aborta antes de T0 + 14 d.
- **Candado propuesto.** [RECOMENDACIÓN] (a) Mantener: ningún fichero `*-resultado-*.md` sin pre-registro previo en el historial (test que recorra `docs/research/` y exija pareja `preregistro`/`resultado` por fecha). (b) Esta auditoría se registra como addendum «antes de ejecutar» en MM, sin cambiar criterios.

## P8 — Prohibido elegir hiperparámetros, calibradores o umbrales por ROI o CLV de cuotas

- **Regla.** La selección de parámetros y métodos se hace por métricas frente a resultados (log loss, Brier, ECE) en walk-forward; ROI y CLV solo se reportan después.
- **Origen.** NHL:609 («ROI y CLV son medidas económicas secundarias»); ATP:342 («sin usar mercado como predictor»); EPL:205 («Nunca elegir una opción solo porque produce edges mayores»); EPL:27 y MLB:14 (benchmark separado del entrenamiento; a reforzar, ver `07` §1.3). Plataforma: `tune_*` puntúan por log loss (`tuning.py:161, 241, 278-279`); incumplimientos heredados: `park_bound` (`ratings.yaml:25-30`), `max_plausible_edge` y `uncertainty_penalty` (`default.yaml:11-26`).
- **Estado.** PARCIAL: la herramienta de tuning cumple; tres parámetros desplegados no. Revalidación diferida a después de MM (cambio de régimen).
- **Cómo se comprueba.** Grep de «ROI» en las justificaciones de `configs/leagues/ratings.yaml` y `configs/default.yaml`; lectura de `scripts/tune_ratings.py` (no importa `roi_engine`, grep sin resultados).
- **Candado propuesto.** [RECOMENDACIÓN] (a) Test de que `sqp.backtesting.tuning` y `scripts/tune_ratings.py` no importan `sqp.backtesting.roi_engine` ni leen `data/odds`. (b) Test documental: todo override de `ratings.yaml` con efecto en λ/μ/σ cita un documento de `docs/research/` con métrica frente a resultados; la lista de excepciones heredadas (`park_bound`) se declara explícitamente con fecha y queda marcada «pendiente de revalidación». (c) Añadir la cláusula explícita a los 21 prompts.

## P9 — Calibrar la creencia pre-blend contra resultados, nunca contra el mercado

- **Regla.** El calibrador aprende de `adjusted_probability` frente al resultado sobre la distribución servida completa (no solo picks) y se aplica antes de cualquier mezcla.
- **Origen.** Plataforma: `probabilities.py:277-296`; `calibration/data.py:12-19, 31-34, 69, 207-227`; `calibrator.py:714-740` (`min_n` en eventos). Prompts: Brier/log loss/curvas de calibración con resultados (MLB:261; NHL:609; WTA:274).
- **Estado.** CUMPLE SIN CANDADO.
- **Cómo se comprueba.** `TRAINING_COLS` y `_project_training`: la columna de mercado no entra como feature; el objetivo es `adjusted_probability`.
- **Candado propuesto.** [RECOMENDACIÓN] (a) Test que entrena un calibrador sintético con `implied_probability_novig` perturbada y comprueba que el calibrador resultante es idéntico. (b) Test de que `calibrate_probability` se invoca sobre `_p_adj` y no sobre `p_used` (fijar la línea `probabilities.py:299-302`). (c) Test de que `train_market_calibrators` rechaza grupos con < `min_n` **eventos**.

## P10 — Probabilidad servida coherente con la liquidación (push y líneas)

- **Regla.** Push explícito en líneas enteras; cuartos asiáticos como mitad de stake en cada vecina; la probabilidad servida es la de decisión `win/(win+loss)` y el EV se calcula con la misma convención.
- **Origen.** Prompts: `P_win/P_push/P_loss` y `P_break_even = (1−P_push)/D` (MLB:194-195; NHL:456-458; ATP:321-323; todos los de fútbol). Plataforma: `distributions.py:239-262` (AUD-001), `default.yaml:4` (AUD-011), `daily.py:971-973`.
- **Estado.** CUMPLE con candado (tests de líneas de cuarto, memoria de la auditoría 2026-09-17).
- **Candado propuesto.** [RECOMENDACIÓN] Mantener; añadir el caso `spread_line = 0` y totales enteros en la familia Normal (`distributions.py:46-50, 62-66`) para fijar que la renormalización no cambie de convención.

## P11 — No declarar ejecutado, validado ni rentable lo que no lo está

- **Regla.** Sin motor numérico, no afirmar Monte Carlo ni backtesting; distinguir probabilidad estimada, implícita, edge, hit rate observado frente a prometido, ROI esperado y realizado; nunca prometer beneficio.
- **Origen.** MLB:17; NHL:61 y 578 (individual); estados VALIDADO/EXPLORATORIO/INCOMPLETO en los 21. Plataforma: `.claude/rules/betting-output-rules.md`; comentarios «not a profit claim» (`default.yaml:15, 23`; `ratings.yaml:29`); reportes «necesitabas X %, acertaste Y %» (`default.yaml:191-194`).
- **Estado.** CUMPLE SIN CANDADO completo.
- **Candado propuesto.** [RECOMENDACIÓN] Test de redacción en los reportes generados (ya existen tests de reporte): presencia obligatoria de las columnas separadas (estimada, implícita, edge, hit observado, break-even) y ausencia de «garantiza»/«asegura» en texto generado.

## P12 — Ningún umbral ni constante inventada; valores provisionales etiquetados

- **Regla.** Constantes de liga se estiman por temporada y `as_of`; si se usa un valor provisional, se etiqueta y no se llama validado.
- **Origen.** NFL:44 («No imponer constantes fijas de liga por años»); MLB:33, 48; NHL:98 (individual: «por estimar»). Plataforma: comentarios de procedencia en `registry.py` y `ratings.yaml`; `pitcher_bound` activado «por orden, no por evidencia concluyente» (`ratings.yaml:17-21`); `tests/test_config_yaml_keys.py` cierra claves sin consumidor (`default.yaml:148-149`).
- **Estado.** CUMPLE SIN CANDADO para la etiqueta; constantes fijas de familia (`avg_total 44`, `elo_home_adv 55` NFL) sin revalidación por temporada.
- **Candado propuesto.** [RECOMENDACIÓN] Test que exija a cada parámetro de `LEAGUE_OVERRIDES` y `ratings.yaml` una fecha y una etiqueta (`medido` / `por orden` / `provisional`) en comentario o en un manifiesto paralelo.

## P13 — La unidad de inferencia es el evento, no la fila

- **Regla.** `n`, los IC y los mínimos de muestra cuentan eventos independientes (una por partido-mercado), no filas del stream (que repite cada pick por día de horizonte, 2,19-2,67×).
- **Origen.** Plataforma: `prediction_gate.py:15-20` (`_independent_units`, AUD-20260906-03); `calibrator.py:731-740`; MM addendum 2026-10-13 (unidad por pick, IC por evento); peso-mercado §4.2. Prompts: `MC_SE = sqrt(p(1−p)/N)` solo para ruido MC (NFL:273; NBA:215).
- **Estado.** CUMPLE con candado en gate y calibrador.
- **Candado propuesto.** [RECOMENDACIÓN] Test transversal: toda función de `sqp.evaluation`/`sqp.risk` que calcule un IC o un `n` acepta un `group_key` y lo usa (lista cerrada de funciones, con test de firma).

## P14 — Comparar al modelo PURO con el mercado cuando la pregunta es «¿predice el modelo?»

- **Regla.** Las comparaciones modelo-mercado que gobiernan stake o pausas usan `model_probability` (o `cal(p_adj)` reconstruida), nunca una cantidad que ya contenga el precio.
- **Origen.** `prediction_gate.py:10-14`; MM («`estimated_probability` contiene el mercado… sería circular», `preregistro-el-modelo-manda.md:68-74`). Prompts: NHL:428 («comparación con mercado sin margen exclusivamente evaluación», individual §7).
- **Estado.** PARCIAL: el gate cumple; el monitor de degradación compara la mezcla (`degradation.py:71`).
- **Candado propuesto.** [RECOMENDACIÓN] Test de que todo comparador modelo-mercado en `sqp.risk` y `sqp.evaluation` declara la columna que usa, y que las que deciden stake/pausa leen `model_probability` o justifican por qué no (la de degradación quedaría marcada «mezcla, diagnóstico diluido» hasta que el operador decida).

## Tabla de síntesis

| Principio | Origen principal (prompt) | Origen principal (plataforma) | Estado | Candado |
|---|---|---|---|---|
| P1 Independencia en estimación | NHL:6; ATP:37; NFL:24 | adaptadores sin precios | CUMPLE SIN CANDADO | tests de importación y de invariancia |
| P2 Congelación | MLB:178; ATP:317; NFL:319 | `daily.py:1031`, `1126` | PARCIAL (decisión mezclada; MM decide) | identidad algebraica por fila |
| P3 Una distribución | NFL:36; NBA:195 | `distributions.py:204` sí; `32-70` no | PARCIAL | coherencia ML/spread@0; marcar familias |
| P4 Localía una vez | EPL:174; BUNDESLIGA:228 | `elo.py:70-77` + `adapters.py:141` | PARCIAL | registro de canales |
| P5 No trasladar parámetros | WNCAAB:35; NHL:94 | `registry.py:20-98` | PARCIAL | lista de herencias permitidas |
| P6 Validación temporal / cutoff | MLB:261; WNBA:43 | `probabilities.py:319-325`; `park.py:10-13` | CUMPLE (parcial) | test de no-anticipación |
| P7 Pre-registro, una medición | MLB:261 | MM, peso-mercado | CUMPLE | pareja preregistro/resultado |
| P8 No optimizar por ROI de cuotas | NHL:609; EPL:205 | `tuning.py`; excepciones `ratings.yaml:25-30`, `default.yaml:11-26` | PARCIAL | test de importaciones + manifiesto |
| P9 Calibrar pre-blend contra resultados | MLB:261 | `data.py:69`; `probabilities.py:299-302` | CUMPLE SIN CANDADO | invariancia al no-vig |
| P10 Push coherente con liquidación | MLB:194-195 | `distributions.py:239-262` | CUMPLE | mantener, ampliar Normal |
| P11 No declarar lo no ejecutado | MLB:17 | `betting-output-rules.md` | CUMPLE SIN CANDADO | test de redacción |
| P12 Sin constantes inventadas | NFL:44; MLB:48 | `ratings.yaml:17-21` | CUMPLE SIN CANDADO | manifiesto de procedencia |
| P13 Unidad = evento | NFL:273 | `prediction_gate.py:15-20` | CUMPLE | firma con `group_key` |
| P14 Comparar el modelo puro | NHL:428 | `prediction_gate.py:10-14` | PARCIAL (`degradation.py:71`) | declaración de columna |
