# Auditoria individual: PROMPT_191_NBA_v1_0

Fecha de la auditoria: 2026-11-10. Etiquetas: [COMPROBADO] [INFERENCIA] [HIPOTESIS] [RECOMENDACION]. Citas `prompt:linea` se refieren a `C:\dev\Prompts\PROMPT_191_NBA_v1_0.md`.

## 1. Ficha
- Fichero: PROMPT_191_NBA_v1_0.md, 433 lineas. Version declarada: 1.0 (l.2). Deporte: baloncesto, NBA exclusivamente (l.5). Competicion: temporada regular, NBA Cup, play-in, playoffs, pretemporada (l.31).
- Rol: asistente cuantitativo pregame que estima la distribucion conjunta de puntos y de ella ML, spread, totales, puntos esperados y EV (l.5-11). Objetivo: no declarar probabilidades "reales" sin calibracion OOS (l.13).
- Modos: VALIDADO / EXPLORATORIO / INCOMPLETO (l.36-40). 21 fases (l.77-300).

## 2. Reglas y restricciones
- [COMPROBADO] Reglas absolutas l.23-32: sin invenciones, datos pregame (`as_of`), **no cuotas para predecir** (l.25, "ni odds, lineas, consenso, picks, rankings de apuestas ni movimientos"), tres estados, ejecutar de verdad, sin doble conteo, incertidumbre explicita, no forzar oportunidades.
- Excepciones (l.410-419): sin partidos, partido iniciado, lesion incierta (escenarios IN/OUT), Pace ausente (prior de liga, solo EXPLORATORIO), sin distribucion (solo medias), sin cuotas (sin EV).
- "Validado" (l.395-408): walk-forward con snapshots pregame, Brier/LogLoss/calibracion por tramos, MAE/RMSE, ablaciones, robustez por temporada/playoffs.

## 3. Variables y parametros
| Nombre | Valor | Unidad | Linea | Justificado |
|---|---|---|---|---|
| K_games | 20 | partidos equivalentes | 57 | No: "prior heuristico", declarado NO calibrado |
| HCA_margin_points | +2.0 (neutral 0.0) | puntos de margen | 58, 151 | No: "hipotesis inicial"; sustituir por estimacion historica |
| N_MC_objetivo | 100000 | simulaciones | 59, 213 | Computacional |
| sigma_margin, sigma_total, rho | NO imponer | - | 60 | Correcto: estimar de residuos o cargar de version |
| L_ORtg, L_Pace | de temporada, `as_of` | pts/100 pos; pos/48 | 44, 94 | Si, por datos |
| Poisson OT | OT_i ~ Poisson(max(0, 5/48*mu_i_reg)) | puntos por OT de 5 min | 206 | Solo fallback explicito |
| Minutos-equipo | 240 | minutos | 135 | Regla del juego |
| Matchup_4F, delta_descanso, delta_viaje | 0 en base | - | 131, 145 | Declarado "omitido, no ausencia" |

[COMPROBADO] No hay un solo coeficiente deportivo fijado salvo K=20 y HCA=2.0; ambos marcados como provisionales.

## 4. Fuentes de datos
Jerarquia (l.63-71): 1 NBA.com/NBA Stats (calendario, ORtg/DRtg/Pace); 2 Injury Report oficial; 3 Basketball-Reference; 4 viajes/horarios; 5 sportsbooks solo tras congelar (l.69). [COMPROBADO] Periodicidad y frescura: via `as_of` y trazabilidad por variable (l.86). [INFERENCIA] No fija tolerancia maxima de antiguedad del dato; la frescura se delega al criterio "disponible en as_of".

## 5. Cadena predictiva
1. Suavizado (l.98-99): `w_games = G / (G + K_games)`; `X_suavizado = w_games * X_temporada + (1 - w_games) * X_prior`.
2. Ritmo (l.123): `Poss_48_base = sqrt(Pace_away_suavizado * Pace_home_suavizado)`.
3. Eficiencia (l.159-160): `E_away_base = ORtg_away_suavizado * DRtg_home_suavizado / L_ORtg`; `E_home_base = ORtg_home_suavizado * DRtg_away_suavizado / L_ORtg`. Deltas aditivos (l.166-167) solo si validados, si no 0.
4. Puntos (l.175-176): `mu_away_reg = Poss_48 * E_away / 100 − HCA_margin_points / 2`; `mu_home_reg = Poss_48 * E_home / 100 + HCA_margin_points / 2`; margen y total de regulacion (l.178-179).
5. Distribucion conjunta (l.187-195): A validado; B bootstrap de pares de residuos `(eps_home_j, eps_away_j)`; C bivariante (Total, Margin) con covarianza estimada; D si no hay datos, NO CALCULAR. Marcadores `round(mu + eps)`, rechazo de negativos.
6. Prorroga (l.199-209): empate -> OT de 5 min; en validado modelo entrenado; en exploratorio remuestreo de incrementos o Poisson independiente. Se recalculan medias finales desde las simulaciones.
7. Monte Carlo (l.213-215): semilla registrada, `SE_MC = sqrt(p*(1-p)/N)`.
8. Mercados (l.220-237): ML `P_home_ML = Pr(Score_home_final > Score_away_final)`; spread `P_win_spread_i(h) = Pr(Score_i_final + h > Score_opponent_final)`, push y loss; totales con `P_over + P_under + P_push = 1`.
Mercados: ML, spread, totales; no produce team totals ni 1X2.

