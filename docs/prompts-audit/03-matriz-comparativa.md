# 03. Matriz comparativa de los prompts deportivos

Fecha: 2026-11-10. Solo lectura. Fuente: los 21 informes individuales y 6 de familia de `docs/prompts-audit/` (enlaces en [01-inventario.md](01-inventario.md)); lo no incluido en ellos se cita como `prompt:línea`. Etiquetas: [COMPROBADO], [INFERENCIA], [HIPÓTESIS], [RECOMENDACIÓN]. Abreviaturas: DC = Dixon-Coles; OT = prórroga; ET = tiempo extra; MC = Monte Carlo; HFA = ventaja de localía; V/E/I = VALIDADO/EXPLORATORIO/INCOMPLETO.

Principio (operador): las probabilidades salen solo de información deportiva y modelos independientes; el mercado solo compara tras congelar; una línea como umbral a evaluar es legítima, como media o ajuste no. [COMPROBADO] Ningún prompt viola el principio (las familias lo confirman); lo viola la plataforma (§4).

## 1. Matriz prompts × dimensiones

### 1.1 Distribución, empate/prórroga y localía

| Prompt | Distribución del marcador | Empate y prórroga | Localía |
|---|---|---|---|
| EPL, LaLiga, Bundesliga, Serie A, Ligue 1 | Poisson (o NB) bivariante log-lineal; DC con cuatro τ; matriz conjunta a 90'; mercados desde una sola matriz | Empate propio del 1X2; sin ET en liga | EPL y Bundesliga: interceptos `beta_home/beta_away`; LaLiga, Serie A, Ligue 1: intercepto común + HFA (`β_HFA`, `beta_H`); aplicarla una sola vez |
| UCL | Igual + módulo de eliminatoria (ida/vuelta/global/ET/penales), fase liga 36 clubes y campeón | ET y penales en la eliminatoria; penales sin 50/50 por defecto (según familia) | `HFA_g` por grupo; 0 en la final (sede neutral) |
| UWCL | Igual, escala interligas (F5), fase liga y título | ET solo en la vuelta y la final; prohíbe 50/50 en penales (UWCL:47) | `HFA`; sede por estadio |
| MLS | Igual (nombra DC sin escribir las τ, MLS:179) | Playoffs: Wild Card, Bo3, ET 2×15' desde semifinales de conferencia (F17) | `beta0_H`/`beta0_A` o un término (MLS:159) |
| Liga MX | Igual + altitud (F12) | Liguilla; ET solo en la final (LMX:281) | `beta_home·H` (LMX:182) |
| Brasileirão | Igual + receso del Mundial y viajes largos | Sin ET | `beta_home` (BRA:164) |
| Chile | Igual + estadio real, superficie, altitud | Sin ET | `beta_HFA` (CHI:174) |
| NBA | Posesiones × eficiencia; margen y total desde distribución conjunta (bootstrap de residuos o bivariante) | OT recalculado; fallback Poisson(5/48 μ) (NBA:206) | `HCA = +2.0` por defecto (NBA:58) |
| WNBA | Idem con Pace40; regularización por posesiones | OT entrenado (WNBA:69); sin modelo no publica spread/total | Sin valor; a calibrar (WNBA:66) |
| NCAAB | AdjO/AdjD/AdjT; λ, κ (NCAAB:94); dos mitades de 20 | OT con parámetros entrenados o fallback etiquetado (NCAAB:240) | Sin valor (NCAAB:162); sede neutral y torneos |
| WNCAAB | Como NCAAB; cuatro cuartos de 10; log-lineal (WNCAAB:282) | OT explícito (WNCAAB:346); 50/50 solo para ML exploratorio (WNCAAB:351) | Sin valor (WNCAAB:247) |
| NFL | PMF conjunta de puntos (6/1/2/3/2, NFL:195) con números clave; escenarios de QB | Empate posible en regular; OT de 10 min; playoffs sin empate (NFL:259, 263) | Estimada; sin constantes (NFL:72) |
| NCAAF | PMF conjunta; SOS jerárquico; priors de roster/portal | Sin empate; OT por rondas sin reloj (NCAAF:217-221) | Estimada; sin constantes (NCAAF:48) |
| ATP | Markov: `p_service = f·a + (1−f)·b` → `Hold(p)` (ATP:138, 223) → tie-break → DP de sets → DP de partido; BO3 y BO5 | Sin empate; tie-break 7 (margen 2), 10 en set decisivo de Slam (ATP:75-76); retiradas | Sin localía; superficie vía `beta_s` (ATP:161) |
| WTA | Idem, solo BO3 | Idem (WTA:79); fallback R de retiradas (WTA:388) | Sin localía; no trasladar parámetros ATP (WTA:49) |
| MLB | NB con gamma compartida (`NB_k = 0,15`, `f = 0,30`; MLB:36-46); 9 entradas | Extras con corredor automático (MLB:143-145); la distribución de 9 entradas no es la final (MLB:125) | `HomeAdj = √1,02` (MLB:43), provisional |
| NHL | Poisson por estado de juego: `λ_s = xGF·xGA/League`, `Σ_s T_s/60·λ_s` | Regulación vs final separadas: OT 3v3 + SO (REG), OT 20 min 5v5 (PLAYOFF) (NHL:352-365); cinco marcadores (NHL:53) | `HFA` estimado (NHL:95) |

