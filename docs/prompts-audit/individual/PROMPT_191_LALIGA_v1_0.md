# Auditoría individual: PROMPT_191_LALIGA_v1_0

Fecha: 2026-11-10. Citas `P:n` = líneas de `C:\dev\Prompts\PROMPT_191_LALIGA_v1_0.md`.

## 1. Ficha

- **Fichero / versión:** PROMPT_191_LALIGA_v1_0.md, «Versión: 1.0» [COMPROBADO P:3].
- **Deporte / competición:** fútbol; LALIGA EA SPORTS (Primera División masculina); excluye Hypermotion, Copa del Rey, Supercopa, UEFA [P:43].
- **Tamaño:** 554 líneas.
- **Rol:** «motor de análisis cuantitativo prepartido» [P:11].
- **Objetivo:** λ, 1X2, marcadores, BTTS, CS, Over/Under, hándicap europeo/asiático, doble oportunidad, DNB; EV y edge solo con cuota [P:13-18].
- **Alcance / modos:** estados VALIDADO/EXPLORATORIO/INCOMPLETO [P:336]; log-lineal «preferente» o baseline exploratorio [P:216-238]; Poisson o Dixon-Coles [P:244-262]; salida parcial «Modelo INCOMPLETO» [P:52].

## 2. Reglas y restricciones

- **Absolutas (15) [P:41-55]:** prohibido inventar [P:41]; corte `as_of` [P:42]; 90' + añadido sin prórroga [P:43]; ranking/Elo no es probabilidad [P:44]; xG homogéneo [P:45]; no duplicar efectos [P:46]; parámetros sin evidencia = HIPÓTESIS EXPLORATORIAS [P:47]; 1X2 incluye empate [P:50]; cuartos con media ganancia [P:51]; huso `Europe/Madrid` [P:54]; exclusión de partidos iniciados [P:55].
- **Excepciones [P:453-464]:** sin xG → modelo alternativo validado o predicción incompleta sin porcentajes [P:457]; sin DC válido → Poisson [P:460].
- **«Validado» [P:517-529]:** walk-forward por jornadas y temporadas, log loss y Brier multiclase, calibración, log-verosimilitud de marcador, ablaciones, bootstrap con dependencia temporal. Sin umbrales numéricos [INFERENCIA].
- **Pruebas:** dice «MÍNIMO 35» [P:468] y enumera 42 [P:470-511]. [COMPROBADO] Desajuste de recuento.

## 3. Variables y parámetros

| Nombre | Valor | Unidad | Línea | Justificación |
|---|---|---|---|---|
| `L_H`, `L_A`, `L_xGF`, `L_xGA` | no fijados | goles, xG/90 | P:63-64 | Liga y temporada hasta `as_of` |
| `A_i`, `D_i` | estimados | log | P:65 | Modelo entrenado |
| `HFA` | estimado | log | P:66 | «no duplicar intercepto local» |
| `tau_metric`, `xi`, `rho_DC` | estimados | – | P:67-69 | `rho_DC` por máxima verosimilitud, «jamás fijar arbitrariamente» |
| `tail_tol` | «p.ej. 1e-5» | masa | P:72 | Ejemplo, sin justificar |
| `G_max`, `MC_N` | adaptativos | – | P:71, 73 | Convergencia |
| Localía «1.02» | prohibida | factor | P:76 | Resto de una versión anterior |
| Equipos / jornadas | 20 / 38 | – | P:101 | Formato |
| Ascendidos 2026/27 | Racing de Santander, Deportivo de La Coruña, Málaga | clubes | P:151 | Cita a laliga.com [P:536] |

[COMPROBADO] No hay coeficientes entrenados en el texto. [COMPROBADO] Rastro vestigial: «ni 1.02 de localía» [P:76] alude a una constante de una versión previa. [HIPÓTESIS] Los tres ascendidos no se pudieron verificar contra la fuente (la URL P:536 habla de «siete clubes ascendidos», lo que no coincide a simple vista con una lista de tres; no consultada).

## 4. Fuentes de datos

Jerarquía [P:82-87]: LaLiga.com; clubes y Comité de Disciplina; Opta/The Analyst/Understat para xG; FBref; AEMET para clima; operadores de cuotas después del congelado. Registro por campo con `publicado_en`, `consultado_en`, `as_of` [P:89]. Frescura: «Nunca usar retrospectivamente datos corregidos después del partido sin preservar la versión pregame» [P:91] (mejor que el resto de la familia). [INFERENCIA] No define antigüedad máxima.

