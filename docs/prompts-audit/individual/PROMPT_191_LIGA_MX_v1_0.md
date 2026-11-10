# Auditoría de PROMPT_191_LIGA_MX_v1_0.md

Fecha: 2026-11-10. Citas `LMX:n` = líneas de `C:\dev\Prompts\PROMPT_191_LIGA_MX_v1_0.md`.

## 1. Ficha

| Campo | Valor |
|---|---|
| Fichero | `PROMPT_191_LIGA_MX_v1_0.md` |
| Versión | "PREGAME PRICING ENGINE v1.0" (LMX:1); fecha documental 2026-11-10 (LMX:6) |
| Deporte / competición | Fútbol masculino; Liga MX varonil, Apertura y Clausura, fase regular y Liguilla (LMX:3) |
| Tamaño | 454 líneas, 21 fases, 35 controles (LMX:400-436), 17 reglas absolutas (LMX:31-47), bloque YAML de configuración (LMX:53-71) y tabla de fallbacks (LMX:339-351) |
| Rol | Motor cuantitativo pregame, "especificación para un motor de cálculo real; no se presume que un modelo de lenguaje haya ejecutado simulaciones" (LMX:5) |
| Objetivo | λ, 1X2, BTTS, portería a cero, marcadores, Over/Under, hándicaps, DNB; Liguilla (avanzar y campeón); EV (LMX:12-19) |
| Modos | `status: EXPLORATORIO` (LMX:64), VALIDADO/EXPLORATORIO/INCOMPLETO (LMX:42, :323) |

## 2. Reglas y restricciones

- [COMPROBADO] "El mercado nunca entra en las estimaciones λ ni en la distribución deportiva" (LMX:25); `odds_usage: comparison_only_after_freeze` (LMX:70).
- [COMPROBADO] Regla propia del prompt: Apertura y Clausura son torneos independientes con tabla y Liguilla propias; información previa solo como prior ajustado por plantilla (LMX:33).
- [COMPROBADO] No convertir posición, cociente, rachas o cuotas en probabilidad (LMX:36). No aplicar automáticamente ajustes positivos por altitud, clima, horario o localía (LMX:37).
- [COMPROBADO] "No definir por intuición valores numéricos para HFA, tau, coeficientes de altitud, rho, efecto de portero, sanciones ni ventaja por posición de Liguilla" (LMX:73).
- Excepción: ruta exploratoria con parámetros documentados o abstención (LMX:73). Fallbacks permitidos solo según tabla (LMX:341-351).
- VALIDADO exige backtest cronológico fuera de muestra para Liga MX con Brier, log loss y calibración, y para Liguilla log loss/Brier por ronda (LMX:329).

## 3. Variables y parámetros

| Nombre | Valor | Unidad | Fase/línea | Justificación |
|---|---|---|---|---|
| `model_id` / `version` | PROMPT_191_LIGA_MX / 1.0 | | YAML :54-55 | Metadato |
| `default_calendar_timezone` | America/Mexico_City | | :61 | Zona de Liga MX (nótese que hay estadios en otras zonas: :62) |
| `score_grid_tail_tolerance` | 0.000001 | probabilidad | YAML :68 y F14 :224 | Tolerancia numérica |
| `model_preferred` | calibrated_log_linear_goals | | :65 | |
| `model_baseline` | independent_poisson | | :66 | |
| Clubes / jornadas Apertura 2026 | 18 / 17 | | :35, :280 | "información disponible a la fecha de referencia"; revalidar |
| Acceso a cuartos | 8 mejores, sin Play-In | | :35, :280 | Reglamento; [HIPÓTESIS] sin verificar |
| `tau` | estimado | | :126-130 | "No fijar valor arbitrario" |
| `beta_home`, `beta0`, `Attack`, `DefWeakness`, `b_context` | estimados | | :182-190 | |
| `rho_DC` | estimado | | :216-222 | |
| Stake asiático | 50/50 | | :266 | |

[COMPROBADO] Ningún coeficiente numérico deportivo se fija.

## 4. Fuentes de datos

[COMPROBADO] Jerarquía (LMX:77-82): 1) oficiales (Liga MX/FMF/clubes); 2) proveedores avanzados con cobertura verificable "p. ej., FotMob" (LMX:78) con registro de cobertura y licencia; 3) meteorología y altitud verificada; 4) mercado solo para benchmark. Regla de conflicto: un proveedor principal por campo; para xG prevalece homogeneidad (LMX:82). [INFERENCIA] La cobertura xG de Liga MX en FotMob depende de la temporada (el prompt lo reconoce en :444 "cobertura según temporada"); riesgo de series cortas para el prior de torneo (17 jornadas por torneo, LMX:120).

## 5. Cadena predictiva

