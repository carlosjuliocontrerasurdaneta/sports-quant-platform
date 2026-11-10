# Auditoría de PROMPT_191_BRASILEIRAO_v1_0.md

Fecha: 2026-11-10. Citas `BRA:n` = líneas de `C:\dev\Prompts\PROMPT_191_BRASILEIRAO_v1_0.md`.

## 1. Ficha

| Campo | Valor |
|---|---|
| Fichero | `PROMPT_191_BRASILEIRAO_v1_0.md` |
| Versión | "v1.0"; control de versión por `data_as_of` y versión de modelo (BRA:7) |
| Deporte / competición | Fútbol masculino; Campeonato Brasileiro Série A (BRA:3) |
| Tamaño | 431 líneas, 21 fases, 45 controles (BRA:370-414), 17 reglas absolutas (BRA:21-37), tabla de fallbacks (BRA:356-366) |
| Rol | Motor cuantitativo pregame (BRA:11) |
| Objetivo | 1X2, doble oportunidad, DNB, hándicap asiático/europeo, totales asiáticos, BTTS, portería a cero, marcador correcto (BRA:5); sin prórroga ni penales (BRA:6, :29) |
| Modos | `MODEL_STATUS` VALIDADO / EXPLORATORIO / INCOMPLETO (BRA:275); estado inicial EXPLORATORIO (BRA:4) |

Es el único prompt de la familia sin fase eliminatoria: Série A es un todos contra todos, así que la sección de playoffs no existe.

## 2. Reglas y restricciones

- [COMPROBADO] Regla absoluta de independencia (BRA:17, :28): "No utilizar cuotas, mercado, picks, consenso, narrativas ni movimientos de línea para definir lambdas o probabilidades"; además, "No utilizar rankings derivados de apuestas como proxies de calidad" (BRA:17).
- [COMPROBADO] No mezclar Série A con Série B, Estaduais, Copa do Brasil, Libertadores, etc., sin conversión calibrada (BRA:24, :41). Un partido de otra competición solo informa minutos y rotación (BRA:148).
- [COMPROBADO] "Nunca obligar a emitir una recomendación; SIN APUESTA / INCOMPLETO es una salida válida" (BRA:37).
- Reglas de excepción: fallbacks predefinidos (tabla BRA:356-366); parámetros sin entrenar: "Ninguno → probabilidades NO CALCULADAS" (BRA:364).
- Condiciones de VALIDADO (BRA:279-288): rolling-origin con purga; Brier multicategoría y log loss; calibración por bins; log-verosimilitud de marcadores; segmentación por favorito, sede, temprano/tarde de temporada, ascendidos, viajes, receso y congestión; ablaciones; baselines simples; EV/ROI/CLV solo con precios observables.

## 3. Variables y parámetros

| Nombre | Valor | Unidad | Fase/línea | Justificación |
|---|---|---|---|---|
| Clubes / jornadas 2026 | 20 / 38 | | F1 :45 | Reglamento CBF (enlace BRA:418) |
| Ascendidos 2026 | Coritiba, Athletico-PR, Chapecoense, Remo | clubes | F6 :95 | CBF; [HIPÓTESIS] sin verificar aquí |
| `w = n_eff/(n_eff+tau)` | tau estimado | | F6 :88-92 | "tau NO es una constante universal" |
| `beta_0`, `beta_home`, `A_i(t)`, `Dweak_i(t)`, `gamma`, `delta` | estimados | log-goles | F15 :164-166 | Poisson log-lineal con efectos dinámicos |
| `rho` DC | estimado | | F16 :198-206 | |
| Masa omitida | `<= 1e-6` | probabilidad | F16 :208 | Tolerancia |
| Ventanas de forma (5/10) | no fijas | | F7 :102 | "no fijar 5/10 partidos o pesos ad hoc" |
| Efecto `-0.15 xG` por baja | prohibido | | F8 :111 | Ejemplo de lo que no se debe hacer |
| Stake asiático | 50/50 | | F18 :238 | |

[COMPROBADO] Ningún coeficiente deportivo propio.

## 4. Fuentes de datos

[COMPROBADO] BRA:49-54: A) CBF; B) clubes y partes médicos; C) proveedores de eventos/xG con derechos verificables; D) alineaciones, lesiones y clima de proveedores independientes "triangulados cuando sea posible". Cada métrica con `provider`, `definition`, `unit`, `period`, `n`, `fetched_at`, `published_at` (BRA:56). "Nunca inferir que una métrica avanzada está disponible por el mero hecho de que una web muestre resultados" (BRA:58). La aclaración final dice que el motor "está descrito, no entrenado" (BRA:425). [INFERENCIA] Cobertura de xG de Série A: razonable desde ~2018 en proveedores comerciales, pero variable en proveedores gratuitos.

