# 04 — Auditoría matemática transversal (fase 2)

Fecha: 2026-11-10. Escalón Fable. Base: los 21 informes de `docs/prompts-audit/individual/` y los 6 de `docs/prompts-audit/familias/`, con cada afirmación elevada a hallazgo verificada contra `C:\dev\Prompts\*.md` (citas `PROMPT:línea`) o contra el repositorio (citas `ruta:línea`). Etiquetas: [COMPROBADO] cita verificada; [INFERENCIA] razonamiento técnico; [HIPÓTESIS] no comprobado; [RECOMENDACIÓN].

Principio del operador que rige la lectura: las probabilidades se construyen solo con información deportiva y modelos estadísticos; el mercado solo compara después de congelar; una línea de mercado usada como umbral `P(X > t)` es legítima, usada como media no lo es.

## 0. Mapa: qué modelo pide cada prompt y qué modelo corre en producción

| Familia (prompts) | Modelo que piden los prompts | Modelo de producción | Cita de producción |
|---|---|---|---|
| Fútbol (11: EPL, LaLiga, Bundesliga, Serie A, Ligue 1, UCL, UWCL, MLS, Liga MX, Brasileirão, Chile) | log-lineal ataque/defensa con xG → λ por equipo → Poisson independiente o Dixon-Coles → malla entera → 1X2/BTTS/CS/totales/hándicap | Elo (con `elo_home_adv`) → `p_home` → `tilt` sobre el total esperado por tasas de equipo → λ_home/λ_away → malla Poisson con `dc_rho` opcional, `max_score 10` | `src/sqp/sports/adapters.py:126-143`, `src/sqp/models/distributions.py:204-266`, `src/sqp/sports/registry.py:45-47` |
| Baloncesto (4: NBA, WNBA, NCAAB, WNCAAB) | Pace × eficiencia (ORtg·DRtg/L) → distribución conjunta de marcadores (bootstrap de residuos o bivariante) → OT explícita → ML/spread/total de los mismos marcadores | Margen ~ Normal(Elo·`points_per_elo` + descanso, `margin_sigma`); total ~ Normal(tasas de equipo, `total_sigma`); **independientes** | `adapters.py:60-80`, `distributions.py:32-70`, `registry.py:29-31` |
| Fútbol americano (2: NFL, NCAAF) | PMF conjunta de marcadores enteros por drives/posesiones; OT y empate explícitos; prohíbe «Normal con sigma arbitrario» (NFL:271) | Misma familia Normal independiente que el baloncesto; sin empate; sin OT | `adapters.py:168-169`, `registry.py:32-34`, `registry.py:97` |
| MLB (1) | NB por equipo vía gamma compartida (`k=0,15`, `f=0,30`), carreras de 9 entradas, simulador de reglas (walk-off, extras) | NB por equipo (`dispersion_k 3,8`), marcador FINAL, sin simulador; abridor y parque como factores acotados sobre λ | `registry.py:40-42`, `distributions.py:86-100`, `adapters.py:174-221` |
| NHL (1) | Tasas por estado de juego (5v5/PP/PK), portero, simulador de eventos con OT 3v3 y SO | Poisson por equipo (dispersión medida 1,01), gol extra en empate reglamentario con reescalado (`TIE_ADDS_GOAL`), portero acotado inactivo (`goalie_beta 0`) | `registry.py:43-44`, `distributions.py:219-236`, `adapters.py:288-312` |
| Tenis (2: ATP, WTA) | Servicio/resto → `Hold(p)` → DP de tie-break, set y partido; BO3/BO5; retiradas | Elo escalar por jugador, sin superficie, `elo_k 40`, `neutral=True`; solo `h2h` | `adapters.py:318-338`, `registry.py:48-52` |

[COMPROBADO] Ninguna de las seis cadenas de los prompts está implementada como tal; la plataforma comparte dos motores (malla Poisson/NB y Normal independiente) más Elo. La auditoría matemática debe, por tanto, juzgar dos objetos distintos: la especificación de los prompts y el motor real.

## 1. Fútbol: Poisson y Dixon-Coles

### 1.1 Fundamento estadístico

