# 01. Inventario de los prompts deportivos (`C:\dev\Prompts`)

Fecha: 2026-11-10. Solo lectura; sin commits. Etiquetas: [COMPROBADO], [INFERENCIA], [HIPÓTESIS], [RECOMENDACIÓN]. Los informes individuales están en `individual/` y los de familia en `familias/` (enlaces relativos a este fichero).

Principio rector de la auditoría (operador): las probabilidades se construyen solo con información deportiva y modelos estadísticos independientes; el mercado solo compara, después de congelar. Una línea usada como umbral a evaluar es legítima; usada como media o ajuste, no.

## 1. Inventario por fichero

[COMPROBADO] Líneas, bytes y sha256 calculados con un script de Python sobre los ficheros (`gen_inv.py`, en el scratchpad de la sesión). «Fases» = número de encabezados `#… Fase` del fichero. «Versión declarada» = primera línea literal del fichero. Los modos VALIDADO/EXPLORATORIO/INCOMPLETO son el estado de salida; ATP y WTA añaden NO CALCULADO y fallbacks.

| Fichero | Deporte, competición, género | Versión declarada (línea 1) | Líneas | Bytes | sha256 | Fases | Modos de operación | Mercados que produce | Informe individual |
|---|---|---|---|---|---|---|---|---|---|
| `PROMPT_191_ATP_v1_0.md` | Tenis; ATP Tour, Finals y módulo Slam; masculino | # PROMPT 191-ATP v1.0 — Motor cuantitativo de pricing pregame de tenis masculino individual | 450 | 31385 | `96097d94b76f8aa3c0447de1ddee92acdc39e4656f803abd6ae01c5dcfa12a30` | 21 | Fallbacks A-D; VALIDADO/NO CALCULADO/INCOMPLETO/EV NO EVALUABLE | Ganador, sets, juegos (O/U, hándicap), tie-break; BO3 y BO5 | [informe](individual/PROMPT_191_ATP_v1_0.md) |
| `PROMPT_191_BRASILEIRAO_v1_0.md` | Fútbol; Brasileirão; masculino | # PROMPT 191-BRASILEIRÃO v1.0 | 431 | 28027 | `2ca4dbc31a658d713305c4e7a101cb8ee20176acffab0cfb91109b8d4024b256` | 21 | VALIDADO/EXPLORATORIO/INCOMPLETO | 1X2, BTTS, CS, totales, hándicap, DNB, doble oportunidad | [informe](individual/PROMPT_191_BRASILEIRAO_v1_0.md) |
| `PROMPT_191_BUNDESLIGA_v1_0.md` | Fútbol; Bundesliga; masculino | # PROMPT 191-BUNDESLIGA — PREGAME PRICING ENGINE v1.0 | 468 | 28242 | `a0f514969945d5db974faa0e610655450ac16d9b97ffa8d60d5f3e11edaef724` | 21 | VALIDADO/EXPLORATORIO/INCOMPLETO | 1X2, BTTS, CS, totales, hándicap | [informe](individual/PROMPT_191_BUNDESLIGA_v1_0.md) |
| `PROMPT_191_CHILE_v1_0.md` | Fútbol; Primera División de Chile; masculino | # PROMPT 191-CHILE v1.0 — Motor cuantitativo pregame para la Primera División de Chile | 402 | 26467 | `49db11698d00a47f4689dd3f79fea6b2eb34ed80ce20ac836a6fccd8abc71be7` | 21 | VALIDADO/EXPLORATORIO/INCOMPLETO | 1X2, BTTS, CS, totales, hándicap, tabla/descenso | [informe](individual/PROMPT_191_CHILE_v1_0.md) |
| `PROMPT_191_EPL_v1_0.md` | Fútbol; Premier League; masculino | # PROMPT 191-EPL v1.0 | 429 | 28855 | `009e75a249299a931a90567c6448f6e84a7becf9d9c0cb823e771db0bb6f4a2e` | 21 | VALIDADO/EXPLORATORIO/INCOMPLETO | 1X2, BTTS, CS, totales, hándicap | [informe](individual/PROMPT_191_EPL_v1_0.md) |
| `PROMPT_191_LALIGA_v1_0.md` | Fútbol; LaLiga; masculino | # PROMPT 191-LALIGA — MOTOR CUANTITATIVO DE PRICING PREGAME | 554 | 32070 | `139d4cf68494375cf9037b651a18509beec47c2c3d1d2b20587180dbf7e59775` | 21 | VALIDADO/EXPLORATORIO/INCOMPLETO | 1X2, BTTS, CS, totales, hándicap, combinados BTTS+resultado | [informe](individual/PROMPT_191_LALIGA_v1_0.md) |
| `PROMPT_191_LIGA_MX_v1_0.md` | Fútbol; Liga MX (+ Liguilla); masculino | # PROMPT 191-LIGA MX — PREGAME PRICING ENGINE v1.0 | 454 | 26542 | `e45c94626d1c4a78a9505ae9bf3b98fd85deaae57d5b1d570a02e24e7b94efc7` | 21 | VALIDADO/EXPLORATORIO/INCOMPLETO | 1X2, BTTS, CS, totales, hándicap, Liguilla | [informe](individual/PROMPT_191_LIGA_MX_v1_0.md) |
| `PROMPT_191_LIGUE_1_v1_0.md` | Fútbol; Ligue 1; masculino | # PROMPT 191-LIGUE 1 — PREGAME PRICING ENGINE | 357 | 26324 | `04713d864def96155038507579a9b26d776af336c593a54d4f9fa283c0b5b169` | 21 | VALIDADO/EXPLORATORIO/INCOMPLETO | 1X2, BTTS, CS, totales, hándicap | [informe](individual/PROMPT_191_LIGUE_1_v1_0.md) |
| `prompt_191_mlb_corregido_v2.md` | Béisbol; MLB (regular y playoffs); masculino | # PROMPT 191 — MLB PREGAME PRICING ENGINE v2.0 | 266 | 28137 | `2154f7fa61404044cd6f5454f84a17391edfe876a521eadca78fa98c864eef97` | 21 | VALIDADO/EXPLORATORIO/INCOMPLETO | ML, run line ±1,5 (y otras), totales; sin team totals ni F5 | [informe](individual/prompt_191_mlb_corregido_v2.md) |
| `PROMPT_191_MLS_v1_0.md` | Fútbol; MLS (+ playoffs); masculino | # PROMPT 191-MLS v1.0 — MOTOR CUANTITATIVO DE PRICING PREGAME | 360 | 28521 | `8a751d5957e4276e7456c579f1a3fc733d94c7f41cdfb191ed8eeccd104f11e3` | 21 | VALIDADO/EXPLORATORIO/INCOMPLETO | 1X2, BTTS, CS, totales, hándicap, playoffs con prórroga | [informe](individual/PROMPT_191_MLS_v1_0.md) |
| `PROMPT_191_NBA_v1_0.md` | Baloncesto; NBA (incl. Cup/play-in); masculino | # PROMPT 191-NBA — MOTOR CUANTITATIVO DE PRICING PREGAME | 433 | 33771 | `f6f3a33d01f79e49b41e6c7abb2ea426ad242e305bdc69917e57453a4bb6be49` | 21 | VALIDADO/EXPLORATORIO/INCOMPLETO | ML, spread, total con push; OT | [informe](individual/PROMPT_191_NBA_v1_0.md) |
| `PROMPT_191_NCAAB_v1_0.md` | Baloncesto; NCAA D-I; masculino | # PROMPT 191-NCAAB v1.0 — Motor cuantitativo pregame NCAA Division I masculina | 506 | 30173 | `31c8a734ff0c901f2ee120d3f4449c857f90442ce966e04ec37618d1712d6adb` | 21 | VALIDADO/EXPLORATORIO/INCOMPLETO | ML, spread, total con push; OT; torneos | [informe](individual/PROMPT_191_NCAAB_v1_0.md) |
| `PROMPT_191_NCAAF_v1_0.md` | Fútbol americano; NCAA FBS (bowls, CFP); masculino | # PROMPT 191-NCAAF v1.0 — MOTOR CUANTITATIVO DE PRICING PREGAME | 447 | 32117 | `58618687c69b2976c5b18c701f1596b407ad4539e9f99896f7443d804f3f7001` | 21 | VALIDADO/EXPLORATORIO/INCOMPLETO | ML 2 vías, spread, total con push | [informe](individual/PROMPT_191_NCAAF_v1_0.md) |
| `PROMPT_191_NFL_v1_0.md` | Fútbol americano; NFL (regular y playoffs); masculino | # PROMPT 191-NFL — PREGAME QUANTITATIVE PRICING ENGINE v1.0 | 491 | 31642 | `df107a58849ef826d9b5eceeff0ee0efc794a680b2077027ba27ced2b86311c7` | 21 | VALIDADO/EXPLORATORIO/INCOMPLETO | ML (con empate en regular), spread, total con push | [informe](individual/PROMPT_191_NFL_v1_0.md) |
| `PROMPT_191_NHL_v1_0.md` | Hockey; NHL (REG y PLAYOFF); masculino | # PROMPT 191-NHL v1.0 — MOTOR CUANTITATIVO DE PRICING PREGAME | 632 | 35261 | `1904497d047fc0b12da76a32af5e396d5ac6bd9f3631464dd584e07085a50e00` | 21 | VALIDADO/EXPLORATORIO/INCOMPLETO | 1X2 60 min, ML final, puck line, totales reg/final, team totals | [informe](individual/PROMPT_191_NHL_v1_0.md) |
| `PROMPT_191_SERIE_A_v1_0.md` | Fútbol; Serie A; masculino | # PROMPT 191-SERIE A — PREGAME PRICING ENGINE v1.0 | 532 | 27381 | `3def8b77447dcedae1fdf1db06ca9b12c141c08b43409313a0ff5f318b55f5a8` | 21 | VALIDADO/EXPLORATORIO/INCOMPLETO | 1X2, BTTS, CS, totales, hándicap | [informe](individual/PROMPT_191_SERIE_A_v1_0.md) |
| `PROMPT_191_UCL_v1_0.md` | Fútbol; UEFA Champions League; masculino | # PROMPT 191-UCL v1.0 — UEFA CHAMPIONS LEAGUE PREGAME PRICING ENGINE | 389 | 28432 | `cc38d61ace14e8a6dd8156f88b3cfc46c777c8428f7b5738c540e6a2bb8b49c2` | 21 | VALIDADO/EXPLORATORIO/INCOMPLETO | 1X2 90', eliminatoria (ida/vuelta/global/ET/penales), fase liga, campeón, BTTS, totales | [informe](individual/PROMPT_191_UCL_v1_0.md) |
| `PROMPT_191_UWCL_v1_0.md` | Fútbol; UEFA Women's Champions League; femenino | # PROMPT 191-UWCL — Motor cuantitativo de pricing pregame | 468 | 27608 | `3fcf5ff71ccbf60e7f48df3937928b3fa9cfbd26552905fdded8db7e05614095` | 21 | VALIDADO/EXPLORATORIO/INCOMPLETO | 1X2 90', BTTS, totales, hándicap, fase liga, título | [informe](individual/PROMPT_191_UWCL_v1_0.md) |
| `PROMPT_191_WNBA_v1_0.md` | Baloncesto; WNBA; femenino | # PROMPT 191-WNBA v1.0 — MOTOR CUANTITATIVO PREGAME | 457 | 31406 | `6e099df4fe6214cade1930c7614c0d30472299a39d9d20fba9c6c375033714f9` | 21 | VALIDADO/EXPLORATORIO/INCOMPLETO | ML, spread, total con push; OT | [informe](individual/PROMPT_191_WNBA_v1_0.md) |
| `PROMPT_191_WNCAAB_v1_0.md` | Baloncesto; NCAA D-I; femenino | # PROMPT 191-WNCAAB v1.0 | 610 | 34782 | `888468dd69fac7084a4ec337176d50503a0f19a30d88170063f0aa11122e0cd0` | 21 | VALIDADO/EXPLORATORIO/INCOMPLETO | ML, spread, total con push; OT | [informe](individual/PROMPT_191_WNCAAB_v1_0.md) |
| `PROMPT_191_WTA_v1_0.md` | Tenis; WTA 1000/500/250/125, Finals, Slams; femenino | # PROMPT 191-WTA — PREGAME PRICING ENGINE | 406 | 26135 | `21ab8f789a8cf050347e0a4390c9ba7ee529554893219d3ef673623caefc6d8b` | 21 | Fallbacks A-D y R; VALIDADO/EXPLORATORIO/INCOMPLETO/NO CALCULADO | Ganador, sets 2-0/2-1, juegos, tie-break, P(torneo) con simulación | [informe](individual/PROMPT_191_WTA_v1_0.md) |