### 1.2 Variables principales

| Prompt | Ofensiva y defensiva | Ritmo | Lesiones y alineación | Fatiga y descanso | Clima y entorno |
|---|---|---|---|---|---|
| Fútbol de club y UCL/UWCL | xG/NPxG homogéneo, ataque + `DefenseWeakness` ajustados por rival | No aplica | Once probable, portero (PSxG), balón parado | Descanso/calendario, viajes | Altitud (Liga MX, Chile), superficie (Chile), receso Mundial (BRA) |
| Baloncesto (4) | ORtg/DRtg, Four Factors (`Eff = Off×Def/League_ORtg`) | `sqrt(Pace_a×Pace_h)`; Pace48/Pace40 | Escenarios IN/OUT, prior de roster | Back-to-back (NBA) | Poco; sede neutral en NCAA |
| NFL, NCAAF | EPA, PROE (NFL), SOS jerárquico (NCAAF) | Posesiones/drives | QB escenarios A/B; portal/transferencias (NCAAF) | Semana corta, pretemporada | Clima como feature (signo del margen con clima extremo según v3) |
| ATP, WTA | % puntos de saque/resto, `Hold`, `Break` | No aplica | Retiradas, estado físico | Carga de partidos | Superficie, altitud, pista |
| MLB | `Off`, abridor `IP/(IP+80)` (xFIP→FIP→ERA), bullpen, defensa, ump | Entradas/IP esperadas | Alineación (`LineupAdj`) | No central | Parque, viento, techo (MLB:102) |
| NHL | xGF/xGA, GSAx, SV% por estado | Tasa por 60 min | Alineación, portero titular | Viaje y descanso | Viento exterior prohibido (NHL:72, 248) |

### 1.3 Datos faltantes, Monte Carlo y congelación

| Prompt | Datos faltantes | Monte Carlo | Congelación previa al mercado |
|---|---|---|---|
| Fútbol (11) | Salida parcial NO CALCULADO/INCOMPLETO sin inventar; ascendidos con puente de ligas inferiores (EPL P:128, BRA, CHI); UCL niveles de fallback A-D | Matriz exacta; simulación solo para fase liga, tabla, título y descenso (UCL, UWCL, Chile F21) | Fase de congelación (F18-19) con `as_of`; LaLiga preserva versión pregame (P:91); Bundesliga `available_at` (P:63) |
| NBA | Estados V/E/I; shrinkage `G/(G+K)`, `K_games = 20` (NBA:57) | 100.000 (NBA:59) | `prediction_id`, `source_hash` |
| WNBA | Regularización `n_eff/(n_eff+tau)`; aviso de expansión | 100.000-1.000.000; semiancho 0,5 pp (WNBA:70-71) | `prediction_id`, `source_hash` |
| NCAAB | Separación D-I / no-D-I; fallback etiquetado | Adaptativo (NCAAB:231) | Snapshot sin hash obligatorio |
| WNCAAB | Reglas de datos más estrictas; traza por fase | Semilla/n_iter (WNCAAB:338); prohíbe heredar `rho = 0.12` | `input_hash` y `locked=true` |
| NFL | Escenarios; sin constantes | 100.000 provisional (NFL:77) | Fase 18/19; `ruleset_id` (NFL:97) |
| NCAAF | FBS/FCS, bowls con opt-outs | 10.000 = «prototipo» (NCAAF:234) | Fase 18/19; sin `ruleset_id` |
| ATP | Fallbacks A-D (ATP:428-431), EV NO EVALUABLE | DP exacta; simulación solo para formatos con grupos (Finals) | Congelación antes de EV |
| WTA | Fallbacks A-D y R (WTA:382-388) | DP exacta; P(torneo/avance) con simulación (WTA:24, 73) | Idem |
| MLB | Constantes provisionales etiquetadas; V/E/I | 1e5-1e6; semiancho 0,003 | Fase 16 (MLB:177-178) |
| NHL | Todo «por estimar»; salida parcial | Error < 0,5 pp | Fase 19 (NHL:432-445) |

