# Auditoría de PROMPT_191_MLS_v1_0.md

Fecha de la auditoría: 2026-11-10. Marcas: [COMPROBADO] (con cita), [INFERENCIA], [HIPÓTESIS], [RECOMENDACIÓN]. Las citas `MLS:n` son líneas de `C:\dev\Prompts\PROMPT_191_MLS_v1_0.md`.

## 1. Ficha

| Campo | Valor |
|---|---|
| Fichero | `C:\dev\Prompts\PROMPT_191_MLS_v1_0.md` |
| Versión declarada | "PROMPT 191-MLS v1.0" (MLS:1); reglas de referencia "MLS 2026" (MLS:6) |
| Deporte / competición | Fútbol masculino de clubes; MLS temporada regular y Audi MLS Cup Playoffs (MLS:3) |
| Tamaño | 360 líneas, 21 fases, 30 controles automáticos (MLS:321-352) |
| Rol | "motor cuantitativo pregame", "orquestador de datos, motor numérico reproducible y auditor" (MLS:12) |
| Objetivo | Probabilidades deportivas independientes del mercado para 1X2 a 90', avanzar en eliminatorias, hándicaps y totales; después, EV (MLS:4) |
| Modos de operación | Estado de salida VALIDADO / EXPLORATORIO / INCOMPLETO (MLS:75-79). Declara "EXPLORATORIO hasta entrenar y validar parámetros" (MLS:5). Es una especificación: no trae datos, parámetros ni código (MLS:12, :33). |

## 2. Reglas y restricciones

- [COMPROBADO] 18 reglas absolutas (MLS:24-41). Las más relevantes: no usar información posterior a `as_of` (:25); tandas no suman goles (:26); modelar siempre local/empate/visitante, nunca empate al favorito (:27); sin modelo ejecutado, "probabilidades: NO CALCULADAS" (:33); sin cuota verificada, "EV/edge: NO EVALUABLES" (:35); excluir partidos iniciados o suspendidos (:40).
- [COMPROBADO] Principio: "El mercado NUNCA es input de los parámetros predictivos o de las probabilidades deportivas" (MLS:18).
- Reglas de excepción: sin xG, modelo de goles observados "solo si ha sido entrenado/validado para tal degradación; en otro caso INCOMPLETO" (MLS:248); faltantes con prior calibrado, no con factor 1.00 silencioso (:248).
- Condiciones de VALIDADO (MLS:276): split temporal; snapshots sin fuga; backtest por temporada, fase y localía; log loss multinomial, Brier multiclase, RPS, curvas de calibración por P(empate), log-verosimilitud de marcador, MAE, BTTS/hándicaps/totales; intervalos; comparación con Poisson simple y ablaciones (portero, plantillas, local, calendario, Dixon-Coles); ROI con precios realmente disponibles; sensibilidad al proveedor de xG.
- [COMPROBADO] Criterio de congelación: persistir todo antes de consultar cuotas y "no ajustar el pronóstico para hacerlo similar al mercado" (MLS:256).

## 3. Variables y parámetros

[COMPROBADO] El prompt no fija ningún coeficiente numérico deportivo; lo declara una y otra vez ("no fijarlo arbitrariamente", MLS:111; "No asignar rho manual", :179; "no una constante inventada", :129). Las únicas constantes son estructurales.

| Nombre | Valor | Unidad | Fase/línea | Justificación |
|---|---|---|---|---|
| Puntos temporada regular | 3/1/0 | puntos | F1, :87 | Reglamento MLS; fuente oficial citada (:58) |
| Prórroga en playoffs (semis de conferencia a MLS Cup) | 2 x 15 min | min | F1 :87, F17 :235 | Reglamento 2026 (a verificar, :87) |
| Wild Card y Round One Bo3 | empate a 90' va directo a penales | regla | :87, :233 | Reglamento 2026 [HIPÓTESIS: no verificado por mí contra la fuente] |
| Shrinkage `w = n_eff/(n_eff+tau)` | `tau` estimado | adimensional | F4 :107-109 | Se exige estimarlo por variable (:111); sin valor |
| `beta0_H`, `beta0_A`, `AttackStrength`, `DefenseWeakness`, `Adjustments` | estimados | log-goles | F12 :151-157 | MLE sobre histórico MLS (:159) |
| `rho` Dixon-Coles | estimado | adimensional | F13 :179 | MLE; prohibido manual |
| Tolerancia de cola | "especificada" sin valor | probabilidad | F13 :181 | Sin número (las otras cuatro fijan 1e-6) |
| `q_home_shootout` | no definido | prob. | F17 :240-242 | "no debe inventarse" |
| Stake asiático de cuarto | 50 % / 50 % | fracción | F16 :223 | Convención del mercado |
| Escala de salida | `XX.X%`, `X.XX` | | :294-299 | Formato |

