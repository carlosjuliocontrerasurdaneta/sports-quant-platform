# 06 — Arquitectura recomendada: integrar los prompts deportivos en `sports-quant-platform`

Fecha: 2026-11-10. Escalón Fable, fase 2 de la auditoría de los 21 prompts `PROMPT_191_*`. Entradas: los 21 informes de `docs/prompts-audit/individual/` y los 6 de familia en `docs/prompts-audit/familias/`; lectura dirigida de `src/sqp/`, `configs/`, `docs/research/` y `.claude/skills/`. Etiquetas: [COMPROBADO] con cita, [INFERENCIA], [HIPÓTESIS], [RECOMENDACIÓN]. graphify no estaba disponible (MCP caído); todas las citas provienen de Grep/Read directos.

Principio que gobierna este documento (dictado por el operador, `BRIEF.md`): las probabilidades se construyen solo con información deportiva y modelos independientes; el mercado solo sirve para comparar, y después de congelar. Una línea del mercado usada como umbral a evaluar (P(margen > −5,5)) es legítima; usada como entrada (λ = total del mercado) no lo es.

---

## 0. Diagnóstico de partida: dónde está hoy la frontera con el mercado

Antes de proponer, conviene fijar con precisión qué hace la plataforma, porque la arquitectura recomendada es en gran parte una **reordenación** de piezas que ya existen.

| Punto de la cadena | Qué ocurre hoy | Clasificación según el BRIEF |
|---|---|---|
| Universo de eventos | `run_league` obtiene los eventos del proveedor de cuotas (`OddsAPIClient`, `src/sqp/pipeline/daily.py:28, 671`) | [INFERENCIA] Selección del universo por el mercado: no contamina el valor de la probabilidad, pero decide qué se modela. |
| Umbrales de spread y total | `_pick_main_lines` elige la línea más cotizada y la pasa a `adapter.estimate(eo.event, spread, total)` (`src/sqp/pipeline/probabilities.py:236-247`; `src/sqp/pipeline/daily.py:888`) | [COMPROBADO] **UMBRAL LEGÍTIMO**: μ y σ salen de Elo, `TeamScoringRates` y las tasas Poisson (`src/sqp/sports/adapters.py:60-70, 145-153`); la línea solo fija dónde se evalúa la CDF. |
| Probabilidad pura | `model_probability` (`src/sqp/domain/models.py:90`; columna del stream servido `src/sqp/storage/served_store.py:711-713`) | [COMPROBADO] Independiente del mercado por construcción. |
| Capa de ajustes de features | `adjust_model_probability` (`daily.py:966`) con todos los coeficientes a 0 en `configs/default.yaml:43-116` | [COMPROBADO] Inerte hoy; varios términos (`totals_tendency`, `over_under_rate`) toman la línea como **referencia**, no como entrada (`default.yaml:55-60, 112-116`). |
| Calibración | `calibrate_probability` sobre `_p_adj`, entrenada contra el desenlace (`probabilities.py:299-302`; `scripts/train_calibration.py` docstring; `src/sqp/calibration/calibrator.py:714-730`) | [COMPROBADO] Objetivo = frecuencia realizada. No entra el mercado en el target. [INFERENCIA] El universo de entrenamiento (stream servido) está condicionado a «evento con cuota» y, en spreads/totals, a la línea principal del mercado como umbral: legítimo, pero conviene registrarlo como condicionante. |
| Mezcla con el no-vig | `p_decision = (1−s)·cal(p_adj) + s·fair`, `s = market_shrink = 0,5` (`probabilities.py:303-306`; `daily.py:969-970`; `configs/default.yaml:17`) | [COMPROBADO] **ENTRADA PROHIBIDA** según el principio del operador. Es la única mezcla de valor; afecta a `p_decision`, `estimated_probability` y al stake. |
| Penalización por desacuerdo | `adjusted_edge(..., uncertainty_penalty=0,35)` (`daily.py:982-983`; `default.yaml:26`) | [COMPROBADO] Entrada del mercado en el **edge** y el stake, no en la probabilidad pura. |
| Hiperparámetros | `avg_total` y `scoring_half_life_days` de WNBA justificados «en la línea REAL del mercado» (`src/sqp/sports/registry.py:57-75`) | [INFERENCIA] La línea actúa como umbral de evaluación (legítimo), pero el diagnóstico y la motivación del cambio comparan la proyección con la línea: zona gris que la arquitectura debe cerrar con el protocolo del documento 10. |
| Regla de salida | `prediction_gate` compara `model_probability` pura con el no-vig (`src/sqp/risk/prediction_gate.py:431-435`) | [COMPROBADO] **COMPARACIÓN POSTERIOR LEGÍTIMA**, ya situada en el módulo correcto (`risk/`). |
| Motor congelado opcional | `freeze_model` + `compare_quotes` (`src/sqp/models/independent.py:150-228`; `src/sqp/markets/independent.py:66-73`; `scripts/price_independent.py`) | [COMPROBADO] Ya existe un prototipo de «congelar, luego comparar» con hash SHA-256 y timestamps, **fuera** del run diario. |

