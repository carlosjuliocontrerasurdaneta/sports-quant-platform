# Auditoría individual: PROMPT_191_BUNDESLIGA_v1_0

Fecha: 2026-11-10. Citas `P:n` = líneas de `C:\dev\Prompts\PROMPT_191_BUNDESLIGA_v1_0.md`.

## 1. Ficha

- **Fichero / versión:** PROMPT_191_BUNDESLIGA_v1_0.md; «PREGAME PRICING ENGINE v1.0» [COMPROBADO P:1].
- **Deporte / competición:** fútbol; Fußball-Bundesliga. Se la rotula «Primera División de Alemania» [P:3]; excluye DFB-Pokal, Bundesliga 2, relegación y UEFA [P:75].
- **Tamaño:** 468 líneas.
- **Rol:** motor cuantitativo pregame [P:11].
- **Objetivo:** 1X2; goles esperados; marcadores; Over/Under y BTTS; hándicaps asiáticos y europeos, DNB, doble oportunidad; EV solo con cuota verificada [P:13-18].
- **Alcance / modos:** estados VALIDADO/EXPLORATORIO/INCOMPLETO [P:349-350]; log-lineal «calibrado» o fallback exploratorio [P:206-228]; Poisson o Dixon-Coles [P:237-251]; abstención [P:358].

## 2. Reglas y restricciones

- **Absolutas (17) [P:30-46]:** no inventar [P:30]; `as_of < kickoff` y prohibición de fugas en backtest [P:31]; no usar cuotas, picks, predicciones editoriales ni movimientos de línea como inputs [P:32]; xG/NPxG/PSxG/xGOT no intercambiables [P:33]; parámetros estimados para Bundesliga [P:35]; evitar doble conteo de localía, penal, portero, lesiones, balón parado, presión, forma [P:37]; 90' + descuento [P:38]; distribución reproducible y normalizada [P:39]; sin cuota no hay edge [P:41]; escenarios sin pesos inventados [P:44]; huso `Europe/Berlin` [P:46].
- **«Validado» [P:354]:** walk-forward; temporadas, jornadas tempranas y ascendidos por separado; Brier/Log Loss 1X2, curvas de calibración, log-verosimilitud de marcadores, MAE/RMSE de goles, BTTS/totales, ablaciones (base, porteros, presión, balón parado, descanso, XI); mejora frente a baseline con incertidumbre. Sin umbral numérico.
- **Controles:** 35 [P:405-439] (el título dice «CONTROLES», sin cifra declarada).

## 3. Variables y parámetros

| Nombre | Valor | Unidad | Línea | Justificación |
|---|---|---|---|---|
| Masa residual conjunta | `< 0.0001` (0,01 %) | prob. | P:255 | Declarada; sin justificar |
| Cobertura de malla en los controles | ≥ 99,99 % | prob. | P:421-422 | Equivale a lo anterior |
| Equipos / jornadas | 18 / 34 | – | P:77 | Formato |
| `tau`, `rho`, pesos | no fijados | – | P:178, 251 | «No inventarlo» |
| `rho` dominio | todos τ ≥ 0 | – | P:251 | Estimado «exclusivamente con datos de Bundesliga» |
| Ascendidos 2026/27 | Schalke 04, SV Elversberg, SC Paderborn 07 | clubes | P:195 | Fuente bundesliga.com [P:466] |
| Husos | Europe/Berlin, usuario, UTC | – | P:46, 73 | Convención |

[COMPROBADO] No hay coeficientes entrenados. [HIPÓTESIS] Los tres ascendidos no se verificaron contra la fuente.

## 4. Fuentes de datos

Prioridad por variable [P:52-59]: Bundesliga/DFL y clubes para calendario y estado; Bundesliga Match Facts/AWS (xGoals), Opta, Understat, StatsBomb para métricas «cuando estén realmente accesibles» [P:56]; PSxG/xGOT del mismo proveedor [P:57]; meteorología con estado del techo; mercado al final. Registro `{match_id, team_id, field, value, unit, definition, season, sample, source, observed_at, available_at, as_of, fallback, model_version}` [P:63]; incluye `available_at`, útil para evitar fugas (mejor que EPL). Clasifica cada variable `VERIFICADA / PROVISIONAL / AUSENTE / CONFLICTIVA` [P:95].

## 5. Cadena predictiva

