# 05 — Informe de riesgos (fase 2)

Fecha: 2026-11-10. Escalón Fable. Riesgos metodológicos, sesgos, sobreajuste y fugas (temporales y de mercado) de los 21 prompts y de la plataforma, ordenados por severidad. Cada riesgo lleva: riesgo concreto, evidencia (cita verificada), impacto. Etiquetas: [COMPROBADO] [INFERENCIA] [HIPÓTESIS] [RECOMENDACIÓN]. Severidades: CRÍTICA (contradice el principio del operador o invalida una medición), ALTA (sesgo sistemático con efecto en probabilidades o stakes), MEDIA (sesgo acotado o riesgo latente), BAJA (redacción, trazabilidad).

Ninguna recomendación de este informe propone tocar `configs/` ahora: la vigencia de `market_shrink` la decide la medición pre-registrada «el modelo manda» (`docs/research/2026-08-26-preregistro-el-modelo-manda.md`, una sola medición al alcanzar 3.402 eventos, líneas 154-158 y 328-329) y, después de ella, el pre-registro por segmento (`docs/research/2026-10-13-preregistro-peso-mercado-por-segmento.md`, N = 3.300, T0 = resultado de MM, líneas 43-52 y 210-220).

## Resumen ordenado

| # | Severidad | Riesgo | Dónde |
|---|---|---|---|
| R1 | CRÍTICA | La probabilidad que decide, se sirve y se publica contiene un 50 % de mercado (`market_shrink`), y la probabilidad de stake incorpora además la distancia al mercado (`uncertainty_penalty`) | plataforma |
| R2 | CRÍTICA | Parámetros elegidos por ROI realizado sobre cuotas capturadas: `park_bound` (parámetro de modelo), `max_plausible_edge` y `uncertainty_penalty` (decisión) | plataforma |
| R3 | ALTA | Selección in-sample del valor desplegado en todos los `tune_*` (el holdout valida el procedimiento, no el valor) y sin corrección de multiplicidad entre ligas y parámetros | plataforma |
| R4 | ALTA | El monitor de degradación compara la MEZCLA contra el mercado, no el modelo puro: un detector diluido que además pausa por ROI realizado | plataforma |
| R5 | ALTA | Supuestos de distribución contradichos o sin comprobar: MLB `f=0,30`/`k=0,15` del prompt; Normal independiente en baloncesto y fútbol americano; localía por dos canales | prompts y plataforma |
| R6 | MEDIA | Calibradores: entrenamiento conforme (pre-blend, contra resultados) pero con selección por cobertura de cuotas, degradación a solo-liquidadas y método `auto` por grupo sobre muestras pequeñas | plataforma |
| R7 | MEDIA | Fugas temporales residuales: priors elegidos con datos del propio periodo de evaluación; xG revisado retroactivamente; ratings «de temporada»; porteros confirmados tarde | prompts y plataforma |
| R8 | MEDIA | Los prompts son especificaciones no ejecutables con alto riesgo de sobreajuste (21 fases, >100 grados de libertad) y sin umbrales numéricos de aceptación | prompts |
| R9 | MEDIA | Encompassing: el modelo puro aporta información condicional ≈ 0 frente al consenso; cumplir el principio tiene un coste medido | plataforma |
| R10 | BAJA | Ambigüedades de redacción que permitirían optimizar contra el mercado en validación (EPL:27, MLB:14), cláusulas condicionales (Serie A:21, Ligue 1:19), «mercado de fichajes» (LaLiga:152) | prompts |
| R11 | BAJA | Definiciones de edge no comparables entre prompts y plataforma; `.env` no verificable | ambos |

## R1 — CRÍTICA. El mercado entra en la probabilidad de decisión y en la de stake

**Riesgo.** La probabilidad con la que se calcula el edge, se dimensiona Kelly, se seleccionan los picks y se construyen los tiers del tipster es una mezcla al 50 % con la probabilidad sin vig del consenso. La probabilidad del modelo existe y se guarda, pero no es la que decide.