## 5. Cadena predictiva

1. Filtro de partido [P:97-105].
2. Ataque/defensa xG, NPxG, penales, balón parado con regla anti-doble-conteo [P:107-128].
3. Ajuste por rival con identificabilidad (sumas centradas a cero) [P:130-137].
4. Regularización: `w = n_eff / (n_eff + tau_metric)`, `Rating_shrunk = w*Rating_observado + (1-w)*Prior_equipo` [P:143-146]; traducción Segunda → Primera aprendida [P:150].
5. Forma con `weight_t ∝ exp(-xi * días)` [P:160]; once, portero, matchup, calendario, clima como ajustes con coeficientes históricos o 0 [P:165-212].
6. λ [P:218-223]:
   `log(λ_home) = β0 + β_HFA + Attack_home + DefenseWeakness_away + X_home·γ`
   `log(λ_away) = β0 + Attack_away + DefenseWeakness_home + X_away·γ`
   Baseline: `λ_home = LeagueGoals_home * OffIndex_home * DefWeakIndex_away`, `λ_away = LeagueGoals_away * OffIndex_away * DefWeakIndex_home` [P:234-235].
7. Distribución [P:247-260]: Poisson independiente; DC con τ(0,0)=1−λhλaρ, τ(0,1)=1+λhρ, τ(1,0)=1+λaρ, τ(1,1)=1−ρ.
8. Derivados desde la misma `Pmat`: 1X2, BTTS, CS, totales, hándicap, DNB, doble oportunidad, y combinados BTTS+resultado por intersección sobre `Pmat`, «nunca multiplicar» [P:295].
9. Congelación (`Pmat` incluida) y solo después mercado [P:344-348].

Empate: el empate es resultado propio. No hay Monte Carlo base; `MC_N` solo si se simula. Mercados: 1X2, hándicaps, totales, BTTS, CS, DNB, doble oportunidad; no team totals.

## 6. Auditoría matemática

- [COMPROBADO] τ idéntico a Dixon-Coles 1997; [INFERENCIA] conserva la masa exactamente; exige τ ≥ 0 y Poisson si no [P:262].
- [COMPROBADO] `log(λ_home)` lleva `β_HFA` pero `log(λ_away)` no [P:219-220]; consistente con «una sola vez» [P:134 y P:208]. En el baseline multiplicativo `LeagueGoals_home/away` ya contiene la localía [P:234]; el prompt no lo repite como advertencia (Bundesliga sí, P:228 de ese prompt). [INFERENCIA] Riesgo de que quien implemente sume `HFA` a un baseline que ya lo trae.
- [COMPROBADO] El prompt reconoce que «xG observado no equivale automáticamente a media futura de goles» y exige calibración [P:227].
- Push: `Under=1−Over` solo en x.5; en x.0 se calcula el push [P:307]. Correcto. Cuarto asiático por mitad [P:309].
- EV: `EV_por_unidad = P_win*(D-1) - P_loss`, `P_equilibrio=(1-P_push)/D` [P:359-361]: correctos. `EDGE_de_modelo=|P-0.50|` NO es edge [P:365]: correcto.
- Contradicción interna menor: «Considerar movimientos de mercado de fichajes y cambios de entrenador como información deportiva, no cuotas» [P:152]; [INFERENCIA] se refiere al mercado de fichajes (traspasos), no al de apuestas, pero el término «mercado» en un prompt cuya regla central es la independencia del mercado de cuotas invita a confusión. [RECOMENDACIÓN] Sustituir por «ventana de traspasos».
- Tolerancia de cola `tail_tol` 1e-5 ejemplo [P:72] frente a 1e-4 (EPL) y 1e-6 (Serie A/Ligue 1/UCL).
- Fuga: protegida (as-of, versión pregame de datos [P:91], ablaciones). Faltantes: salida parcial y fallbacks con incertidumbre ampliada [P:76, 210].

## 7. Independencia del mercado

| Cita | Mención | Clasificación |
|---|---|---|
| P:5, 35 | «Las cuotas, consensos, cuotas de apertura/cierre, líneas históricas o predicciones de terceros NUNCA son entradas» | Regla (la más completa de la familia) |
| P:17 y P:350-367 | EV, edge, CLV tras congelar | COMPARACIÓN POSTERIOR LEGÍTIMA |
| P:87 | Cuotas «solo después» | COMPARACIÓN POSTERIOR LEGÍTIMA |
| P:152 | «movimientos de mercado de fichajes» | No es cuota; ambiguo (ver §6) |
| P:300-309, 313-329 | Línea `t` y hándicap `h` | UMBRAL LEGÍTIMO |
| P:348 | «nunca ajustar probabilidades para parecerse a las cuotas» | Regla |
| P:355 | Devig para «consenso justo» | COMPARACIÓN POSTERIOR LEGÍTIMA |
| P:526 | Mercado «exclusivamente como benchmark ex post», «no integrar odds en el modelo» | COMPARACIÓN POSTERIOR LEGÍTIMA |

