# Auditoría individual: PROMPT_191_LIGUE_1_v1_0

Fecha: 2026-11-10. Citas `P:n` = líneas de `C:\dev\Prompts\PROMPT_191_LIGUE_1_v1_0.md`.

## 1. Ficha

- **Fichero / versión:** PROMPT_191_LIGUE_1_v1_0.md; «PREGAME PRICING ENGINE», «Versión: 1.0» [COMPROBADO P:1-2].
- **Deporte / competición:** fútbol; Ligue 1 McDonald's (Francia); excluye Ligue 2, Coupe de France, Trophée des Champions y UEFA salvo como carga [P:39].
- **Tamaño:** 357 líneas (el más breve de la familia).
- **Rol:** motor de pricing pregame [P:7].
- **Objetivo:** `lambda_home`/`lambda_away`, distribución conjunta, 1X2, marcadores, BTTS, CS, totales, hándicaps; EV solo con cuotas del mismo período y reglas [P:10-14].
- **Alcance / modos:** estados VALIDADO / EXPLORATORIO / INCOMPLETO [P:34]; log-lineal «calibrado» o fallback exploratorio [P:147-171]; Poisson o Dixon-Coles [P:176-189]; aclara que es «ESPECIFICACIÓN DE EJECUCIÓN» sin coeficientes entrenados [P:4].

## 2. Reglas y restricciones

- **Absolutas (15) [P:22-36]:** no inventar [P:22]; solo información antes de `as_of` [P:23]; **«No uses odds, spreads, consenso, picks, posiciones de apuestas ni predicciones de analistas como variables del motor»** [P:24]; xG ≠ goles, medias calibradas a goles reales [P:25]; no mezclar proveedores [P:26]; sin doble conteo [P:27]; no reusar parámetros de otras ligas [P:28]; solo tiempo reglamentario [P:29]; liquidación distinta para 1X2/DNB/DC/europeo/asiático/Totals [P:30]; no simular mentalmente Monte Carlo [P:32]; sin cuotas no hay EV/CLV [P:33]; abstención [P:35].
- **Ambigüedad:** [P:19] «El mercado se consulta únicamente después de congelar… nunca para inducirlas, calibrarlas durante la ejecución ni corregirlas ad hoc». [INFERENCIA] «calibrarlas durante la ejecución» deja abierta una calibración **fuera** de la ejecución (por ejemplo, entrenamiento de un calibrador contra precios) que el principio del operador prohíbe. [RECOMENDACIÓN] Sustituir por «ni calibrarlas, ni entrenarlas, ni seleccionarlas con el mercado en ningún momento».
- **«Validado» [P:245]:** pruebas cronológicas fuera de muestra, Brier multiclase, Log Loss, calibración, log score de marcadores, MAE/RMSE, cobertura de intervalos, robustez por mes, localía, favoritos/underdogs y ascendidos; ablaciones; «No usar porcentaje de aciertos solo como criterio». Sin umbral cuantitativo.
- **Mínimo viable [P:60-66]:** fixture, ataque y defensa de ambos, baseline de liga, método de cálculo; si falla, `INCOMPLETO`.
- **Controles:** 35 [P:300-334].

## 3. Variables y parámetros

| Nombre | Valor | Unidad | Línea | Justificación |
|---|---|---|---|---|
| Tolerancia de masa fuera de la malla | `1e-6` | masa | P:48, 189, 313 | Declarada, sin justificar |
| `mu_H_league`, `mu_A_league` | no fijados | goles | P:43 | «observables antes de as_of», «Liga + prior temporal» |
| `tau_shrink`, `beta`, `rho_DC`, pesos, HFA | «NO hay valores universales autorizados» | – | P:46 | Se estiman con trazabilidad |
| Equipos / jornadas 2026/27 | 18 / 34 | – | P:75 | Formato; «verificar estructura» |
| Ascendidos 2026/27 | ESTAC Troyes y Le Mans FC («incluyen») | clubes | P:75 | Sin fuente específica en las referencias [P:347-352] |
| Ajuste manual prohibido | ±2–5 % | % | P:134 | Ejemplo a evitar |
| Husos | `Europe/Paris`, UTC para `as_of` | – | P:41 | Convención |

[HIPÓTESIS] Los ascendidos no se verificaron; la frase «incluyen» sugiere una lista incompleta. Las referencias del prompt no incluyen la fuente de los ascendidos [COMPROBADO P:347-352].

## 4. Fuentes de datos