**Evidencia.**
- [COMPROBADO] `configs/default.yaml:17`: `market_shrink: 0.5  # blend model prob toward no-vig market: p=(1-s)*model+s*market`.
- [COMPROBADO] `src/sqp/pipeline/probabilities.py:303-305`: `p_used = (1-shrink)*p_model + shrink*fair`; `p_decision = (1-shrink)*p_cal + shrink*fair`. Llamada en `src/sqp/pipeline/daily.py:969-970`; `edge(p_decision, price)` en `daily.py:974`.
- [COMPROBADO] `uncertainty_penalty: 0.35` (`default.yaml:26`): `gap = abs(probability − market_probability); penalty += gap·uncertainty_penalty` (`src/sqp/markets/edge.py:70-71`) y el resultado se pliega en `effective_probability` (`edge.py:90`), que es lo que recibe Kelly (`daily.py:1002-1006`) y la elegibilidad (`daily.py:1014-1017`).
- [COMPROBADO] El tipster clasifica con `labels.decision_prob` (la calibrada = mezcla) porque la cruda «era una probabilidad descartada por el sistema» (`src/sqp/evaluation/tipster.py:132-136`).
- [COMPROBADO] La probabilidad pura sí se persiste: `model_probability` y `adjusted_probability` en el stream servido (`daily.py:1031-1032`) y en `BetCandidate` (`daily.py:1126`); la columna `market_shrink` viaja por fila (`daily.py:1040-1042`).
- [COMPROBADO] Los 21 prompts prohíben exactamente esto (NHL:6, ATP:37, NFL:24, EPL:27, MLB:14, NBA:19).

**Impacto.** [COMPROBADO] Medido: con `market_shrink: 0` habría 1.824 picks más y el ROI de la selección pasa de −3,02 % a −10,85 % (`Obsidian/Tareas.md:103`); la mezcla **mejora** el Brier del modelo puro (0,2398 puro frente a 0,2308 del mercado; `Tareas.md:109`). Es decir, el incumplimiento del principio es, hoy, lo que sostiene la calidad probabilística servida. Cumplirlo sin medir primero empeoraría la probabilidad servida según la evidencia disponible; por eso existe el pre-registro MM y por eso no se propone cambio alguno ahora. El riesgo metodológico no es el de perder dinero sino el de **no saber qué predice el modelo**: todo lo que se publica, audita y liquida con `estimated_probability`/`calibrated_probability` mide la mezcla.

## R2 — CRÍTICA. Parámetros elegidos por ROI realizado sobre cuotas

**Riesgo.** Un parámetro del modelo que entra en λ fue aceptado porque mejoraba el ROI contra cuotas capturadas. Es optimización contra el mercado (prohibida por el principio) y, además, sobreajuste a una temporada y a un único snapshot de cuotas.

**Evidencia.**
- [COMPROBADO] `configs/leagues/ratings.yaml:25-30`: `park_bound: 0.10` «ENABLED 2026-06-22: on captured odds it flips MLB totals from -17.1% to +2.8% ROI (held-out -15.9% -> +3.8%/+7.0%) and lifts overall MLB ROI +2.4% -> +7.8%. 0.10 chosen over 0.20… One season, single-snapshot proxy». El factor multiplica el total esperado en λ (`src/sqp/sports/adapters.py:190-221`).
- [COMPROBADO] `configs/default.yaml:11-16`: `max_plausible_edge` bajado 0,15 → 0,075 «on 2026-06-22 OOS evidence: on captured odds MLB test ROI +0.41% -> +2.42%».
- [COMPROBADO] `default.yaml:18-26`: `uncertainty_penalty` «ENABLED 2026-06-21 after a walk-forward OOS over captured odds (1654 bets, mostly MLB): aggregate realized ROI -0.74% -> +0.37%… in-sample on parameters».
- [COMPROBADO] El arnés de ROI «replays market-shrink, edge penalties, Kelly staking» (`src/sqp/backtesting/roi_engine.py:12-13`): el objetivo optimizado dependía ya de la mezcla.
- [COMPROBADO] En contraste, los parámetros activados después por pre-registro se eligieron por log loss frente a resultados: descanso NBA (`ratings.yaml:35-40`), tilt NHL (`ratings.yaml:45-50`), abridor MLB (`ratings.yaml:17-23`). La práctica cambió a partir de 2026-09; los tres parámetros de junio son herencia del «project 2».

