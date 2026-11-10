# Auditoría individual: PROMPT_191_SERIE_A_v1_0

Fecha: 2026-11-10. Citas `P:n` = líneas de `C:\dev\Prompts\PROMPT_191_SERIE_A_v1_0.md`.

## 1. Ficha

- **Fichero / versión:** PROMPT_191_SERIE_A_v1_0.md; «PREGAME PRICING ENGINE v1.0» [COMPROBADO P:1].
- **Deporte / competición:** fútbol; «Serie A Enilive», primera división masculina de Italia [P:3]; distingue de Coppa Italia, Supercoppa y UEFA [P:94].
- **Tamaño:** 532 líneas.
- **Rol:** «motor cuantitativo especializado en fútbol de primera división italiana» [P:12].
- **Objetivo:** goles esperados; 1X2; Over/Under, BTTS, CS; hándicaps asiáticos y europeos con liquidación parcial; marcadores; EV solo con cuota [P:14-19].
- **Alcance / modos:** estados VALIDADO / EXPLORATORIO / INCOMPLETO [P:74-78]; log-lineal «entrenado contra los goles finales» o baseline exploratorio [P:209-233]; Poisson o Dixon-Coles [P:239-259].

## 2. Reglas y restricciones

- **Absolutas (15) [P:41-55]:** no inventar [P:41]; no afirmar ejecuciones no hechas [P:42]; datos disponibles en `as_of` [P:43]; **«No utilizar probabilidades, cuotas, picks, consenso, posiciones de apuestas ni movimientos de líneas como inputs del motor deportivo»** [P:44]; no mezclar xG y NPxG [P:45]; no reusar parámetros de EPL/LaLiga/Bundesliga [P:46]; sin doble conteo [P:47]; 90' + descuento [P:49]; sin edge sin cuota [P:51]; entrada crítica desconocida ≠ efecto neutral [P:53].
- **Excepción/ambigüedad:** [P:21] «NUNCA uses las cuotas… cuando operas en el modo independiente aquí especificado». [COMPROBADO] La cláusula «cuando operas en el modo independiente» presupone la existencia de un modo no independiente que el documento no define ni prohíbe. Es el único prompt de la familia con esta salvedad.
- **«Validado» [P:76, 448-463]:** parámetros entrenados y probados temporalmente fuera de muestra con calibración y rendimiento documentados; walk-forward; conjunto de prueba «verdaderamente no visto»; ablaciones; métricas 1X2, goles, submercados, precios.
- **Invariantes:** 35 [P:467-501].

## 3. Variables y parámetros

| Nombre | Valor | Unidad | Línea | Justificación |
|---|---|---|---|---|
| `grid_tail_tolerance` | `1e-6` | masa | P:69, 259, 484 | «umbral numérico… no es coeficiente deportivo» |
| `tau_off`, `tau_def`, `tau_gk`, `rho_DC`, `beta_*` | no fijados | – | P:66 | «solo valores entrenados y versionados» |
| `L_GF_H`, `L_GF_A`, `L_xGF`, `L_xGA` | no fijados | goles / xG | P:64-65 | Por temporada y fecha de corte |
| `timezone` | `Europe/Rome` | – | P:62 | Convención |
| `league_id` | `ITA_SERIE_A` | – | P:61 | Identificador |
| Monte Carlo | N y semilla a declarar | – | P:70 | Precisión declarada |
| Ejemplo de penalización fija prohibida | «dos titulares ausentes = -4 %» | % | P:158 | Citado como ejemplo a no seguir |
| Ascendidos 2026/27 | Venezia, Frosinone, Monza | clubes | P:142 | Fuente Lega Serie A [P:527] |
| Truncado prohibido | 5 o 6 goles | goles | P:259 | Ejemplo a evitar |

[HIPÓTESIS] Los tres ascendidos no fueron verificados contra la fuente. El prompt incluye «mercado» solo en `MarketQuality` [P:351].

## 4. Fuentes de datos

Jerarquía [P:80-88]: Lega Serie A y clubes; Opta/Stats Perform y Understat (xG/NPxG/PSxG, almacenando definición); informes oficiales de plantilla; meteorología; cuotas «solo tras congelación». Conflictos: oficial para estructura/sanciones, sabermétrica para métricas, «dato anterior al kickoff más reciente» [P:88]. Registro: `prediction_id`, `match_id`, `as_of`, `model_version`, `data_version` y fuente/timestamp por campo [P:316-317]. Sin periodicidad ni antigüedad máxima [INFERENCIA]. Señala arbitraje: «no utilizar árbitro over/under como ajuste automático» [P:205].