## 5. Cadena predictiva

1. Ofensiva y defensa (F3-F4) con `xGF/90`, `NPxGF/90`, `xGA/90`, etc., ajustadas por rival y estado del partido (BRA:63-75).
2. Ajuste por oposición (F5): ratings latentes jerárquicos con efectos temporales, liga, sede y competición; restricciones de identificación (BRA:80).
3. Prior y ascendidos (F6): `w = n_eff / (n_eff + tau)`; `rating_reg = w * rating_observado + (1-w) * rating_prior` (BRA:88-90); prior de transición Série B → A con histórico de ascendidos (BRA:94).
4. Forma, alineaciones, porteros, balón parado, matchup, viaje/clima, congestión, localía (F7-F14): sólo coeficientes estimados (BRA:102, :111, :142). Contexto especial 2026: pausa del Mundial (BRA:96, :150).
5. Goles esperados (F15):
   `log(lambda_H) = beta_0 + beta_home + A_H(t) + Dweak_A(t) + gamma' * X_HA(t)` (BRA:164)
   `log(lambda_A) = beta_0 + A_A(t) + Dweak_H(t) + delta' * X_AH(t)` (BRA:166)
   "Entrenar contra goles observados"; xG como predictor, no como target (BRA:172).
   Fallback: `lambda_H = LeagueGoals_H * OffIndex_H * DefWeakIndex_A` (BRA:180).
6. Distribución (F16): `P(H=h, A=a) = Pois(h | lambda_H) * Pois(a | lambda_A)` (BRA:190); DC con `tau(0,0) = 1 - lambda_H * lambda_A * rho`, etc. (BRA:200-203), `tau >= 0` (BRA:206), masa omitida `<= 1e-6` (BRA:208).
7. Mercados (F17-F18): `P_1 = sum_{h>a} p(h,a)`, `P_X`, `P_2` (BRA:216-218); doble oportunidad, DNB (BRA:222-223); BTTS, portería a cero, totales (BRA:228-232); hándicap `P_win=P(H+h>A)` (BRA:236); asiáticos de cuarto con mitades y beneficio neto por marcador (BRA:238-239).
8. Prórroga/penales: no aplica (BRA:29, :127). Team totals: no se producen. Monte Carlo: solo mencionado como "intervalos por simulaciones que no se ejecutaron" (BRA:209).

## 6. Auditoría matemática

- [COMPROBADO] El modelo es el más completo de los cinco en la especificación de la dinámica: efectos `A_i(t)`, `Dweak_i(t)` variables en el tiempo (BRA:164-166). [INFERENCIA] Es la parametrización estándar de Dixon-Coles con pesos temporales (1997), con la ventaja de no fijar la ventana (BRA:102).
- [COMPROBADO] Coherencia interna y push: 45 controles (BRA:397-404); DNB desde la misma matriz (BRA:223, :403); cuartos asiáticos con retorno por marcador (BRA:239, :266).
- [COMPROBADO] Definición de edge: `Edge_precio_pp = 100 * (P_win - (1-P_push)/D)` "no distancia al 50 %" (BRA:262-264, :408).
- [INFERENCIA] Ascendidos: el prior de transición Série B → A (BRA:94) es correcto en principio, pero con 4 ascendidos por año y ~5 temporadas útiles la estimación del prior tiene ~20 observaciones; la incertidumbre debe ser amplia (el prompt la exige en BRA:97).
- [INFERENCIA] El receso del Mundial 2026 rompe la continuidad de `A_i(t)`; el prompt reconoce "quiebre estructural" (BRA:105) sin dar un procedimiento (por ejemplo, aumentar la varianza del proceso de ratings tras la pausa).
- [INFERENCIA] Brasil tiene viajes largos y mucha diversidad climática (BRA:141); un efecto de desplazamiento puede confundirse con la localía y con la fuerza del club (equipos del norte/nordeste). Se pide no duplicar costo de viaje y HFA (BRA:143), pero no se propone efecto aleatorio por par origen-destino.
- [INFERENCIA] Brasileirão tiene menos goles por partido (2,40 en `soccer.yaml:12`) y una tasa de empate mayor; DC con `rho` negativo es especialmente relevante aquí.
- Datos faltantes: fallbacks explícitos y abstención (BRA:358-366).

## 7. Independencia del mercado