Jerarquía [P:52-58]: LFP / Ligue1.com / clubes; Opta/Stats Perform, Understat, Wyscout, «un único proveedor principal por familia de métricas»; FBref; meteorología; cuotas solo en fase de mercado. Cada fuente con URL, timestamp, unidad y rango de fechas [P:58]. Conflictos: competición manda para estructura; para métricas, homogeneidad del proveedor [P:58]. Sin periodicidad ni antigüedad máxima [INFERENCIA]. Citas: LFP calendario 2026/27, Ligue1.com, decisiones disciplinarias LFP [P:347-349].

## 5. Cadena predictiva

1. Identificación y exclusión [P:72-77].
2. Ataque/defensa por xG y ajuste de fuerza rival con modelo jerárquico Poisson/log-lineal [P:79-100].
3. Shrinkage: `w = n_eff / (n_eff + tau)`, `Rating_reg = w*Rating_observado + (1-w)*Rating_prior` [P:105-107]; ascendidos desde Ligue 2 con prior de transición [P:109].
4. Forma con decaimiento aprendido, XI, portero, balón parado, matchup, descanso, localía [P:111-144].
5. λ [P:149-155]:
   `log(lambda_home) = beta0 + beta_H + Attack_home + DefensiveWeakness_away + beta_context*X_context_home`
   `log(lambda_away) = beta0 + Attack_away + DefensiveWeakness_home + beta_context*X_context_away`
   Fallback: `lambda_home = mu_H_league * OffIndex_home * DefWeakIndex_away`; `lambda_away = mu_A_league * OffIndex_away * DefWeakIndex_home` [P:167-169], con la salvedad de que los índices deben ser «sin localía ya incorporada» [P:171].
6. Distribución: `P(H=h,A=a) = Pois(h;lambda_home) * Pois(a;lambda_away)` [P:178]; DC con `x=H`, `y=A`, `L=lambda_home`, `M=lambda_away`: (0,0) `1 - L*M*rho_DC`, (0,1) `1 + L*rho_DC`, (1,0) `1 + M*rho_DC`, (1,1) `1 - rho_DC` [P:180-185]; masa omitida ≤ 1e-6 [P:189].
7. Derivados [P:191-220]: `P_local = sum_{h>a} P(h,a)`, `P_empate`, `P_visitante`; `P_BTTS_Si = sum_{h>=1,a>=1} P(h,a)`; `P_CS_home = P(A=0)`, `P_CS_away = P(H=0)`; totales con push y cuartos 50/50; hándicap `P_win = P(D+h>0)`, `P_push`, `P_loss`; DNB «(AH0)»; team totals «derivar la distribución marginal» [P:203].
8. Congelación y mercado [P:222-235].

Empate: resultado propio. Monte Carlo: opcional con semilla y error MC [P:189].

## 6. Auditoría matemática

- [COMPROBADO] τ de Dixon-Coles correcto con la notación L, M [P:180-185]; [INFERENCIA] masa conservada en soporte completo; exige `tau>=0` y no importar rho de otras ligas [P:187].
- [COMPROBADO] `rho_DC` «no es el coeficiente de correlación de Pearson» [P:187]: aclaración correcta.
- [COMPROBADO] «No calcular BTTS como producto de probabilidades marginales si el modelo final contiene dependencia» [P:205]: correcto.
- Caso sin push: `EV=P_win*D - 1` [P:231]; con push `EV = P_win*(D-1) - P_loss`, `p_break_even=(1-P_push)/D`, `Edge_precio_pp = 100*(P_win-p_break_even)` [P:228-230]: correctos. Para asiáticos, retorno por marcador [P:233].
- `DefensiveWeakness` (nombre) vs `WeakDefense` / `DefWeakness` de otros prompts: terminología no unificada.
- [COMPROBADO] «Asegurar que la predicción es en **goles finales**, no meramente en xG» [P:159].
- [COMPROBADO] Al fallback se le exige que los índices no incorporen localía [P:171], mientras `mu_H_league`/`mu_A_league` ya la contienen: coherente si se cumple; [INFERENCIA] la frase «sin localía ya incorporada» es difícil de operacionalizar (¿se desagrega xG por sede?).
- Es el único prompt que tiene en los controles «Comprobar unidades de probabilidad (0–1 frente a 0–100%)» [P:334]: útil.
- Tolerancia 1e-6, como Serie A/UCL.
- Fuga temporal: `as_of` [P:23], «Versiones y snapshots inmutables antes de consultar cuotas» [P:326]. No pide conservar la versión pregame del xG revisado (LaLiga sí) [INFERENCIA].
- Faltantes: salida parcial `INCOMPLETO` [P:66, 338]; fallback con menor calidad [P:340]. Incertidumbre: `Uncertainty` «estimación e intervalo disponibles o NO CUANTIFICADA»; error MC distinto [P:324].

