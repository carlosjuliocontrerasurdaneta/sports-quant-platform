# Auditoría de PROMPT_191_UWCL_v1_0.md

Fecha: 2026-11-10. Citas `UWCL:n` = líneas de `C:\dev\Prompts\PROMPT_191_UWCL_v1_0.md`.

## 1. Ficha

| Campo | Valor |
|---|---|
| Fichero | `PROMPT_191_UWCL_v1_0.md` |
| Versión | "Versión: 1.0", temporada reglamentaria de referencia 2026/27 (UWCL:3) |
| Deporte / competición | Fútbol femenino de clubes; UEFA Women's Champions League (fase liga, playoffs, cuartos, semifinales, final) |
| Tamaño | 468 líneas, 21 fases, 40 controles (UWCL:409-450), 20 reglas absolutas (UWCL:34-53) |
| Rol | Motor cuantitativo pregame, exclusivamente clubes femeninos (UWCL:9) |
| Objetivo | Goles esperados, 1X2 a 90', BTTS, hándicaps, totales; clasificación de eliminatorias; posiciones de fase liga; título; EV solo tras congelar (UWCL:11-19) |
| Modos | VALIDADO / EXPLORATORIO / INCOMPLETO (UWCL:50); niveles de datos A-D (UWCL:187-193); abstención permitida (UWCL:51, :367) |

Es el prompt más amplio de la familia: único con módulo de fase liga con tabla (F18), título (F19) y escala de fortaleza entre ligas (F5).

## 2. Reglas y restricciones

- [COMPROBADO] "Las cuotas NUNCA son inputs ni objetivos de ajuste del modelo deportivo" (UWCL:30).
- [COMPROBADO] No trasplantar parámetros masculinos (UWCL:37, :182, :427); ajustar por fortaleza de ligas nacionales (UWCL:38-39); no aplicar la regla abolida de goles de visitante a las eliminatorias, pero sí el criterio de goles fuera de casa en la tabla de fase liga (UWCL:44, :297).
- [COMPROBADO] Prohibido 50/50 implícito en tandas salvo baseline explícito no validado (UWCL:47, :311).
- [COMPROBADO] `lambda = NO CALCULADA` si no hay modelo ejecutado (UWCL:215); NO CALCULADO nunca como 0 % (UWCL:49).
- Condiciones de VALIDADO (UWCL:361): dataset, corte cronológico, tamaño de test, métricas, intervalos y reproducción.
- Reglas de excepción: `CrossLeagueCalibration = INSUFICIENTE` obliga a no emitir probabilidades puntuales (UWCL:118).

## 3. Variables y parámetros

| Nombre | Valor | Unidad | Fase/línea | Justificación |
|---|---|---|---|---|
| Clubes en fase liga | 18 | clubes | F1 :62, F18 :286 | Reglamento 2026/27 (enlace UWCL:68) |
| Partidos por club | 6 (3 en casa, 3 fuera) | partidos | :62 | Reglamento |
| Directos a cuartos / playoffs / eliminados | 1-4 / 5-12 / 13-18 | puesto | :62, :287-289 | Reglamento |
| Puntos | 3/1/0 | puntos | :286 | Reglamento |
| Prórroga | 2 x 15 min en la vuelta | min | :309 | Art. 21 |
| `w = n_eff/(n_eff+tau)` | tau estimado | | :124-126 | Estimar por tipo de dato y competición |
| `beta0`, `HFA`, `Attack`, `DefenseWeakness`, `Context` | estimados | log-goles | :203-205 | MLE o bayesiano (:212) |
| `rho` DC | estimado | | :233 | Prohibido manual |
| Tolerancia de cola | 1e-6 | probabilidad | :235 | Declarada "propuesta, no parámetro deportivo" |
| Tau DC | fórmulas estándar | | :227-231 | Dixon-Coles 1997 |
| Stake asiático | 50/50 | | :276 | Convención |

[COMPROBADO] No hay otros números. Todo coeficiente deportivo queda "a estimar".

## 4. Fuentes de datos

[COMPROBADO] Cuatro niveles (UWCL:74-77): UEFA oficial; federaciones y ligas femeninas; proveedores avanzados "cuya cobertura se confirme"; meteorología. Campos mínimos con `published_at`, `retrieved_at`, `as_of_eligible`, `coverage_status` (UWCL:79). Advertencia de snapshots: no usar estadísticas actuales como históricas si incluyen partidos posteriores (UWCL:81).
[INFERENCIA] La cobertura de xG femenino es la debilidad estructural: las ligas fuera de las cinco o seis más grandes tienen pocos datos de eventos; el prompt lo admite con los niveles B-D (UWCL:189-193).
[COMPROBADO en la plataforma] ESPN `soccer/uefa.wchampions` existe (`src/sqp/providers/espn_results.py:94`).

## 5. Cadena predictiva