**Impacto.** `park_bound` contamina la independencia del modelo MLB de totales (el único de los tres que entra en la probabilidad del modelo). `max_plausible_edge` y `uncertainty_penalty` afectan a la decisión, no a la estimación; su valor está ajustado al mercado de 2026 y a MLB. [INFERENCIA] Re-validar `park_bound` por log loss frente a resultados sería un cambio de régimen del modelo MLB y exige addendum en MM antes de medir; queda para después de la medición. [HIPÓTESIS] Es posible que `park_bound 0,10` también mejore el log loss (el parque es información deportiva legítima); el problema es el criterio de elección, no la variable.

## R3 — ALTA. Selección in-sample y multiplicidad en los `tune_*`

**Evidencia.**
- [COMPROBADO] `src/sqp/backtesting/tuning.py:188-193`: «The holdout validates the PROCEDURE, not this value: the recommended point is the full-sample argmin, test blocks included, so the SELECTION IS IN-SAMPLE either way (audit 2026-08-31, N4-A-5)». Igual en `tune_market_param` (`tuning.py:251, 258-263`).
- [COMPROBADO] Valores desplegados por esa vía: `dc_rho −0,2` y `elo_home_adv 15` en EPL/Bundesliga/Serie A, `elo_home_adv 30` + split en MLS, `150` en NCAAF (`ratings.yaml:10-15, 31-33, 41-42, 51-53`); `scoring_half_life_days 60` en WNBA (`registry.py:73-74`, `tune_market_param`, mejora OOS +0,0289 sobre 4 folds con margen 0,0020).
- [INFERENCIA] Con ~23 ligas × varios parámetros × rejillas, y un margen fijo de 0,002 por contraste, no hay corrección de multiplicidad: la familia de contrastes de tuning no está protegida como sí lo está el `prediction_gate` (Bonferroni K = 69, `default.yaml:266-269`).

**Impacto.** Sobreajuste moderado de los overrides por liga; el margen 0,002 y la exigencia de ≥ 200 partidos (`tuning.py:196`) lo acotan. [COMPROBADO] Hay evidencia de prudencia explícita: NBA eligió 180 por precedente y no por argmin (`registry.py:87-89`); `dc_rho` en cuatro ligas se rechazó (`Tareas.md:115`); `score_rho` se rechazó por fallar en un mercado (`docs/research/2026-08-26-resultado-correlacion-marcadores.md:17-30`).

## R4 — ALTA. El monitor de degradación mide la mezcla, no el modelo

**Evidencia.**
- [COMPROBADO] `src/sqp/risk/degradation.py:71-72`: `p_model = _num(df, "estimated_probability")`, `p_market = _num(df, "implied_probability_novig")`. `estimated_probability` es `p_used`, la mezcla cruda al 50 % (`daily.py:1033`; `probabilities.py:304`).
- [COMPROBADO] Regla: pausa si `brier_model > brier_market + 0,01` o `roi_flat < −0,15`; reanuda con histéresis (`degradation.py:96-98, 123-132`; `default.yaml:297-303`).
- [COMPROBADO] El `prediction_gate`, en cambio, usa `model_probability` «porque ambas [mezcla y calibrada] contienen el precio dentro: compararlas con el mercado no diría si el modelo aporta algo propio» (`src/sqp/risk/prediction_gate.py:10-14`).