- [COMPROBADO] Los once prompts escriben la misma corrección Dixon-Coles de 1997 (`τ(0,0)=1−λμρ`, `τ(0,1)=1+λρ`, `τ(1,0)=1+μρ`, `τ(1,1)=1−ρ`; EPL:209-212 según el informe individual; `distributions.py:71-80` en la plataforma). [INFERENCIA, verificado algebraicamente] Con marginales Poisson independientes la masa total se conserva exactamente: `Σ p(i,j)(τ−1) = e^{−λ−μ}·ρ·(−λμ + λμ + λμ − λμ) = 0`. Por eso el prompt EPL acierta al exigir `τ ≥ 0` (EPL:215, informe individual) sin renormalizar. **Matiz de la plataforma:** `poisson_match_probs` aplica `τ` sobre una rejilla que puede ser NB (`dispersion_k`) o con cópula (`score_rho`) (`distributions.py:244-245`); en esos casos la cancelación no se cumple y la función renormaliza por la masa total (`distributions.py:262-266`). En fútbol `dispersion_k` es `None` y `score_rho` 0, así que la rejilla es Poisson pura y el comentario se limita a hockey/béisbol.
- [COMPROBADO] Valor de producción de `dc_rho`: −0,2 en EPL, Bundesliga y Serie A (`configs/leagues/ratings.yaml:10-15, 51-53`), 0,0 en las otras ocho ligas (`registry.py:47`). [COMPROBADO] El intento de tunear `dc_rho` en cuatro ligas más fue refutado por el gate OOS (`Obsidian/Tareas.md:115`: mejoras −0,0007 a +0,0012 frente al margen 0,0020). Es decir, la dependencia de marcadores bajos **no explica** los cortes malos de fútbol.
- [INFERENCIA] Poisson independiente con DC es el estándar defendible de fútbol; el supuesto no comprobado que arrastran todos los prompts es la **conversión xG → goles**: el baseline multiplicativo `λ = LeagueGoals · OffIndex · DefWeakIndex` mezcla goles de liga con índices de xG (EPL:191-194; BUNDESLIGA:105 lo advierte: «xGF es creación de ocasiones, no equivalencia exacta a goles»). Ningún prompt da la forma de la calibración. La plataforma esquiva el problema porque solo usa goles (`team_scoring.py:92-101`), al precio de no usar xG.

### 1.2 Localía: una vez o dos

- [COMPROBADO] Los prompts exigen aplicar la localía **una sola vez** (EPL:174; LALIGA:134 y 208; BUNDESLIGA:228: «Las referencias `LeagueGoals_home/away` ya reflejan diferencia media de sede. No añadir HFA sin justificar»).
- [COMPROBADO] La plataforma la aplica por **dos canales**: `elo_home_adv` entra en `rating_diff` (`src/sqp/models/elo.py:70-77`) y de ahí en `p_home` y en el `tilt` del reparto de goles (`adapters.py:133-140`); además `home_scoring_bonus` (0,15 goles en fútbol, 0,10 en béisbol y hockey; `registry.py:41, 44, 46`) se suma a `λ_home` (`adapters.py:141`). [INFERENCIA] No es necesariamente doble conteo si ambos se estimaron conjuntamente, pero `tune_home_advantage` solo recorre `elo_home_adv` con `home_scoring_bonus` fijo (`src/sqp/backtesting/tuning.py:150-158`), de modo que el segundo canal nunca se ha validado por separado. [HIPÓTESIS] Que la suma sobreestime la localía no está medido.

### 1.3 Truncamiento de la malla

- [COMPROBADO] Los prompts exigen reportar la masa omitida con tolerancias distintas: 1e-4 (EPL:217), 1e-5 (LALIGA:72), 1e-6 (Serie A, Ligue 1, UCL; familia `futbol-europa.md` §2.1), y EPL:217 prohíbe «renormalizar silenciosamente colas grandes».
- [COMPROBADO] La plataforma trunca en `max_score 10` (fútbol), 15 (hockey), 25 (béisbol) y **siempre renormaliza** por la masa (`distributions.py:262-266`) sin reportarla. [INFERENCIA, cálculo propio] Para Poisson con λ ≤ 2,5 la masa por encima de 10 es < 1e-4; con λ = 3,5 (un favorito extremo en una liga de 3,2-3,4 goles) ronda 1e-3 por equipo. El efecto sobre 1X2 es despreciable, pero la regla del prompt (reportar) es la correcta y la plataforma no la cumple. En hockey (λ ≈ 3, techo 15) y béisbol (NB, μ ≈ 5,5, techo 25) la masa omitida es inferior a 1e-4.

