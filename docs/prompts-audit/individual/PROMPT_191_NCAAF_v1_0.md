# Auditoria PROMPT_191_NCAAF_v1_0

Fecha: 2026-11-10. Prompt: `C:\dev\Prompts\PROMPT_191_NCAAF_v1_0.md` (cita `NCAAF:línea`). Plataforma: `C:\dev\3\sports-quant-platform`.

## 1. Ficha

- Fichero: PROMPT_191_NCAAF_v1_0.md; version declarada 1.0 (NCAAF:1, 5); 447 lineas.
- Deporte/competicion: futbol americano universitario, FBS, temporada regular, campeonatos de conferencia, bowls y CFP; FBS-FCS en modo interdivisional; FCS-FCS solo bajo pedido (NCAAF:3).
- Rol: motor pregame cuantitativo (NCAAF:11). Objetivo: P(victoria) sin empate, puntos, margen, spread y total, EV solo al final (NCAAF:13-18).
- Modos: VALIDADO / EXPLORATORIO / INCOMPLETO (NCAAF:42, 293); inicial EXPLORATORIO (NCAAF:5). 21 fases (NCAAF:84-311), 28 pruebas de consistencia (NCAAF:398-427).

## 2. Reglas y restricciones

- [COMPROBADO] 17 reglas absolutas (NCAAF:26-44): no inventar datos (28); no usar odds, power ratings derivados de cuotas ni consenso, y auditar la procedencia de ratings de terceros (29); nada posterior a `as_of_utc` (30); EPA distinto de PPA y de puntos (31); no mezclar FBS/FCS, no usar AP/CFP/estrellas/W-L como probabilidad (32); no fijar HFA, valor del QB, clima ni dispersion como constantes (34); sin empate final y OT universitario, no NFL (38); spreads y totales sobre puntos finales con OT (39).
- Gates minimos (NCAAF:71-80): partido verificado, un indicador ofensivo y uno defensivo con ajuste por oposicion, QB o escenarios, baseline de ritmo y un modelo de distribucion ejecutado.
- "Validado" (NCAAF:297-299): varias temporadas, entrenamiento y pruebas temporales fuera de muestra, Brier/Log Loss/reliability, MAE/RMSE, cobertura de cuantiles, CRPS, ablaciones EPA/SOS -> +QB -> +OL/defensa -> +pace -> +ST -> +contexto, sin leakage de ratings finales.

## 3. Variables y parametros

[COMPROBADO] Como el de NFL, no da valores calibrados (NCAAF:48 "No imponer valores numericos fijos"). Exige un `parameter_registry` (NCAAF:50-55).

| Nombre | Valor | Unidad | Linea | Justificacion |
|---|---|---|---|---|
| `shrinkage_tau`, `n_eff`, prior | sin valor | adim. | NCAAF:112-118 | a estimar por metrica/division |
| `w = n_eff/(n_eff+tau)` | formula | adim. | NCAAF:114-116 | generica |
| `home_advantage_params`, `weather_params`, `special_teams_params` | registro, sin valor | puntos | NCAAF:54 | prohibido fijarlas (NCAAF:34) |
| `simulation_N` | 10 000 = prototipo, subir | sims | NCAAF:234 | reconoce que no distingue edges del 1% |
| `SE_MC = sqrt[p(1-p)/N]` | formula | prob. | NCAAF:234 | si |
| Reglamento: 4x15 min; OT sin reloj; 1.a pos. en yarda 25 rival; 2.a prorroga con 2pt obligatorio; 3.a y siguientes solo 2pt | reglas | - | NCAAF:57, 217-221 | reglamento NCAA; "verificar vigencia" (NCAAF:435) |
| Puntos de anotacion | no enumerados | puntos | NCAAF:410 | solo "legal bajo reglas de anotacion" |
| Umbral garbage time, ventana reciente | sin definir | - | NCAAF:96 | NO justificado |

## 4. Fuentes de datos

- [COMPROBADO] NCAAF:59-69: NCAA, escuelas y conferencias; NCAA Stats y CollegeFootballData (CFBD); rosters, depth charts y notas primarias; meteorologia; sportsbooks solo despues. Campos de proveniencia (NCAAF:69). Advertencia clave: CFBD publica probabilidades pregame derivadas de spreads, prohibidas como input (NCAAF:67).
- [INFERENCIA] Calidad: la frescura de disponibilidad es desigual (conferencias distintas, NCAAF:148); el prompt lo reconoce y prohibe asumir "todos disponibles" (NCAAF:150, 389). No fija ventana de caducidad.

## 5. Cadena predictiva

Principio (NCAAF:22): ataque y defensa ajustados por rival + QB + OL + matchup + ritmo + equipos especiales + lesiones/transferencias + sede + clima + calendario -> resultados de drives -> distribucion conjunta de marcadores -> probabilidades.