[COMPROBADO] Ninguna ENTRADA PROHIBIDA. Congela antes de consultar [P:344-348].

## 8. Validación que propone

Walk-forward por jornadas y temporadas con snapshots pregame reales; baselines (goles Poisson, xG Poisson, log-lineal regularizado, DC, bivariante, portero, alineaciones, descanso, ascendidos); log loss/Brier multiclase; calibración por rango y clase; log-verosimilitud de marcador; calibración específica de BTTS/Over/Under entrenada «sin fugas»; ablaciones; bootstrap con dependencia temporal; sensibilidad a once y a proveedor xG; tolerancia a ascensos, entrenadores y fichajes [P:517-527]. Mejor cobertura de la familia en sensibilidad, pero sin umbral de aceptación [INFERENCIA].

## 9. Contraste con la plataforma

- **Implementado:** `poisson_match_probs` con DC y malla (`src/sqp/models/distributions.py:204`), `SoccerAdapter` de tres vías (`src/sqp/sports/adapters.py:314-316`), cuartos asiáticos y push.
- **Valores de producción LaLiga:** `avg_goals 2.65` [`configs/leagues/soccer.yaml:5`]; sin entrada en `ratings.yaml`, luego hereda el default de familia `soccer`: `dc_rho 0.0`, `elo_home_adv 48`, `tilt_scale 1.0`, `max_score 10`, `home_scoring_bonus 0.15`, `elo_k 18` [`src/sqp/sports/registry.py:45-47`]. [COMPROBADO] `ratings.yaml` solo fija `dc_rho` para bundesliga (l.11), epl (l.14) y seriea (l.52).
- **Difiere:**
  1. LaLiga usa Poisson **independiente** (`dc_rho 0`) mientras el prompt considera DC con ρ estimado; [INFERENCIA] el prompt lo permite si no hay ρ validado [P:262, 460].
  2. Sin xG/NPxG/portero/once/clima/ascendidos (ver `adapters.py:127-144`: Elo + `TeamScoringRates` aditivo).
  3. `elo_home_adv 48` (default) + `home_scoring_bonus 0.15` en λ_local: posible doble localía frente a P:134 y P:208 [INFERENCIA/HIPÓTESIS].
  4. `avg_goals` fijo 2.65 como respaldo (P:76 prohíbe promedios permanentes); solo cold start (`team_scoring.py:95-97`).
  5. Renormalización silenciosa de la malla truncada a 10 goles (`distributions.py:294`); P:264 lo prohíbe sin residuo declarado.
  6. Combinados BTTS+resultado: no encontrados en la plataforma.
- **Mercado en las probabilidades de LaLiga:** el modelo (`estimate`) no usa cuotas; la probabilidad de decisión sí mezcla `market_shrink 0.5` [`configs/default.yaml:17`; `src/sqp/pipeline/probabilities.py:303-304`; `daily.py:969-970`], igual que para todas las ligas. Valor en `.env` de producción: no verificable (acceso denegado). Calibradores sobre `adjusted_probability` pre-blend (`probabilities.py:285-296`), no contra mercado.

## 10. Veredicto por componente

| Componente | Veredicto | Motivo |
|---|---|---|
| Regla de independencia del mercado | CONSERVAR | La más clara |
| Preservar versión pregame de datos (P:91) | CONSERVAR y propagar | Falta en los demás |
| «mercado de fichajes» (P:152) | CORREGIR | Ambigüedad terminológica |
| Referencia «1.02 de localía» (P:76) | CORREGIR | Vestigio |
| «MÍNIMO 35» con 42 pruebas | CORREGIR | Inconsistencia |
| `tail_tol` 1e-5 | OPTIMIZAR | Unificar con la familia |
| Combinados BTTS+resultado sobre `Pmat` | INTEGRAR | La plataforma no los ofrece |
| Dixon-Coles para LaLiga | INTEGRAR | Estimar `dc_rho` (hoy 0 en producción) con tuning walk-forward |
| xG/ascendidos | INTEGRAR (parcial) | Dependen de proveedor |