### 1.4 Prórroga, penales y eliminatorias

- [COMPROBADO] UCL, UWCL, MLS y Liga MX piden módulos de ida/vuelta, prórroga y penales; ninguno define cómo estimar `q_shootout` (familia `futbol-america-y-femenino.md` §2.6; UCL individual §6). La plataforma no tiene módulo de eliminatoria: 1X2 de 90 minutos para todo (`adapters.py:314-316`, `three_way=True`). [INFERENCIA] Es una carencia compartida: los prompts la nombran sin especificarla y la plataforma no la tiene.

## 2. Baloncesto: Normal independiente frente a conjunta

- [COMPROBADO] NBA:195: «No simular un margen y un total independientes si históricamente están correlacionados. No imponer rho sin definir una distribución conjunta realizable». La plataforma hace exactamente lo primero: `normal_margin_probs` y `normal_total_probs` son dos Normales separadas (`distributions.py:32-70`, invocadas en `adapters.py:71-72`).
- [INFERENCIA] Fundamento: el margen de baloncesto es aproximadamente Normal con sigma 11-14 puntos; la plataforma mide `margin_sigma` como residual walk-forward (13,0 NBA; 14,0 WNBA; 16 NCAAB; 18 WNCAAB, `registry.py:26-31, 76, 95-96`). Eso está bien fundado. Lo **no comprobado** es la independencia margen-total: no hay en el repositorio una medición de la correlación margen-total en baloncesto (la medida de `score_rho` es de hockey y béisbol, `distributions.py:123-126`). Con dos Normales separadas, la plataforma no puede producir team totals coherentes ni combinados.
- [COMPROBADO] Push en líneas enteras: la plataforma usa corrección de continuidad ±0,5 y renormaliza `p/(1−push)` (`distributions.py:46-50, 62-66`); el prompt publica `P_win/P_push/P_loss` (NBA:220-237 según el individual). [INFERENCIA] Para baloncesto, sin números clave, la aproximación es aceptable; lo que se pierde es `P_push` como dato publicado.
- [INFERENCIA] Prórroga: la plataforma la absorbe en el sigma del marcador final; el prompt NBA la simula (Poisson como fallback, NBA:206). Poisson sobredispersa un periodo de 5 minutos; impacto pequeño porque `P(OT) ≈ 6 %` (NBA individual §6). WNCAAB:351 admite un 50/50 para desempates solo en ML exploratorio; [INFERENCIA] cuando hay empate en regulación, el favorito tiene ventaja en la prórroga, y el 50/50 sesga el ML hacia el no favorito. En la plataforma el problema no existe porque la Normal no tiene masa de empate.
- [COMPROBADO] HCA: NBA:58 fija +2,0 puntos (informe individual); la plataforma usa `elo_home_adv 70` × `points_per_elo 0,028` = 1,96 puntos (`registry.py:29-31`), coherente. [COMPROBADO] NCAAB y WNCAAB heredan `points_per_elo 0,028` y `elo_home_adv 70` de la **familia** basketball (`registry.py:29-31, 95-96` solo sobrescriben `avg_total`, `total_sigma`, `margin_sigma`), lo que contradice WNCAAB:35 («no copiar medias, sigmas, coeficientes de localía… de NBA, WNBA o NCAAB»). Nota: el informe de familia dice «heredan de NBA»; en rigor heredan de la familia, pues NBA tampoco los sobrescribe.
- [COMPROBADO] Recencia: `scoring_half_life_days` 60 (WNBA) y 180 (NBA) (`registry.py:76-78, 92`). El 180 de NBA se eligió «por el precedente de wnba, no por minimizar el Brier de la rejilla» (`registry.py:87-89`): decisión explícitamente anti-sobreajuste.

## 3. Fútbol americano: Normal, números clave y empate