**Conclusión del diagnóstico.** [INFERENCIA] La plataforma ya separa correctamente probabilidad pura, umbrales y comparación posterior; la violación del principio está concentrada en dos parámetros (`market_shrink`, `uncertainty_penalty`) y en la ausencia de una frontera estructural que impida que vuelvan a aparecer mezclas. El coste de la reordenación es bajo porque el stream servido ya persiste `model_probability` sin mercado.

**Restricción que manda sobre toda la propuesta.** [COMPROBADO] El pre-registro «el modelo manda» exige que `market_shrink` siga en 0,5 hasta su única medición a 3.402 eventos (`docs/research/2026-08-26-preregistro-el-modelo-manda.md:138, 156, 230`; `scripts/research/measure_el_modelo_manda.py:101`), y el de peso por segmento mide a N = 3.300 hacia marzo de 2027 (`docs/research/2026-10-13-preregistro-peso-mercado-por-segmento.md:210, 218`). Por tanto **nada de lo que sigue cambia `p_decision` ni el stream servido antes de esas fechas**: la arquitectura añade una vía paralela de probabilidad congelada y su evaluación, y deja la vía de decisión intacta hasta que el operador cierre los pre-registros.

---

## 1. Integración en `sports-quant-platform`: siete capas

La cadena actual es ETL → features → modelos → calibración → edge → riesgo → backtesting → auditoría. La propuesta la reparte en siete capas con una **frontera dura** entre la 5 y la 6.

```
 1 adquisición y validación de datos deportivos      sqp.providers (sin odds_api), sqp.storage, sqp.features.temporal
 2 features (as-of, con hora de disponibilidad)       sqp.features, sqp.models.{elo,team_scoring,starters,goalies,park,rest}
 3 modelos especializados por deporte                 sqp.sports.adapters (+ módulos nuevos por deporte)
 4 motor de distribución conjunta / simulación        sqp.models.distributions, sqp.simulation.monte_carlo, reglas de OT
 5 generación y CONGELACIÓN de probabilidades         sqp.models.independent.freeze_model  →  registro congelado (hash+ts)
 ───────────────────────── frontera de importación ─────────────────────────
 6 validación sin mercado                             sqp.backtesting, sqp.calibration.metrics, sqp.evaluation.{bootstrap,feature_blocks}
 7 comparación posterior con el mercado + decisión    sqp.markets, sqp.risk, sqp.audit.clv, sqp.evaluation.{model_vs_market,edge_information}
 8 presentación y trazabilidad                        sqp.audit.report, html_report, evaluation.tipster, Obsidian
```

### 1.1 Adquisición y validación de datos (capa 1)

- Existe: `ResultsStore`, `ScheduleStore`, `StartersStore`, `StarterFIPStore`, capturas con hora de porteros y abridores (`src/sqp/storage/`, `src/sqp/pipeline/{pitcher,goalie}_probables_capture.py`), proveedores ESPN/MLB/NHL (`src/sqp/providers/`).
- [RECOMENDACIÓN] El **calendario** debe venir de una fuente deportiva (`schedule_store`), no del proveedor de cuotas; el proveedor de cuotas pasa a ser un **cliente de la capa 7**. Hoy `daily.py` obtiene los eventos de `OddsAPIClient` (`daily.py:28, 671`): se conserva por compatibilidad hasta que el calendario deportivo cubra todas las ligas, pero se registra como deuda.
- [RECOMENDACIÓN] Adoptar el campo `available_at` de los prompts (Bundesliga, NHL `published_at_utc`; ver `familias/futbol-europa.md` y `familias/mlb-nhl.md`) como contrato de **toda** captura: `features/research.py` ya lo exige para proyecciones externas (docstring, líneas 1-6); hay que elevarlo al camino vivo.
- [RECOMENDACIÓN] Estados de calidad de dato `VERIFICADA / PROVISIONAL / AUSENTE / CONFLICTIVA` (Bundesliga P:95) como columna de las tablas de abridores y porteros; la plataforma ya tiene `data_label` (`domain/models.py:15`) pero no el estado por variable.