## 7. Independencia del mercado

| Cita | Mención | Clasificación |
|---|---|---|
| P:7, 19 | Estimaciones independientes del mercado; cuotas solo tras congelar | Regla (con ambigüedad «calibrarlas durante la ejecución») |
| P:24 | Prohíbe odds, spreads, consenso, picks, analistas como variables | Regla |
| P:55 | Cuotas «EXCLUSIVAMENTE en la fase de mercado» | COMPARACIÓN POSTERIOR LEGÍTIMA |
| P:13, 222-235 | EV y edge tras congelar; de-vig documentado; CLV tras cierre | COMPARACIÓN POSTERIOR LEGÍTIMA |
| P:207-220 | Líneas `t` y hándicap `h` | UMBRAL LEGÍTIMO |
| P:235 | «El mercado sigue sin intervenir en el cálculo deportivo» | Regla |
| P:324 | Probabilidad de mercado con/sin vig diferenciada | COMPARACIÓN POSTERIOR LEGÍTIMA |

[COMPROBADO] Sin ENTRADA PROHIBIDA. Congela antes de consultar [P:223]. Matiz en P:19 (ver §2).

## 8. Validación que propone

Pruebas cronológicas fuera de muestra, Brier multiclase 1X2, Log Loss, curvas, log score de marcadores, MAE/RMSE, cobertura de intervalos, robustez por mes, localía, favoritos/underdogs y ascendidos; ablaciones «base xG, +porteros, +onces, +fatiga, +matchup» frente a baseline simple; tamaño de muestra e intervalos [P:245]. [INFERENCIA] No incluye validación de precio (ROI/CLV) a diferencia de otros; sí RPS no mencionado (EPL sí). Falta umbral.

## 9. Contraste con la plataforma

- **Implementado:** `poisson_match_probs` con DC, malla, push y cuartos (`src/sqp/models/distributions.py:204`); tres vías (`src/sqp/sports/adapters.py:314-316`).
- **Valores de producción Ligue 1:** `avg_goals 2.84` [`configs/leagues/soccer.yaml:8`]; **sin** entrada en `ratings.yaml` (solo bundesliga, epl y seriea fijan `dc_rho`: l.11, 14, 52), luego hereda `dc_rho 0.0`, `elo_home_adv 48`, `tilt_scale 1.0`, `max_score 10`, `home_scoring_bonus 0.15`, `elo_k 18` [`registry.py:45-47`].
- **Difiere:**
  1. Ligue 1 usa **Poisson independiente** (sin DC). [INFERENCIA] Compatible con P:187 («rho… con datos Ligue 1», no importar) mientras no se estime; esperaríamos que se estime con `tune_ratings.py`.
  2. Sin xG, once, portero, matchup, ascendidos (Elo + goles; `adapters.py:127-144`).
  3. Localía: `elo_home_adv 48` más `home_scoring_bonus 0.15` en λ_local; P:142 exige un solo HFA [INFERENCIA/HIPÓTESIS]. En Ligue 1 el Elo de local es el default (48), mayor que los 15 de EPL/Bundesliga/Serie A: ahí el posible doble conteo es mayor.
  4. Malla truncada a 10 y renormalizada (`distributions.py:294`); P:189 pide masa omitida visible.
  5. `avg_goals` fijo.
  6. Probabilidad de decisión condicional a no-push.
- **Mercado en las probabilidades:** el adaptador no usa cuotas; `market_shrink 0.5` mezcla el no-vig en `p_used` [`configs/default.yaml:17`; `probabilities.py:303-304`; `daily.py:969-970`]; `.env` no verificable. Calibradores pre-blend (`probabilities.py:285-296`).

## 10. Veredicto por componente

| Componente | Veredicto | Motivo |
|---|---|---|
| Independencia (P:24, 55, 235) | CONSERVAR | Limpia |
| «calibrarlas durante la ejecución» (P:19) | CORREGIR | Deja abierta calibración contra mercado fuera de ejecución |
| Ascendidos (P:75) | CORREGIR | Lista parcial («incluyen») sin fuente |
| Control de unidades 0-1 / 0-100 (P:334) | CONSERVAR y propagar | Útil |
| Terminología `DefensiveWeakness` | OPTIMIZAR | Unificar |
| Falta validación de precio | OPTIMIZAR | Añadir criterio posterior |
| DC en la plataforma | INTEGRAR | Estimar `dc_rho` para Ligue 1 |
| xG, once, portero | INTEGRAR (parcial) | Sin proveedor |