### 1.4 Validación y constantes

| Prompt | Métricas de validación | Constantes fijadas | «A estimar» |
|---|---|---|---|
| Fútbol de club | Brier, log loss, ECE, fiabilidad por banda; 30-45 controles de consistencia (EPL/Bundesliga/Serie A/Ligue 1: 35; LaLiga 42; UCL 30; MLS 30; UWCL 40; LMX 35; BRA 45; CHI 40) | Tolerancia de cola (1e-4 a 1e-6), τ de DC como forma, stake asiático 50/50 | `tau`, `rho`, HFA, pesos de forma |
| Baloncesto | Brier/log loss/ECE, error MC; cobertura OOS; 20 pruebas (WNCAAB) | NBA: `K_games = 20`, `HCA = +2.0`; WNCAAB: reglamento (WNCAAB:55-62) | `tau`/`kappa`, σ y ρ, HCA (WNBA, NCAAB, WNCAAB) |
| NFL/NCAAF | 24 y 28 pruebas; calibración por rango de spread/total | Puntos 6/1/2/3/2 (NFL:195); reglas de OT | `tau`, σ, ρ, correlación margen-total |
| ATP/WTA | Brier, log loss, MAE de juegos, CRPS (WTA:274); 40 controles; subgrupos y retiradas (WTA:390-392) | Reglas de tie-break y formato | `tau`, `alpha`, `beta`, `beta_s`, `p_prior` |
| MLB | 14 tests; calibración y dispersión realizada vs simulada | 14 constantes (1200/600/400 PA, 5,0 IP, 1,02, `k = 0,15`, `f = 0,30`; MLB:36-46) | `L` por temporada, parque |
| NHL | 30 invariantes (NHL:566-597) | Ninguna (NHL:98) | `HFA`, `β_G`, ρ (el `0,12` está prohibido, NHL:94) |

## 2. Por prompt: fortalezas, debilidades, contradicciones y componentes reutilizables

Familia fútbol de club y copa (11):

