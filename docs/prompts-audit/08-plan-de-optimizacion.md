# 08 — Plan de optimización: qué mejorar, en qué orden y con qué prueba

Fecha: 2026-11-10. Escalón Fable, fase 2 de la auditoría de los 21 prompts `PROMPT_191_*`. Depende de `06-arquitectura-recomendada.md` (capas, registro congelado, fronteras) y se valida con `10-protocolo-de-validacion.md`. Etiquetas: [COMPROBADO] con cita, [INFERENCIA], [HIPÓTESIS], [RECOMENDACIÓN].

Regla de este plan: **ninguna mejora se mide contra el mercado**. El criterio de cada escalón es la mejora de la probabilidad congelada frente al desenlace (log loss, Brier, sesgo, ECE, error de marcador), con la infraestructura que el proyecto ya tiene. La comparación con el mercado es evaluación externa posterior (documento 10, §9) y nunca criterio de entrenamiento ni de promoción.

---

## 1. Hechos medidos que acotan el plan

Estos resultados del propio proyecto fijan dónde **no** hay que buscar y qué está ya probado.

| Hecho | Evidencia | Consecuencia para el plan |
|---|---|---|
| Sin ventaja medida frente al consenso; modelo *encompassed* (coeficiente condicional ≈ 0, AUC 0,608) | `preregistro-peso-mercado-por-segmento.md:§2`; `session-summaries.md:1025`; `resultado-recencia-totales-H.md:179` | Las mejoras se miden frente al desenlace. Una probabilidad mejor **no** implica edge; el plan no promete ROI. |
| Escalera de `min_edge` invertida: subir el umbral empeora hit rate (0,430→0,301) y ROI (−11,0 %→−23,9 %), monótono | `Obsidian/Tareas.md:105`; `evaluation/edge_information.py:1-9` | El edge declarado es error del modelo concentrado. **No** se optimiza nada sobre el edge; se reduce el error del modelo. |
| Sobreconfianza en 14 de 24 cortes, incluidos los seis spreads; en Poisson, `dispersion_k` mueve margen y total con el mismo signo | `Obsidian/Tareas.md:130` | Prioridad a la **distribución conjunta** y a σ por mercado, no a sumandos sobre p. |
| `wnba/totals` ordena al revés (pendiente modelo −0,233 frente a mercado +2,791; corr −0,036) y es el peor Brier (0,3020); en auto-pausa | `Obsidian/Tareas.md:117, 134`; `registry.py:57-75` | Caso de prueba natural del modelo ritmo × eficiencia del prompt WNBA. |
| Cuatro cortes peores que 0,50: `wnba/totals`, `ligamx/totals`, `chile/spreads`, `brasileirao/spreads` | `Obsidian/Tareas.md:134` | Mínimo exigible a cualquier escalón: no ser peor que la constante 0,5 ni que la tasa base. |
| `score_rho` RECHAZADO en MLB (spreads acepta, totals no; regla «ambos a la vez») | `docs/research/2026-08-26-resultado-correlacion-marcadores.md:1-30` | La correlación de marcadores en Poisson ya está medida; no se reabre sin hipótesis nueva. |
| Batería de ajustes aditivos: 4 ACEPTA de 24 (solo totales NBA/NFL) y ninguno activable tal como está programado; 20 RECHAZA | `docs/research/2026-10-09-resultado-bateria-ajustes.md:1, 57` | La capa aditiva sobre p no es la vía; el efecto aceptado (tendencia de totales) se absorbe en μ vía recencia. |
| Recencia de totales (`scoring_half_life_days`): NBA y NFL ACEPTAN en fase H, NHL RECHAZA; fase M pendiente (D = 2027-01-31) | `resultado-recencia-totales-H.md:1, 90`; `preregistro-recencia-totales.md:317` | No se activa hasta la fase M; el plan no duplica ese trabajo. |
| Descanso: NBA ACEPTA (0,795 activo), NHL RECHAZA; clima MLB RECHAZA; abridor v1 y FIP: rechazo/empate, hoy `pitcher_bound 0,05` | `resultado-descanso-basket.md:17`; `resultado-descanso-nhl.md:18`; `project-decisions.md:85-88, 121, 447`; `ratings.yaml:22-23` | Las features de contexto de los prompts ya tienen un historial: solo entran con pre-registro y por la λ/μ, no como sumando. |

