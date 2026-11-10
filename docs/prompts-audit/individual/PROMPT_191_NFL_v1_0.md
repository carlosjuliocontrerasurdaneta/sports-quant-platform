# Auditoria PROMPT_191_NFL_v1_0

Fecha: 2026-11-10. Prompt: `C:\dev\Prompts\PROMPT_191_NFL_v1_0.md` (cita `NFL:línea`). Plataforma: `C:\dev\3\sports-quant-platform`.

## 1. Ficha

- Fichero: PROMPT_191_NFL_v1_0.md; version declarada 1.0 (NFL:6); 491 lineas.
- Deporte/competicion: futbol americano, NFL; temporada regular y playoffs, pretemporada solo con modelo propio (NFL:4).
- Rol: motor cuantitativo pregame que produce una distribucion conjunta de marcadores y de ella ML/Spread/Totals (NFL:13).
- Objetivo: proyectar marcador, ganador, margen y total; evaluar precios solo tras congelar (NFL:5).
- Modos: VALIDADO / EXPLORATORIO / INCOMPLETO (NFL:79-82); estado por defecto EXPLORATORIO (NFL:7). 21 fases (NFL:86-427), 24 pruebas automaticas (NFL:431-456), excepciones (NFL:460-470).

## 2. Reglas y restricciones

- [COMPROBADO] 20 reglas absolutas (NFL:28-49). Las decisivas: datos con `as_of` previo al kickoff (NFL:30); ninguna cuota como input (NFL:31); no convertir EPA en puntos (NFL:35); una unica distribucion conjunta (NFL:36); push y tie distintos (NFL:43); sin constantes fijas perpetuas (NFL:44); sin motor ejecutado no hay probabilidades (NFL:40).
- Excepciones: escenarios QB_A/QB_B salvo `P(starter)` creible (NFL:39, 152); degradar a INCOMPLETO sin datos (NFL:46, 469).
- "Validado" (NFL:359): walk-forward sin leakage, Brier/log loss de tres clases en temporada regular, calibracion del empate, Brier por spread/total, MAE/RMSE, log score/CRPS, cobertura, ablaciones y comparacion con modelos simples.

## 3. Variables y parametros

[COMPROBADO] El prompt NO contiene ningun coeficiente numerico calibrado; lo declara expresamente (NFL:72). Es su rasgo central.

| Nombre | Valor | Unidad | Linea | Justificacion |
|---|---|---|---|---|
| League_EPA, SuccessRate, PointsPerDrive, DrivesPerGame, PassRate, TurnoverRate | dinamico | por jugada/drive/% | NFL:74 | si, estimados por temporada y corte |
| HFA_points, coef. QB/lesiones/OL/DL/clima/superficie/descanso/ritmo, regresion al prior | entrenable, sin valor | puntos | NFL:75 | no se da valor; se exige etiqueta exploratorio |
| sigma_home, sigma_away, rho, dispersion de drive | estimado fuera de muestra | puntos | NFL:76 | si, se prohibe heredar de MLB/NBA |
| MC_iters | 100 000 provisional (solo con motor real) | simulaciones | NFL:77 | objetivo operacional, con semilla y error MC |
| w = n_eff/(n_eff+tau) | tau sin valor | adim. | NFL:133-137 | formula generica; tau a estimar |
| Valores de anotacion TD 6, XP 1, 2pt 2, FG 3, safety 2 | 6/1/2/3/2 | puntos | NFL:195 | reglamento |
| Regulacion 60 min; OT max 10 min (reg. 2026) | 4x15; 10 | min | NFL:257-259 | reglamento (a verificar por temporada) |
| Tolerancias, umbral de garbage time, ventana historica | no definidos | - | NFL:106 | NO justificado: "criterios predefinidos" sin criterio |

## 4. Fuentes de datos

