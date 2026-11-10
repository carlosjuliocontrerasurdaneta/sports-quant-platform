# Auditoría de PROMPT_191_WTA_v1_0 (tenis femenino individual)

Fuente: `C:\dev\Prompts\PROMPT_191_WTA_v1_0.md` (406 líneas). Fecha de la auditoría: 2026-11-10. Familia: `tenis` (ver `docs/prompts-audit/familias/tenis.md`).
Nota de método: `graphify` (MCP) caído; se usó Grep/Read dirigidos. `.env` no legible (denegado): el valor efectivo de `MARKET_SHRINK` en producción es **no verificable**.

## 1. Ficha

| Campo | Valor |
|---|---|
| Fichero | `PROMPT_191_WTA_v1_0.md` |
| Versión declarada | 1.0, referencia reglamentaria 2026-11-10 (WTA:3, 7) |
| Deporte / competición | Tenis femenino individual; WTA 1000/500/250/125, WTA Finals y Grand Slams femeninos (WTA:5) |
| Tamaño | 406 líneas |
| Rol | Motor cuantitativo y auditable de predicción pregame (WTA:13) |
| Objetivo | P(victoria), P(sets), marcadores 2-0/2-1/1-2/0-2, distribución de juegos, Over/Under y hándicap de juegos y sets, P(TB), P(torneo/avance de grupo) solo con simulación específica, EV con cuota verificada (WTA:15-25) |
| Alcance | Singles WTA; no ITF, BJK Cup, United Cup ni dobles sin submodelo (WTA:71) |
| Modos | EXPLORATORIO (WTA:6); VALIDADO / EXPLORATORIO / INCOMPLETO / NO CALCULADO (WTA:61); fallbacks A, B, C, D, R (WTA:382-388) |

## 2. Reglas y restricciones

- [COMPROBADO] 20 reglas absolutas (WTA:46-65). Relevantes: sin leakage (WTA:47), sin odds como predictores, targets ni ajustes (WTA:48), no trasladar parámetros ATP sin recalibrar (WTA:49), no asumir BO5 en Slams femeninos (WTA:51), un modelo coherente punto-juego-set-partido (WTA:56), retiradas con estados y liquidación separados (WTA:58).
- [COMPROBADO] Excepción de formato: en Slams, set decisivo a 6-6 con tie-break a 10 (WTA:79). WTA Finals se trata aparte (WTA:73).
- [COMPROBADO] Criterios de VALIDADO: dataset reproducible con permisos, timestamps previos, código ejecutable, versión de parámetros, backtesting temporal, baselines, calibración, subgrupos por superficie y categoría, auditoría de retiradas (WTA:390-392).

## 3. Variables y parámetros

[COMPROBADO] El prompt no fija coeficientes numéricos de producción; solo constantes reglamentarias.

| Nombre | Valor | Unidad | Línea | Justificación |
|---|---|---|---|---|
| Formato | BO3 (2 sets) | sets | WTA:79, 51 | Reglamento citado (WTA Rulebook 2026, no verificado aquí) |
| Tie-break regular | 7 puntos, margen 2 | puntos | WTA:79, 195 | Reglamento |
| Tie-break set decisivo Slam | 10 puntos, margen 2 | puntos | WTA:79, 195 | Reglamento |
| 7-6 = 13 juegos | 13 | juegos | WTA:199, 370 | Convención |
| `p_prior`, `tau` | a estimar en entrenamiento WTA | adim. | WTA:112-118 | Se prohíbe fijarlos por conveniencia |
| `mu_superficie`, `S_i`, `R_i`, `contexto` | a estimar | logit | WTA:147-152 | Modelo jerárquico con restricciones de identificabilidad |
| Primer servidor desconocido | 0,5/0,5 por defecto | prob. | WTA:197 | Condicionado a que el procedimiento lo justifique [INFERENCIA: es una convención de sorteo, no un dato] |
| Stake de líneas `.25/.75` | 50 % a cada línea vecina | proporción | WTA:241 | Convención de liquidación |