Notas:
- [COMPROBADO] Todos tienen 21 fases por recuento de encabezados; el recuento de «fases» no garantiza numeración homogénea (ver familia baloncesto, [baloncesto.md](familias/baloncesto.md) §2).
- [COMPROBADO] Familias y su informe: [baloncesto](familias/baloncesto.md) (NBA, WNBA, NCAAB, WNCAAB), [futbol-americano](familias/futbol-americano.md) (NFL, NCAAF), [futbol-europa](familias/futbol-europa.md) (EPL, LaLiga, Bundesliga, Serie A, Ligue 1, UCL), [futbol-america-y-femenino](familias/futbol-america-y-femenino.md) (MLS, Liga MX, Brasileirão, Chile, UWCL), [mlb-nhl](familias/mlb-nhl.md), [tenis](familias/tenis.md).
- [COMPROBADO] Los mercados de las filas son los que declara cada informe individual (sección 1/5); el MLB no produce team totals ni F5 (`prompt_191_mlb_corregido_v2.md:159-165`, según su informe).

## 2. Clasificación

**Por deporte (21 prompts):** fútbol 11 (EPL, LaLiga, Bundesliga, Serie A, Ligue 1, UCL, UWCL, MLS, Liga MX, Brasileirão, Chile); baloncesto 4 (NBA, WNBA, NCAAB, WNCAAB); fútbol americano 2 (NFL, NCAAF); tenis 2 (ATP, WTA); béisbol 1 (MLB); hockey 1 (NHL). Total 21. [COMPROBADO por suma]