| Prompt | Fortalezas | Debilidades | Contradicciones | Reutilizable |
|---|---|---|---|---|
| EPL | Puente Championship→Premier para ascendidos (P:128); tolerancia 1e-4 declarada | No nombra ascendidos; sin título global de fases | Prohíbe renormalizar «silenciosamente» (P:217) frente a Bundesliga | Puente de ascendidos |
| LaLiga | Revisión más cuidada: versión pregame de datos (P:91), combinados BTTS+resultado por intersección (P:295) | Vestigio «1.02 de localía» (P:76); «mínimo 35» con 42 pruebas | Tolerancia «p.ej. 1e-5» | Intersección de combinados; versión pregame |
| Bundesliga | `available_at`; estados `VERIFICADA/PROVISIONAL/AUSENTE/CONFLICTIVA` (P:95); PPDA | Residuos de hockey (P:105) y QB (P:358) | Renormaliza «con justificación» frente a EPL | Estados de verificación de dato |
| Serie A | `ParameterUncertainty`; árbitro; tolerancia 1e-6 | Cláusula de independencia condicionada (P:21) | Cinco ejes de calidad frente a cuatro | Eje de incertidumbre de parámetros |
| Ligue 1 | Control de unidades 0-1/0-100 (P:334) | «Calibrarlas durante la ejecución» (P:19); sin validación de precio | Ascendidos «incluyen» (lista abierta) | Control de unidades |
| UCL | Módulo de eliminatoria, fase liga, campeón; normalización multiliga; niveles de fallback A-D | 30 controles «mínimos»; reglamento 2026/27 sin verificar | Zurich como huso de «día de competición» | Módulo de eliminatoria y de campeón |
| UWCL | Escala interligas (F5); fase liga; título; 40 controles | Datos de eventos femeninos escasos | `Uncertainty: CUANTIFICADA` sin método (UWCL:344) | Escala interligas |
| MLS | Playoffs 2026 (Wild Card, Bo3, ET) | Tolerancia de cola sin cifra (MLS:181); DC sin escribir las τ | `q_shootout` como probabilidad a modelar (MLS:240-242) | Modelo de ronda de playoffs |
| Liga MX | Liguilla con desempate por posición; altitud | Hechos de formato envejecen por torneo | ET solo en la final (LMX:281); `q_shootout` NO CALCULADO | Altitud como covariable estimada |
| Brasileirão | 45 controles; receso del Mundial; viajes largos | Proveedores genéricos | `Dweak` frente a `DefenseWeakness` | Control de viajes |
| Chile | Estadio real, superficie, altitud; simulador de tabla/descenso | `RESULTADO` además de `ModelStatus` (CHI:316); intervalos sin método (CHI:283) | Retención ≥ 0.999999 frente a tolerancia | Simulador de tabla/descenso |

Resto de familias:

| Prompt | Fortalezas | Debilidades | Contradicciones | Reutilizable |
|---|---|---|---|---|
| NBA | Única con valores explícitos (`K_games`, HCA) y fallback de OT; fases 12-14 separadas | Numeración de fases distinta; referencia al Injury Report 2026-27 caduca | HCA con valor frente a los otros tres | Fallback de OT; control de back-to-back |
| WNBA | MC con error exigido; «no es una NBA reducida» (WNBA:443) | Sin HCA ni K | Aviso de expansión sin cifra | Regularización por posesiones |
| NCAAB | AdjO/AdjD/AdjT; D-I vs no-D-I; sede neutral y torneos | «No incluye parámetros entrenados» (NCAAB:506) | Etiqueta `P_break_even_condicional = 1/D` (NCAAB:311) | Separación D-I/no-D-I |
| WNCAAB | Más extenso (610 l.); `input_hash`; 20 pruebas; reglamento como constantes | 50/50 en OT permitido para ML exploratorio (l.351) | Cuatro cuartos frente a las dos mitades de NCAAB | `input_hash`/`locked`; traza por fase |
| NFL | `ruleset_id`; resumen ejecutivo y ranking; números clave | OT y reglas 2026 fechadas; URL de host de autoría (NFL:479) | Prohíbe constantes (NFL:44) pero fija OT 2026 | `ruleset_id`; PROE |
| NCAAF | SOS jerárquico; portal; FBS/FCS | 10.000 iteraciones como prototipo; sin `ruleset_id` | Idem constantes | SOS jerárquico |
| ATP | Jerarquía de fuentes numerada (ATP:86-91); baselines (ATP:342); `FairDecimal` | Primer servidor sin regla definida (ATP:257) | Distinto de WTA (0,5/0,5) | `Hold(p)`; baselines |
| WTA | Identificabilidad (WTA:152); CRPS; auditoría de retiradas | `p_A = logistic(logit(p_A))` (WTA:154); sin baselines | 0,5/0,5 por defecto (WTA:197) | Identificabilidad |
| MLB | 14 constantes provisionales etiquetadas (números ejecutables); `rho_9` derivada | Constantes sin medición; extras no modeladas fuera de la regla | Distinto linaje frente al v3 (`NB_alpha`) | Política «provisional con etiqueta» |
| NHL | Cinco marcadores; 30 invariantes; `score_reg` vs `score_for_settlement` | Ninguna constante; 632 líneas | `rho = 0,12` prohibido sin validar | Invariantes; separación regulación/final |

## 3. Matriz plataforma × prompt (sección 9 de cada informe)