1. Ratings ofensivo/defensivo (F3-F4) por club con separación de competición, rival y sede (UWCL:87-94, :99-106). `DefenseWeakness_j`: mayor = más vulnerable (:106).
2. Escala entre ligas (F5, UWCL:112-118): rating jerárquico multiliga con componentes club, liga, temporada y localía; conexión mediante partidos internacionales; aumento de incertidumbre si el grafo está poco conectado.
3. Regularización (F6): `w = n_eff / (n_eff + tau)`; `Rating_adj = w*Rating_observado + (1-w)*Rating_prior` (UWCL:124-126).
4. Modelo de goles (F14):
   `log(lambda_H) = beta0 + HFA + Attack_H + DefenseWeakness_A + Context_H` (UWCL:203)
   `log(lambda_A) = beta0 + Attack_A + DefenseWeakness_H + Context_A` (UWCL:205)
   con restricciones de identificación (suma de efectos centrada por liga/periodo, :213).
5. Distribución (F15): `P(H=h,A=a) = Pois(h;lambda_H) * Pois(a;lambda_A)` (UWCL:221). Dixon-Coles: `tau(0,0)=1-lambda_H*lambda_A*rho`, `tau(0,1)=1+lambda_H*rho`, `tau(1,0)=1+lambda_A*rho`, `tau(1,1)=1-rho` (UWCL:227-231). Malla con cola omitida `<= 1e-6` (UWCL:235).
6. Mercados (F16-F17): `P_H = SUM_{h>a}`, `P_X`, `P_A`; `E[Margin_H]`, BTTS, porterías a cero, 3-5 marcadores (UWCL:243-256). Hándicap `P_cover = P(Goals_sel+k > Goals_rival)`, push, loss; totales (UWCL:262-274). Cuartos asiáticos 50/50 (UWCL:276). Team totals: no se producen como mercado, solo medias por equipo.
7. Fase liga (F18): simular los partidos restantes y aplicar el orden de desempates del Art. 18 (diferencia, goles marcados, goles fuera en fase liga, victorias, victorias visitante, etc., UWCL:295); `P(top4)`, `P(5-12)`, `P(eliminado)` con suma 100 % (UWCL:296).
8. Eliminatorias (F19, UWCL:303-316): condicionar a la ida real; simular 90' pendientes; clasificar por suma de goles, sin goles de visitante; empate global: 2 x 15' en la vuelta y luego penales; "`P_clasificar = NO CALCULADO` o intervalo condicionado" si faltan parámetros de penales (UWCL:311). Final: partido único neutral. Título solo con bracket y sorteos (UWCL:316).
9. Monte Carlo: opcional; registrar semilla, réplicas, error (UWCL:237).

## 6. Auditoría matemática

- [COMPROBADO] Fórmulas DC correctas y consistentes con la plataforma (`distributions.py:71-83`). [INFERENCIA] Con Poisson, `tau` preserva la masa total y las marginales (los cambios se cancelan en cada marginal); por eso UWCL:251 es correcta al condicionar `E[Goals]=lambda` a que "el modelo lo garantice".
- [COMPROBADO] Coherencia interna: 40 controles incluyen sumas de 1X2, BTTS, over/under/push y hándicap (UWCL:439-442).
- [INFERENCIA] Problema central del deporte: el fútbol femenino de élite europeo tiene dispersión competitiva muy alta (UWCL:41); un modelo Poisson con ratings por club y una `HFA` única exige mucha regularización. El prompt lo reconoce (:41, :114-118) pero no da un método de conexión (por ejemplo, ratings tipo Elo multiliga o Bradley-Terry jerárquico).
- [INFERENCIA] Riesgo de sobreajuste: cientos de partidos por año en toda la competición frente a decenas de clubes y varias ligas; la lista de covariables de la F14 (`Context`) y los matchups de la F11 superan fácilmente la información disponible. El prompt exige "prueba de mejora incremental" (UWCL:174).
- [COMPROBADO] Penales: la prohibición de 50/50 (UWCL:47) deja `P_clasificar` no calculable en empates globales; coherente, pero hace el módulo inútil sin un modelo de tandas.
- [INFERENCIA] El tratamiento de la prórroga ("no reutilizar la tasa de 90'", UWCL:309) es correcto cualitativamente, pero no da forma alguna para λ en 30'. Una práctica estándar es escalar λ por 30/90 con un factor de fatiga estimado; aquí falta.
- [COMPROBADO] Simulación de fase liga: pide evitar "considerar independientes lesiones, forma o parámetros compartidos" (UWCL:294). Correcto: la incertidumbre paramétrica debe muestrearse una vez por réplica, no por partido.
- [HIPÓTESIS] El formato 2026/27 (18 clubes, 6 partidos, 4+8 plazas) se declara "a 2026/27" (UWCL:62) pero la fuente es el reglamento a verificar; no confirmado aquí.
- Datos faltantes: niveles A-D con abstención (UWCL:187-199). Buena práctica.

## 7. Independencia del mercado