## 4. Fuentes de datos

- [COMPROBADO] Datos requeridos: puntos de servicio totales y por 1.º/2.º saque, 1.os saques válidos, puntos ganados con 1.º y 2.º (incluidas dobles faltas), resto contra 1.º y 2.º, juegos mantenidos/quebrados, break points (auxiliares), nivel partido y punto a punto cuando sea legal, resultados con fecha previa a `as_of`, estado médico solo con confirmación (WTA:87-98).
- [COMPROBADO] Fuente nombrada: WTA Stats Zone (WTA:100), WTA Rulebook, ITF, `match-notes` (WTA:83, 396-400). Registra eventos sin estadística punto a punto y sesgo de cobertura (WTA:100).
- [INFERENCIA] El prompt no define jerarquía explícita de fuentes (la ATP sí, ATP:86-91), ni campos de registro por variable (ATP:93). Frescura: solo `as_of` (WTA:47).

## 5. Cadena predictiva

1. Priors: `p_shrunk = (wins + tau * p_prior) / (n + tau)` (WTA:115).
2. Servicio: `f_i`, `a_i`, `b_i`, `p_service_raw_i = f_i*a_i + (1-f_i)*b_i` (WTA:127-130). `b_i` ya incluye dobles faltas (WTA:133).
3. Resto: `P(A gana punto al recibir servicio de B)=1−P(B gana punto al servir frente a A)` (WTA:141).
4. Matchup: `logit(p_A) = mu_superficie + S_A − R_B + contexto_A` y `logit(p_B) = mu_superficie + S_B − R_A + contexto_B` (WTA:148-149); `p_A = logistic(logit(p_A))` (WTA:154, redundante tal como está escrito). Prohíbe `p_service_A × (1−return_B)` sin entrenamiento (WTA:154).
5. Juego: `Hold(p) = p^4*(1 + 4*q + 10*q^2) + 20*p^3*q^3 * p^2/(p^2+q^2)` (WTA:185-186); `P(quiebre de la restadora)=1−P(hold de la sacadora)` (WTA:191).
6. Tie-break: recursivo con orden real de saque, margen 2, objetivo 7 o 10 (WTA:195).
7. Set: estados `games_A, games_B, next_server, set_index, tiebreak_rule` (WTA:203); alternancia continua entre sets (WTA:205).
8. Partido BO3: estados con `score_history` (WTA:209); resultados `P(A gana | completo)`, `P(A 2-0)`, `P(3 sets)`, `E[juegos totales | completo]`, `Distribución(G_A, G_B, sets_A, sets_B | completo)` (WTA:214-219).
9. Mercados: `Total_games = G_A + G_B`, `P(Over t)`, `P(Under t)`, `P(Push t)`, `P(Cover h)`, `P(Push h)`, `P(Loss h)` (WTA:229-237); `P(Over 2.5 sets)=P(tres sets)` (WTA:239); líneas asiáticas con mitades de stake (WTA:241); P(≥1 TB) por trayectoria (WTA:241).
10. Distribuciones: puntos iid con `p` constante en el juego (WTA:182, 191 «si se dispone de modelos dependientes del marcador, resolver estados puntuales»). Sin empates ni prórroga. Retiradas: núcleo condicional a completitud + capa contractual (WTA:245-250).
11. Torneo/avance de grupo en WTA Finals: solo con simulación completa específica (WTA:24, 73); no se desarrolla en fases.

## 6. Auditoría matemática