---

## 2. Mejoras priorizadas (impacto, riesgo, dificultad)

Escala: impacto sobre la calidad de la probabilidad congelada (A alto, M medio, B bajo); riesgo de romper algo o de contaminar un pre-registro vigente (B/M/A); dificultad de implementación (B/M/A). Orden = prioridad propuesta.

| # | Mejora | Impacto | Riesgo | Dificultad | Depende de | Decisión del operador |
|---|---|---|---|---|---|---|
| 1 | Fronteras de importación + `prediction_id`/`frozen_at`/`model_version` en el stream (06 §4-5) | A (habilita todo lo demás y hace verificable el principio) | B (no cambia ninguna probabilidad) | B-M | — | no |
| 2 | Protocolo de validación sin mercado sobre el registro congelado, con MAE/RMSE de marcador (doc. 10) | A | B | B | 1 | no |
| 3 | Distribución conjunta margen-total en la familia Normal (baloncesto, fútbol americano) y σ por mercado | A (seis spreads sobreconfiados; `Tareas.md:130`) | M (toca la salida servida; addendum a «el modelo manda» o shadow) | M | 1, 2 | no (pre-registro) |
| 4 | `dc_rho` y localía por liga en las 8 ligas de fútbol que usan el default de familia (`familias/futbol-europa.md §4`, `futbol-america-y-femenino.md §4`) con `tune_ratings.py` | M-A (11 ligas) | B (arnés existente con guardarraíles: `tuning.py:224-227`) | B | 1 | no |
| 5 | Modelo ritmo × eficiencia para totales de baloncesto, empezando por `wnba/totals` (en pausa, nada que perder) y NBA | M-A | B (mercado pausado; challenger en shadow) | M | 1, 2 | no (pre-registro) |
| 6 | Reglamento como datos: OT/empate NFL, extras MLB, OT+SO NHL, prórroga y penales en copas, con `ruleset_id` | M (moneyline y totales de 60'/reglamentarios) | B-M | M | 1 | no |
| 7 | Fuerza ofensiva/defensiva log-lineal en fútbol (challenger al Elo + `home_scoring_bonus`) | M | M | M | 1, 2, 4 | no (pre-registro) |
| 8 | Portero NHL: ejecutar `--pre` y el modo completo del pre-registro vigente | M | B (ya pre-registrado) | B (script existe: `scripts/research/measure_goalie_nhl.py`) | — | sí: ejecución del `--pre` (lo lanza el operador) |
| 9 | MLB: IP esperadas del abridor y bullpen como factor acotado sobre λ | M | M | M | 1, 2 | no (pre-registro); datos de MLB StatsAPI ya integrados (`providers/mlb_statsapi.py`) |
| 10 | Tenis: cadena saque-resto + DP de sets por superficie (hoy Elo escalar sin superficie) | A para ATP/WTA | M | A | 1, 2, datos | **sí: fuente de estadísticas de saque/resto** (gasto o scraping) |
| 11 | Fútbol americano: EPA/éxito y QB (hoy Normal + Elo) | M-A | M | A | 1, 2, datos | **sí: fuente play-by-play** (NFL: nflverse es público; NCAAF: el prompt veta CFBD, NCAAF:67) |
| 12 | xG y alineaciones en fútbol | M | M | A | 7, datos | **sí: proveedor de xG/alineaciones** (gasto) |
| 13 | Calendario deportivo como universo de eventos (no la API de cuotas) | B-M (trazabilidad) | B | M | 1 | sí: cobertura de ligas sin proveedor de resultados |
| 14 | Política de mercado (`market_shrink`, `uncertainty_penalty`) | — | A (pre-registros vigentes) | B | MM y peso por segmento medidos | **sí, y solo después de 2026-11-24 y de marzo de 2027** |

[INFERENCIA] Las filas 1, 2 y 4 son «sin arrepentimiento»: no cambian probabilidades servidas (1, 2) o usan un arnés que ya decidió parámetros de producción antes (4, con sus guardarraíles). Las filas 3, 5, 6, 7, 9 son challengers y exigen pre-registro (`.claude/skills/model-change/SKILL.md:20-32`). Las filas 10-12 están bloqueadas por datos.

---

## 3. Escalera de complejidad progresiva por deporte

Convenciones comunes a todas las escaleras:

- **Baseline del escalón 0** = el modelo de producción actual, congelado por (`model_version`, `params_hash`). Baselines independientes del mercado adicionales: constante 0,5, tasa base de la liga, Elo puro sin ajustes (doc. 10 §5).
- **Criterio de mejora empírica** (el que ya define el proyecto): mejora de log loss **fuera de muestra** con holdout de origen rodante de 4 bloques y semilla de entrenamiento ≥ 40 % (`backtesting/tuning.py:214-215`), margen mínimo 0,002 en log loss frente al baseline (`tuning.py:227`), n mínimo de 200 partidos evaluados o 80 empates observados cuando el parámetro es de empate (`tuning.py:225-226`), sin empeorar el **sesgo** (`engine.py:17-30`) ni la ECE, y nunca peor que 0,50 ni que la tasa base. Para error de marcador (MAE/RMSE) el proyecto no define umbral: **a fijar en el pre-registro**. Cada escalón se evalúa en **todos** los mercados que afecta y se acepta solo si no empeora ninguno (regla «ambos a la vez» del resultado de `score_rho`, `resultado-correlacion-marcadores.md:22`).
- **Hipótesis pre-registrable**: formulada como H₁ con efecto mínimo, muestra calculada por potencia (precedente: `preregistro-el-modelo-manda.md:§Potencia`), particiones temporales, bootstrap por días o eventos (`evaluation/bootstrap.py`), ejecución única y re-ejecución solo por defecto documentado (precedente E10 en `resultado-descanso-nhl.md:150-155`).
- Un escalón solo se sube cuando el anterior está **aceptado o descartado**; no se saltan escalones para no confundir la fuente de la mejora.

### 3.1 Fútbol (11 ligas: `soccer.yaml:4-13, 30`)

| Esc. | Modelo | Qué añade | Criterio empírico | Hipótesis pre-registrable |
|---|---|---|---|---|
| 0 | Producción: Elo + `home_scoring_bonus` + `tilt_scale` → Poisson con `dc_rho` (`adapters.py:126-143`) | — | baseline | — |
| 1 | `dc_rho` y `elo_home_adv` por liga en las 8 ligas sin override (`tune_ratings.py`) | parámetros por liga | log loss 1X2 −0,002 OOS; ≥ 80 empates | «El ajuste de empates por liga mejora el log loss 1X2 en al menos 0,002 en ≥ k de 8 ligas» (k a fijar) |
| 2 | Ataque/defensa log-lineal con decaimiento (MLE), localía como intercepto, shrinkage estimado (prompts F2-F5) | fuerza por lado, no solo diferencia | log loss 1X2 y totales; MAE de goles por equipo (umbral a fijar); sesgo de totales | «Las tasas por lado reducen el log loss del total 2,5 y el MAE de goles frente al Elo-tilt» |
| 3 | Distribución conjunta completa: BTTS, team totals, mitades, asiáticos desde una sola rejilla | mercados derivados | conservación de masa (tests tipo `test_independent_pricing.py:78`); ECE por mercado | «Los mercados derivados de la rejilla están calibrados (ECE ≤ a fijar) sin reajuste» |
| 4 | Once, portero, balón parado, árbitro (prompts F7-F9) | contexto | como 2, por partición; solo si `available_at` ≤ corte | requiere datos de alineaciones (decisión del operador) |
| 5 | xG como insumo de las tasas (conversión calibrada, no sustituto de goles) | señal avanzada | como 2 | requiere proveedor de xG (gasto) |
| 6 | Eliminatorias: ida/vuelta, prórroga, penales con `q_shootout` estimado (UCL, UWCL, MLS, Liga MX) | reglamento | log loss de «clasifica»; nunca 50/50 fijo (UWCL:47) | «La probabilidad de clasificación simulada bate al baseline “gana el favorito del global”» |

### 3.2 Baloncesto (NBA, WNBA, NCAAB, WNCAAB)

| Esc. | Modelo | Qué añade | Criterio empírico | Hipótesis pre-registrable |
|---|---|---|---|---|
| 0 | Producción: Elo → margen Normal; `TeamScoringRates` → total Normal; independientes (`adapters.py:29-82`) | — | baseline | — |
| 1 | `points_per_elo` y `elo_home_adv` propios para NCAAB/WNCAAB (hoy heredados de NBA: `familias/baloncesto.md §5`) y σ residual por liga y mercado | parámetros por liga | log loss spreads/ML; sesgo ≈ 0; cobertura de intervalos | «σ por mercado corrige la sobreconfianza de spreads sin empeorar ML» |
| 2 | Distribución conjunta margen-total (Normal bivariante con ρ estimado, o bootstrap de residuos de los prompts) | dependencia | log loss y ECE **en los tres mercados a la vez**; RMSE de margen y total | «La conjunta reduce el log loss de spreads ≥ 0,002 sin empeorar totales ni ML» |
| 3 | Ritmo × eficiencia: posesiones por fórmula de FTA, ORtg/DRtg ajustados por rival, `μ = Poss×Eff/100 ± HCA/2` (prompts F10-F13) | modelo de totales | sesgo de totales, MAE de puntos; **primero en `wnba/totals`** | «El total por posesiones elimina la pendiente negativa de `wnba/totals` (modelo −0,233 → ≥ 0)» |
| 4 | OT explícita (recalcular ML/spread/total con prórroga) | reglamento | ECE de ML en partidos cerrados; push en líneas enteras | «Modelar OT mejora la calibración de ML en |margen esperado| < 3» (umbral a fijar) |
| 5 | Lesiones/rotación con `available_at` | contexto | como 3 | requiere fuente de partes de lesiones con hora |

### 3.3 Fútbol americano (NFL, NCAAF)

| Esc. | Modelo | Qué añade | Criterio empírico | Hipótesis pre-registrable |
|---|---|---|---|---|
| 0 | Producción: Normal + Elo (`adapters.py:168`; `registry.py:70-72`) | — | baseline | — |
| 1 | σ por liga (NCAAF `margin_sigma 20`, NFL 13,5) revalidada walk-forward; números clave (3, 7) en la liquidación de spreads | dispersión y push | sesgo, ECE de spreads; MAE de margen | «La masa en números clave mejora el push/cover frente a la Normal continua» |
| 2 | Conjunta margen-total (como 3.2-2) | dependencia | tres mercados a la vez | idem 3.2-2 |
| 3 | Reglamento: empate en NFL regular, OT 2026, OT por rondas en NCAAF, con `ruleset_id` | reglamento | log loss ML (tres vías NFL) | «Incluir la masa de empate mejora el log loss de ML en NFL regular» |
| 4 | EPA/éxito por jugada, PROE, QB con escenarios A/B, SOS jerárquico (NCAAF) | señal avanzada | como 1-2 | **requiere play-by-play** (decisión del operador) |

### 3.4 Tenis (ATP, WTA)

| Esc. | Modelo | Qué añade | Criterio empírico | Hipótesis pre-registrable |
|---|---|---|---|---|
| 0 | Producción: Elo escalar K=40 sin superficie, solo `h2h` (`adapters.py:318-338`; `daily.py:73`) | — | baseline | — |
| 1 | Elo por superficie con mezcla hacia el global (baseline independiente que el prompt ATP exige: ATP:342) | superficie | log loss ML OOS; orientación aleatorizada como en `registry.py:86-89` | «El Elo por superficie mejora el log loss ≥ 0,002» |
| 2 | Cadena saque-resto: `p_service = f·a + (1−f)·b`, `Hold(p)`, DP de juego-set-partido BO3/BO5 | estructura de puntuación | log loss ML; **nuevos mercados** (sets, juegos) evaluados por CRPS/MAE de juegos (WTA:274; umbral a fijar) | «El modelo de puntos iguala o mejora el Elo en ML y habilita totales de juegos calibrados» |
| 3 | Retiradas, primer servidor, ranking como covariable (WTA:42) | contexto | ablación | requiere datos punto a punto o de saque/resto por partido (decisión del operador) |

### 3.5 MLB

| Esc. | Modelo | Qué añade | Criterio empírico | Hipótesis pre-registrable |
|---|---|---|---|---|
| 0 | Producción: Elo tilt 0,4 + abridor (`pitcher_bound 0,05`) + parque → NB `k = 3,8` (`registry.py:73-80`; `ratings.yaml:16-30`) | — | baseline | — |
| 1 | IP esperadas del abridor y reparto abridor/bullpen de las 9 entradas (MLB v2 F5-F8) | estructura del pitcheo | log loss ML/RL/totales; MAE de carreras | «Separar bullpen reduce el sesgo de totales sin empeorar la runline» |
| 2 | Dispersión por mercado: `dispersion_k` distinto para margen y total (aviso de `Tareas.md:130`: hoy mueve ambos con el mismo signo) | dispersión | los dos mercados a la vez | «Un k por mercado corrige la sobreconfianza de totales sin degradar la runline» (ojo: `score_rho` ya fue rechazado; esta es otra palanca) |
| 3 | Extras con corredor automático (final ≠ 9 entradas) | reglamento | ECE de ML en empates a 9 | «Simular extras mejora la calibración de ML en partidos igualados» |
| 4 | Clima/viento/techo | contexto | ya medido: RECHAZADO (`project-decisions.md:447`) | no reabrir sin hipótesis nueva |

### 3.6 NHL

| Esc. | Modelo | Qué añade | Criterio empírico | Hipótesis pre-registrable |
|---|---|---|---|---|
| 0 | Producción: Elo tilt 0,439 → Poisson; OT aproximada con `tie_adds_goal` (`ratings.yaml:43-50`; `distributions.py:219-238`) | — | baseline | — |
| 1 | Portero titular y calidad (`goalie_beta`): **pre-registro vigente, `--pre` sin ejecutar** | portero | el del pre-registro (`preregistro-portero-nhl.md:§5-6`) | ya escrita; no se reformula |
| 2 | Tasas por estado de juego (5v5, PP, PK) y TOI esperado | estructura | log loss ML/PL/totales | «λ por estado mejora totales sin empeorar ML» |
| 3 | OT 3v3 + SO explícitos con marcador reglamentario y final separados (NHL:53) | reglamento | ECE de ML FT y 1X2 60' | «Separar regulación y final mejora la calibración del 1X2 de 60'» |
| 4 | xG a favor/en contra | señal avanzada | como 2 | requiere proveedor de xG |

---

## 4. Qué simplificar o quitar

[RECOMENDACIÓN] En la plataforma:

1. **Capa de ajustes aditivos sobre p** (`adjust_model_probability`, 15 coeficientes a 0 en `default.yaml:43-116`): 20 de 24 rechazados y los 4 aceptados no son activables (`resultado-bateria-ajustes.md:1`). Congelar como código legado sin nuevas entradas; cualquier efecto futuro entra por λ/μ.
2. **Mezcla con ML (opción B)**: `models/blend.py` con peso 0 y `evaluation/compare.py`; mantener solo como evaluador de referencia del documento 10, no como vía de producción.
3. **`clv_gate`** (`enabled: false`, `default.yaml:259-261`): ya no decide; dejarlo como diagnóstico y retirarlo del camino de `daily` cuando se separe `price_league`.
4. **Modo `accuracy`** (`default.yaml:174-201`): revertido con razón; no reactivar.
5. **Penalizaciones de mercado a 0** (`line_movement_*`, `line_velocity_*`, `books_spread_*`): ocupan configuración sin consumidor activo; moverlas al bloque `market_policy` (06 §5.2) o retirarlas con el test de claves.
6. **Monte Carlo** (`simulation/monte_carlo.py`): no se usa en producción; reservar para dependencias no analíticas (OT, extras, eliminatorias) y no para reemplazar las rejillas exactas, como piden los propios prompts («no declarar MC no ejecutado», MLB:17).

[RECOMENDACIÓN] En los prompts (son especificaciones; la plataforma no los lee):

7. **Un solo núcleo común + anexo por deporte.** [COMPROBADO] No existe plantilla textual común (medido en los seis informes de familia: 0-11 líneas idénticas entre pares); 21 redacciones de la misma especificación con 7 nombres para la debilidad defensiva, tres etiquetas de estado, tres tolerancias de masa (1e-4 a 1e-6) y dos esquemas de localía. Reducir a un documento de reglas comunes (independencia, congelación, estados, EV, controles) y un anexo por deporte con solo lo que cambia (unidad de tasa, distribución, reglamento, fuentes).
8. **Quitar las constantes provisionales con valor** (MLB v2: 1200/600/400, `k = 0,15`, `f = 0,30`, `√1,02`): la plataforma ya tiene los equivalentes medidos (`dispersion_k 3,8`, `home_scoring_bonus 0,10`, `prior_games 6`). La política NHL («por estimar») es la compatible con el pre-registro.
9. **Quitar el apartado de EV/CLV de cada prompt** y remitirlo a un único módulo de comparación posterior: el prompt no debe calcular EV, porque el motor congelado no ve cuotas.
10. **Residuos entre deportes** (hockey y QB en Bundesliga P:105, 358; «1.02 de localía» en LaLiga P:76): eliminar.

---

## 5. Cuello de botella de datos por escalón

| Escalón | Dato necesario | ¿Existe en la plataforma? | Fuente candidata | Coste |
|---|---|---|---|---|
| Fútbol 1-3, Baloncesto 1-4, FA 1-3, MLB 1-3, NHL 2-3 | marcadores históricos por partido, fechas, localía | sí (`ResultsStore`, ESPN/MLB/NHL providers) | — | ninguno |
| Baloncesto 3 | FGA, FTA, ORB, TO por equipo y partido (posesiones) | **no** (solo marcadores) | ESPN box scores (ya se usa ESPN para resultados) | desarrollo; sin gasto conocido [HIPÓTESIS] |
| Baloncesto 4, FA 3, MLB 3, NHL 3 | marcador reglamentario vs final, períodos | parcial (NHL: `tie_adds_goal` aproxima; MLB: no) | boxscores ESPN/NHL API (`providers/nhl_api.py:75`) | desarrollo |
| Fútbol 4 | alineaciones con hora de publicación | **no** | proveedor con `available_at` | **gasto** |
| Fútbol 5, NHL 4 | xG por partido/equipo | **no** | proveedor comercial | **gasto** |
| Tenis 1 | superficie por torneo | parcial [HIPÓTESIS: ESPN scoreboard trae torneo; superficie no verificada] | tabla torneo→superficie | desarrollo |
| Tenis 2-3 | % puntos ganados al saque/resto por jugador y superficie | **no** | estadísticas de tour o datos punto a punto | **decisión del operador** (gasto o scraping) |
| FA 4 | play-by-play con EPA | **no** | NFL: nflverse (público); NCAAF: el prompt veta CFBD (NCAAF:67) | NFL desarrollo; NCAAF **decisión** |
| MLB 1 | IP por apertura y uso del bullpen | parcial (`StarterFIPStore` por apertura) | MLB StatsAPI (ya integrada) | desarrollo |
| NHL 1-2 | portero probable con hora, TOI por estado | portero: sí (`goalie_probables_capture.py`); estados: no | NHL API boxscore | portero: ninguno; estados: desarrollo |
| Todos | calendario deportivo independiente de la API de cuotas | parcial (`schedule_store.py`) | ESPN/MLB/NHL | desarrollo |

[INFERENCIA] Los escalones que solo necesitan marcadores (fútbol 1-3, baloncesto 1-2, FA 1-3, MLB 1-3, NHL 2-3) cubren la mayor parte del impacto esperado sobre la sobreconfianza y las pendientes invertidas, y no requieren gasto. Los escalones de «señal avanzada» (xG, EPA, saque/resto) son los más caros y, dado que el modelo ya está *encompassed* con datos públicos, su justificación es **información con hora de llegada** que el consenso aún no incorpore (`session-summaries.md:1025`), no más features del mismo tipo.

---

## 6. Lo que necesita una decisión del operador (separado)

### 6.1 Gasto o fuentes nuevas
- Estadísticas de saque/resto de tenis (escalera 3.4-2/3).
- Alineaciones y xG de fútbol (3.1-4/5) y xG de hockey (3.6-4).
- Play-by-play NCAAF sin CFBD (3.3-4).
- Partes de lesiones con hora para baloncesto (3.2-5).

### 6.2 Cambio de política de mercado
- `market_shrink` y `uncertainty_penalty`: **nada antes de** la medición única de «el modelo manda» (3.402 eventos, ≈ 2026-11-24, `preregistro-el-modelo-manda.md:138`) y de «peso por segmento» (N = 3.300, ≈ 2027-03-21, `preregistro-peso-mercado-por-segmento.md:218`). Cualquier cambio anterior invalida ambos (`preregistro-el-modelo-manda.md:230`).
- Si tras esas mediciones el operador mantiene el principio de independencia en la decisión, el bloque `market_policy` (06 §5.2) se fija en `market_shrink: 0` y la decisión pasa a depender solo de `prediction_gate`, que ya evalúa la probabilidad pura.

### 6.3 Cambios en producción durante los pre-registros vigentes
- Los challengers 3, 5, 6, 7, 9 del cuadro de §2 cambian `model_probability` servida. [COMPROBADO] «El modelo manda» admite cambios de régimen **registrados como addendum antes de ejecutar** (addenda 2026-09-26 y 2026-09-30, `preregistro-el-modelo-manda.md:256-270`). [RECOMENDACIÓN] Hasta 2026-11-24, ejecutarlos en **shadow** (`evaluation/feature_shadow.py`, `scripts/feature_shadow.py`) y no en producción; después, activar solo con addendum o tras la medición. Lo decide el operador.
- Portero NHL: el `--pre` aborta si los parámetros NHL resueltos no coinciden con §6 del pre-registro o si hay cambios sin commitear en `src/`, `configs/` o `scripts/research/` (`preregistro-portero-nhl.md:685-686`). **Ningún cambio en NHL (escalones 3.6-2/3) antes de ejecutar el `--pre`.**
- Brecha tier A: `max_plausible_ev` congelado en 0,075 y la clasificación de `evaluation/tipster.py` no se toca hasta la medición (≈ julio de 2027, `preregistro-brecha-tier-a.md:183, 280`).
- Recencia de totales: `scoring_half_life_days` de NBA/NFL/NHL no se activa hasta la fase M (D = 2027-01-31).

### 6.4 Datos nuevos de bajo coste que conviene autorizar explícitamente
- Captura de boxscores (posesiones, períodos, marcador reglamentario) desde las APIs ya integradas: no supone gasto conocido [HIPÓTESIS], pero añade llamadas diarias y columnas nuevas a `data/`; conviene que el operador lo apruebe como cambio de captura (precedente: team totals MLB, `frente-derivados-2026-08-24`).

---

## 7. Orden de ejecución propuesto (resumen)

1. Fronteras + `prediction_id` (06 §4-5) → 2. protocolo sin mercado (doc. 10) → 3. `tune_ratings` para las 8 ligas de fútbol sin override → 4. pre-registro de la conjunta margen-total (baloncesto, FA) en shadow → 5. pre-registro de ritmo × eficiencia en `wnba/totals` → 6. reglamento como datos (OT/extras) → 7. `--pre` del portero NHL (operador) → 8. log-lineal de fútbol → 9. bullpen MLB → 10. decisiones de datos (tenis, EPA, xG) → 11. política de mercado tras los pre-registros.