### 1.2 Features (capa 2)

- Existe y es correcto: regresión a la media con `prior_games` (`TeamScoringRates`, `StarterRatings`, `GoalieRatings`), ventanas por fecha estrictamente anterior (`features/temporal.py:ordered_games`), descanso (`models/rest.py`), parque (`models/park.py`), FIP (`models/fip.py`).
- [COMPROBADO] Todos los ajustes de la capa `adjust_model_probability` valen 0 (`configs/default.yaml:43-116`) y los pre-registros los han rechazado o acotado (clima MLB rechazado, `project-decisions.md:447`; rachas desactivadas, `default.yaml:65-93`). [RECOMENDACIÓN] **No** reactivar esa capa aditiva sobre probabilidades; las features de los prompts entran en los **parámetros de la distribución** (λ, μ, σ), no como sumandos a p.

### 1.3 Modelos especializados por deporte (capa 3)

Compartido: `SportAdapter` (`src/sqp/sports/base.py:29`), Elo (`models/elo.py`), registro de parámetros por familia y liga (`registry.py:FAMILY_PARAMS`, `LEAGUE_OVERRIDES`, `configs/leagues/*.yaml`).

Especializado (mapa detallado en §2): fuerza ofensiva/defensiva log-lineal para fútbol, ritmo × eficiencia para baloncesto, EPA/éxito para fútbol americano, cadena servicio-resto para tenis, abridor + bullpen para MLB, portero + estados de juego para NHL.

### 1.4 Motor de distribución conjunta o simulación (capa 4)

- Existe: rejilla exacta Poisson/NB con Dixon-Coles, `score_rho` y `dispersion_k` (`models/distributions.py:204-309`), Normal independiente para margen y total (`:32-68`), Monte Carlo analítico no usado en producción (`simulation/monte_carlo.py`).
- Falta [COMPROBADO en los informes de familia]: distribución conjunta margen-total en la familia Normal; reglas de prórroga, extras, OT 3v3 + SO, corredor automático; mercados derivados (team totals, mitades, BTTS, hándicaps con push coherente) para todos los deportes; tenis entero.
- [RECOMENDACIÓN] Un único contrato de salida por evento: una **distribución conjunta de marcador por período** (`score_reg`, `score_final`, `score_for_settlement`, siguiendo NHL:53) de la que se derivan todos los mercados. Es lo que `FrozenScoreModel._grid` ya hace para la familia de conteo (`independent.py:100-114`).

### 1.5 Generación y congelación (capa 5)

- La probabilidad congelada es el **objeto canónico** del sistema. Se produce **sin** haber leído ninguna cuota del día. Detalle del hash y el timestamp en §4.

### 1.6 Validación sin mercado (capa 6)

- Existe: `walk_forward_backtest` con `bias`, Brier, log loss, ECE, tabla de fiabilidad (`backtesting/engine.py:17-40, 42`), `tune_home_advantage` / `tune_dc_rho` / `tune_market_param` con holdout de origen rodante y guardarraíles (`backtesting/tuning.py:143, 201, 271; 212-227`), `validate_oos.py` con parámetros congelados, `compare.py` (sim vs ML), `feature_blocks.evaluate_blocks` (ablaciones pareadas), `bootstrap.cluster_bootstrap_ci`.
- Protocolo completo en `10-protocolo-de-validacion.md`.

### 1.7 Comparación posterior con el mercado (capa 7)

- Existe y está bien situado: `prediction_gate` (`risk/prediction_gate.py`), `model_vs_market`, `edge_information` (escalera), `audit/clv.py`, `markets/vig.py`, `markets/edge.py`, `risk/kelly.py`, `degradation.py`.
- [RECOMENDACIÓN] Este módulo **solo lee probabilidades congeladas** (por `prediction_id`) y cuotas con timestamp ≥ `frozen_at`. `compare_quotes` ya impone `frozen_at <= now < starts_at` y rechaza cotizaciones futuras o caducadas (`markets/independent.py:72-73, 92-94`); ese contrato se generaliza al run diario.
- `market_shrink` y `uncertainty_penalty` viven aquí, como **política de decisión** explícitamente etiquetada, nunca como parte de la probabilidad. Su valor lo decide el operador tras los pre-registros vigentes (§0).