**Impacto.** [INFERENCIA] Con `s = 0,5` el Brier de la mezcla está mecánicamente cerca del Brier del mercado (la mezcla es convexa), así que `brier_worse_than_market` casi nunca puede dispararse por debilidad del modelo: el monitor es un detector diluido. La rama `roi_pause` sí actúa, pero es retroalimentación del mercado (ROI realizado) sobre qué cortes llevan stake. No altera probabilidades (los cortes pausados se siguen estimando, `default.yaml:214-219`), por lo que no rompe la congelación; pero la plataforma tiene dos vigilantes con dos columnas distintas y solo uno responde a la pregunta «¿predice el modelo?». [RECOMENDACIÓN, diferida] Medir el monitor también sobre `model_probability` (es medición, no cambio de política; las pausas no alteran las filas servidas que mide MM).

## R5 — ALTA. Supuestos de distribución contradichos o sin comprobar

Detallado en `04-auditoria-matematica.md`. Resumen con evidencia:
- [COMPROBADO] Prompt MLB: `k = 0,15` frente a `1/3,8 = 0,263` equivalente medido (`registry.py:35-41`); `f = 0,30` implica ρ ≈ 0,12 frente a −0,004 medido (`distributions.py:123-126`). Colas subdispersadas y dependencia positiva inexistente.
- [COMPROBADO] Baloncesto y fútbol americano: margen y total son Normales independientes (`distributions.py:32-70`); NBA:195 y NFL:36 lo prohíben; sin empate en NFL (`distributions.py:43-44`) ni números clave; sigma único en NCAAF (20, `registry.py:97`).
- [COMPROBADO] Localía por dos canales (`elo.py:70-77`; `adapters.py:141`), validado solo uno (`tuning.py:150-158`), contra EPL:174/LALIGA:134/BUNDESLIGA:228.
- [COMPROBADO] NCAAB/WNCAAB heredan `points_per_elo` y `elo_home_adv` de la familia (`registry.py:29-31, 95-96`) contra WNCAAB:35.
- [INFERENCIA] 50/50 en empates (WNCAAB:351; h2h de la plataforma en NHL, `distributions.py:251`) sesga contra el favorito; acotado.

**Impacto.** Error de modelo, no de mercado: sobreconfianza en colas (MLB prompt), `P(push)` mal estimada en NFL, team totals imposibles en Normal. El pre-registro MM lo mide tal cual está; cualquier corrección es cambio de régimen posterior a la medición.

## R6 — MEDIA. Calibración: conforme en lo esencial, con tres riesgos residuales

**Lo que está bien.** [COMPROBADO] El calibrador se aplica a la creencia PRE-blend (`probabilities.py:277-283, 299-302`) y se entrena sobre `adjusted_probability` frente al resultado (`src/sqp/calibration/data.py:69`), con `implied_probability_novig` presente en el esquema «aunque el entrenamiento no la use» (`data.py:31-34`). Fuente: liquidadas ∪ stream servido deduplicado, donde el stream es «EVERY priced market side… unbiased per-event sample» (`data.py:12-19, 207-227`; `daily.py:1018-1021`). Esto **refuta** la hipótesis de la fase 1 (familia `baloncesto.md` §5; individual NBA §9) de que los calibradores se entrenan sobre picks seleccionados por edge: la selección adversa de las liquidadas se diluye a propósito en el stream completo.

**Riesgos residuales.**
- [COMPROBADO] Selección por cobertura: solo entran lados con precio (`daily.py:947`: `if price is None … continue`). No es sesgo por edge, pero sí por disponibilidad de cuotas (ligas y mercados que el feed cubre).
- [COMPROBADO] «Degrades gracefully to the settled-only history while the stream has no graded rows yet» (`data.py:216`). [HIPÓTESIS] Algún calibrador vivo pudo entrenarse en esa fase sobre liquidadas (muestra adversa); no verificable sin leer `data/`.
- [COMPROBADO] Método `auto` = mejor por (liga, mercado) según `calibration_methods.json` (`default.yaml:207`); `min_n 40` eventos independientes por grupo (`calibrator.py:714-740`, corregido de filas a eventos tras medir 5,01x de duplicación). [INFERENCIA] Elegir entre isotónica y beta por ECE OOS en ~50 grupos pequeños es una selección con multiplicidad; la isotónica con n ≈ 40 eventos sobreajusta. Hay precedente de colapso: un calibrador constante pasó ECE, Brier y monotonía (memoria `calibrador-colapsado-2026-08-28`). Mitigado por la promoción humana (`default.yaml:208-213`).