## 5. Cadena predictiva

1. Identificación y filtro [P:92-98].
2. Ataque y defensa por xG/NPxG, ajustado por oposición [P:100-128].
3. Regularización [P:132-138]: `w_i = n_eff_i / (n_eff_i + tau_i)`, `rating_adj_i = w_i * rating_observado_i + (1 - w_i) * rating_prior_i`; ascensos Serie B → A con transformación entrenada [P:140].
4. Forma, XI (escenarios IN/OUT), portero, balón parado/penales, matchup, descanso, localía/entorno/arbitraje [P:144-205].
5. λ [P:211-217]:
   `log(lambda_home) = beta0 + beta_HFA + Attack_home + WeakDefense_away + Context_home`
   `log(lambda_away) = beta0 + Attack_away + WeakDefense_home + Context_away`
   Baseline: `lambda_home = LeagueGoals_home * OffIndex_home * DefWeakIndex_away`; `lambda_away = LeagueGoals_away * OffIndex_away * DefWeakIndex_home` [P:229-231].
6. Distribución: `P(H=h,A=a) = Pois(h; lambda_home) * Pois(a; lambda_away)` [P:241]; DC con `(0,0): tau = 1 - lambda_home * lambda_away * rho_DC`, `(0,1): 1 + lambda_home * rho_DC`, `(1,0): 1 + lambda_away * rho_DC`, `(1,1): 1 - rho_DC` [P:247-251], `P_DC = tau * Pois * Pois` [P:253]; malla adaptativa con masa fuera ≤ 1e-6 [P:259].
7. Derivados: 1X2 [P:263-271], BTTS/CS [P:277-280], totales con push y cuartos [P:286-296], hándicap con `D = goles_equipo - goles_rival`: `P_cover = P(D+h>0)`, `P_push = P(D+h=0)`, `P_loss = P(D+h<0)` [P:300-304]; DNB, doble oportunidad, europeo 3 vías [P:306-308].
8. Congelación [P:314-323] y mercado [P:327-343].

Empate: resultado propio. No hay team totals explícitos. Monte Carlo opcional con semilla.

## 6. Auditoría matemática

- [COMPROBADO] τ correcto; [INFERENCIA] masa conservada exactamente en soporte completo; el prompt exige «validar que cada τ ≥ 0, que la masa total… sea coherente» [P:255] y Poisson si no hay `rho_DC` calibrado (**no inventar rho**).
- [COMPROBADO] «No confundas xG de los tiros con goles finales esperados» [P:37] y entrenamiento contra goles finales [P:209]: la mejor formulación de la familia sobre xG → goles.
- [COMPROBADO] Localía: la ecuación lleva `beta_HFA` en el local [P:211] y «No añadir otro `HomeAdj` si `LeagueGoals_home/away` ya contiene la diferencia» [P:233].
- EV: `EV_unit = P_win*(D_odds-1) - P_loss`, `BreakEvenPWin = (1-P_push)/D_odds`, `Edge_price_pp = 100*(P_win - BreakEvenPWin)` [P:331-335]: correctos. Para asiáticos: `EV_unit = sum_{h,a} P(h,a) * ProfitNet(...)` [P:339]: correcto.
- Pequeña contradicción de tolerancia: 1e-6 en la tabla [P:69] y en la malla [P:259]; coherente internamente, pero distinto de EPL/Bundesliga (1e-4) y LaLiga (1e-5 ejemplo).
- [COMPROBADO] Cita un ejemplo numérico «dos titulares ausentes = -4 %» [P:158] solo para prohibirlo; no es un coeficiente en uso.
- [INFERENCIA] «Empates de ranking: ordenar por mayor evidencia… sin atribuir ventaja matemática» [P:363]: regla de presentación sin impacto probabilístico.
- Datos faltantes: «Una entrada crítica desconocida no equivale a un efecto neutral conocido» [P:53]; escenarios [P:156, 509-510]. Incertidumbre: `ParameterUncertainty` Cuantificada / No cuantificada [P:350]; nombre distinto al `Uncertainty` de otros prompts (inconsistencia terminológica de la familia).
- Fuga temporal: ajuste por rival sin resultados posteriores a `as_of` [P:128]; snapshots verificables; «Un cambio posterior de XI produce nuevo `prediction_id`» [P:499].

## 7. Independencia del mercado