### 1.8 Presentación y trazabilidad (capa 8)

- Existe: `audit/report.py`, `audit/html_report.py`, `evaluation/tipster.py`, vistas por vigencia (`evaluation/labels.py`).
- [RECOMENDACIÓN] Toda vista muestra, separadas y con nombre, las seis cantidades que exige `.claude/rules/betting-output-rules.md` (estimada, implícita, edge, hit rate observado, ROI esperado, ROI realizado) y añade `prediction_id`, `frozen_at`, `model_version` y el estado `VALIDADO / EXPLORATORIO / INCOMPLETO` del prompt, que mapea a `model_confidence` de `independent.py:136` y a `reliability_warning` (`sports/base.py:76`).

---

## 2. Mapa: componente de los prompts → módulo actual o nuevo

Las fases se citan con la numeración común de los 21 prompts (21 fases; `familias/*.md §1`). «Existe» cita la ruta; «Nuevo» propone una ruta bajo `src/sqp/`.

| Componente del prompt (fase) | Deportes | Módulo actual (ruta) | Estado | Módulo nuevo o cambio |
|---|---|---|---|---|
| Identificación, `as_of`, huso, calendario (F1) | todos | `storage/schedule_store.py`, `storage/results_store.py`, `providers/date_window.py` | parcial: el universo lo da la API de cuotas (`daily.py:671`) | `providers/schedule_*` por deporte; `daily` consume `ScheduleStore` |
| Jerarquía de fuentes, `available_at`, estados de dato (F1-F2) | todos | `features/research.py:1-6` (solo investigación); capturas con hora de abridores/porteros | parcial | columna `available_at` + `data_state` en `storage/{starters,goalies,pitchers_capture}.py` |
| Ataque/defensa log-lineal con shrinkage `w = n/(n+τ)` (F2-F5) | fútbol | `models/elo.py` + `home_scoring_bonus`, `tilt_scale` (`adapters.py:126-143`) | difiere: fuerza vía Elo, no log-lineal | `models/soccer_strength.py` (Poisson log-lineal ataque/defensa/localía, MLE con decaimiento) |
| Ritmo × eficiencia, `Eff = Off×Def/League`, `μ = Poss×Eff/100 ± HCA/2` (F10-F13) | baloncesto | `models/team_scoring.py` (tasas regresadas), Elo → margen (`distributions.py:394`) | difiere: sin posesiones ni eficiencia | `models/basketball_efficiency.py` (posesiones por fórmula de FTA, ORtg/DRtg ajustados) |
| EPA/éxito por jugada, QB escenarios A/B, SOS jerárquico (F3-F8) | NFL, NCAAF | `FootballAdapter` = Normal + Elo (`adapters.py:168`) | falta | `models/football_epa.py`; requiere datos play-by-play (ver `08 §5`) |
| Cadena saque-resto, `Hold(p)`, DP de sets BO3/BO5, tie-break (F6-F12) | ATP, WTA | `TennisAdapter` Elo escalar (`adapters.py:318-338`) | falta por completo | `models/tennis_markov.py` (Hold(p), DP de set/partido, superficie), `sports/adapters.TennisAdapter` lo consume |
| Abridor xFIP/FIP, IP esperadas, bullpen (F5-F8) | MLB | `models/starters.py`, `models/fip.py`, `pitcher_bound 0,05` (`ratings.yaml:22-23`) | parcial: sin bullpen ni IP esperadas | `models/bullpen.py`; `features/mlb.py` añade IP esperadas |
| Portero GSAx/SV%, TOI, estados de juego (F4-F9) | NHL | `models/goalies.py` (`goalie_beta 0,0`, pre-registro pendiente) | parcial e inactivo | nada hasta ejecutar `--pre`; estados PP/PK como `models/hockey_states.py` tras el portero |
| Localía, sede neutral, altitud, viaje, descanso (F11-F12) | todos | `elo_home_adv`, `home_scoring_bonus`, `models/rest.py`, `features/rest_form.py` | parcial; coeficientes aditivos a 0 | parámetro `neutral_site` en `Event`; altitud/viaje solo como **parámetro de λ** pre-registrado |
| Clima, parque (F12) | MLB | `models/park.py`, `features/weather.py` (`weather.enabled false`) | parque activo; clima rechazado (`project-decisions.md:447`) | ninguno |
| λ / μ por equipo (F13) | todos | `adapters._rates`, `NormalMarginAdapter.estimate` | existe | sin cambio de interfaz: los módulos nuevos devuelven (λ_h, λ_a) o (μ, σ) |
| Distribución conjunta: Poisson, Dixon-Coles, NB, bivariante, bootstrap de residuos (F14) | todos | `models/distributions.py` (`dc_rho`, `dispersion_k`, `score_rho`), `simulation/monte_carlo.py` | parcial: Normal independiente margen/total | `models/joint_normal.py` (margen-total bivariante); `simulation` para dependencias no analíticas |
| Prórroga, extras, OT+SO, playoffs (F15-F16) | NFL, NCAAF, NBA, NHL, MLB, copas | `tie_adds_goal` + reescalado NHL (`distributions.py:219-238`, informes de familia) | parcial (solo NHL, aproximado) | `models/overtime_rules.py` con `ruleset_id` por competición y temporada |
| Mercados: 1X2/ML, spread, total, team totals, BTTS, mitades, asiáticos con push (F15-F18) | todos | `distributions.poisson_match_probs`, `markets/settlement_math.py` (asiáticos, push) | parcial: sin team totals, BTTS, mitades | `models/market_derivation.py` que lea solo la rejilla congelada |
| Congelación con hash y `locked` (F19) | todos | `models/independent.freeze_model` (offline) | existe fuera del run | cablear en `pipeline/estimate.py` (§4) |
| Confianza y estados VALIDADO/EXPLORATORIO/INCOMPLETO (F20) | todos | `reliability_warning`, `data_label`, `model_confidence: UNVALIDATED` (`independent.py:136`) | parcial | enum `ModelStatus` en `domain/models.py`; lo fija la capa 6 por (liga, mercado, versión) |
| Validación: backtest, Brier, log loss, ECE, tests de coherencia (F20) | todos | `backtesting/engine.py`, `calibration/metrics.py`, `tests/test_independent_pricing.py:78` (conservación de masa) | existe; faltan MAE/RMSE de marcador | `10-protocolo-de-validacion.md` |
| EV, break-even con push, CLV (F19-F21) | todos | `markets/edge.py`, `risk/kelly.py`, `audit/clv.py` | existe; la definición de edge difiere de los prompts (`familias/futbol-america-y-femenino.md §2.5`) | capa 7; documentar ambas definiciones |
| Ranking y reporte (F21) | todos | `evaluation/tipster.py`, `audit/report.py` | existe | añadir `prediction_id`, estado y las seis cantidades separadas |