- [COMPROBADO] NFL:271 prohíbe «una Normal de margen/total con sigma arbitrario» y NFL:36 exige una única distribución conjunta; NFL:263 prohíbe publicar ML/spread/total finales si no se modela la prórroga. La plataforma usa Normal con `margin_sigma 13,5` y `total_sigma 13,5` de familia (`registry.py:32-34`) y `margin_sigma 20` en NCAAF (`registry.py:97`, residual medido 20,2); no modela empate ni OT.
- [INFERENCIA] El margen de la NFL es discreto con masa concentrada en 3, 6, 7, 10 y 14; la Normal subestima `P(push)` en líneas enteras de 3 y 7 y suaviza P(cover) alrededor de ellas. Es el deporte donde la aproximación Normal es **peor fundada**. Ningún prompt nombra los números clave (NFL individual §6, [RECOMENDACIÓN] de añadirlos como prueba de la PMF).
- [COMPROBADO] `normal_margin_probs` no genera empate (`home_win = 1 − cdf(0)`, `distributions.py:43-44`), mientras el Elo cuenta el empate como 0,5 (`elo.py:121-122`, individual NFL §9). [HIPÓTESIS] P(empate) real en temporada regular ≈ 0,3-0,4 %; el sesgo sobre ML es de ese orden.
- [INFERENCIA] NCAAF: `margin_sigma 20` con disparidad de talento → colas pesadas y asimetría (palizas); una Normal con sigma único es un supuesto no comprobado; el individual sugiere mezcla o modelo de cola.
- [INFERENCIA] Los prompts, por su parte, especifican modelos drive-by-drive con `Softmax(g(θ…))` (NFL:220) no ejecutables y con muchos grados de libertad frente a ~272 partidos/temporada: el riesgo opuesto (sobreajuste) está en los prompts, no en la plataforma.

## 4. MLB: binomial negativa, gamma compartida y correlación

- [COMPROBADO, verificado algebraicamente] El prompt MLB define `Z_shared ~ Gamma(f/k, k)`, `Z_i ~ Gamma((1−f)/k, k)`, `G_i = Z_shared + Z_i`, carreras|G ~ Poisson(μ_i·G_i). Con escala `k`: `E[G_i] = 1`, `Var(G_i) = k`, `Cov(G_a, G_h) = f·k`; marginales `Var(R_i) = μ_i + k·μ_i²` y `ρ_9 = f·k·μ_a·μ_h / sqrt((μ_a + kμ_a²)(μ_h + kμ_h²))` (MLB:138). La fórmula es correcta.
- [COMPROBADO] La plataforma parametriza `Var = μ + μ²/k` con `k = 3,8` (`distributions.py:86-96`, `registry.py:35-41`: razón varianza/media medida 2,21 sobre 14.223 equipos-partido). En la parametrización del prompt eso equivale a `k_prompt = 1/3,8 ≈ 0,263`; el prompt fija `k = 0,15`. [INFERENCIA] Para μ ≈ 4,35 la varianza por equipo es 7,19 (prompt) frente a 9,33 (plataforma): el prompt **subdispersa** y sobreconfía colas de totales y run line.
- [INFERENCIA, cálculo propio] Con `f = 0,30`, `k = 0,15` y μ ≈ 4,35, `ρ_9 = 0,30·0,15·18,9 / 7,19 ≈ 0,118`. Es decir, las constantes provisionales del prompt MLB **implican el mismo 0,12** que los prompts NHL y NFL prohíben importar «de MLB» (NHL:94, 274; NFL:271). [COMPROBADO] La plataforma midió la correlación residual walk-forward en MLB: −0,0043, p = 0,68 (`distributions.py:123-126`), es decir, **cero**. La estructura de dependencia positiva del prompt es un supuesto no comprobado y contradicho por la medición disponible; el propio prompt la etiqueta provisional (MLB:48).
- [COMPROBADO] Nueve entradas frente a marcador final: el prompt lo reconoce (MLB:125) y exige simulador de reglas; la plataforma ajusta marcadores finales con `TIE_ADDS_GOAL = False` para béisbol porque «extras can add several runs» (`adapters.py:93-96`). [INFERENCIA] Ambas son aproximaciones; la de la plataforma es coherente con la liquidación (marcador final), la del prompt necesita un simulador que no existe.
- [COMPROBADO] Abridor: `pitcher_bound 0,05` activado «por orden, no por evidencia concluyente» (Δ log loss −0,00087 frente a margen 0,002; `ratings.yaml:17-23`). Parque: `park_bound 0,10` (`ratings.yaml:25-30`), ver `05-informe-de-riesgos.md` R2 por el criterio de elección.
- [HIPÓTESIS] `HomeAdj = √1,02` del prompt implica ~50,8 % de victoria local (individual MLB §6), por debajo del ~53 % histórico; no medido aquí.

## 5. NHL: Poisson, empate reglamentario y portero

