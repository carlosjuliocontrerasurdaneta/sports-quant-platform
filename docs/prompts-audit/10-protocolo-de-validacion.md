# 10 — Protocolo de validación sin cuotas

Fecha: 2026-11-10. Escalón Fable, fase 2 de la auditoría de los 21 prompts `PROMPT_191_*`. Procedimiento reproducible para comprobar el rendimiento real de las probabilidades congeladas **sin usar cuotas**. Se apoya en la infraestructura que el proyecto ya tiene (se cita la ruta) y señala lo que falta. Etiquetas: [COMPROBADO] con cita, [INFERENCIA], [HIPÓTESIS], [RECOMENDACIÓN].

Regla de oro: en las secciones 1-8 **no entra ninguna columna de mercado** (`price_decimal`, `implied_probability_novig`, `consensus_*`, `closing_*`, líneas de mercado salvo como umbral declarado en §4.3). La comparación con el mercado existe, pero es evaluación externa y va al final (§9), nunca criterio de entrenamiento, selección ni promoción.

Umbrales: solo se usan los que el proyecto ya define, con cita. Donde no hay umbral definido se escribe **«a fijar en el pre-registro»**; este documento no inventa ninguno.

---

## 0. Objeto evaluado y unidad de muestra

- **Objeto**: el registro congelado por evento (`prediction_id`, `frozen_at`, `model_version`, `params_hash`, distribución y probabilidades; `06-arquitectura-recomendada.md §4.2`). Mientras ese registro no exista, el sustituto es la columna `model_probability` del stream servido (`src/sqp/storage/served_store.py:711-713`), que es la probabilidad pura pre-mezcla [COMPROBADO `src/sqp/domain/models.py:90`].
- **Unidad de muestra**: **un evento** (partido) por mercado, nunca una fila. [COMPROBADO] El stream servido guarda una fila por día de horizonte y las dos caras de cada mercado; sin colapsar, cada pick pesa 2,19-2,37 veces y la independencia se rompe (`src/sqp/evaluation/model_vs_market.py:554-571`; `src/sqp/risk/prediction_gate.py:436-440`). Colapso con `one_row_per_pick` (`src/sqp/evaluation/edge_information.py:55`) o `_independent_units` (`prediction_gate.py:346`); primera fila servida por pick (precedente: `preregistro-brecha-tier-a.md:§1.2`).
- **Resultado**: `y ∈ {0,1}` para mercados binarios (push excluido o ponderado por fracción resuelta, `_PESO_RESUELTO`, `prediction_gate.py:449-450`); marcador final y reglamentario para métricas de marcador (§4.2).

---

## 1. Backtest cronológico y walk-forward con corte as-of

### 1.1 Lo que existe

- `walk_forward_backtest(results, league, family, ...)` (`src/sqp/backtesting/engine.py:42`): ajusta ratings solo con el pasado, estima el siguiente partido y registra probabilidad vs desenlace; temporal por construcción, sin splits aleatorios; devuelve por mercado `n`, `brier`, `log_loss`, `ece`, `mean_probability`, `observed_rate`, **`bias`** y las series ordenadas (`engine.py:17-40`). Acepta `spread_lines`/`total_lines` como umbrales (Tareas.md:118).
- Entradas operativas: `scripts/backtest_history.py` (histórico almacenado, baseline de tasa local in-sample como referencia), `scripts/run_backtest.py` (demo o CSV).
- Selección de parámetros con holdout de origen rodante: `rolling_origin_improvement` (`src/sqp/backtesting/tuning.py:75`), `DEFAULT_HOLDOUT_SPLITS = 4`, `HOLDOUT_MIN_TRAIN_FRAC = 0.4` (`tuning.py:214-215`); `temporal_cutoff` (`tuning.py:327`); `scripts/validate_oos.py` congela parámetros en train y mide solo en test (`validate_oos.py:docstring`).
- Para modelos ML: `daily_splits` (TimeSeriesSplit, `n_splits = 5`) y `holdout_start(fraction = 0.20)` (`src/sqp/features/temporal.py:22, 33`); `compare_league` selecciona en la primera mitad del holdout y puntúa en la segunda (`src/sqp/evaluation/compare.py:5-9`).

### 1.2 Procedimiento