[COMPROBADO] De los 21 prompts, ninguno usa el mercado como entrada (informes de familia, §5 de cada uno). [COMPROBADO] De la plataforma, solo `market_shrink` y `uncertainty_penalty` lo hacen (tabla de §0).

---

## 3. Qué compartir y qué especializar

### Compartir (una sola implementación, probada una vez)

1. **Contrato temporal**: `ordered_games`, recorte `< ref_date` (`features/temporal.py:9`; `AdjustmentContext.ref_date`, `probabilities.py:319-325`), `available_at`.
2. **Regularización**: `w = n_eff/(n_eff+τ)` ya está implementada como `prior_games`/`prior_shots` en `team_scoring.py`, `starters.py`, `goalies.py`. [RECOMENDACIÓN] Extraerla a `models/shrinkage.py` para que τ se estime (no se fije) con el mismo procedimiento en todos los deportes, como piden los 21 prompts.
3. **Elo** como baseline y como una de las features de fuerza (no como el único motor): `models/elo.py`.
4. **Rejilla de marcador y derivación de mercados**: `distributions.py` + `settlement_math.py` (push, asiáticos, cuartos).
5. **Congelación, hash, versión**: `models/independent.py` (§4).
6. **Métricas y bootstrap por clúster**: `calibration/metrics.py`, `evaluation/bootstrap.py`.
7. **Esquema de salida**: un solo `ValidationStatus` (`VALIDADO/EXPLORATORIO/INCOMPLETO`), una sola etiqueta de break-even, una sola numeración de fases. [COMPROBADO] Hoy los prompts divergen en estas tres cosas (`familias/baloncesto.md §2`, `familias/futbol-america-y-femenino.md §2.2`).
8. **Reglamento como datos**: `ruleset_id` + fecha por competición (puntos, OT, descensos, formato), no constantes en código.