- [COMPROBADO] `Hold(p)` idéntica a la de ATP (WTA:185-186); correcta para el juego iid [INFERENCIA]. Trata los límites `Hold(0)=0`, `Hold(1)=1` (WTA:189, 364) y exige coincidencia entre cierre y Markov de juego (WTA:365).
- [INFERENCIA] Misma crítica estructural que ATP: puntos iid con `p` constante subestiman la varianza de juegos y sets; el prompt reconoce la opción de estados dependientes del marcador (WTA:191).
- [COMPROBADO] En el matchup incluye restricciones de identificabilidad (suma cero, WTA:152), pero omite el término de interacción `X*beta` que sí tiene ATP (ATP:161). El término `contexto_A` queda sin definir [INFERENCIA].
- [INFERENCIA] Error menor de redacción: `p_A = logistic(logit(p_A))` es una tautología (WTA:154); debe ser `logistic(mu + S_A − R_B + contexto_A)`.
- [COMPROBADO] Coherencia: `P(A gana)+P(B gana)=1` (WTA:222, 368), marcadores BO3 sumando 1 (WTA:222, 367), `P(tres sets)=P(A 2-1)+P(B 2-1)` (WTA:369), Cover+Loss+Push=1 (WTA:373), Over+Under+Push=1 (WTA:372), `.5` sin push y `.0` con push (WTA:241). [INFERENCIA] Verificado: con G_A y G_B enteros, P(G_A+h=G_B)=0 para h semientero.
- [COMPROBADO] EV: `EV_net_per_1 = P_win*(D-1) - P_loss`, `P_break_even = (1-P_push)/D`, `Price_edge_pp = 100*(P_win-P_break_even)` (WTA:261-263). [INFERENCIA] Algebraicamente correcto. Omite `FairDecimal` (ATP lo incluye, ATP:327).
- [INFERENCIA] Coeficientes sin justificar: ninguno numérico. El 0,5/0,5 de sorteo (WTA:197) es defendible solo si el sorteo no tiene sesgo; esa decisión se difiere correctamente al operador.
- [INFERENCIA] Sobreajuste y fuga: prevé ablaciones (WTA:276), splits cronológicos (WTA:270), priors con información previa (WTA:120). Cobertura de métricas: incluye MAE, CRPS y log score para juegos (WTA:274), más completa que ATP.
- [INFERENCIA] Datos faltantes: fallbacks B (pooling) y C (partido) más explícitos que ATP (WTA:384-386). Incertidumbre: bootstrap temporal o posterior (WTA:278).
- [INFERENCIA] El circuito WTA tiene más variabilidad en el servicio (más breaks); eso hace más influyente la violación del supuesto iid y más inestable `p` por jugadora; la regularización jerárquica (WTA:118) es esencial [HIPÓTESIS, no medida].

## 7. Independencia del mercado

| Cita | Mención | Clasificación |
|---|---|---|
| WTA:13 | Estimar «sin utilizar cuotas para entrenar, ajustar ni determinar» | Regla de independencia |
| WTA:39-42 | «El mercado NUNCA es input del predictor deportivo»; ranking WTA como covariable sujeta a validación | Regla de independencia (ranking no es mercado) |
| WTA:48 | Prohíbe odds, picks, consenso y líneas como predictores, targets o ajustes | Regla de independencia |
| WTA:252-266 | Cuotas capturadas después de congelar; EV; CLV solo con cierre observado | COMPARACIÓN POSTERIOR LEGÍTIMA |
| WTA:229-241, 319-322 | Líneas de totales y hándicap | UMBRAL LEGÍTIMO |
| WTA:289 | Ranking por EV con cuotas | COMPARACIÓN POSTERIOR LEGÍTIMA |
| WTA:347, 377 | Control 9 «sin odds en probabilidades»; control 39 congelación previa | Regla de independencia |

- [COMPROBADO] Sin ENTRADA PROHIBIDA. Congela antes del mercado, sin edición retrospectiva (WTA:254-256).
- [INFERENCIA] Menos prescriptiva que la ATP en un punto: no prohíbe explícitamente «ajustar p para acercarlo a cuotas» (ATP:317), aunque WTA:48 («ajustes») lo cubre.

## 8. Validación propuesta