**Por metodología (distribución de la puntuación):**

| Metodología | Prompts |
|---|---|
| Poisson / binomial negativa bivariante + Dixon-Coles, matriz conjunta de goles a 90' | los 11 de fútbol |
| Normal bivariante / posesiones × eficiencia, con OT recalculado | NBA, WNBA, NCAAB, WNCAAB |
| Distribución conjunta de puntos con números clave, EPA, escenarios de QB | NFL, NCAAF |
| Cadena de Markov punto → juego → set → partido (programación dinámica) | ATP, WTA |
| Binomial negativa con gamma compartida, 9 entradas + extras | MLB |
| Poisson por estado de juego (`Σ_s T_s/60·λ_s`) con OT/SO | NHL |

**Por finalidad:** los 21 son motores de pricing pregame (estimar probabilidades justas, congelarlas y solo después comparar con cuotas); las diferencias son de formato de competición (liga, copa, eliminatoria, playoffs, Slams) y de género. Ninguno es un prompt de apuestas en vivo, de gestión de banca ni de selección de stake.

**Por género:** femenino: WNBA, WNCAAB, WTA, UWCL; masculino: los otros 17. [COMPROBADO] La plataforma no tiene módulos femeninos propios salvo la entrada `uwcl` en `configs/leagues/soccer.yaml:30` y las ligas `wnba`/`wncaab` del registro.