1. Ordenar los partidos por fecha de inicio UTC (`ordered_games`, `temporal.py:9`).
2. Para cada día `d`, el estado del modelo se construye con resultados cuya fecha es **estrictamente anterior** a `d` (contrato de `AdjustmentContext.ref_date`, `src/sqp/pipeline/probabilities.py:319-325`; `features/builders.py` «only results from earlier UTC days»). Las capturas con hora (abridores, porteros) se admiten solo si `available_at ≤ as_of` del run (`features/research.py:1-6`).
3. Calentamiento: `--warmup` partidos por liga antes de puntuar (`backtest_history.py`, `tune_ratings.py:--warmup 60`).
4. Se puntúa **cada** evento con la probabilidad congelada de ese día; se guardan las series por evento para bootstrap.
5. Para cualquier parámetro elegido en el propio histórico, la métrica honesta es la del holdout rodante o de `validate_oos.py`, no la in-sample (`tuning.py:190-202`: «selection is still in-sample» salvo con holdout).

### 1.3 Lo que falta

- [RECOMENDACIÓN] `walk_forward_backtest` debe poder puntuar el **registro congelado** tal cual (replay por `prediction_id`), además de recalcular; así se valida lo que de verdad se sirvió. Hoy el replay de lo servido lo hace `calibration/data.py` para calibradores, no el motor de backtest.
- [RECOMENDACIÓN] Reproducir la semántica de fecha local vs UTC de cada liga (MLB usa fecha local en resultados y UTC en cuotas: memoria `fechas-resultados-local-vs-utc`); el protocolo fija el día del evento por `game_date_local` (`evaluation/labels.py:331`).

---

## 2. Prevención de fuga

### 2.1 Lo que existe

- Features de resultado solo con el estado del cierre del día anterior (`features/research.py`, `features/builders.py`); recorte `< ref_date` dentro de cada feature (`probabilities.py:319-325`, AUD-LOW-005).
- Elo secuencial y regresión de temporada aplicada **antes** de estimar (`src/sqp/sports/base.py:33-44`, pre-registro Elo regresión §12.1).
- Portero/abridor: solo apariciones con fecha estrictamente anterior (`models/goalies.py:7-8`; `models/starters.py:6-7`); el problema «titular real vs probable» está tratado en el pre-registro del portero (`preregistro-portero-nhl.md:§1`).
- Gate: solo filas con `game_date` posterior al pre-registro (`VALIDATION_START`, `prediction_gate.py:452-456`; KI-019 «no validar sobre la muestra del hallazgo»).
- Calibradores: split temporal y entrenamiento sobre lo servido, no sobre el replay de cierre (`calibration/data.py:1-7`; `scripts/train_calibration.py`).
- Agente `leakage-detector` y skill `model-change` (paso 2: «verify temporal split, feature availability time, and leakage risks»).

### 2.2 Lista de comprobación obligatoria por escalón

| Comprobación | Cómo se verifica | Existe |
|---|---|---|
| Ningún insumo con `available_at > sporting_as_of` | `freeze_model` rechaza fuentes posteriores al corte (`models/independent.py:181-182`) | sí (offline) |
| `sporting_as_of ≤ frozen_at < starts_at` | `independent.py:171-174`; test `tests/test_independent_pricing.py:71` | sí (offline) |
| Sin postgame en features (marcador, goalie que jugó, abridor real) | revisión del `leakage-detector`; test que recalcule features con el histórico truncado a `d−1` y compare | parcial |
| Sin split aleatorio | `TimeSeriesSplit`/walk-forward únicamente (`temporal.py`) | sí |
| Sin selección sobre la muestra de validación | holdout rodante; parámetros congelados en train (`validate_oos.py`) | sí |
| Sin columnas de mercado en la capa deportiva | test de fronteras de importación y de nombres de columna (06 §5.1) | **falta** |
| Sin «mirar antes» un pre-registro | registro `--contar` sin desenlaces (`preregistro-brecha-tier-a.md`), ejecución única | sí (convención) |
| Alias de equipos estables en el tiempo | `configs/leagues/team_aliases.yaml`, `scripts/audit_team_names.py` | sí |

---

## 3. Métricas

### 3.1 Probabilísticas (existen)