## 6. Auditoria matematica
- [INFERENCIA] El producto `ORtg_a * DRtg_h / L_ORtg` es el estandar multiplicativo (elasticidad unitaria); el prompt lo marca provisional (l.164) y cumple el chequeo de identidad (l.162). Solido para NBA como baseline.
- [INFERENCIA] Media geometrica del ritmo: razonable; el prompt la rotula "no ley fisica" (l.125).
- [COMPROBADO] Coherencia: total y margen salen de los mismos marcadores simulados; push tratado correctamente en lineas enteras (l.237 "no definir P_under = 1−P_over"). Suma 1 verificada en l.245-247 y l.389.
- [INFERENCIA] Defecto sutil: `round(mu + eps)` con residuos empiricos y rechazo de negativos es irrelevante en NBA (puntos ~110), pero **residuos de regulacion con medias recentradas** no se mencionan: si el sesgo medio de los residuos no es 0, las probabilidades heredan el sesgo (el prompt solo pide comparar medias, l.247). [RECOMENDACION] Exigir recentrado o corregir el mu con el sesgo medio OOS.
- [INFERENCIA] Poisson para OT (l.206): subdispersion real en baloncesto (el marcador de 5 min es mucho menos disperso que Poisson); la varianza del OT queda sobreestimada, impacto pequeno porque P(OT) ~ 6%.
- [INFERENCIA] HCA +2.0 es plausible para NBA actual; las estimaciones recientes suelen estar entre 2 y 3 puntos [HIPOTESIS: no verificado aqui].
- Fuga temporal: bien controlada (l.24, 397: nunca ajustar baseline con el resultado del mismo juego). Riesgo residual: ORtg/DRtg "de temporada" publicados que incorporan el propio partido si se usan en backtest historico sin snapshot (el prompt lo reconoce l.397).
- Sobreajuste: bajo; casi sin coeficientes. Datos faltantes: tratamiento explicito y tipificado (l.90, 139).
- Incertidumbre: separa error MC del de modelo (l.215). Pero [INFERENCIA] no propaga la incertidumbre de parametros (ORtg estimado con ruido) a las probabilidades; solo la reporta cualitativamente.

## 7. Independencia del mercado
| Cita | Mencion | Clasificacion |
|---|---|---|
| l.19, 25, 69 | cuotas nunca variable; solo tras congelar | Politica correcta |
| l.229 | Calcular Home -1.5/Away +1.5 sin mercado; "cualquier linea real despues" | UMBRAL LEGITIMO |
| l.239 | umbral del usuario no es cuota | UMBRAL LEGITIMO |
| l.253-262 | conversion de cuotas, vig, p_implicita | COMPARACION POSTERIOR LEGITIMA |
| l.263-277 | EV, edge, CLV | COMPARACION POSTERIOR LEGITIMA |
| l.277 | movimiento de mercado "nunca ajuste de probabilidades" | Politica correcta |
| l.305-306 | benchmark sin vig en backtest | COMPARACION POSTERIOR LEGITIMA |
- [COMPROBADO] No hay ninguna ENTRADA PROHIBIDA. El prompt congela antes de consultar (l.248-249, 251). [INFERENCIA] Punto debil: el ejemplo de la validacion "ventanas de cuotas" como eje de robustez (l.405) es analisis posterior, aceptable.

## 8. Validacion que propone
Walk-forward con snapshots pregame (l.397); Brier, LogLoss, calibracion; MAE/RMSE/cobertura; log-verosimilitud discreta; ablaciones ORtg/DRtg/Pace vs +lesiones/descanso/4F/matchup; robustez por temporada, playoffs, favorito, local; EV realizado/ROI/CLV con incertidumbre (l.399-408). [INFERENCIA] No fija tamano minimo de muestra ni criterio de aceptacion cuantitativo (que es "bueno"); solo "no proclamar mejora sin resultados sostenidos".