## 3. Evolución y versiones

- [COMPROBADO] En `C:\dev\Prompts` hay una sola serie: `PROMPT_191_<X>_v1_0.md` (20 ficheros) más `prompt_191_mlb_corregido_v2.md` (nombre en minúsculas, v2.0). No hay v1 de MLB como fichero allí (`.claude/worktrees/agent-a2bc3d835b878219b/docs/prompts/README.md:38`: «La v1 de prompt 191 no existe como archivo»).
- [COMPROBADO] No hay changelog interno en ningún prompt de `C:\dev\Prompts`; las referencias normativas están fechadas en 2026 y caducan (NBA Injury Report 2026-27, NFL OT 2026, WTA Rulebook 2026-07-27; según las familias).
- [COMPROBADO] **Otra línea de versiones dentro del repo:** `docs/prompts/` (tracked en git; commits `c5287a1`, `d0f254e`, `f93bdc1`) y copias en `.claude/worktrees/*/docs/prompts/`. Son seis motores agrupados por familia en versión **v3**, sincronizados el 2026-08-15 y corregidos el 2026-09-16 (README `docs/prompts/README.md`). Las cinco copias de worktree son idénticas byte a byte a `docs/prompts/` (comprobado por hash).

| Ruta | Líneas | sha256 |
|---|---|---|
| `docs/prompts/README.md` | 119 | `eda473e4d84fe6a4a65f21403def0706f925bf08b75ec2b35eec31ca63eb28dc` |
| `docs/prompts/prompt-191-mlb-pricing-v3.md` | 646 | `5b3fb30ac11fabd8d5c5b58f1ff7b790d8c683786cdb6079c72c04dd3c4df58a` |
| `docs/prompts/prompt-basket-pricing-v3.md` | 429 | `a6acb64e852882c97dd39ed59f4246628ca7f366c29d34b372f0270410db8bb9` |
| `docs/prompts/prompt-football-pricing-v3.md` | 446 | `ddbc9582de68a6756ffa925449e8af2a8d4b9b047b79bf56957fd6a1a23a51d3` |
| `docs/prompts/prompt-nhl-pricing-v3.md` | 465 | `de02eaa6bb92ec7347bb6425fef3cb52aff8511c9d5bba1186fc807c5572ad50` |
| `docs/prompts/prompt-soccer-pricing-v3.md` | 477 | `a2a36b78c31594157d276add1c8b4440086a342b7c662fb2ec95bc2b6f3cffef` |
| `docs/prompts/prompt-tenis-pricing-v3.md` | 461 | `bbe71bab5675beaec93758713f3840839ca0d201c4ad586e7b3b5827fe613f23` |