## 4. Fuentes de datos

[COMPROBADO] Jerarquía de cuatro niveles (MLS:47-53): 1) MLSsoccer.com, clubes, IFAB; 2) American Soccer Analysis (xGoals, GA, portería) y proveedor de eventos "con metodología transparente"; 3) meteorología y datos de estadio; 4) mercado, solo al final. Reglas de conflicto: oficial para estructura y alineaciones, el dato más reciente "que ya existía a `as_of`" (:55). Periodicidad no especificada; frescura controlada por `as_of`/`available_at` (:71). Calidad: `DataQuality` Alta/Media/Baja (:250).
[INFERENCIA] Las citas a URLs de 2026 (reglas MLS, API de ASA) no se pueden verificar desde la plataforma; son enlaces a reglamentos vivos.
[HIPÓTESIS] La cobertura de ASA es estable y con licencia suficiente para uso comercial; el prompt solo pide "licencia de uso apropiada" (:49).

## 5. Cadena predictiva

1. Datos y rating (F2-F4): `xGF90`, `xGA90`, `NPxG` ajustados por rival y shrinkage (MLS:105-111). Lo más próximo a una fórmula de rating es el shrinkage:
   `w = n_eff / (n_eff + tau)` y `Rate_shrunk = w * Rate_observed + (1-w) * Rate_prior` (:107-109).
2. Ajustes de plantilla, portero, estilo, localía, descanso y clima (F5-F11): solo con coeficientes estimados fuera de muestra (:133, :137, :141, :145). Sin evidencia, "factor cualitativo con incertidumbre, no delta de goles inventado" (:141).
3. Modelo de goles (F12), preferente log-lineal:
   `log(lambda_home_90) = beta0_H + AttackStrength_home + DefenseWeakness_away + Adjustments_home` (:151)
   `log(lambda_away_90) = beta0_A + AttackStrength_away + DefenseWeakness_home + Adjustments_away` (:153)
   Baseline alternativo: `lambda_home_NP = League_NPGoals_home_90 * AttackIndex_home * DefenseAllowedIndex_away` (:167), con índices `NPxGF90_adj/League_NPxGF90` y `NPxGA90_adj/League_NPxGA90` (:163-165). "Si esa conversión [NPxG a goles] no está definida, no producir lambdas" (:171).
4. Distribución conjunta (F13-F14): Poisson independiente como baseline; Dixon-Coles, Poisson bivariante, gamma-Poisson como candidatos; sin `rho` manual (:177-179). Matriz `P_90(h,a)` con masa de cola controlada y comprobaciones `sum=1` y esperanzas coherentes con las lambdas (:185-189).
5. Mercados (F15-F16), todos de la misma matriz (:191, :209):
   `P_1 = sum_{h>a} P_90(h,a)`; `P_X = sum_{h=a} P_90(h,a)`; `P_2 = sum_{h<a} P_90(h,a)` (:197-201); BTTS `sum_{h>=1,a>=1}` (:205); portería a cero (:207); marcador exacto (:209); hándicap `win si goals_selected + h > goals_opponent` (:215); over/under con push (:217); doble oportunidad, DNB, hándicap y totales asiáticos con pago medio por marcador (:219-223).
6. Prórroga/penales (F17): modelo separado para Wild Card (sin prórroga) y rondas con prórroga. `P_home_wins_match = P_1 + P_X * q_home_shootout` (:238); `P_away_wins_match = P_2 + P_X * (1-q_home_shootout)` (:240). Prórroga: "simular los 30' adicionales condicionados a empate, y después penales" (:242). Team totals: no se producen (solo totales del partido). Monte Carlo: opcional; si se usa, registrar semilla, iteraciones, SE (:181).

Dependencias entre variables: Dixon-Coles para marcadores bajos; el prompt prohíbe combinar cópula y corrección DC sin justificación (:179).

## 6. Auditoría matemática