`src/sqp/calibration/metrics.py`: `brier_score` (:9), `log_loss` con `eps = 1e-12` (:14), `reliability_table` con 10 bins y descarte de pares no finitos (:20), `expected_calibration_error` (:51), `calibration_report` (:59). Sesgo direccional `bias = media(p) − tasa observada` en `engine.py:17-30`. Pendiente de calibración (regresión de logit) usada en la investigación de `wnba/totals` (Tareas.md:117) [HIPÓTESIS: no localizada como función reutilizable; a extraer].

[RECOMENDACIÓN] Añadir a `calibration_report`: pendiente e intercepto de calibración (logit de y sobre logit de p), con IC bootstrap, porque es la métrica que detectó la inversión de `wnba/totals` y la sobreconfianza (pendiente < 1).

### 3.2 De marcador (faltan)

[COMPROBADO] No existe en `src/sqp/` una métrica de error de marcador: `calibration/metrics.py` solo cubre probabilidades binarias. [RECOMENDACIÓN] Nuevo módulo `src/sqp/evaluation/score_metrics.py`, alimentado por la distribución congelada:

- MAE y RMSE de **goles/puntos por equipo** (E[X_h] vs marcador local; E[X_a] vs visitante);
- MAE y RMSE del **margen** (E[X_h − X_a]) y del **total** (E[X_h + X_a]);
- cobertura de intervalos de predicción (p. ej. 50 % y 90 %) del margen y del total, calculada de la rejilla o de la Normal congelada;
- CRPS del total y del margen (discreto desde la rejilla; los prompts de tenis lo piden para juegos, WTA:274);
- para fútbol: log loss de la distribución del **marcador exacto** (multiclase sobre la rejilla), que es la prueba directa del Dixon-Coles.

Umbrales de aceptación para estas métricas: **a fijar en el pre-registro** (el proyecto no define ninguno).

### 3.3 Reglas de lectura

- Log loss y Brier son la primaria; la ECE y la fiabilidad diagnostican, no deciden (un calibrador constante pasa ECE y Brier: memoria `calibrador-colapsado-2026-08-28`).
- Siempre junto a `bias` y pendiente: el Brier mezcla dirección y afilamiento (`engine.py:21-24`).
- Nunca peor que 0,50 ni que la tasa base (Tareas.md:134).

---

## 4. Evaluación por deporte, competición, temporada y mercado

### 4.1 Particiones obligatorias

Por **liga** (nunca solo por familia: «a model can be calibrated in NHL and miscalibrated in NFL», `metrics.py:1-3`), por **mercado** (ML/1X2, spread, total, y cada derivado), por **temporada** y por **bloque temporal** del holdout rodante, por **banda de probabilidad** (10 bins), y, cuando aplique, por fase (regular/playoffs/eliminatoria), sede neutral y estado de dato (`VERIFICADA/PROVISIONAL`). La skill `model-change` ya exige segmentar «by sport, market, season/time, probability band, and sample size» (`SKILL.md:27`).

### 4.2 Períodos de marcador

Para deportes con prórroga o extras se evalúa por separado el marcador **reglamentario** y el **final** (NHL:53 `score_reg`/`score_final_official`/`score_for_settlement`). [COMPROBADO] Hoy el histórico guarda un solo marcador por partido (`ResultsStore`; `independent.py:5-6` «No OT/tie redistribution is invented»). [RECOMENDACIÓN] Capturar ambos (08 §5) antes de validar los escalones de reglamento.

### 4.3 Umbrales para spreads y totales sin mercado

Para evaluar P(margen > L) y P(total > T) **sin** la línea del mercado hay tres opciones, por orden de preferencia:

1. **Rejilla de umbrales fijos** por deporte (p. ej. márgenes −10…+10 y totales en una malla alrededor de la media de la liga): mide la CDF congelada en puntos independientes del mercado; se reporta la curva completa.
2. **Umbral = mediana del propio modelo** (L tal que P(margen > L) ≈ 0,5): evalúa la dispersión y el sesgo de la distribución.
3. **Línea del mercado como umbral declarado** (UMBRAL LEGÍTIMO según el BRIEF): se permite **solo** como partición adicional, etiquetada, porque es la línea sobre la que se sirve en producción; no entra en ningún ajuste ni selección. El arnés ya lo soporta (`walk_forward_backtest(spread_lines, total_lines)`).

---

## 5. Baselines independientes del mercado