- [COMPROBADO] Dispersión medida 1,01 sobre 52.540 equipos-partido (`distributions.py:88-91`): Poisson está **fundado** en hockey, a diferencia del béisbol.
- [COMPROBADO] Gol extra en empate reglamentario con reescalado de tasas para conservar el total final (`distributions.py:219-236`), validado contra frecuencias observadas (P(Over 4,5/5,5/6,5/7,5) = 0,764/0,553/0,442/0,255 frente a 0,781/0,558/0,444/0,244). [INFERENCIA] Es una aproximación sólida al problema que el prompt resuelve con simulador de OT/SO (NHL:352-365); reparte el empate 50/50 en el h2h. En hockey el 50/50 es menos erróneo que en baloncesto porque OT 3v3 y SO están cerca de la moneda, pero sigue sin dar ventaja al favorito [HIPÓTESIS: no medido].
- [COMPROBADO] Correlación de marcadores: `score_rho` medido −0,0873 (p < 0,0001, n = 32.777) e implementado como término de primer orden de cópula gaussiana que preserva marginales (`distributions.py:119-150`); el pre-registro lo **RECHAZÓ** porque pasa el gate en spreads (+0,0068) pero no en totals (0,0000) (`docs/research/2026-08-26-resultado-correlacion-marcadores.md:1-17`). En producción `score_rho = 0`. El prompt NHL exige estimar la dependencia y no fijarla (NHL:274): la plataforma lo hizo y decidió por evidencia.
- [INFERENCIA] Portero: el prompt usa `exp(−β_G·GSAx60)` (NHL:188), que mezcla unidades salvo que β absorba la escala; la plataforma usa `f = clip(1 − β·q/(1−L_D), 1−bound, 1+bound)` (`src/sqp/models/goalies.py:22`), con significado directo (fracción de goles evitados). Está inactiva (`goalie_beta 0`, `adapters.py:292`).

## 6. Tenis: cadena de Markov frente a Elo escalar

- [COMPROBADO] `Hold(p) = p⁴(1+4q+10q²) + 20p³q³·p²/(p²+q²)` (ATP:223, WTA:185-186 según individuales) es la fórmula cerrada correcta del juego con puntos iid. ATP:225 reconoce que «es una identidad del modelo iid, no evidencia».
- [INFERENCIA] Supuesto no comprobado: puntos iid con `p` constante durante el partido. Subestima la varianza de juegos y sets (dependencia por marcador, fatiga, lado); sobreconfía totales de juegos y marcadores exactos. Es el riesgo estructural de la familia.
- [INFERENCIA] Identificabilidad: ATP suma `ServeStrength − ReturnStrength + X·β` sin restricción de suma cero (ATP individual §6); WTA la incluye (WTA:152) pero omite `X·β` y contiene la tautología `p_A = logistic(logit(p_A))` (WTA:154).
- [COMPROBADO] La plataforma: Elo de tour completo, sin superficie, `elo_k 40` medido con orientación aleatorizada (log loss 0,6563 frente a 0,6931 de la moneda; `registry.py:48-52`), `neutral=True` (`adapters.py:333`). No hay sets, juegos ni tie-break; solo `h2h`.

## 7. Coherencia entre mercados (ML, spread, total de una misma distribución)

| Motor | ML y spread | Total | Team totals / combinados | Push |
|---|---|---|---|---|
| Malla Poisson/NB (fútbol, MLB, NHL) | Misma rejilla (`distributions.py:246-266`) | Misma rejilla | Posibles por construcción (no servidos) | Probabilidad de decisión `win/(win+loss)` coherente con la liquidación, cuartos asiáticos por líneas adyacentes (AUD-001) |
| Normal independiente (baloncesto, fútbol americano) | Misma Normal del margen: coherentes entre sí | Normal **separada** | No derivables de forma coherente | Continuidad ±0,5 y renormalización |
| Elo tenis | Solo ML | — | — | — |
| Prompts (21) | Exigen una sola distribución (NFL:36; NBA:195; ATP individual §6; fútbol: matriz única) | Idem | Derivables si la distribución los sostiene (EPL:20) | Publican `win/push/loss` por separado |

[COMPROBADO] El contrato de servicio de la plataforma es «probabilidad de decisión» (push eliminado), que coincide con lo que liquida `settle._grade`; los prompts publican tres componentes. No es una incoherencia sino una convención distinta: `EV` del prompt (`P_win(D−1) − P_loss`) y `edge` de la plataforma (EV por unidad resuelta, `configs/default.yaml:4`; `daily.py:971-973`) tienen el mismo signo pero no son comparables numéricamente (familia `futbol-america-y-femenino.md` §2.5).