## R7 — MEDIA. Fugas temporales residuales

**Plataforma.** [COMPROBADO] Protecciones fuertes: walk-forward en todos los `tune_*`; `AdjustmentContext.ref_date` recorta cada feature a lo estrictamente anterior (`probabilities.py:319-325`, AUD-LOW-005); `ParkFactors` «leakage-safe: update must be called only AFTER a game is estimated» (`src/sqp/models/park.py:10-13`); el gate solo cuenta filas posteriores al pre-registro (`prediction_gate.py:28-33`); las poblaciones de MM y peso-mercado excluyen `generated_at ≥ start_time` (peso-mercado §4.1).
Residuales: [COMPROBADO] `avg_total 171` de WNBA se fijó con «total observado 2026 = 170,9 (n=137)» y la media vida 60 se aceptó «evaluando 2026» (`registry.py:56-75`): el prior incorpora el periodo que luego se evalúa en producción (fuga de prior, no de resultado por partido). [INFERENCIA] Mismo patrón en NBA (`registry.py:83`, evaluación «desde 2024» para elegir el decaimiento).

**Prompts.** [COMPROBADO] Reglas `as_of` sólidas (WNBA:43; MLB:261 walk-forward; UCL:365 cronológico; NCAAF:299 «no usar ratings retrospectivos finales de temporada»). Residuales señalados por la fase 1 y confirmados: xG revisado retroactivamente por proveedores sin exigir la versión pregame (solo LaLiga la exige, LALIGA:91 según individual; Bundesliga pide `available_at`); ratings «de temporada» (NBA:397); porteros confirmados tarde en backtest (NHL individual §6). [HIPÓTESIS] Magnitud no medida.

## R8 — MEDIA. Prompts: especificación no ejecutable y sobreajuste por diseño

- [COMPROBADO] NFL:220-223 (`Softmax(g(θ…))`, «modelos entrenados, no ejecutables»), NHL (21 fases, ~15 módulos, ablaciones en NHL:426), tenis (modelos jerárquicos por jugador/superficie/temporada). [INFERENCIA] >100 grados de libertad frente a ~270 (NFL), ~870 (MLS), ~1.300 (NHL) partidos por temporada; ningún prompt fija un criterio de complejidad ni un tamaño mínimo de muestra.
- [COMPROBADO] Mitigación en los propios prompts: prohibición de declarar ejecutado lo no ejecutado (MLB:17; NHL:61 según individual) y estados VALIDADO/EXPLORATORIO/INCOMPLETO en los 21.
- [COMPROBADO] Sin umbrales numéricos de aceptación en ningún prompt (todas las familias, §«Validación»); tolerancias de malla que difieren por 100× (1e-4 a 1e-6).
- [INFERENCIA] Riesgo operativo: un LLM que «ejecute» el prompt sin motor produce números con apariencia de modelo. La plataforma es el motor; los prompts no deben usarse para generar probabilidades fuera de ella.

## R9 — MEDIA. Encompassing y el coste medido de la independencia