### Especializar (un módulo por deporte, con su propio pre-registro)

| Deporte | Unidad de tasa | Distribución | Variable ancla | Dependencia entre marcadores |
|---|---|---|---|---|
| Fútbol | goles/90' | Poisson log-lineal + Dixon-Coles (`dc_rho` por liga) | ataque/defensa, once, portero | `dc_rho` (existe), `score_rho` (existe, 0) |
| Baloncesto | puntos/posesión | Normal bivariante margen-total o bootstrap de residuos | ritmo, ORtg/DRtg | **nueva**: correlación margen-total |
| Fútbol americano | puntos/drive o EPA | Normal/discreta con números clave + OT por reglamento | QB, EPA ofensivo/defensivo | **nueva** |
| Tenis | p(punto al saque) por superficie | Markov/DP de juego-set-partido | saque/resto, superficie, formato BO3/BO5 | n/a |
| MLB | carreras/9 entradas | NB con `dispersion_k` (existe) + extras | abridor (existe), bullpen (nuevo), parque (existe) | `score_rho` o gamma compartida (MLB v2:138) |
| NHL | goles/60' por estado | Poisson (medido 1,01, `registry.py:77`) + OT/SO | portero (pre-registro pendiente) | `score_rho` |

[INFERENCIA] Las familias `basketball`/`football` comparten `NormalMarginAdapter` y `baseball`/`hockey`/`soccer` comparten `PoissonAdapter` (`adapters.py:29, 83`). Se mantiene esa herencia: los módulos especializados solo sustituyen `_rates`/la construcción de (μ, σ), no la derivación de mercados.

---

## 4. Cómo se congela y versiona una probabilidad

### 4.1 Lo que ya existe y se reutiliza

- `freeze_model(spec, now)` valida campos estrictos (rechaza cualquier clave ajena al modelo deportivo: `independent.py:155-156`, test `tests/test_independent_pricing.py:51`), exige `sporting_as_of <= now < starts_at` (`:171-174`), que ninguna fuente tenga `as_of` posterior al corte (`:181-182`), y produce `model_id = sha256("independent-v1\n" + frozen_at + "\n" + canonical_json(spec) + grid_bytes)` (`:225-228`). El objeto es `frozen=True` y no expone referencias mutables (`:57-68`).
- `compare_quotes` solo acepta cotizaciones con `frozen_at <= now < starts_at` y edad ≤ `max_age_minutes` (`markets/independent.py:72-73, 92-94`); test de que la comparación no puede alterar el modelo congelado (`tests/test_independent_pricing.py:126, 212`).
- Huellas ya usadas en el proyecto: `feature_shadow.digest` (SHA-256 de ficheros) y `runtime_versions` (`evaluation/feature_shadow.py:31-39`); `_escribir_sidecar_sha256` para artefactos ML (`models/ml_train.py:96`); `git rev-parse HEAD` registrado en los `--pre` de los pre-registros (`docs/research/2026-09-26-preregistro-portero-nhl.md:685-686`).

### 4.2 Registro congelado propuesto (por evento y run)

[RECOMENDACIÓN] Un registro inmutable `data/predictions/frozen/frozen_{league}_{YYYYMM}.jsonl` (append-only, escritura atómica con `storage/atomic.py`) con:

```
schema_version      1
prediction_id       sha256(schema_version | league | event_id | period | sporting_as_of
                           | model_version | params_hash | inputs_hash | canonical_json(probabilidades))
frozen_at           ISO-8601 UTC (reloj del run, después de calcular y antes de leer cuotas)
sporting_as_of      ISO-8601 UTC: instante hasta el que se admite información deportiva
starts_at           ISO-8601 UTC del evento
model_version       entero; cambia con cualquier cambio de código o fórmula del adaptador
params_hash         sha256 de los parámetros resueltos de la liga (registry + yaml) en JSON canónico
inputs_hash         sha256 de los insumos deportivos usados (ratings al cierre del día anterior,
                    abridor/portero con available_at, parque, descanso)
code_rev            git rev-parse HEAD; runtime_versions (python, numpy, scipy, pandas)
distribution        parámetros de la distribución conjunta (λ/μ/σ/ρ/k) y, para conteo, la rejilla o su hash
probabilities       todas las caras que el modelo sabe valorar SIN línea de mercado: ML/1X2, team totals,
                    y una CDF discreta de margen y de total (percentiles) para evaluar cualquier umbral después
model_status        VALIDADO | EXPLORATORIO | INCOMPLETO (lo fija la capa 6 por versión)
data_state          por variable: VERIFICADA | PROVISIONAL | AUSENTE | CONFLICTIVA
```