1. Ofensiva (F2): `xGF/90`, `NPxGF/90`, tiros, xG por tiro; jerarquía "xG ajustable por rival > modelo de tiros validado > goles regularizados" (LMX:100).
2. Defensa (F3), ajuste por rival (F4): ratings "conjunto o iterativo"; sin ajuste: `opp_adjustment = unavailable` y baja `DataQuality` (LMX:116).
3. Regularización (F5): `w = n_eff / (n_eff + tau)`; `rating_regularizado = w * rating_actual + (1 - w) * prior_plantilla` (LMX:126-128).
4. Forma, alineaciones, porteros, balón parado, matchup, viajes, altitud/clima (F6-F12): sólo con coeficientes entrenados; escenarios `IN/OUT` sin probabilidades inventadas (LMX:144).
5. Goles esperados (F13):
   `log(lambda_home) = beta0 + beta_home * H + Attack_home + DefWeakness_away + b_context * X_home` (LMX:182)
   `log(lambda_away) = beta0 + Attack_away + DefWeakness_home + b_context * X_away` (LMX:184)
   Fallback: `lambda_home = LeagueGoals_home * OffIndex_home * DefWeakIndex_away` con `OffIndex_i = xGF_adj_i / League_xGF_adj` (LMX:194-200).
6. Distribución (F14): `P(H=h,A=a) = Pois(h;lambda_home) * Pois(a;lambda_away)`, `Pois(k;lambda) = exp(-lambda)*lambda^k / k!` (LMX:208-210); DC con `tau(0,0)=1 - lambda_home*lambda_away*rho_DC`, etc. (LMX:216-220). Malla hasta `masa_residual <= 1e-6` (LMX:224).
7. Mercados (F15-F17): `P_1`, `P_X`, `P_2` (LMX:230-234); BTTS, portería a cero, doble oportunidad (LMX:242-248); totales `P_over`, `P_under`, `P_push` (LMX:256); hándicap `P_cover = P(G_equipo + handicap > G_rival)` (LMX:260); asiáticos de cuarto con 50/50 (LMX:266). Team totals no se producen.
8. Liguilla (F18): separa `P_1X2_leg`, `P_advance_series`, `P_champion` (LMX:274-276). Para Apertura 2026: cuartos y semifinales a ida y vuelta, gana el global y, en empate, "el equipo mejor ubicado en la fase regular"; sin goles de visitante ni ET/penales en esas rondas (LMX:281). Final: ida y vuelta; si empata el global, ET y penales (LMX:282). La vuelta condiciona a la ida real (LMX:284). Sin regla completa o módulo ET/penales: `NO CALCULADO` (LMX:286).
9. Monte Carlo: opcional, registrar semilla y número de simulaciones (LMX:430).

## 6. Auditoría matemática

- [COMPROBADO] Fórmulas Poisson y DC correctas; coherencia entre mercados garantizada por matriz única (LMX:250, :414-418).
- [INFERENCIA] Particularidad deportiva importante: la **Liguilla** con desempate por posición hace que la serie dependa del marcador global y de un criterio no aleatorio. Es la única de la familia con este criterio, y el prompt lo trata bien (LMX:281). El modelo de ida y vuelta debe incluir que el equipo mejor ubicado "gana" un empate global, por lo que `P_advance` no se obtiene de simular tandas (LMX:281). Correcto.
- [INFERENCIA] Altitud: el prompt rechaza un multiplicador fijo y pide efectos incrementales con interacción con la aclimatación (LMX:168, :174, :408). Es matemáticamente prudente; en Liga MX es el factor contextual más plausible (Toluca, Ciudad de México, Pachuca) y es susceptible de confusión con el efecto de localía y la fuerza de club. [RECOMENDACIÓN] Estimar con efecto aleatorio de estadio, no con un coeficiente universal.
- [COMPROBADO] Doble conteo: reglas explícitas sobre localía, forma, ausencias, PSxG vs defensa (LMX:39, :144, :150, :176).
- [INFERENCIA] Riesgo de sobreajuste: 18 clubes y 17 jornadas por torneo ofrecen 153 partidos por torneo; con dos torneos al año, un modelo con covariables de altitud, clima, viaje y matchups está subidentificado. El prompt exige ablaciones (LMX:329).
- [COMPROBADO] Falta de datos: tabla de fallbacks (LMX:341-351) con regla "no asumir 0 impacto demostrado" para altitud (LMX:347).
- [HIPÓTESIS] El formato Apertura 2026 (18 clubes, 17 jornadas, ocho a cuartos sin Play-In) está marcado como vigente a 2026-11-10 (LMX:35) pero cambia con frecuencia; el prompt lo sabe (LMX:34, :448).
- [INFERENCIA] La fecha documental 2026-11-10 coincide con el día de la auditoría: el prompt fue redactado o fechado el mismo día; no hay historial de versiones.

## 7. Independencia del mercado