| Cita | Mención | Clasificación |
|---|---|---|
| BRA:11 | "Solo al final comparas esas probabilidades con cuotas" | COMPARACIÓN POSTERIOR LEGÍTIMA |
| BRA:17 | Prohibición de mercado como input y de rankings de apuestas | Principio |
| BRA:28 | No usar cuotas, consenso, picks ni movimientos de línea | Principio |
| BRA:232-238 | Líneas `t`, `h` | UMBRAL LEGÍTIMO |
| BRA:243-252 | Congelación; nueva versión si hay dato deportivo nuevo | Congelación correcta |
| BRA:254-268 | EV, edge, CLV | COMPARACIÓN POSTERIOR LEGÍTIMA |
| BRA:288, :291 | ROI/CLV históricos, ranking con cuotas | COMPARACIÓN POSTERIOR LEGÍTIMA |
| BRA:411 | Control 42: "Ausencia de fuga temporal en features, mercado y lesiones" | Control |

[COMPROBADO] Sin ENTRADA PROHIBIDA. Es el prompt de la familia que enuncia más explícitamente "entrenar, calibrar, corregir o seleccionar" (BRA:17), cubriendo también la calibración y la selección de variables, tal como pide el operador.

## 8. Validación que propone

[COMPROBADO] BRA:279-288 (ver sección 2). [INFERENCIA] Brasileirão aporta 380 partidos por temporada, la mayor muestra de la familia para una liga de 20 clubes, así que la validación temporal es viable. [RECOMENDACIÓN] Añadir un criterio numérico de aceptación (mejora de log loss con IC contra Poisson simple) y definir la ventana mínima de entrenamiento previa al receso 2026.

## 9. Contraste con la plataforma

- [COMPROBADO] `configs/leagues/soccer.yaml:12` `brasileirao: {sport_key: soccer_brazil_campeonato, avg_goals: 2.40}`; ESPN `soccer/bra.1` (`espn_results.py:92`); alias `team_aliases.yaml:38`; sedes `venues.yaml:194`.
- [COMPROBADO] Sin entrada en `ratings.yaml`: valores de familia (`registry.py:45-47`): `elo_home_adv 48`, `home_scoring_bonus 0.15`, `tilt_scale 1.0`, `dc_rho 0.0`, `max_score 10`.
- Implementado: Poisson + DC con `tau` idéntico (`distributions.py:71-83`), mercados 1X2/hándicap/total desde una malla única, líneas asiáticas de cuarto (`distributions.py:253-293`), `three_way` (`adapters.py:314-316`).
- Faltan: ratings dinámicos jerárquicos con xG; porteros; alineaciones; viaje/clima/altitud; prior de ascendidos; tratamiento del receso del Mundial; enlace de competiciones paralelas (Libertadores, Copa do Brasil) para congestión.
- Difiere: lambdas de la plataforma vienen de Elo (K=18) + tasas de gol globales sin separar local/visitante + `tilt` (`adapters.py:126-143`, `team_scoring.py:92-101`); no hay `beta_home` estimado sino `elo_home_adv 48` más `home_scoring_bonus 0.15` ([INFERENCIA]: doble canal de localía, contra BRA:158); `dc_rho 0.0` (el prompt pide estimar `rho`); masa truncada renormalizada sin reporte (`distributions.py:294-297`).
- **Mercado en las probabilidades de la plataforma:** [COMPROBADO] `market_shrink: 0.5` (`default.yaml:17`; `probabilities.py:303-306`; `daily.py:969-970`) mezcla el no-vig en la probabilidad de decisión; valor del `.env` NO VERIFICADO (acceso denegado). `uncertainty_penalty 0.35` (`default.yaml:26`). El prompt lo prohíbe expresamente (BRA:17, :28).

## 10. Veredicto por componente

| Componente | Veredicto | Motivo |
|---|---|---|
| Prohibición del mercado en entrenamiento/calibración/selección (BRA:17) | CONSERVAR | Formulación más completa de la familia |
| Ratings dinámicos jerárquicos `A_i(t)`, `Dweak_i(t)` | INTEGRAR | La plataforma usa Elo; probar OOS |
| Prior Série B → A | INTEGRAR | Falta en plataforma |
| Quiebre por receso del Mundial 2026 | OPTIMIZAR | Se detecta pero no se especifica el método |
| Efectos de viaje y clima | OPTIMIZAR | Riesgo de confusión con localía; usar efectos aleatorios |
| DC y mercados derivados | CONSERVAR | Ya implementados |
| Tolerancia 1e-6 | CONSERVAR | Frente a la renormalización silenciosa de la plataforma |
| `market_shrink` de la plataforma | CORREGIR | Contradice BRA:17 y BRA:28 |