## 8. Cuantificación de la incertidumbre

- [COMPROBADO] Los prompts separan error Monte Carlo de incertidumbre de modelo y de datos (NBA:215 según individual; EPL:292-298; UCL:243) pero **ninguno define el método** para el intervalo (familia `futbol-america-y-femenino.md` §2.7: CHI:283 prohíbe intervalos sin método, UWCL:344 y BRA:278 exigen «CUANTIFICADA»).
- [COMPROBADO] La plataforma no propaga incertidumbre de parámetros: sigmas fijos por liga, λ puntuales. El parámetro llamado `uncertainty_penalty` (`configs/default.yaml:26`) **no es incertidumbre epistémica**: es la distancia `|p − fair|` entre modelo y mercado (`src/sqp/markets/edge.py:70-71`). El nombre induce a confundir desacuerdo con el mercado e incertidumbre del modelo; ver `07-independencia-del-mercado.md`.
- [INFERENCIA] La única cuantificación empírica de incertidumbre en la plataforma es ex post: residuales walk-forward (`registry.py:21-28`), ECE/Brier del calibrador (`src/sqp/calibration/calibrator.py:690-720`) y los IC bootstrap de los pre-registros.

## 9. Lo que tiene fundamento, lo que es supuesto, lo que no debe trasladarse

| Elemento | Estado | Evidencia |
|---|---|---|
| Poisson en hockey | Fundado | dispersión 1,01 (`distributions.py:88-91`) |
| NB en béisbol, k = 3,8 | Fundado | 2,21 var/media (`registry.py:35-38`) |
| Dixon-Coles con τ ≥ 0, masa conservada | Fundado (álgebra §1.1) | prompts + `distributions.py:71-80` |
| Normal del margen en baloncesto, sigma residual | Fundado | `registry.py:26-28` |
| Independencia margen-total (Normal) | **Supuesto no comprobado** | sin medición en el repo |
| Normal en NFL/NCAAF (números clave, empate, colas) | **Supuesto débil** | §3 |
| `f = 0,30`, `k = 0,15` (MLB prompt) | **Supuesto contradicho** (ρ ≈ 0,12 frente a −0,004 medido; k subdispersado) | §4 |
| `rho = 0,12` en cualquier deporte | **No trasladar** | NHL:94, 274; NFL:271; plataforma mide por deporte |
| Puntos iid en tenis | Supuesto no comprobado, declarado | ATP:225 |
| xG como tasa de goles sin calibrar | Supuesto no comprobado, declarado | BUNDESLIGA:105 |
| Localía por dos canales (plataforma) | Supuesto no validado por separado | §1.2 |
| `points_per_elo` y `elo_home_adv` de familia en NCAAB/WNCAAB | **No trasladar**: contradice WNCAAB:35 | `registry.py:29-31, 95-96` |
| Half-life 60/180, rest 0,795 (NBA), tilt 0,439 (NHL) | Específicos de liga; **no trasladar** | `registry.py:76-92`, `ratings.yaml:34-50` |
| Gol extra en empate (`TIE_ADDS_GOAL`) | Solo hockey; **no trasladar** a béisbol | `adapters.py:93-96, 288` |
| 50/50 en empates (WNCAAB:351; NHL h2h de la plataforma) | Supuesto sesgado contra el favorito | §2, §5 |

## 10. Conclusión matemática

[INFERENCIA] Los prompts son especificaciones metodológicamente correctas (una distribución por partido, push explícito, localía única, dependencia estimada y no fijada) pero no ejecutables y, en los dos casos con constantes (MLB, NBA), con valores que la evidencia de la plataforma contradice (MLB `f`, `k`) o confirma (NBA HCA). La plataforma es matemáticamente más modesta y, en las familias de malla, más coherente con la liquidación; su debilidad estructural está en la familia Normal independiente (baloncesto y, sobre todo, fútbol americano) y en la localía por dos canales. Las correcciones de modelo que de aquí se deriven son cambios de régimen y, por el pre-registro «el modelo manda» (`docs/research/2026-08-26-preregistro-el-modelo-manda.md:289`), exigen addendum antes de medir; no se propone ninguna para antes de esa medición.