## 9. Contraste con la plataforma
- [COMPROBADO] La plataforma NO implementa la cadena ORtg/DRtg/Pace. Usa `NormalMarginAdapter` (`src/sqp/sports/adapters.py:29-80`): el margen sale de Elo (`rating_diff` -> `elo_diff_to_margin`, `distributions.py:394-396`, `points_per_elo` 0.028 en `registry.py:29`) mas ajuste de descanso; el total sale de tasas ofensivas/defensivas por equipo (`team_scoring.py:92`, regresion con `prior_games` 6.0 por defecto, `adapters.py:39`); `margin_sigma` 13.0 y `total_sigma` 22.0 (`registry.py:29-31`), `avg_total` 224; `elo_home_adv` 70 y `elo_k` 20 (`registry.py:31`).
- Sobrescrituras NBA: `scoring_half_life_days` 180 (`registry.py:92`) y `rest_points_per_day` 0.795 (`configs/leagues/ratings.yaml:34-40`), activado 2026-09-26 tras pre-registro. [COMPROBADO] `ratings.yaml` no fija elo_home_adv NBA: vale 70.
- [COMPROBADO] Sin distribucion conjunta: margen y total son normales continuas e independientes (`distributions.py:32-68`) con sigma fijos; sin correlacion margen-total, sin marcadores enteros, sin simulacion. El prompt (l.195) prohibe exactamente esto ("No simular un margen y un total independientes").
- [COMPROBADO] Sin prorroga: no hay modelo OT en la familia Normal; el margen Normal absorbe la prorroga implicitamente (sigma residual del historico final con OT).
- [COMPROBADO] Push: lineas enteras renormalizan eliminando el push (`distributions.py:46-50, 62-66`); el prompt publica tres probabilidades. Se pierde P(push).
- [COMPROBADO] Faltan: pace, Four Factors, lesiones (no hay modulo; `grep` sin resultados de ortg/pace en `sports/` o `models/`), escenarios IN/OUT, prior de roster, bootstrap, MC, error MC, estados VALIDADO/EXPLORATORIO.
- Implementado equivalente: descanso/back-to-back (`models/rest.py`), regresion a la media del scoring, `sigma` residuales medidos walk-forward (`registry.py:21-28`), recencia.
- **Uso del mercado en las probabilidades:** [COMPROBADO] `configs/default.yaml:17` `market_shrink: 0.5`, blend `p=(1-s)*model+s*market` (no-vig); se aplica en `src/sqp/pipeline/daily.py:968-970` (`_decision_probability`) antes de edge y Kelly. `uncertainty_penalty: 0.35` (`default.yaml:26`) deflacta el edge por la discrepancia modelo-mercado, con penalizaciones por movimiento de linea (`daily.py:~985-995`). [INFERENCIA] Esto es mercado como ENTRADA de la probabilidad de decision para NBA, contra el principio del operador. [HIPOTESIS] La probabilidad estimada "pura" se conserva en `estimated_edge`/columnas servidas (el codigo dice "estimated_edge stays the RAW e", `daily.py` ~989); no verifique si la columna de probabilidad almacenada es pre-shrink. Los calibradores se entrenan sobre historial de picks (`calibrator.py:714`): [HIPOTESIS] sesgo de seleccion por haber sido elegidos por edge de mercado.
- Dato relevante: `docs/` y `default.yaml:72-89` registran que el edge declarado empeora al subir `min_edge` (memoria del proyecto).

## 10. Veredicto por componente
- Principio de independencia del mercado y orden de congelacion (l.19, 248-251): CONSERVAR.
- Estados VALIDADO/EXPLORATORIO/INCOMPLETO: CONSERVAR.
- Suavizado `K_games=20`: OPTIMIZAR (estimar K por backtest; la plataforma usa 6 partidos en scoring).
- Cadena ORtg/DRtg/Pace multiplicativa: INTEGRAR como challenger de totales y margen; hoy la plataforma solo tiene Elo y puntos por equipo.
- HCA +2.0: CORREGIR (medir HCA NBA con los datos propios; Elo 70 puntos x 0.028 = 1.96 puntos [INFERENCIA], coherente).
- Distribucion conjunta bootstrap + OT: INTEGRAR (cierra el defecto de sigma independientes y push).
- Poisson para OT: CORREGIR (subdispersion); aceptable solo como fallback.
- Four Factors, lesiones, matchup en 0: CONSERVAR como regla, INTEGRAR lesiones cuando exista fuente oficial.
- Bloque EV/edge/CLV (l.251-277): CONSERVAR (posterior); en plataforma, `market_shrink` y penalizaciones DESCARTAR de la construccion de probabilidad si se adopta el principio.