- Fase 3 SOS jerarquico simultaneo; Fase 4 priors de roster (retornos, transferencias, staff) con shrinkage; 5-6 ataque/defensa pase y carrera; 7-8 QB, portal, opt-outs; 9 matchup; 10 distribucion de drives y snaps; 11 equipos especiales; 12 clima; 13 localia/descanso/neutral/bowl; 14 modelo de resultado de drive `P(Y_d = y | team, opponent, QB, field_position, clock, score, context; theta)` (NCAAF:195); 15 simulador de regulacion 4x15; 16 OT NCAA; 17 convergencia; 18 probabilidades.
- Distribucion: simulacion stateful; fallback a "distribucion conjunta de puntuaciones finales previamente entrenada/calibrada, no una Normal arbitraria" (NCAAF:210). Si no existe ninguno, NO CALCULAR (NCAAF:210).
- Dependencias: oportunidades de drive dependen del reloj de ambos; `PPD × drives` solo con independencia justificada o covarianza (NCAAF:166).
- OT: P(tie final)=0 (NCAAF:226, 244); OT sin reloj, modelado por rondas (NCAAF:217-221). [COMPROBADO] El prompt trata OT como proceso aparte con `OT_probability` y `points_OT` (NCAAF:224).
- Formulas literales: `P_home_win = P(H > A)`, `P_away_win = P(A > H)`, `P_tie_final = 0` (NCAAF:240-244); `P_cover = P(X+h > Y)`, `P_push`, `P_loss` (NCAAF:247-254); `P_over = P(H+A > t)` (NCAAF:257-264).
- Mercados: ML (2 vias), spread y totales sobre puntos finales con OT; sin team totals (NCAAF:266).

## 6. Auditoria matematica

- [COMPROBADO] Coherencia: `P_home + P_away = 1`; `cover+push+loss = 1`; `over+under+push = 1`; ML/spread/total del mismo score conjunto (NCAAF:414-417); totales incluyen OT (NCAAF:418).
- [COMPROBADO] Reglamento OT descrito (NCAAF:217-221). [INFERENCIA] La descripcion es plausible respecto al reglamento actual (1.a y 2.a prorroga con posesion desde la 25; 3.a en adelante, solo 2pt), pero la regla exacta de la 2.a prorroga ("obligacion de intentar conversion de dos puntos tras touchdown") es detalle regulatorio que debe verificarse contra la fuente citada (NCAAF:437-438). [HIPOTESIS] no comprobado aqui.
- [INFERENCIA] Matematica para NCAAF: la varianza del margen es mucho mayor que en NFL (la plataforma mide residual 20.2 frente a 13.5 de familia; `registry.py:94-97`), y la disparidad de talento hace el margen no gaussiano (colas pesadas, palizas). La exigencia de ratings jerarquicos con incertidumbre y de dominio FBS/FCS separado (NCAAF:102-104, 386-387) es correcta. [RECOMENDACION] Pedir ademas modelo de cola/mezcla para el margen y cobertura de cuantiles extremos.
- Coeficientes sin justificar: ninguno por construccion; igual que en NFL el limite es que el prompt es una especificacion no ejecutable sin entrenamiento (NCAAF:14, 41, 393).
- Sobreajuste: ~130 equipos FBS, calendarios poco conectados al inicio (NCAAF:104); piden regularizacion y ablaciones (NCAAF:126, 299). Fuga temporal: bien tratada (NCAAF:30, 299, 405). [COMPROBADO] Regla anti-leakage especifica: "no usar ratings retrospectivos finales de temporada" (NCAAF:299).
- Datos faltantes: `missing` con fallback explicito y efecto sobre la incertidumbre; prohibe sustituir por 1.00 (NCAAF:41); nunca "plantilla completa" (NCAAF:389).
- [INFERENCIA] Inconsistencia menor: dice "no imponer EPA a puntos" (NCAAF:200) pero acepta "yards/play como fallback debil" (NCAAF:124) sin validacion; la regla 6 pide aportacion incremental (NCAAF:35).

## 7. Independencia del mercado

| Cita | Mencion | Clasificacion |
|---|---|---|
| NCAAF:24 | mercado no es entrada, consulta tras congelar | conforme |
| NCAAF:29 | prohibe odds, power ratings derivados de cuotas, modelos de mercado | prohibicion (conforme) |
| NCAAF:67 | CFBD pregame win prob. derivada de spreads: prohibida | prohibicion expresa de una ENTRADA |
| NCAAF:65 | sportsbooks solo despues | COMPARACION POSTERIOR LEGITIMA |
| NCAAF:266 | linea de spread/total como umbral | UMBRAL LEGITIMO |
| NCAAF:272-286 | congelar, luego precios, EV, edge, CLV | COMPARACION POSTERIOR LEGITIMA |
| NCAAF:282 | "mercado sin vig" como normalizacion posterior | COMPARACION POSTERIOR LEGITIMA |
| NCAAF:403 | prueba 4: ningun campo de mercado entra al modelo | conforme |