1. Identificación [P:71-82], inventario [P:84-97].
2. Normalización por 90' y ajuste por oposición con ratings conjuntos [P:99-108]; ataque [P:110-118], defensa [P:120-126].
3. XI, portero (PSxG/xGOT), presión/transiciones, balón parado/penales [P:128-166].
4. Forma, descanso, clima, ascendidos [P:168-202]; regularización `w = n_eff / (n_eff + tau)`, `Rating_reg = w * Rating_observado + (1-w) * Rating_prior` [P:174-176].
5. Goles esperados [P:208-214]:
   `log(lambda_home) = beta0_home + Attack_home + WeakDefense_away + Context_home`
   `log(lambda_away) = beta0_away + Attack_away + WeakDefense_home + Context_away`
   Fallback: `lambda_home = LeagueGoals_home * OffIndex_home * DefWeakIndex_away` [P:224-226]; `Total_xG = lambda_home + lambda_away`; `GoalDifference = lambda_home - lambda_away` [P:230-231].
6. Distribución: `P(H=h,A=a) = Pois(h; lambda_home) * Pois(a; lambda_away)` [P:239]; DC `p_DC = tau * p_ind` con τ(0,0)=1−λhλaρ, τ(0,1)=1+λhρ, τ(1,0)=1+λaρ, τ(1,1)=1−ρ [P:243-249]; «El ajuste preserva la suma de masa en soporte completo» [P:251].
7. Derivados desde la misma matriz: 1X2, BTTS, CS [P:261-277]; totales con push y cuartos [P:281-296]; hándicap `P_cover = P(G_i + h > G_opponent)`, push, loss [P:300-306]; europeo 3 vías, DNB, doble oportunidad, team totals «siempre con reglas específicas» [P:310-314].
8. Congelación y mercado [P:320-343].

Empate: resultado propio. Monte Carlo: «No afirmar que se ha usado Monte Carlo si se calculó una malla analítica» [P:255]; si se usa, semilla e iteraciones [P:257].

## 6. Auditoría matemática

- [COMPROBADO] τ correcto; [INFERENCIA] la afirmación «preserva la suma de masa» [P:251] es exacta en soporte completo (los términos se cancelan) y la salvedad de truncado es correcta.
- [COMPROBADO] En el fallback, `LeagueGoals_home/away` «ya reflejan diferencia media de sede. No añadir HFA sin justificar» [P:228]: buena advertencia anti-doble-localía.
- [COMPROBADO] Las ecuaciones omiten un parámetro de localía separado y usan interceptos `beta0_home` y `beta0_away` [P:208-210]; [INFERENCIA] coherente con «una sola vez» [P:188].
- Contaminación de plantilla (restos de otros deportes) [COMPROBADO]: «si sólo existe 5v5 no corresponde a fútbol; nunca reutilizar categorías de hockey» [P:105]; «XI/QB (no aplicable aquí)» [P:358]. Son errores de copia que no afectan a las fórmulas pero delatan reutilización de plantilla; [RECOMENDACIÓN] eliminarlos.
- [COMPROBADO] «`GoalDifference = lambda_home - lambda_away`» [P:231] es la diferencia esperada de goles; correcta bajo Poisson y bajo DC solo aproximadamente (DC cambia las medias). El prompt exige comprobar medias bajo otras distribuciones en EPL (P:229 de ese prompt) pero aquí no. [INFERENCIA] Pequeño riesgo de reportar medias inexactas con DC.
- Tolerancias: 1e-4 aquí frente a 1e-6 de Serie A/Ligue 1/UCL.
- Coherencia: sumas 1X2/BTTS/Over/Cover [P:277, 287, 422-425]; EV `P_win*(D-1) - P_loss`, `P_break_even_win = (1-P_push)/D`, `Edge_precio_pp = 100*(P_win - P_break_even_win)` [P:332-335] correctos; conversión americana `D = 1 + X/100` y `D = 1 + 100/abs(X)` [P:326-327] correctas. En 1X2 «P_loss = 1 - P_win, no es push» [P:337]: correcto.
- «Evita aplicar por separado fatiga y rotación si ya se estima mediante minutos» [P:184]: declarativo, sin procedimiento.
- Faltantes: «No convertir valores faltantes silenciosamente en promedios neutralizados» [P:97]; escenarios sin pesos [P:134]. Incertidumbre: `Uncertainty = Cuantificada / No cuantificada` [P:352].
- Fuga temporal: señala «revisiones retrospectivas de xG, alineaciones publicadas después del kickoff y cuotas de cierre vistas antes del pronóstico» [P:356]; lo último es una fuga de **mercado** hacia el modelo si ocurriera, por lo que su mención es una salvaguarda. 