| Cita | Mención | Clasificación |
|---|---|---|
| LMX:19 | EV si hay cuotas verificadas | COMPARACIÓN POSTERIOR LEGÍTIMA |
| LMX:25 | "El mercado nunca entra en λ" | Principio |
| LMX:36 | No convertir cuotas en probabilidad | Principio |
| LMX:80 | Mercado como nivel 4, solo benchmark/EV | COMPARACIÓN POSTERIOR LEGÍTIMA |
| LMX:70 | `odds_usage: comparison_only_after_freeze` | Congelación |
| LMX:256-266 | Líneas `t`, `handicap` | UMBRAL LEGÍTIMO |
| LMX:294-300 | Snapshot antes de buscar cuotas | Congelación correcta |
| LMX:314 | No-vig vs equilibrio de la cuota | COMPARACIÓN POSTERIOR LEGÍTIMA |

[COMPROBADO] No hay ENTRADA PROHIBIDA y el prompt congela antes de consultar el mercado (LMX:292-296).

## 8. Validación que propone

[COMPROBADO] LMX:329: backtest cronológico fuera de muestra; Brier, log loss, calibración 1X2, log-verosimilitud de marcadores, cobertura de intervalos, error de goles; para Liguilla, log loss/Brier de clasificación por ronda; segmentación por torneo, sede, fase, temporada y disponibilidad de XI; Poisson independiente contra variantes y ablaciones de porteros, altitud, localía y forma. [INFERENCIA] Con ≈153 partidos por torneo, la validación de la Liguilla (8+4+2 series por torneo) es estadísticamente inalcanzable en pocos años: el prompt no lo reconoce. [RECOMENDACIÓN] Declarar la clasificación de Liguilla como no validable y pedir abstención.

## 9. Contraste con la plataforma

- [COMPROBADO] `configs/leagues/soccer.yaml:10` `ligamx: {sport_key: soccer_mexico_ligamx, avg_goals: 2.85}`; ESPN `soccer/mex.1` (`espn_results.py:90`); alias `team_aliases.yaml:63`; sedes (latitud/longitud) en `configs/venues.yaml:130`.
- [COMPROBADO] Sin override en `ratings.yaml`: usa la familia (`registry.py:45-47`): `elo_home_adv 48`, `home_scoring_bonus 0.15`, `tilt_scale 1.0`, `dc_rho 0.0`, `max_score 10`, `elo_k 18`.
- [COMPROBADO] Cadena: Elo → `p_home` → `tilt` → `lam_home = avg*(0.5+tilt)+0.15`, `lam_away = avg*(0.5-tilt)` (`adapters.py:126-143`), con `avg` de las tasas de gol propias (`team_scoring.py:92-101`); Poisson + DC con malla `max_goals 10` (`distributions.py:204-309`).
- Faltan: xG/NPxG, PSxG, XI, altitud estimada, descanso para fútbol, Liguilla (ida/vuelta, criterio de posición), campeón, tabla Apertura/Clausura como torneos separados (la plataforma no los distingue; el Elo es continuo entre torneos).
- Difiere: modelo de goles por Elo + total esperado; `dc_rho` 0 (el prompt exige estimarlo); localía doble ([INFERENCIA]: `elo_home_adv` y `home_scoring_bonus`); masa truncada renormalizada sin reportar (`distributions.py:294-297`); el edge del prompt (`Edge_pp`, EV incondicional) frente al edge de la plataforma condicionado a no-push (`daily.py` comentario sobre `edge`, AUD-011).
- [HIPÓTESIS] La altitud no está modelada, pero `venues.yaml` aporta ubicaciones; no se comprobó si hay término de altitud en `adjust_model_probability`.
- **Mercado en las probabilidades de la plataforma:** [COMPROBADO] `market_shrink: 0.5` (`default.yaml:17`) mezcla el no-vig del consenso en `p_decision` (`probabilities.py:303-306`, `daily.py:969-970`); sin override por liga en `configs/`; el `.env` productivo no es legible desde este agente (valor efectivo NO VERIFICADO). `uncertainty_penalty 0.35` (`default.yaml:26`).

## 10. Veredicto por componente

| Componente | Veredicto | Motivo |
|---|---|---|
| Separación Apertura/Clausura y prior por continuidad | INTEGRAR | La plataforma usa Elo continuo sin ruptura de torneo |
| Modelo log-lineal + Poisson/DC | CONSERVAR | Implementado en lo esencial; estimar `rho` |
| Regla "no multiplicador fijo de altitud" | CONSERVAR | Prudente |
| Efecto de altitud estimado por estadio | INTEGRAR (condicionado) | Requiere datos y validación |
| Liguilla: avance por global y posición | INTEGRAR | Reglas distintas a la mayoría de ligas; hay que verificarlas por torneo |
| Final con ET y penales | OPTIMIZAR | Sin módulo de tandas queda `NO CALCULADO`; correcto |
| Tabla de fallbacks (LMX:339-351) | CONSERVAR | Clara y auditable |
| Dependencia de FotMob | OPTIMIZAR | Cobertura variable; homogeneizar |
| `market_shrink` de la plataforma | CORREGIR | Contradice el principio |