| Cita | Mención | Clasificación |
|---|---|---|
| P:5, 21 | «NUNCA uses las cuotas… cuando operas en el modo independiente aquí especificado»; «El mercado es solo un benchmark posterior» | Regla con salvedad ambigua (§2) |
| P:44 | Prohíbe cuotas, consenso, posiciones de apuestas y movimientos de línea como inputs | Regla |
| P:35, 86 | Cuotas «solo tras congelación» | COMPARACIÓN POSTERIOR LEGÍTIMA |
| P:312-323 | «Congelar antes de recuperar cuotas» | Regla |
| P:327-343 | EV, edge, devig «probabilidad justa de mercado sin margen» | COMPARACIÓN POSTERIOR LEGÍTIMA |
| P:287-304 | Líneas de total y hándicap | UMBRAL LEGÍTIMO |
| P:343 | CLV observado con cierre real | COMPARACIÓN POSTERIOR LEGÍTIMA |
| P:463 | «variación de CLV observado» en validación de precios | COMPARACIÓN POSTERIOR LEGÍTIMA |

[COMPROBADO] Ninguna ENTRADA PROHIBIDA literal. [INFERENCIA] La frase «cuando operas en el modo independiente» [P:21] abre la puerta formal a un modo con mercado; contradice el principio rector del operador. [RECOMENDACIÓN] Eliminarla y dejar «NUNCA» incondicional.

## 8. Validación que propone

Walk-forward; snapshots pregame verificables; separación calibración/evaluación; conjunto no visto; ablaciones; evaluación «por liga y temporada» (nótese: «por liga» no aplica a una sola liga) [P:456]; métricas: Log Loss y Brier multiclase, curvas, MAE/RMSE, log-verosimilitud de marcador, por submercado; EV, resultados realizados y CLV «con intervalos y tamaño muestral; no equiparar ROI positivo breve con evidencia concluyente» [P:458-463]. Falta umbral cuantitativo de aceptación [INFERENCIA].

## 9. Contraste con la plataforma

- **Implementado:** `poisson_match_probs` con DC, malla, push y cuartos (`src/sqp/models/distributions.py:204`; τ en `:71-80`); `SoccerAdapter` tres vías (`src/sqp/sports/adapters.py:314-316`).
- **Valores de producción Serie A:** `dc_rho -0.2`, `elo_home_adv 15.0` [`configs/leagues/ratings.yaml:51-53`]; `avg_goals 2.53` [`configs/leagues/soccer.yaml:7`]; default `soccer` [`src/sqp/sports/registry.py:45-47`]: `tilt_scale 1.0`, `max_score 10`, `home_scoring_bonus 0.15`, `elo_k 18`.
- **Difiere:**
  1. Sin xG/NPxG/PSxG/once/portero/árbitro/ascendidos: Elo y goles (`adapters.py:127-144`).
  2. Localía doble: Elo 15 pts + `home_scoring_bonus 0.15` (P:47 y P:205) [INFERENCIA].
  3. `max_score 10` y renormalización: prohibido truncar silenciosamente [P:259], aunque el prompt admite renormalizar un residuo ínfimo indicándolo; la plataforma no reporta masa omitida (`distributions.py:294`) [COMPROBADO].
  4. `dc_rho` por rejilla temporal (cabecera `ratings.yaml`), no MLE [HIPÓTESIS sobre el script].
  5. `avg_goals` fijo de respaldo.
  6. Probabilidad servida de líneas con push = decisión `win/(win+loss)`, no el trío.
- **Mercado en las probabilidades:** el adaptador no usa cuotas; `p_used = (1-s)*p_model + s*fair` con `market_shrink 0.5` [`configs/default.yaml:17`; `probabilities.py:303-304`; `daily.py:969-970`] afecta a todas las ligas incluida Serie A; `.env` de producción no verificable. Calibradores pre-blend (`probabilities.py:285-296`).

## 10. Veredicto por componente

| Componente | Veredicto | Motivo |
|---|---|---|
| xG ≠ goles; entrenamiento contra goles finales | CONSERVAR | La mejor formulación de la familia |
| Cláusula «modo independiente» (P:21) | CORREGIR | Ambigua; elimina la garantía |
| Tolerancia 1e-6 | CONSERVAR | Adecuada; unificar con la familia |
| `ParameterUncertainty` vs `Uncertainty` | OPTIMIZAR | Nombre inconsistente |
| «por liga y temporada» (P:456) | CORREGIR | Residuo multiliga |
| DC con `rho_DC` entrenado | CONSERVAR | La plataforma tiene -0.2 |
| xG, once, portero, ascendidos | INTEGRAR (parcial) | No existen en la plataforma |