- [COMPROBADO] Jerarquia NFL:57-62: NFL.com/Football Operations (calendario, reglas, lesiones), nflverse/nflfastR (PBP, EPA), Next Gen Stats, estadisticas oficiales, meteorologia, y sportsbooks solo despues de congelar (NFL:62). Campos minimos por observacion (NFL:66). Conflictos: prioridad por tipo de dato (NFL:64).
- [INFERENCIA] Periodicidad: PBP semanal; lesiones oficiales dia a dia con cierre de inactivos ~90 min antes del kickoff. El prompt no fija frescura maxima ni umbral de caducidad del informe de lesiones.

## 5. Cadena predictiva

Principio (NFL:22): calidad ofensiva + defensiva + QB + disponibilidad + matchup + ritmo + campo/retornos + clima + descanso + localia -> posesiones y puntuaciones -> marcador -> probabilidades -> mercado.

Fases: 1-2 identificacion e ingesta; 3-4 perfiles ofensivo/defensivo (EPA/play, SR, PROE); 5 ajuste por rival y shrinkage `Rating_adj = w × Rating_obs + (1-w) × Rating_prior` (NFL:135); 6-8 QB, plantilla, matchup; 9 ritmo/drives; 10 equipos especiales; 11-12 clima, descanso, HFA; 13 modelo por jugada/drive `p_outcome_i(s) = Softmax(g(θ_off_i, θ_def_j, field_position, down_distance, clock, score, ruleset))` (NFL:220), con f y g declaradas "modelos entrenados, no ejecutables" (NFL:223); 14 simulacion de estado/posesiones o distribucion conjunta empirica; 15 prorroga y empates; 16 Monte Carlo; 17 ML/Spread/Totals.

- Distribucion: ninguna parametrica fija. Prohibe "Normal de margen/total con sigma arbitrario" (NFL:270). Alternativa: distribucion conjunta empirica calibrada (NFL:241).
- Dependencias: correlacion entre equipos, margen y total conservada (NFL:241, 269); no se da forma funcional.
- Prorroga/empate: en regular puede terminar empatado; `P_tie_final` se guarda (NFL:259, 265); playoffs sin empate (NFL:261). Si no se implementa OT, no publicar ML/Spread/Totals finales (NFL:263).
- Formulas literales: `P_home_win = P(H > A)`, `P_tie = P(H = A)` (NFL:285-289); `P_cover = P(score_s + h > score_opponent)`, push y lose analogos (NFL:297-303); `P_over = P(H+A > t)` (NFL:307-313).
- Mercados: ML 3 vias en regular, spread y totales sobre linea dada; sin linea solo medias, mediana y cuantiles (NFL:315). No produce team totals de forma explicita.

## 6. Auditoria matematica

- [COMPROBADO] Coherencia: las identidades de suma 1 (ML con empate, cover/push/lose, over/under/push) derivan del mismo PMF (NFL:36, 291, 303, 313), y la prueba 10 exige que medias de margen y total salgan de la misma distribucion (NFL:442).
- [COMPROBADO] Rigor: separa EPA de puntos (NFL:35, 253), `MC_SE ≈ sqrt(p(1-p)/N)` solo ruido MC (NFL:273), push distinto de tie (NFL:43).
- [INFERENCIA] Futbol americano es discreto y con masa en numeros clave (3, 6, 7, 10, 14): una Normal es mala para P(push) y para lineas de 3 y 7. El prompt acierta al exigir un PMF de marcadores enteros y soporte NFL, aunque no menciona los key numbers explicitamente. [RECOMENDACION] Anadirlos como prueba de calibracion de la PMF (masa del margen en {±3,±6,±7,±10}).
- [COMPROBADO] Coeficientes sin justificar: ninguno por construccion; el defecto contrario es que el prompt es una especificacion, no un modelo: no se puede ejecutar sin entrenar f, g y sigma (NFL:223). El riesgo es que un LLM lo "ejecute" sin motor; mitigado por NFL:40, 465.
- [INFERENCIA] Sobreajuste: las ablaciones y el walk-forward (NFL:359-361) lo mitigan; falta mencionar tamano muestral minimo: la NFL tiene ~272 partidos/ano, muy poca muestra para un modelo drive-by-drive con muchos coeficientes. Se menciona sobreajuste de forma generica (NFL:363).
- Fuga temporal: bien cubierta (NFL:30, 107, 433-434). Datos faltantes: escenarios y abstencion (NFL:39, 46, 163), sin imputacion silenciosa.
- [INFERENCIA] Ambiguedad: "Temporada regular 2026 (reglas verificadas al disenar)" (NFL:259) fija una regla de OT por ano en un texto que dice no imponer constantes por anos (NFL:44, 468); es coherente solo si se trata como `ruleset_id`.
- [HIPOTESIS] La regla de OT 2026 no se ha verificado frente a la fuente oficial en esta auditoria.