| Copias en worktrees | Relación |
|---|---|
| `.claude/worktrees/agent-a2bc3d835b878219b/docs/prompts/` | idénticos byte a byte a `docs/prompts/` |
| `.claude/worktrees/agent-aac79c4e2e1372416/docs/prompts/` | idénticos byte a byte a `docs/prompts/` |
| `.claude/worktrees/agent-acbd20486daae5fd2/docs/prompts/` | idénticos byte a byte a `docs/prompts/` |
| `.claude/worktrees/agent-adb1fb729ac1bc0f4/docs/prompts/` | idénticos byte a byte a `docs/prompts/` |
| `.claude/worktrees/agent-aefd305e1627906b1/docs/prompts/` | idénticos byte a byte a `docs/prompts/` |

- [COMPROBADO] Relación con los de `C:\dev\Prompts`:

| v3 del repo | Cubre | Equivalente en `C:\dev\Prompts` | Relación |
|---|---|---|---|
| `prompt-191-mlb-pricing-v3.md` (646 l.) | MLB | `prompt_191_mlb_corregido_v2.md` (266 l.) | Distinto linaje, no fichero anterior ni posterior comprobable. El v3 usa `NB_alpha = 0.15` (l.113, 371) y `HomeAdj = 1.02` sin corregir; el v2.0 usa `NB_k = 0.15` + `f = 0.30` y constantes «PROVISIONAL». |
| `prompt-basket-pricing-v3.md` (429 l.) | NBA, WNBA, NCAAB, WNCAAB | los 4 de baloncesto | Un solo prompt multi-liga frente a 4 redacciones independientes. |
| `prompt-football-pricing-v3.md` (446 l.) | NFL, NCAAF | NFL, NCAAF | Idem. |
| `prompt-nhl-pricing-v3.md` (465 l.) | NHL | NHL v1.0 (632 l.) | Idem; el v1.0 separa más estados y mercados (30 invariantes). |
| `prompt-soccer-pricing-v3.md` (477 l.) | 12 competiciones | 11 de fútbol | Un solo prompt multi-liga frente a 11 redacciones. |
| `prompt-tenis-pricing-v3.md` (461 l.) | ATP, WTA | ATP, WTA | Idem. |