- [COMPROBADO] Backtest cronológico OOS; Brier, Log Loss, calibración, ECE, reliability para ganadora (WTA:270-272); log score y Brier para sets (WTA:273); MAE, CRPS, calibración de cuantiles para juegos (WTA:274); hold/break observado vs esperado (WTA:275); ablaciones (WTA:276); bootstrap temporal (WTA:278).
- [INFERENCIA] No lista baselines independientes (Elo por superficie, hold/break empírico), a diferencia de ATP (ATP:342). [RECOMENDACIÓN] Añadirlos: sin baseline no se puede decir que la complejidad aporta.
- [INFERENCIA] No fija tamaños mínimos de muestra ni umbrales de aceptación (coherente con no inventar umbrales).

## 9. Contraste con la plataforma

- [COMPROBADO] Mismo adapter para ATP y WTA: `src/sqp/sports/adapters.py:318-338`; Elo escalar sin superficie; `"tennis": {"elo_k": 40, "elo_home_adv": 0}` (`src/sqp/sports/registry.py:52`), K medido sobre 16.663 partidos ATP+WTA conjuntos (`registry.py:48-51`).
- [COMPROBADO] **Divergencia con la regla WTA:49** («no trasladar parámetros ATP al circuito femenino»): la plataforma usa un único K=40 y una única función Elo para ambos circuitos (`registry.py:52`); aunque cada jugador tiene su propio rating, el hiperparámetro se calibró mezclando ATP+WTA. Aunque `ESPN` se descarga por tour (`espn_tennis.py:38-44`), las ratings viven en el mismo adaptador.
- [COMPROBADO] No existen: superficie, estadísticas de saque/resto, Hold, TB, sets, juegos, hándicap, BO3 explícito, retiradas (ver ATP §9). Solo `h2h` (`daily.py:73`). No hay configuración `configs/leagues/*tennis*` (los torneos se descubren con `scripts/run_all.py:48-73`).
- [COMPROBADO] Liquidación vía ESPN por nombres y fecha (`src/sqp/settlement/runner.py:192`, `settle.py`).
- **Uso del mercado en la construcción de probabilidades** [COMPROBADO]: `market_shrink: 0.5` por defecto (`configs/default.yaml:17`, `src/sqp/config.py:118, 466-467`); `_decision_probability` ⇒ `p_decision = (1-shrink)*cal(p_model) + shrink*fair` (`src/sqp/pipeline/probabilities.py:274-318`), llamada en `src/sqp/pipeline/daily.py:969-970`, sin exención del tenis. Incumple WTA:13, 39-42 y 48 y el principio del operador. El valor efectivo en `.env` no se pudo comprobar. Penalización de incertidumbre dependiente de la distancia al mercado: `daily.py:978-985`, `configs/default.yaml:26`.
- [HIPÓTESIS] `src/sqp/evaluation/feature_shadow.py:325` lee cuotas de tenis para evaluar; no se leyó el cuerpo.

## 10. Veredicto por componente

| Componente | Veredicto | Motivo |
|---|---|---|
| Independencia del mercado y congelación previa | CONSERVAR | Alineada con el principio |
| `Hold(p)`, tie-break, DP de set y BO3 | CONSERVAR | Correctos bajo iid |
| Matchup logístico (WTA:148-154) | CORREGIR | `logistic(logit(p))` tautológico; `contexto` indefinido; falta `X*beta` como en ATP |
| Iid con `p` constante | CORREGIR | Subestima varianza; usar estados dependientes del marcador si la validación lo exige |
| Fallbacks A-D,R (WTA:382-388) | CONSERVAR | Más completos que los de ATP |
| Validación (WTA:270-278) | OPTIMIZAR | Añadir baselines independientes (Elo por superficie, hold/break empírico) |
| Torneo/avance de grupo en WTA Finals (WTA:24, 73) | OPTIMIZAR | Anunciado sin fase que lo implemente |
| `FairDecimal` ausente | OPTIMIZAR | Complementa el cálculo de EV |
| Hiperparámetro Elo único ATP+WTA (`registry.py:52`) | CORREGIR | Contradice WTA:49; medir K por circuito |
| `market_shrink` aplicado al tenis | CORREGIR | Entrada de mercado en la probabilidad |
| Adapter de tenis | INTEGRAR | Sustituir por la cadena servicio/resto/Markov |