## 7. Independencia del mercado

| Cita | Mención | Clasificación |
|---|---|---|
| P:5, 26, 32 | Mercado «no interviene» en ratings, goles ni distribución; benchmark posterior | Regla |
| P:18, 322-343 | EV con cuota verificada tras congelar; devig «benchmark, no input» [P:341] | COMPARACIÓN POSTERIOR LEGÍTIMA |
| P:59 | Mercado «solamente al final» | COMPARACIÓN POSTERIOR LEGÍTIMA |
| P:287-296, 300-308 | Líneas `t` y `h` de hándicap/total | UMBRAL LEGÍTIMO |
| P:343 | CLV tras cierre real | COMPARACIÓN POSTERIOR LEGÍTIMA |
| P:356 | «cuotas de cierre vistas antes del pronóstico» como fuga a evitar | Salvaguarda |

[COMPROBADO] Sin ENTRADA PROHIBIDA. Congela antes de consultar [P:320-322].

## 8. Validación que propone

Walk-forward; evaluación separada por temporada, jornada temprana y ascendidos; Brier/Log Loss 1X2, curvas, log-verosimilitud de marcadores, MAE/RMSE; BTTS/totales; ablaciones; mejora frente a baseline con su incertidumbre [P:354-356]. [INFERENCIA] No fija tamaño mínimo ni umbral; la validación por jornada temprana es útil (cold start).

## 9. Contraste con la plataforma

- **Implementado:** Poisson + DC, malla, push y cuartos (`src/sqp/models/distributions.py:71-80, 204`); `SoccerAdapter` tres vías (`adapters.py:314-316`).
- **Valores de producción Bundesliga:** `dc_rho -0.2`, `elo_home_adv 15.0` [`configs/leagues/ratings.yaml:10-12`]; `avg_goals 3.20` [`configs/leagues/soccer.yaml:6`]; resto del default `soccer` [`registry.py:45-47`] (`tilt_scale 1.0`, `max_score 10`, `home_scoring_bonus 0.15`, `elo_k 18`).
- **Difiere:** (1) sin xG/NPxG/PSxG/presión/clima/ascendidos; Elo + `TeamScoringRates` aditivo (`adapters.py:127-144`, `team_scoring.py:98-101`); (2) localía por Elo (15 pts) más `home_scoring_bonus 0.15` en λ_local: posible doble conteo frente a P:37 y P:188 [INFERENCIA]; (3) `dc_rho -0.2` de búsqueda en rejilla (cabecera de `ratings.yaml`), no MLE; compatible con «estimado con datos de Bundesliga» [P:251] si el tuning es temporal [HIPÓTESIS: no auditado aquí el script]; (4) `avg_goals 3.20` fijo como respaldo; (5) malla truncada a 10 y renormalizada (`distributions.py:294`) frente a «no renormalizar… sin justificación numérica» [P:251]; no se reporta la masa omitida; (6) probabilidad de decisión condicional a no-push, no el trío win/push/loss.
- **Mercado en las probabilidades:** el adaptador no usa cuotas; la probabilidad de decisión se mezcla con el no-vig: `market_shrink 0.5` [`configs/default.yaml:17`; `probabilities.py:303-304`; `daily.py:969-970`], también para Bundesliga. `.env` de producción no verificable. Calibradores pre-blend (`probabilities.py:285-296`).

## 10. Veredicto por componente

| Componente | Veredicto | Motivo |
|---|---|---|
| Independencia del mercado (P:26, 32, 59, 341) | CONSERVAR | Limpio |
| Campo `available_at` en el registro (P:63) | CONSERVAR y propagar | Evita fuga |
| Restos de hockey/QB (P:105, 358) | CORREGIR | Contaminación de plantilla |
| Tolerancia 1e-4 | OPTIMIZAR | Unificar |
| Medias bajo DC (P:231) | CORREGIR | Verificar medias reales de la matriz |
| Fallback multiplicativo | CONSERVAR como exploratorio | Con advertencia de localía (P:228) |
| Presión/PPDA, xG | INTEGRAR (parcial) | Sin proveedor en la plataforma |
| Ascendidos | INTEGRAR | La plataforma no los trata |