Todo escalón se compara, en las mismas filas, con:

| Baseline | Existe | Ruta |
|---|---|---|
| Constante 0,5 (y, en 1X2, 1/3) | referencia implícita | `preregistro-el-modelo-manda.md:§Lo que ya está medido` (moneda 0,25000) |
| Tasa base de la liga (localía media, tasa de Over media) | sí, in-sample | `backtest_history.py` («home-rate baseline… in-sample») |
| Elo puro sin ajustes (`tilt`, `home_scoring_bonus`, descanso, abridor, portero = default de familia) | sí | `validate_oos.py` config `family_default` |
| Campeón congelado por (`model_version`, `params_hash`) | convención | skill `champion-challenger` §Flujo 1 |
| Elo por superficie / hold-break empírico / prior de torneo (tenis) | no | exigido por ATP:342 |
| Poisson independiente sin Dixon-Coles (fútbol) | sí | `dc_rho = 0` |
| Normal con σ de familia (baloncesto, FA) | sí | `registry.py:FAMILY_PARAMS` |

[RECOMENDACIÓN] Formalizar las dos primeras como funciones de `evaluation/` (hoy la tasa base se calcula in-sample en el script) con la misma unidad de muestra que el modelo.

---

## 6. Estabilidad y degradación

### 6.1 Lo que existe

- Holdout de origen rodante con 4 bloques: la mejora debe sostenerse por bloque (`tuning.py:75-113`).
- Monitor de degradación por (liga, mercado): ventana 60 días, `min_n 30`, histéresis (`configs/default.yaml:297-303`; `src/sqp/risk/degradation.py`). [COMPROBADO] Uno de sus dos criterios compara Brier con el del mercado (`default.yaml:288-290`): es evaluación externa (§9), no parte de este protocolo.
- Skill `drift-monitor` (DATA_DRIFT / CONCEPT_DRIFT / MARKET_DRIFT).
- Regresión de Elo al inicio de temporada (pre-registro 2026-10-29) y modo inicio de temporada (pre-registro 2026-10-31).

### 6.2 Procedimiento sin mercado

1. **Por bloque temporal**: log loss, Brier, sesgo y pendiente en cada uno de los 4 bloques; el escalón se acepta solo si no empeora el baseline en más bloques que los que mejora (regla a fijar en el pre-registro; `rolling_origin_improvement` ya devuelve la serie por bloque).
2. **Degradación en producción**: Brier y sesgo móviles (60 días, `min_n 30`, los valores vigentes de `degradation_monitor`) de la probabilidad congelada frente al desenlace y frente a la **tasa base**, por (liga, mercado). [RECOMENDACIÓN] Añadir este criterio interno al monitor, junto al externo que ya tiene.
3. **Inicio de temporada**: particiones «primeras N jornadas» vs resto; comparar con el modo CONSERVATIVE/SHADOW de `season-transition`.
4. **Cambios de régimen**: todo cambio de `model_version` o `params_hash` queda en el registro congelado, de modo que una degradación se pueda atribuir a una versión concreta.

---

## 7. Ablación y sensibilidad

### 7.1 Lo que existe

- `evaluate_blocks` (`src/sqp/evaluation/feature_blocks.py:32`): ablaciones pareadas por bloques de features con expansión diaria (`n_splits = 5`), «exploratory evidence, never promotion»; entrada `scripts/evaluate_feature_blocks.py`.
- `feature_shadow` (`src/sqp/evaluation/feature_shadow.py`): candidatos aislados y congelados, captura pregame append-only y evaluación a fecha fija; huellas SHA-256 y versiones de runtime.
- Barridos con guardarraíles: `tune_market_param` (`tuning.py:201`), con `DC_RHO_BOUNDS` y rejillas acotadas (`tuning.py:217-222`).
- Precedentes de ablación pre-registrada: control de intercepto y criterio sobre partidos afectados (`preregistro-portero-nhl.md:20-27`), contraprueba obligatoria (`resultado-suelo-de-precio.md`).

### 7.2 Procedimiento