- [COMPROBADO] Coherencia 1X2/BTTS/hándicap/total: todo se deriva de `P_90` y se exigen sumas 1 (controles 14-17, MLS:338-339). El tratamiento del push es correcto en líneas enteras y de cuarto (:215-223); el EV de cuartos usa el vector real de pagos (:223, :264).
- [COMPROBADO] `Edge_pp = 100 * [P_win - (1-P_push)/D]` (MLS:266) es correcto para pago simple; el propio prompt lo limita a esa estructura.
- [INFERENCIA] Distribución adecuada: Poisson independiente + Dixon-Coles es el estándar para fútbol; en MLS (3,07 goles por partido en la config de la plataforma) la sobredispersión es modesta, pero el prompt la admite como candidata (:179).
- [INFERENCIA] Shrinkage sobre "rates" (:109) se escribe en escala lineal; con ratings log-lineales el shrinkage natural es aditivo en log. Detalle menor.
- [INFERENCIA] El baseline multiplicativo (:167) usa xG como proxy de goles. xG no es el valor esperado de goles de forma calibrada, y el prompt lo reconoce (:171); sin esa calibración es solo un índice.
- [COMPROBADO] Omisión de Mundial 2026: el prompt no menciona el parón de la temporada MLS por el Mundial 2026; el Brasileirão sí lo hace (BRASILEIRAO:150). [HIPÓTESIS] MLS tuvo parón en 2026; el calendario no se verificó aquí. La fase 10 genérica (:141) cubre "calendario FIFA" pero no el parón largo.
- [INFERENCIA] Coeficientes sin justificar: ninguno numérico (por diseño). Riesgo de sobreajuste: con una liga de 30 clubes y pocas temporadas de xG de ASA (que cubre la MLS desde 2013 según su API, no verificado), el número de parámetros (ataque, defensa por club, plantilla, portero, matchups) es alto frente a ~870 partidos por temporada; el prompt exige regularización y ablaciones (:276) pero no un criterio de selección de complejidad.
- [COMPROBADO] Fuga temporal: la regla 2 y el control 4 (MLS:25, :326) y la exigencia de `available_at` (:71) son correctas; aun así no menciona expresamente la reescritura retrospectiva de xG por proveedores [INFERENCIA, riesgo real].
- Datos faltantes: tratamiento explícito y conservador (:248, :252); sin imputación implícita a 1.00.

## 7. Independencia del mercado

| Cita | Mención | Clasificación |
|---|---|---|
| MLS:4 | "Solo después de congelar el modelo, comparar cuotas" | COMPARACIÓN POSTERIOR LEGÍTIMA |
| MLS:18 | "El mercado NUNCA es input"; prohíbe picks, consenso, apuestas públicas | Declaración de principio |
| MLS:53 | Nivel 4 de fuentes, "solo al final" | COMPARACIÓN POSTERIOR LEGÍTIMA |
| MLS:215-217, :223 | Líneas de hándicap y total como parámetro `h`, `t` | UMBRAL LEGÍTIMO (la probabilidad viene de `P_90`) |
| MLS:256 | Congelación previa; no ajustar para parecerse al mercado | Congelación correcta |
| MLS:262-268 | No-vig, EV, CLV | COMPARACIÓN POSTERIOR LEGÍTIMA |
| MLS:276 | ROI con precios históricos | COMPARACIÓN POSTERIOR LEGÍTIMA |
| MLS:49 | ASA/xG de proveedor | No es mercado; es dato deportivo |

[COMPROBADO] No hay ninguna ENTRADA PROHIBIDA. El prompt congela las probabilidades antes de consultar el mercado (MLS:256, :258) y reitera la regla en MLS:360.

## 8. Validación que propone

[COMPROBADO] MLS:276: split temporal, snapshots sin fuga, backtest por temporada/fase/localía, log loss, Brier, RPS, calibración por P(empate), log-verosimilitud de marcadores, ablaciones y comparación con Poisson simple, EV/ROI con precios disponibles y "sensibilidad a cambios de proveedor de xG". [INFERENCIA] Falta un tamaño de muestra mínimo o un umbral numérico de aceptación (por ejemplo, mejora de log loss con IC), así que "VALIDADO" es un juicio no operativo. [RECOMENDACIÓN] Fijar criterios pre-registrados como los que ya usa el proyecto (ver `docs/research/`).

## 9. Contraste con la plataforma

Hechos de la plataforma (verificados):

- [COMPROBADO] Liga registrada: `configs/leagues/soccer.yaml:11` `mls: {sport_key: soccer_usa_mls, avg_goals: 3.07}`. Resultados de ESPN `soccer/usa.1` (`src/sqp/providers/espn_results.py:91`).
- [COMPROBADO] Familia `soccer`: `avg_total 2.7`, `tilt_scale 1.0`, `max_score 10`, `home_scoring_bonus 0.15`, `elo_k 18`, `elo_home_adv 48`, `dc_rho 0.0` (`src/sqp/sports/registry.py:45-47`). Overrides de MLS: `elo_home_adv: 30.0`, `elo_home_away_split: true` (`configs/leagues/ratings.yaml:31-33`). `dc_rho` de MLS queda en 0.0 (solo bundesliga, epl, seriea tienen -0.2: `ratings.yaml:11-21`).
- [COMPROBADO] Lambdas: `SoccerAdapter` (`adapters.py:314-316`) hereda `PoissonAdapter._rates`: `p_home` del Elo → `tilt = clamp((p_home-0.5)*tilt_scale, ±0.30)` → `lam_home = avg*(0.5+tilt) + home_scoring_bonus`, `lam_away = avg*(0.5-tilt)` (`adapters.py:126-143`); `avg` = total esperado de las tasas de gol propias del equipo (`team_scoring.py:92-101`) con `avg_goals` de la liga como prior (`pipeline/daily.py:95`).
- [COMPROBADO] Distribución: `poisson_match_probs` (`models/distributions.py:204-309`), Poisson o binomial negativa, Dixon-Coles con `tau` idéntico al del prompt (`distributions.py:71-83`), malla `max_goals=10`, renormalización de la masa truncada (`:294-297`, sin informar la cola), líneas asiáticas de cuarto (`:253-293`).