## 7. Independencia del mercado

| Cita | Mencion | Clasificacion |
|---|---|---|
| NFL:24 | "el mercado nunca entra en el motor" | principio conforme |
| NFL:31 | prohibe odds, spreads, totales, consenso, movimientos como input | prohibicion (conforme) |
| NFL:62 | sportsbooks solo despues de congelar | COMPARACION POSTERIOR LEGITIMA |
| NFL:315 | lineas de spread/total como umbral sobre la distribucion del modelo | UMBRAL LEGITIMO |
| NFL:318-323 | congelacion con hash antes de consultar cuotas | conforme |
| NFL:329-345 | cuota, prob. implicita, EV, CLV | COMPARACION POSTERIOR LEGITIMA |
| NFL:361 | "mercado sin vigorish solo como comparacion externa" | COMPARACION POSTERIOR LEGITIMA |
| NFL:446 | prueba 14: ninguna cuota ajusta ratings | conforme |

[COMPROBADO] No hay ninguna ENTRADA PROHIBIDA. El prompt congela probabilidades antes de ver el mercado (Fase 18, NFL:317-323). Observacion: la Fase 14 ya prohibe tanto un maximo/minimo arbitrario como acercarse al consenso (NFL:24).

## 8. Validacion propuesta

[COMPROBADO] NFL:347-363: walk-forward/rolling-origin, predicciones almacenadas pre-kickoff, Brier/log loss de 3 clases, calibracion del empate, MAE/RMSE, CRPS, cobertura, ablaciones, comparacion contra baseline por equipos con priors; segmentos por temporada, etapa, clima, rango de spread/total y disponibilidad del QB. Falta: umbrales numericos de aceptacion y tamano minimo de muestra (NFL:359-363 no los dan).

## 9. Contraste con la plataforma