1. **Ablación por componente**: para cada escalón, el modelo con y sin el componente, mismas filas, diferencia pareada de log loss por evento, IC bootstrap por clúster (evento o día; `cluster_bootstrap_ci`, `n_boot 1000`, `seed 42`, `evaluation/bootstrap.py:22`).
2. **Control de intercepto**: el componente debe batir a un desplazamiento constante equivalente (precedente del portero NHL: `preregistro-portero-nhl.md:20`).
3. **Sensibilidad a hiperparámetros**: curva de la métrica en la rejilla (p. ej. τ de shrinkage, media vida, σ); se exige un mínimo **interior** y suave (la «curva en U con mínimo claro» que justificó `elo_k 40` en tenis, `registry.py:86-90`); un óptimo en el borde invalida la rejilla, no la conclusión.
4. **Sensibilidad a la tolerancia numérica**: masa omitida de la rejilla ≤ `max_tail_mass` (1e-6 por defecto en `independent.py:206`) y conservación de masa en todos los estados de liquidación (`tests/test_independent_pricing.py:78`).
5. **Sensibilidad al calentamiento y al inicio de temporada**: repetir con `warmup` ×0,5 y ×2.
6. **Partidos afectados**: reportar la métrica también solo sobre los eventos donde el componente cambia la probabilidad en más de un δ (δ a fijar en el pre-registro), como exige el precedente del portero.

---

## 8. Tamaños mínimos y multiplicidad

### 8.1 Lo que el proyecto ya define (se reutiliza tal cual)

| Regla | Valor | Ruta |
|---|---|---|
| Partidos evaluados para aceptar un override de localía | ≥ 200 | `tuning.py:225` (`MIN_EVAL_HOME_ADV`) |
| Empates observados para aceptar `dc_rho` | ≥ 80 | `tuning.py:226` (`MIN_DRAWS_DC_RHO`) |
| Mejora mínima de log loss frente al default de familia | 0,002 | `tuning.py:227` (`IMPROVEMENT_MARGIN`) |
| Bloques de holdout rodante / fracción semilla | 4 / 0,40 | `tuning.py:214-215` |
| Eventos independientes para entrenar un calibrador | ≥ 40 (`train_market_calibrators`), ≥ 30 para promoción | `calibrator.py:714`; `default.yaml:210-212` |
| Monitor de degradación | `min_n 30`, ventana 60 días | `default.yaml:299-300` |
| Gate de predicción (externo, §9) | n ≥ 300 no empatadas; α por mercado 0,000702 (familia 0,05 por Bonferroni, K = 69, techo 84) | `default.yaml:264-269`; `prediction_gate.py:212` (`fwer_bound`) |
| Muestra por potencia antes de medir, ejecución única | N calculado con DE de nuisance (p. ej. 3.402, 2.100, 3.300) | `preregistro-el-modelo-manda.md:§Potencia`; `preregistro-brecha-tier-a.md:169`; `preregistro-peso-mercado:210` |
| Bootstrap | por clúster, 1.000 réplicas, semilla 42, α 0,05 | `evaluation/bootstrap.py:22-25` |

### 8.2 Procedimiento

1. **Antes de medir**: calcular N por potencia con parámetros de nuisance (DE de la diferencia pareada por evento, tasa de acumulación), sin mirar ninguna media ni signo; registrarlo con `--contar` o equivalente y commit (convención de `preregistro-brecha-tier-a.md`).
2. **Multiplicidad**: cada pre-registro declara K (número de contrastes: ligas × mercados × escalones evaluados a la vez) y reparte α de familia por Bonferroni, como hace el gate (`preregistro-multiplicidad-del-gate.md`); una mirada por contraste («un test único que se gasta», `default.yaml:275-279`). Un escalón evaluado en varios mercados a la vez usa la regla «acepta solo si pasa en todos» (`resultado-correlacion-marcadores.md:22`), que no necesita corrección adicional porque es una intersección.
3. **α de familia y potencia objetivo**: el proyecto usa 0,05 de familia y 0,80 de potencia en los pre-registros citados; cualquier otro valor **a fijar en el pre-registro**.
4. **Muestras pequeñas**: con n por debajo de los mínimos de §8.1 el veredicto es `muestra_insuficiente`, no «rechaza» ni «acepta» (misma semántica que el gate).
5. **Inferencia**: solo bootstrap por clúster (`evaluation/bootstrap.py:1-12`: «la única inferencia válida en este proyecto»).

---

## 9. Evaluación externa posterior: comparación con el mercado