[COMPROBADO] Ninguna ENTRADA PROHIBIDA. Es el mas explicito de la familia en vetar ratings de terceros de procedencia de mercado (NCAAF:29, 67). Congela antes de consultar (NCAAF:272).

## 8. Validacion propuesta

[COMPROBADO] NCAAF:288-303: multiples temporadas; entrenamiento y prueba temporal; Brier, Log Loss, reliability; MAE/RMSE de puntos y margen; cobertura de cuantiles; CRPS; spread/total por rango; baselines; ablaciones por bloques (NCAAF:299). Falta tamano minimo de muestra y umbrales de aceptacion numericos.

## 9. Contraste con la plataforma

- Implementado: `FootballAdapter` compartido con NFL (`src/sqp/sports/adapters.py:168-169`) con override `ncaaf` en `registry.py:97`: `avg_total 55.0, total_sigma 15.5, margin_sigma 20.0` ("residual margen 20.2"), y `elo_home_adv 150.0` en `configs/leagues/ratings.yaml:41-42` (base de familia `points_per_elo 0.025, elo_k 24, elo_mov True`, `registry.py:34-35`). Margen por Elo y Normal (`distributions.py:32-56, 394-396`), total por tasas ofensivas/defensivas (`team_scoring.py:92-101`). Sigma y avg_total de NCAAF son valores medidos (walk-forward), mas defendibles que los de la familia.
- Cubierto: nada de SOS jerarquico explicito (el Elo lo absorbe parcialmente), nada de QB/lesiones/portal, PPA/EPA, drives, equipos especiales, clima como feature, FBS/FCS: la plataforma no distingue division (una sola liga `ncaaf`, `espn_results.py:82`, `odds_api.py:64`). [INFERENCIA] Mezclar FBS y FCS viola NCAAF:32, 386-387.
- Difiere: (a) Normal para margen y total, dos modelos independientes, contra el score conjunto (NCAAF:210, 417); (b) sin OT: `normal_margin_probs` no tiene masa de empate (correcto para NCAAF, P_tie_final = 0), pero tampoco modela OT ni el efecto de OT en el total; (c) el empate se trata 0.5 en el Elo (`elo.py:121-122`), irrelevante porque en NCAAF no hay empates; (d) push de linea entera por correccion de continuidad (`distributions.py:46-52`), no PMF discreta; (e) HFA 150 Elo es un valor fijo de liga, el prompt exige HFA estimado con sesgo de seleccion y neutral/bowl (NCAAF:186-188); el Elo acepta `neutral` (`elo.py:70-77`) pero no se verifico que el adaptador lo pase para NCAAF [HIPOTESIS].
- Informacion de mercado en la construccion de probabilidades: igual que NFL, `p_used = (1 - shrink) * p_model + shrink * fair`, `market_shrink 0.5` (`default.yaml:17`; `probabilities.py:303-305`) y `uncertainty_penalty 0.35` (`default.yaml:26`). ENTRADA PROHIBIDA para el principio del operador. No hay uso de ratings de terceros derivados de mercado (verificado: sin proveedor CFBD en `src/sqp/providers`, solo `espn_results.py` y `odds_api.py`).
- Cobertura de cuotas con Pinnacle ncaaf 85% (`default.yaml:166-171`), por lo que la ejecucion usa esa casa en la mayoria de eventos (esto afecta a ejecucion, no a probabilidades).

## 10. Veredicto por componente

| Componente | Veredicto | Motivo |
|---|---|---|
| Veto a ratings con procedencia de mercado (CFBD, NCAAF:67) | CONSERVAR | Refuerza el principio. |
| OT NCAA y P_tie = 0 | CONSERVAR | Correcto en estructura; verificar detalles. |
| Separacion FBS/FCS/interdivisional | INTEGRAR | La plataforma no lo distingue. |
| SOS jerarquico, priors de roster | INTEGRAR | Inexistente; alto valor en NCAAF. |
| Simulador de drives y PMF conjunta | INTEGRAR | Sin equivalente; hoy dos Normales. |
| Margen gaussiano | CORREGIR | Colas pesadas por disparidad de talento. |
| Umbrales de aceptacion y garbage time | OPTIMIZAR | No definidos. |
| `market_shrink 0.5` en la plataforma | DESCARTAR | Mercado como entrada. |
| Sigma 20.0 y avg_total 55.0 de la plataforma | CONSERVAR | Medidos walk-forward (comentario `registry.py:97`); revisar periodicamente. |