Estados: IMPL = implementado; PARC = parcial; AUS = ausente; INAC = implementado e inactivo. Columnas = grupos de fases. Valores de producción citados en los informes. Para el cálculo común: `NormalMarginAdapter` (`src/sqp/sports/adapters.py:29`), `BasketballAdapter` (`:165`), `FootballAdapter` (`:168`), `SoccerAdapter` (`:314-316`), `TennisAdapter` (`:318-338`), `HockeyAdapter` (`:276`); distribuciones en `src/sqp/models/distributions.py`.

| Prompt | Ratings ataque/defensa | Ritmo, once, lesiones, matchup | Distribución conjunta | OT / empate / formato | Simulación MC / DP | Congelación | Validación del prompt |
|---|---|---|---|---|---|---|---|
| EPL, Bundesliga, Serie A | PARC: Elo + tasas aditivas (`team_scoring.py:98-101`); `dc_rho −0,2`, `elo_home_adv 15` | AUS: sin xG, once ni portero | IMPL: Poisson/DC con malla (`distributions.py:204`) | IMPL (90', tres vías) | AUS (no necesario: malla exacta) | IMPL (`daily.py:1031`) | PARC |
| LaLiga, Ligue 1 | PARC: `dc_rho 0,0`, `elo_home_adv 48` (defecto) | AUS | IMPL | IMPL | AUS | IMPL | PARC |
| UCL | PARC: `avg_goals 3,37`, sin ratings multiliga | AUS | IMPL (90') | AUS: eliminatoria, fase liga, campeón | AUS | IMPL | PARC |
| UWCL | PARC: `avg_goals 3,00` (`soccer.yaml:30`), Elo único por liga | AUS | IMPL | AUS | AUS | IMPL | PARC |
| MLS | PARC: `elo_home_adv 30`, `elo_home_away_split true` | AUS | IMPL | AUS: playoffs, ET | AUS | IMPL | PARC |
| Liga MX, Brasileirão, Chile | PARC: valores de familia | AUS (altitud, viajes, superficie) | IMPL | AUS: Liguilla; Chile: tabla/descenso | AUS | IMPL | PARC |
| NBA | PARC: Elo `points_per_elo 0,028`, tasas por equipo | PARC: descanso `0,795` (`ratings.yaml:34-40`); AUS: Pace, ORtg/DRtg, lesiones | AUS: dos Normales independientes (`distributions.py:32-68`) | AUS: sin OT; push eliminado | AUS | IMPL | AUS |
| WNBA | PARC: `points_per_elo 0,024`, `margin_sigma 14` | AUS | AUS | AUS | AUS | IMPL | AUS |
| NCAAB | PARC: σ 16/18, `avg_total 145` | AUS: AdjO/AdjD/AdjT | AUS | AUS | AUS | IMPL | AUS |
| WNCAAB | PARC: σ 18/17, `avg_total 132`; heredados de NBA | AUS | AUS | AUS | AUS | IMPL (sin `input_hash`) | AUS |
| NFL | PARC: Elo con margen; `margin_sigma 13,5` | AUS: EPA, QB, lesiones | AUS | AUS (sin OT, sin empate) | AUS | IMPL | AUS |
| NCAAF | PARC: `margin_sigma 20`, `elo_home_adv 150` | AUS: SOS jerárquico, portal; FBS/FCS sin distinguir | AUS | AUS | AUS | IMPL | AUS |
| ATP | PARC: Elo escalar, `elo_k 40` (`registry.py:52`), sin superficie | AUS: estadística de saque/resto | AUS: solo `h2h` | AUS: BO3/BO5, tie-break | AUS: sin DP | IMPL | AUS |
| WTA | PARC: mismo adapter; K compartido con ATP | AUS | AUS | AUS | AUS | IMPL | AUS |
| MLB | PARC: `avg_total 8,7` fijo, NB `dispersion_k 3,8` | PARC: abridor `pitcher_bound 0,05`; IMPL: parque `park_bound 0,10`; AUS: bullpen, alineación, ump; clima rechazado | PARC: rejilla independiente, `score_rho 0` | AUS: extras con corredor (`TIE_ADDS_GOAL=False`) | AUS | IMPL | PARC |
| NHL | PARC: `avg_total 6,1`, Poisson, `tilt_scale 0,439` | INAC: portero (`goalie_beta 0`), descanso; AUS: PP/PK, xG, empty net | PARC | PARC: `tie_adds_goal` + reescalado; AUS: 1X2 60 min, playoffs | AUS | IMPL | PARC |

[COMPROBADO] Vale para todas las filas: la plataforma estima margen y total (o goles) sin simulador de reglas; ningún motor implementa fases de ranking del prompt ni estados V/E/I.

## 4. Mercado como entrada: prompts frente a plataforma

- [COMPROBADO] Prompts: ninguno usa el mercado como entrada; todos lo consultan tras congelar (informes, sección 7). Líneas de spread/total usadas como umbral: UMBRAL LEGÍTIMO.
- [COMPROBADO] Plataforma: `market_shrink 0.5` (`configs/default.yaml:17`), `p_decision = (1−shrink)·cal(p_model) + shrink·fair` (`src/sqp/pipeline/probabilities.py:303-306`, llamada `daily.py:968-970`) y `uncertainty_penalty 0.35` (`default.yaml:26`), sin exención por deporte: ENTRADA PROHIBIDA en la probabilidad de decisión. La probabilidad pura se conserva en `model_probability`/`adjusted_probability` (`daily.py:1031-1033`). Valor del `.env`: no verificable aquí.
- [COMPROBADO] Hiperparámetros justificados contra la línea de mercado: `registry.py:57-73` (WNBA) y `ratings.yaml:25-29` (`park_bound`, por ROI sobre cuotas).
- [HIPÓTESIS] Calibradores entrenados sobre picks elegidos por edge de mercado (`calibrator.py:714`): sesgo de selección no verificado. Para MLB el informe halla que se entrenan sobre `adjusted_probability` contra resultados (`calibration/data.py:69-80`).

## 5. Componentes a estandarizar y componentes que deben seguir especializados

**Estandarizar (un solo contrato para los 21):**
1. [RECOMENDACIÓN] Esquema de salida: `ValidationStatus` único, `DefenseWeakness` con signo fijo (mayor = más débil), numeración de fases común y `ruleset_id` obligatorio.
2. [RECOMENDACIÓN] Cláusula de independencia incondicional (corregir Serie A l.21 y Ligue 1 l.19) y regla de congelación con `input_hash`/`locked` (WNCAAB) y `as_of`/`available_at` (Bundesliga).
3. [RECOMENDACIÓN] Fórmulas de decisión y etiquetas (`EV`, `P_break_even = (1−P_push)/D`; corregir NCAAB:311) y tolerancia de masa omitida única.
4. [RECOMENDACIÓN] Política de constantes: «provisional con etiqueta y procedencia» (MLB) frente a «vacío» (NHL, resto); elegir una y fijar el criterio de MC (N, semiancho y semilla).
5. [RECOMENDACIÓN] Tratamiento de datos faltantes con niveles de fallback A-D (UCL, ATP) y estados de verificación de dato (Bundesliga); tratamiento común de `q_shootout` y de intervalos de predicción con método explícito.
6. [RECOMENDACIÓN] Lista de invariantes (NHL: 30) y baselines independientes (ATP) como paquete común; política de HFA por defecto.

**Mantener especializados:**
- Distribución del marcador y su mecanismo de resolución: Markov de tenis, NB con gamma del béisbol, Poisson por estado del hockey, posesiones × eficiencia del baloncesto, PMF con números clave del fútbol americano, matriz DC del fútbol.
- Reglas de formato y prórroga (UCL/UWCL/MLS/Liga MX, OT NBA/NFL/NHL/MLB, tie-break), ascendidos y calendario, y los efectos físicos propios (abridor, portero, QB, superficie, altitud, parque).
- Priors de datos y fuentes por competición (ASA, KenPom/Torvik, EPA, Next Gen Stats); y no trasladar parámetros entre ATP/WTA, NBA/WNBA, NCAAB/WNCAAB (prohibido por los propios prompts, por ejemplo WTA:49, WNCAAB:336).

[INFERENCIA] Con las limitaciones de esta auditoría (sin ejecutar los prompts, sin verificar reglamentos 2026/27), cualquier unificación debe validarse con datos de la plataforma antes de fijar constantes.