Esta sección **no** forma parte de la validación del modelo. Se ejecuta después, sobre probabilidades ya congeladas y con cuotas cuyo `captured_at ≥ frozen_at`, y responde a otra pregunta: si la probabilidad validada aporta algo frente al precio y si sobrevive al vig. Nunca es criterio de entrenamiento, de selección de parámetros ni de promoción de un escalón.

| Evaluación | Qué mide | Existe | Ruta |
|---|---|---|---|
| Brier/log loss pareado modelo vs no-vig, IC por evento | si el modelo iguala al patrón de medida | sí | `src/sqp/evaluation/model_vs_market.py:122`; `scripts/model_vs_market_report.py` |
| Escalera de `min_edge` y de cap | si el edge declarado tiene información | sí | `src/sqp/evaluation/edge_information.py:142, 232` |
| Gate de predicción (test de signo pareado + EV del lado del modelo) | regla de salida a stake real | sí | `src/sqp/risk/prediction_gate.py`; `scripts/update_prediction_gate.py` |
| CLV frente al cierre capturado | calidad del precio obtenido | sí (diagnóstico) | `src/sqp/audit/clv.py`; `scripts/clv_analysis.py`; `clv_gate` desactivado (`default.yaml:259-261`) |
| EV esperado vs ROI realizado, hit rate vs punto de equilibrio | rentabilidad, nunca prometida | sí | `scripts/backtest_roi.py`; `scripts/validate_oos.py`; `default.yaml:191-194` |
| Comparación offline con cotizaciones con timestamp | prototipo del contrato «congelar y luego comparar» | sí | `src/sqp/markets/independent.py:66`; `scripts/price_independent.py` |

Reglas de esta sección:

- Se publican, separadas y con nombre, probabilidad estimada, probabilidad implícita, edge, hit rate observado vs prometido, ROI esperado y ROI realizado (`.claude/rules/betting-output-rules.md`).
- Un modelo que **mejora** en §1-8 y **no** mejora aquí sigue siendo una mejora del modelo; un modelo que mejora aquí sin mejorar en §1-8 es sospechoso de haber aprendido el mercado y se rechaza.
- Los pre-registros vigentes que usan el mercado como patrón («el modelo manda», «peso por segmento», brecha tier A) pertenecen a esta sección y conservan sus fechas y sus candados (`08-plan-de-optimizacion.md §6.2-6.3`).

---

## 10. Resumen: qué existe y qué falta

| Pieza | Estado | Ruta o acción |
|---|---|---|
| Walk-forward con sesgo, Brier, log loss, ECE, fiabilidad | existe | `backtesting/engine.py`, `calibration/metrics.py` |
| Holdout rodante, parámetros congelados, guardarraíles | existe | `backtesting/tuning.py`, `scripts/validate_oos.py` |
| Ablación pareada y shadow de candidatos | existe | `evaluation/feature_blocks.py`, `evaluation/feature_shadow.py` |
| Bootstrap por clúster | existe | `evaluation/bootstrap.py` |
| Mínimos y multiplicidad | existen (tabla §8.1) | `tuning.py`, `prediction_gate.py`, pre-registros |
| Congelación con hash y timestamp | existe offline | `models/independent.py`; cablear al run (06 §4.3) |
| Replay del registro congelado en el backtest | **falta** | ampliar `walk_forward_backtest` |
| MAE/RMSE/CRPS/cobertura de marcador, log loss de marcador exacto | **falta** | nuevo `evaluation/score_metrics.py` |
| Pendiente e intercepto de calibración como función | **falta** | ampliar `calibration_report` |
| Marcador reglamentario y final por separado | **falta** | captura en `ResultsStore` (08 §5) |
| Baselines (0,5, tasa base) como funciones con la misma unidad de muestra | **falta** | nuevo en `evaluation/` |
| Umbrales fijos independientes del mercado para spreads/totales | **falta** | parámetro de `walk_forward_backtest` |
| Test de fronteras de importación y de columnas | **falta** | `tests/test_architecture_boundaries.py` (06 §5.1) |
| Degradación interna (frente a tasa base) en el monitor | **falta** | ampliar `risk/degradation.py` |
| Umbrales de aceptación para métricas de marcador y para «bloques que mejoran» | no definidos | **a fijar en el pre-registro** |