| Elemento del prompt | Estado en la plataforma |
|---|---|
| Poisson + Dixon-Coles, mercados de la misma matriz | Implementado (`distributions.py:204-309`); `dc_rho=0` en MLS |
| Líneas asiáticas de cuarto con mitades | Implementado (`distributions.py:253-293`) |
| xG, NPxG, PSxG, porteros, alineaciones, clima | FALTAN: solo aparece una mención "xg" en `adapters.py`; los ratings son Elo + tasas de goles |
| Modelo log-lineal con ataque/defensa por club y MLE | FALTA: se usa Elo logístico + `tilt`; los coeficientes (`tilt_scale 1.0`, `home_scoring_bonus 0.15`) son de familia, no ajustados para MLS |
| Localía una sola vez | DIFIERE [INFERENCIA]: `elo_home_adv` (30, con split local/visita) entra en `p_home` y además se suma `home_scoring_bonus 0.15` a `lam_home` (`adapters.py:141`): dos canales de localía |
| Prórroga/penales/avanzar en playoffs | FALTA: la plataforma sirve el mercado h2h de 3 vías a 90'; sin modelo de serie |
| Cola de la malla reportada | DIFIERE: renormaliza sin reportar masa omitida (`distributions.py:294-297`) |
| Congelación antes del mercado | Parcial: se guarda `model_probability`/`adjusted_probability` y `p_used` (`probabilities.py:285-298`); la mezcla con mercado se hace en el mismo flujo |

**Uso del mercado en la construcción de probabilidades (plataforma).** [COMPROBADO] `market_shrink: 0.5` en `configs/default.yaml:17` y `_decision_probability` hace `p_used = (1-s)*p_model + s*fair` y `p_decision = (1-s)*cal(p_model) + s*fair` con `fair` = no-vig del consenso (`pipeline/probabilities.py:303-306`; uso en `pipeline/daily.py:969-970`). Es un ajuste hacia el mercado que el principio del operador prohíbe como entrada. No hay override por liga de MLS en `configs/`; el valor de producción del `.env` no se pudo leer (permiso denegado), así que el valor efectivo `MARKET_SHRINK` es NO VERIFICADO. Además `uncertainty_penalty: 0.35` (`default.yaml:26`) deflacta el edge usando la distancia modelo-mercado y el movimiento de línea (`daily.py:983-1000`): decisión de apuesta, no probabilidad, pero consume mercado. [COMPROBADO] La probabilidad pura del modelo (`p_model`) no usa mercado: el Elo, las tasas de gol y la malla Poisson solo usan resultados. El calibrador se entrena contra resultados, no contra el mercado (`probabilities.py:278-296`).

## 10. Veredicto por componente

| Componente | Veredicto | Motivo |
|---|---|---|
| Principio de independencia y congelación previa (MLS:18, :256) | CONSERVAR | Coincide con el principio del operador |
| Estructura de fases y estados VALIDADO/EXPLORATORIO/INCOMPLETO | CONSERVAR | Evita falsa precisión |
| Modelo log-lineal con ataque/defensa por club (F12) | INTEGRAR | La plataforma usa Elo+tilt; integrar solo tras backtest OOS contra la línea base |
| Dixon-Coles | CONSERVAR | Ya implementado; estimar `rho` de MLS (hoy 0.0) |
| Baseline NPxG→goles (MLS:167) | OPTIMIZAR | Exige conversión calibrada; sin ella no calcula |
| Reglas de playoffs 2026 y `q_home_shootout` | INTEGRAR | La plataforma no modela series; verificar reglamento vigente antes |
| Fase 10 / Mundial 2026 | CORREGIR | Falta el parón largo del calendario 2026 |
| Tolerancia de cola sin valor (MLS:181) | CORREGIR | Fijar 1e-6 como en las otras ligas |
| Fase 20 (mercado, EV, CLV) | CONSERVAR | Posterior al congelado |
| Mezcla con mercado de la plataforma (`market_shrink`) | CORREGIR | Contradice el principio fundamental (ver 9) |