- Implementado: `FootballAdapter(NormalMarginAdapter)` en `src/sqp/sports/adapters.py:168-169`; margen `elo_diff_to_margin(diff, points_per_elo)` (`src/sqp/models/distributions.py:394-396`) y probabilidades por `normal_margin_probs` (`distributions.py:32-56`) y `normal_total_probs` (`distributions.py:59-70`), invocadas en `adapters.py:71-72`. Valores de produccion de la familia: `points_per_elo 0.025, margin_sigma 13.5, avg_total 44.0, total_sigma 13.5, elo_k 24, elo_home_adv 55, elo_mov True` (`src/sqp/sports/registry.py:34-35`). La NFL no tiene override propio en `configs/leagues/ratings.yaml` (solo `ncaaf`, `:41-42`), asi que la NFL corre con los defaults de familia.
- Total: `TeamScoringRates.expected_total` mezcla ofensiva y defensiva de cada equipo (`src/sqp/models/team_scoring.py:92-101`); `scoring_totals` por defecto activo (`adapters.py:67-68`). Elo con multiplicador de margen (`src/sqp/models/elo.py:125-128`). Descanso `rest_points_per_day` 0.0 por defecto (`adapters.py:40-42`), activado solo en NBA (`ratings.yaml:40`).
- Falta (vs prompt): EPA/PBP, QB, lesiones, matchup, clima como features de modelo, drives/posesiones, simulacion estado a estado, equipos especiales, OT con empate, key numbers, Monte Carlo y PMF conjunta. Toda la cadena de las Fases 3-16 no existe; la plataforma modela margen y total como dos Normales separadas.
- Difiere: (a) el prompt prohibe una Normal con sigma arbitrario (NFL:270); la plataforma usa Normal con `margin_sigma 13.5` y `total_sigma 13.5` (sigma de familia; el comentario del registro indica que se mide walk-forward para otros deportes, `registry.py:20-24`, pero para `football` no hay evidencia citada). (b) Margen y total son dos Normales independientes, contra la regla de una distribucion conjunta (NFL:36, 442). (c) `normal_margin_probs` no genera empate: `home_win = 1 - cdf(0)` (`distributions.py:43-44`), mientras NFL regular tiene P_tie > 0 (unas ~0.3-0.4% de partidos reales [HIPOTESIS]). En Elo el empate cuenta 0.5 (`elo.py:121-122`). (d) Push de linea entera: aproximacion por correccion de continuidad ±0.5 con renormalizacion `p/(1-push)` (`distributions.py:46-52`), no PMF discreta; subestima la masa de 3 y 7. (e) `avg_total 44.0` y `elo_home_adv 55` son constantes fijas de familia, contra NFL:44.
- Informacion de mercado en la construccion de probabilidades (hallazgo, aplica a toda la plataforma y por tanto a NFL): `p_used = (1 - shrink) * p_model + shrink * fair` con `market_shrink 0.5` (`configs/default.yaml:17`; `src/sqp/pipeline/probabilities.py:303-305`). Es ENTRADA PROHIBIDA segun el principio del operador: mezcla la probabilidad no-vig del mercado en la probabilidad de decision. Ademas `uncertainty_penalty 0.35` (`default.yaml:26`) deflacta por la discrepancia con el mercado (`daily.py` ~970-980). El calibrador se aplica antes del blend (`probabilities.py:299-305`) y se entrena con resultados, no contra el mercado (`calibration/data.py` usa `adjusted_probability`), lo que es conforme. Para la NFL la lectura efectiva queda "50% modelo / 50% mercado" cuando hay cuota completa.
- Las lineas de spread/total se pasan al adaptador solo como umbral (`adapters.py:63-72`): UMBRAL LEGITIMO.
- Nota de cobertura: `execution.books: [pinnacle]` cubre solo 31% de eventos nfl (`default.yaml:166-171`).

## 10. Veredicto por componente

| Componente | Veredicto | Motivo |
|---|---|---|
| Reglas absolutas de independencia del mercado y congelacion (Fases 18-19) | CONSERVAR | Alinean con el principio del operador. |
| Separacion EPA/puntos, push/tie, una sola PMF | CONSERVAR | Rigurosas. |
| Cadena drive-by-drive (Fases 3-16) | INTEGRAR | Inexistente en la plataforma; requiere entrenar f, g, sigma. |
| Parametros sin valor (Seccion de parametros) | OPTIMIZAR | Dar proceso de estimacion y umbrales de aceptacion. |
| Key numbers y PMF discreta | CORREGIR | El prompt no los nombra; la plataforma los pierde con la Normal. |
| Regla OT 2026 fijada en el texto | CORREGIR | Pasar a `ruleset_id` verificable. |
| Normal margen/total + empate ausente en la plataforma | CORREGIR | Contra NFL:36, 263, 270. |
| `market_shrink 0.5` en p_used / p_decision | DESCARTAR | Mercado como entrada. |
| Monte Carlo 100 000 | CONSERVAR | Solo con motor real. |