- [HIPÓTESIS] La serie de 21 ficheros de `C:\dev\Prompts` es una generación posterior y separada de los v3 (misma fecha de modificación 2026-11-10 07:53 para los dos MLB; sin fechas de origen para ordenarlos). No se leyeron los v3 completos; solo cabeceras, README y las líneas citadas.
- [COMPROBADO] Otras menciones en el repo: `docs/INDEPENDENT-PRICING.md` (contrato v1 de «pricing independiente», módulos `sqp.models.independent`, `sqp.markets.settlement_math`, `sqp.markets.independent`, CLI `scripts/price_independent.py`), y en `Obsidian/`: `Conocimiento/Prompt 191 - origen del modelo.md` (análisis de v1/v2 MLB; cita `docs/prompts/prompt-191-mlb-pricing-v2.md`, fichero que ya no está en `docs/prompts/`), `Conocimiento/Motores de pricing por deporte - analisis.md`, `Conocimiento/Idea fundacional - alcance y objetivo.md`, bitácoras 2026-08-15/16/17 y `Tareas.md`. No se buscó en `docs/` fuera de lo anterior ni se leyó `data/`.
- [COMPROBADO] No hay otras variantes `PROMPT_191*` en el árbol del repo excepto los informes de esta auditoría (`docs/prompts-audit/individual/`).

## 4. Duplicidades, contradicciones y versiones obsoletas (resumen de las familias)