- [COMPROBADO] Séptima medición (2026-09-07): el modelo está encompassed por el consenso, AUC 0,608 real pero coeficiente condicional ≈ 0 (`docs/research/2026-10-13-preregistro-peso-mercado-por-segmento.md:36`; memoria `feed-publico-cerrado-2026-09-07`). Brier calibrada servida frente a no-vig +0,0038 IC95 [+0,0022, +0,0055] (`peso-mercado:31`).
- [COMPROBADO] Escalera de `min_edge` invertida: subir el umbral empeora hit rate y ROI (`Tareas.md:105`): el edge declarado es error del modelo.
- [INFERENCIA] Riesgo: interpretar el principio de independencia como «el modelo manda en el stake» sin pasar la medición pre-registrada. El propio pre-registro lo encuadra: «el modelo estima bien; lo que no está demostrado es que estime mejor que el mercado» (`preregistro-el-modelo-manda.md:40-42`). No es motivo de cierre (memoria `mejorar-no-cerrar`): acota dónde buscar mejoras (modelos de los prompts como challengers, §R5).

## R10 — BAJA. Ambigüedades de redacción en los prompts

- [COMPROBADO] EPL:27: «Si se usan precios como benchmark para validación histórica, registrar ese hecho sin contaminarlos en el entrenamiento» y MLB:14: «Si se usa como benchmark en evaluaciones históricas, debe quedar separado del entrenamiento». Ninguno prohíbe **seleccionar hiperparámetros o calibradores por métricas contra el mercado**, que es exactamente R2. [RECOMENDACIÓN] Cláusula explícita en los 21 (ver `09-principios-fundamentales.md`, P8).
- [COMPROBADO] SERIE_A:21 condiciona la prohibición a «cuando operas en el modo independiente aquí especificado»; LIGUE_1:19 la limita a «calibrarlas durante la ejecución». Abren un modo no independiente.
- [COMPROBADO] LALIGA:152: «movimientos de mercado de fichajes… como información deportiva, no cuotas»: correcto, pero el término «mercado» en un prompt cuya regla central es el mercado de cuotas invita a confusión.
- [COMPROBADO] NHL:609 trata ROI y CLV como «medidas económicas secundarias» y ATP:342 exige baselines «sin usar mercado como predictor»: son los dos prompts que mejor cierran la puerta.

## R11 — BAJA. Comparabilidad y verificabilidad

- [COMPROBADO] `Edge_precio_pp = 100·[P_win − (1−P_push)/D]` en los prompts frente a `edge` = EV por unidad resuelta en la plataforma (`default.yaml:4`; `daily.py:971-973`, AUD-011). Mismo signo, distinta magnitud; no mezclar en informes.
- [COMPROBADO] `.env` no legible por esta auditoría; el valor efectivo de `MARKET_SHRINK` en producción es NO VERIFICADO. Mitigación existente: `_warn_risk_divergence` avisa de divergencias yaml/entorno (`Tareas.md:114`) y el pre-registro peso-mercado lo verificó con `Settings.load()` el 2026-10-13 (`peso-mercado:12`).

## Qué NO es un riesgo (para no sobrediagnosticar)

- [COMPROBADO] Las líneas de spread y total que llegan del consenso (`probabilities.py:240-247`, la más frecuente) se usan solo como umbral en los adaptadores (`adapters.py:63-72, 146-153`): UMBRAL LEGÍTIMO.
- [COMPROBADO] `tune_market_param` puntúa «on a FIXED reference line: the outcome comes from the scoreboard… not an estimate of live market performance» (`tuning.py:208-216, 265-268`). La línea de mercado es el umbral de evaluación, no un objetivo; `avg_total 171` de WNBA coincide con el total observado (170,9), no con la línea (175,1) (`registry.py:56-60`). La fase 1 (individual WNBA §9) lo clasificó como «ENTRADA prohibida»; esta fase lo rebaja a UMBRAL LEGÍTIMO con la salvedad de R7 (prior con datos del periodo evaluado).
- [COMPROBADO] No hay columnas de cuotas en `src/sqp/features/`, `models/ml_train.py`, `ml_predict.py`, `park.py`, `starters.py` ni `team_scoring.py` (grep de `implied|novig|price_decimal|odds` sin resultados); `blend.py` tiene peso 0 por defecto.
- [COMPROBADO] `prediction_gate` compara el modelo PURO con el no-vig y solo decide stake (`prediction_gate.py:10-24`): comparación posterior legítima.