Invariantes verificables (tests):

1. `sporting_as_of <= frozen_at < starts_at` (ya en `freeze_model`).
2. Recalcular `prediction_id` desde el registro reproduce el mismo hash (determinismo; test análogo a `tests/test_independent_pricing.py:42`).
3. Ninguna fila del stream servido o de cuotas asociada a un `prediction_id` tiene `captured_at < frozen_at`.
4. Un `prediction_id` nunca se sobreescribe; una re-estimación pregame (skill `pregame-refresh`) produce **otro** `prediction_id` con `supersedes = <id anterior>`.
5. El par (`model_version`, `params_hash`) identifica al **campeón**; `champion-challenger` exige ya hashes de ambos objetos (`.claude/skills/champion-challenger/SKILL.md:29-38`).

### 4.3 Dónde encaja en el run diario sin romper los pre-registros

[RECOMENDACIÓN] Dividir `run_league` en dos funciones con módulos distintos:

- `pipeline/estimate.py::estimate_league(league, day, schedule)` → lista de registros congelados. Importa adaptadores, modelos y stores deportivos. **No importa** `providers.odds_api`, `storage.odds_store`, `markets`, `risk`.
- `pipeline/price.py::price_league(frozen, odds)` → lo que hoy hace `daily.py:888-1041` a partir de `model_probability`: umbrales, no-vig, calibración, `p_decision`, edge, stake, gate.

La CDF de margen y total guardada en el registro permite evaluar después **cualquier** línea de mercado sin volver al modelo: P(margen > −L) se lee de la CDF congelada. Así `_pick_main_lines` deja de ser una entrada del adaptador y pasa a ser una consulta a la probabilidad congelada (UMBRAL LEGÍTIMO por construcción).

Mientras «el modelo manda» y «peso por segmento» no se midan, `price_league` sigue produciendo byte a byte las mismas columnas servidas (`market_shrink 0,5`, `uncertainty_penalty 0,35`); el único cambio visible es que cada fila servida lleva `prediction_id` y `frozen_at`. [INFERENCIA] Añadir columnas al stream servido es compatible con el guard de unión de columnas de `ServedStore` (`served_store.py:717-720`), pero debe revisarse contra `tests/test_served_store*` y los lectores (`calibration/data.py`) antes de desplegar.

---

## 5. Cómo se impide por construcción que entre el mercado

### 5.1 Fronteras de importación

[COMPROBADO] Hoy no existe ningún test que fije qué módulos pueden importar a cuáles: la búsqueda de tests de frontera (`forbidden|boundary|must not import`) en `tests/` no devuelve ninguno, y `tests/test_audit_pipeline_isolation.py` aísla rutas de salida, no importaciones. `models/independent.py` declara en su docstring que «never imports odds providers, risk or live state» (`:2`), pero nada lo verifica.

[RECOMENDACIÓN] Definir el grafo permitido en un fichero de datos (`configs/architecture.yaml` o constante en el test) y comprobarlo con un recorrido AST de `src/sqp/`:

```
capa_deportiva  = {sqp.providers.(espn_*, mlb_statsapi, nhl_api, date_window, base, synthetic),
                   sqp.storage.(results_store, schedule_store, starters, starter_fip, goalies, pitchers_capture,
                                feature_store, atomic, lock),
                   sqp.features.*, sqp.models.*, sqp.sports.*, sqp.simulation.*, sqp.pipeline.estimate}
capa_mercado    = {sqp.providers.(odds_api, odds_cache), sqp.storage.odds_store, sqp.markets.(odds, vig, edge,
                   line_movement, independent), sqp.risk.*, sqp.audit.(clv, clv_movement, intraday_gate),
                   sqp.evaluation.(model_vs_market, edge_information), sqp.pipeline.(price, closing_capture,
                   intraday_scan, revalidation, daily)}

REGLA 1  ningún módulo de capa_deportiva importa (ni estática ni dinámicamente) un módulo de capa_mercado.
REGLA 2  sqp.markets.settlement_math es matemática de líneas sin datos de mercado: se permite en capa_deportiva
         (ya lo usa independent.py:21) pero debe seguir sin importar nada de capa_mercado.
REGLA 3  sqp.calibration.* puede leer el stream servido (desenlaces y p pura) pero no implied_probability_novig
         ni price_decimal: se comprueba por nombre de columna en calibration/data.py.
```