| Cita | Mención | Clasificación |
|---|---|---|
| UWCL:19 | EV solo tras congelar | COMPARACIÓN POSTERIOR LEGÍTIMA |
| UWCL:30 | Cuotas nunca inputs ni objetivos de ajuste | Principio |
| UWCL:15, :262-274 | Líneas de hándicap/total en las fórmulas | UMBRAL LEGÍTIMO |
| UWCL:116 | Coeficientes UEFA, rankings y prestigio "no son probabilidades"; solo como característica auxiliar validada | Dato deportivo (no es mercado) |
| UWCL:320-322 | "Congelar antes de mirar cuotas" | Congelación correcta |
| UWCL:324-336 | EV, edge de precio, CLV | COMPARACIÓN POSTERIOR LEGÍTIMA |
| UWCL:366 | Ranking con cuotas | COMPARACIÓN POSTERIOR LEGÍTIMA |

[COMPROBADO] Sin ENTRADA PROHIBIDA. [INFERENCIA] El mismo prompt añade que el "price edge" no es `P(win)-0.5` (UWCL:336).

## 8. Validación que propone

[COMPROBADO] UWCL:351-361: split temporal; calibración de ratings entre ligas con partidos anteriores a `as_of`; Brier multiclase, log loss, reliability; log-verosimilitud de marcadores, error de lambda, colas, tasa de empate; clasificación y título evaluados con simulaciones retrospectivas "sin conocer sorteos futuros"; Poisson vs DC vs modelo completo; ablaciones (liga, alineaciones, porteras, calendario, localía, forma); robustez por club dominante. [INFERENCIA] No fija mínimos de partidos de test; con ~150 partidos por temporada UWCL, la potencia estadística es baja y los intervalos serán anchos. [RECOMENDACIÓN] Entrenar con ligas domésticas y validar en UWCL solo como test agregado de varias temporadas.

## 9. Contraste con la plataforma

- [COMPROBADO] `configs/leagues/soccer.yaml:30` registra `uwcl: {sport_key: soccer_uefa_champs_league_women, avg_goals: 3.00}`. No hay entrada en `ratings.yaml` (`configs/leagues/ratings.yaml:9-39`), de modo que usa los valores de la familia: `elo_home_adv 48`, `home_scoring_bonus 0.15`, `tilt_scale 1.0`, `dc_rho 0.0`, `max_score 10` (`src/sqp/sports/registry.py:45-47`).
- [COMPROBADO] Alias de equipos de UWCL en `configs/leagues/team_aliases.yaml:112`; resultados vía ESPN `uefa.wchampions` (`espn_results.py:94`); fila en `pipeline/budget.py:29`.
- [COMPROBADO] No hay ratings multiliga: el Elo es único por liga (`adapters.py:83-143`), de modo que un club noruego o islandés entra con el mismo Elo inicial que uno de la Liga F, sin conexión entre ligas. La plataforma no tiene datos de ligas femeninas domésticas (la Frauen-Bundesliga se retiró, comentario en `soccer.yaml:15-29`). Esa retirada la dejó sin proveedor de resultados históricos, y la misma restricción puede afectar a UWCL: la comparación con 3 días de ventana de The Odds API se indica en el comentario [INFERENCIA, aplica por analogía].
- Faltan: xG femenino, porteras, elegibilidad UEFA, fase liga con desempates, eliminatorias con ida/vuelta, título (no existe ningún simulador de serie ni de tabla para fútbol).
- Difiere: lambdas por Elo+tilt en lugar de ataque/defensa jerárquicos; localía duplicada ([INFERENCIA]: `elo_home_adv` y `home_scoring_bonus`, `adapters.py:141`).
- **Mercado en las probabilidades de la plataforma:** [COMPROBADO] `market_shrink: 0.5` (`configs/default.yaml:17`; `pipeline/probabilities.py:303-306`; `pipeline/daily.py:969-970`) mezcla el no-vig del consenso en `p_decision`; es un ajuste hacia el mercado, contrario al principio. Valor del `.env` de producción no verificable (lectura denegada). `uncertainty_penalty 0.35` (`default.yaml:26`) usa distancia al mercado en la decisión.

## 10. Veredicto por componente

| Componente | Veredicto | Motivo |
|---|---|---|
| Principio de independencia y orden congelación → mercado | CONSERVAR | Alineado con el principio |
| Escala multiliga jerárquica (F5) | INTEGRAR | Es la parte más valiosa y la que falta en la plataforma; requiere datos de ligas domésticas |
| Modelo log-lineal + Poisson/DC | CONSERVAR | Estándar; DC ya está implementado |
| Fase liga (tabla, desempates) | INTEGRAR | Falta en la plataforma; el orden de desempates debe verificarse con el reglamento 2026/27 [HIPÓTESIS] |
| Eliminatorias con ida/vuelta, ET y penales | OPTIMIZAR | Falta modelo de ET (λ en 30') y de tandas |
| Título | DESCARTAR (por ahora) | Sin bracket ni modelo de tandas la salida solo puede ser NO CALCULADO |
| Matchup táctico (F11) | DESCARTAR hasta tener datos | Sin datos femeninos de eventos no se puede estimar |
| Tolerancia 1e-6 y comprobaciones de masa | CONSERVAR | Útil frente a la renormalización silenciosa de la plataforma |
| Estado mercado en plataforma (`market_shrink`) | CORREGIR | Contradice el principio fundamental |