| Tema | Hallazgo | Fuente |
|---|---|---|
| Plantilla | [COMPROBADO] No hay plantilla textual común dentro de ninguna familia (1-11 líneas idénticas entre pares); sí una estructura conceptual común de 21 fases y mismas fórmulas EV/edge. Un `diff` no localiza cambios. | todas las familias |
| Constantes | [COMPROBADO] MLB trae 14 constantes provisionales con valor; NHL, ATP, WTA, NFL, NCAAF y el fútbol no fijan ninguna. NBA es la única con `K_games = 20` y `HCA = +2.0` en baloncesto. | [mlb-nhl](familias/mlb-nhl.md), [baloncesto](familias/baloncesto.md) |
| Tolerancia de masa omitida | [COMPROBADO] 1e-4 (EPL, Bundesliga) a 1e-6 (Serie A, Ligue 1, UCL, UWCL, Liga MX, Brasileirão); MLS sin cifra. Factor 100. | [futbol-europa](familias/futbol-europa.md) §2, [america-femenino](familias/futbol-america-y-femenino.md) §2 |
| Cláusula de independencia | [COMPROBADO] Serie A (l.21: «cuando operas en el modo independiente») y Ligue 1 (l.19: «durante la ejecución») la condicionan; los demás la formulan sin condición. | [futbol-europa](familias/futbol-europa.md) §2 |
| Etiqueta de salida y terminología | [COMPROBADO] `ValidationStatus` / `MODEL_STATUS` / `ModelStatus`; `DefenseWeakness`/`Dweak`/`defense_weakness`/… | [america-femenino](familias/futbol-america-y-femenino.md) §2, [futbol-europa](familias/futbol-europa.md) §2 |
| Localía | [COMPROBADO] Fútbol: interceptos propios (EPL, Bundesliga) frente a intercepto común + HFA (resto). Baloncesto: solo NBA da HFA por defecto. | familias fútbol y baloncesto |
| Prórroga y penales | [COMPROBADO] Sin definición común de `q_shootout` (MLS lo modela, UWCL prohíbe 50/50, Liga MX lo deja NO CALCULADO). NBA da Poisson de fallback; los otros tres de baloncesto lo exigen entrenado. NFL exige modelo propio de OT. | [america-femenino](familias/futbol-america-y-femenino.md) §2, [baloncesto](familias/baloncesto.md) §2 |
| Número de iteraciones MC | [COMPROBADO] NFL 100.000 provisional; NCAAF 10.000 «prototipo»; WNBA 100.000-1.000.000 con semiancho 0,5 pp; MLB 1e5-1e6 con semiancho 0,003. | [futbol-americano](familias/futbol-americano.md), [baloncesto](familias/baloncesto.md), [mlb-nhl](familias/mlb-nhl.md) |
| Tenis | [COMPROBADO] Primer servidor desconocido: ATP exige escenarios/mezcla justificada, WTA fija 0,5/0,5. Baselines solo en ATP. WTA:154 contiene `p_A = logistic(logit(p_A))` (error tipográfico). | [tenis](familias/tenis.md) |
| Contaminación entre deportes | [COMPROBADO] Bundesliga menciona hockey (l.105) y QB (l.358); LaLiga conserva «1.02 de localía» (l.76): rastros de plantillas reutilizadas. | [futbol-europa](familias/futbol-europa.md) §3 |
| Obsolescencia | [COMPROBADO] Hechos de formato y reglamento fechados en 2026 (ascendidos 2026/27, formato UCL de 36 clubes, OT NFL 2026, Slams) sin `ruleset_id` (solo NFL lo tiene) ni hash; [HIPÓTESIS] sin verificar contra fuentes oficiales. Ninguno incorpora las mediciones propias de la plataforma. | todas |
| MLB/NHL | [COMPROBADO] Convive un v3 con `NB_alpha`/`HomeAdj = 1.02` sin corregir (repo) con el v2.0 corregido (`C:\dev\Prompts`). | [mlb-nhl](familias/mlb-nhl.md) |
| Incumplimiento del principio | [COMPROBADO] Ningún prompt usa el mercado como entrada. La plataforma sí: `market_shrink 0.5` (`configs/default.yaml:17`) y `uncertainty_penalty 0.35` (`default.yaml:26`) en `src/sqp/pipeline/probabilities.py:303-305` y `daily.py:968-970`, para todos los deportes. | todas las familias |

## 5. Principios comunes a los 21 prompts

1. Mercado fuera de la estimación: cuotas, líneas y consenso solo después de congelar; las líneas valen como umbral.
2. Estados de salida VALIDADO / EXPLORATORIO / INCOMPLETO; no se inventan números ni se declara Monte Carlo no ejecutado.
3. 21 fases con identificación, datos con `as_of` (corte de información), ratings regularizados, distribución conjunta, mercados desde una sola distribución y congelación previa al mercado.
4. Shrinkage `w = n_eff/(n_eff+tau)` con `tau` estimado, no fijado (salvo MLB provisional).
5. Mismas fórmulas de decisión: `EV = P_win·(D−1) − P_loss`, break-even `(1−P_push)/D`, `Edge_precio_pp = 100·[P_win − (1−P_push)/D]`; `|P−0,5|` no es edge.
6. CLV solo con cierre observado.
7. Push y líneas asiáticas tratadas explícitamente; probabilidades que suman 1 con tests de consistencia (24-45 controles por prompt).
8. Prohibición de heredar parámetros de otro deporte, liga o género (por ejemplo `rho = 0,12` o sigma de NBA).