Tests concretos (`tests/test_architecture_boundaries.py`, nuevo):

1. **Estático**: `ast.walk` de cada fichero de capa deportiva; falla si un `Import`/`ImportFrom` resuelve a capa de mercado. Cubre también importaciones dentro de funciones (hoy `evaluation/compare.py:36` importa `pipeline.daily` dentro de `_sim_probs`: ese patrón quedaría prohibido para la capa deportiva).
2. **Dinámico**: en un subproceso limpio, `import sqp.pipeline.estimate` y `import sqp.sports.registry`; asertar que `sys.modules` no contiene `sqp.providers.odds_api` ni `sqp.storage.odds_store`. Es la misma técnica que `tests/test_audit_pipeline_isolation.py:28-47` usa con subprocesos.
3. **Contrato de datos**: `EstimatedProbabilities` y el registro congelado no admiten campos cuyo nombre contenga `implied`, `novig`, `price`, `odds`, `consensus`, `closing`, `clv` (extensión de `tests/test_independent_pricing.py:51`).
4. **Temporal**: para cada fila servida con `prediction_id`, `frozen_at <= captured_at` de toda cotización usada; test sobre un run demo (`SyntheticProvider`).
5. **Parámetros**: `tune_market_param` y los scripts de `scripts/research/` que optimicen un parámetro de capa deportiva deben declarar su función objetivo; el test de contrato comprueba que ninguna función objetivo lee `implied_probability_novig`/`price_decimal` (lista blanca de columnas, como ya hace `tests/test_config_yaml_keys.py` para claves del yaml).

### 5.2 Fronteras de configuración

- `market_shrink`, `uncertainty_penalty`, `anomaly_*`, `low_book_penalty`, `books_spread_*`, `line_movement_*` se mueven del bloque `risk` a un bloque `market_policy` de `configs/default.yaml` con un comentario que los declara **política de decisión posterior a la congelación**. [COMPROBADO] `tests/test_config_yaml_keys.py` ya falla si una clave del yaml no tiene consumidor (`default.yaml:148-149`): se reutiliza para que ningún parámetro de `market_policy` sea leído por un módulo de la capa deportiva.
- Los parámetros de liga (`configs/leagues/*.yaml`) solo admiten claves de la capa deportiva; el test de claves rechaza `market_shrink` por liga (hoy no existe override: `preregistro-peso-mercado:` «No existe ningún override de `market_shrink` por liga»).

### 5.3 Lo que esto NO cambia

- No se toca `p_decision`, `market_shrink` ni `uncertainty_penalty` antes de que el operador cierre los pre-registros de §0.
- No se cambia la unidad ni la composición del stream servido que miden «el modelo manda» (`preregistro-el-modelo-manda.md:272-282`) y «peso por segmento».
- `prediction_gate` sigue siendo la regla de salida (`default.yaml:283-284`), y seguirá leyendo `model_probability`, que es exactamente la probabilidad congelada.

---

## 6. Secuencia de adopción (sin fechas; el orden sí importa)

1. Test de fronteras (§5.1) en modo **informe** (lista de violaciones actuales) → corregir las que no dependen de pre-registros.
2. `prediction_id` + `frozen_at` + `model_version` + `params_hash` en el stream servido y el registro JSONL (§4.2), sin cambiar ninguna probabilidad.
3. Separar `estimate_league` / `price_league` (§4.3) con prueba de **identidad byte a byte** del CSV servido antes y después (el proyecto ya usa ese criterio: `default.yaml:152-153`, line shopping).
4. Protocolo de validación sin mercado (`10-protocolo-de-validacion.md`) ejecutándose sobre el registro congelado.
5. Escalera de modelos por deporte (`08-plan-de-optimizacion.md`), cada escalón como challenger con su pre-registro.
6. Cuando «el modelo manda» y «peso por segmento» se hayan medido, el operador decide la política de `market_policy`; la arquitectura ya la tiene aislada.
