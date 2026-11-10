# Auditoria individual: PROMPT_191_WNBA_v1_0

Fecha: 2026-11-10. Citas `prompt:linea` = `C:\dev\Prompts\PROMPT_191_WNBA_v1_0.md`.

## 1. Ficha
- Fichero: PROMPT_191_WNBA_v1_0.md, 457 lineas. Version: "v1.0" (l.1). Deporte: baloncesto femenino profesional; WNBA (temporada regular, Commissioner's Cup, playoffs) (l.3).
- Rol: "interfaz auditora y orquestadora de un motor cuantitativo" (l.12). Cuatro preguntas: ganador, margen, total, EV (l.14). Estatus de fabrica: EXPLORATORIO (l.6). Mercados ML, spread, total (l.4). 21 fases (l.87-345).
- Modos: VALIDADO / EXPLORATORIO / INCOMPLETO (l.332-336).

## 2. Reglas y restricciones
- [COMPROBADO] 13 reglas absolutas (l.43-55): pregame verdadero con `as_of` UTC y local; no inventar; no adjudicar validacion; no simulaciones ficticias; sin doble conteo; **escalas compatibles** (40 min, no importar Pace48 ni coeficientes NBA/NCAAB, l.48); 4 periodos de 10 min + OT de 5 (l.49); plantillas historicamente correctas / expansion (l.50); no convertir favoritismo en edge; no llamar CLV a un edge pregame.
- Excepciones (l.414-424). Validado exige backtest cronologico, baseline, Brier/LogLoss, MAE/RMSE, ablaciones, analisis de cambios de regimen y benchmark no-vig "sin usarlo como feature" (l.332).
- Invariantes antes de publicar: 12 puntos (l.426-439), incluido que total y margen deriven "de los mismos marcadores simulados" (l.436).

## 3. Variables y parametros
| Nombre | Valor | Unidad | Linea | Justificado |
|---|---|---|---|---|
| League_ORtg, League_Pace40 | cargar de temporada/as_of | pts/100 pos; pos/40 | 61-62 | Si (datos) |
| tau_team, tau_player, tau_pace | estimar en entrenamiento | - | 65, 125 | Delegado, sin valor |
| HCA_points | calibrar en WNBA; neutra = 0 | puntos de margen | 66, 193-201 | Sin valor; prohibe importar el de NBA/NCAAB |
| delta_player/rest/matchup | solo entrenados | pts/100 pos | 67, 187 | No hay valores |
| Var_home, Var_away, Cov | estimar OOS | - | 68, 239 | Sin valor |
| OT_kernel | entrenar | - | 69 | Sin valor |
| MC_min, MC_max | 100.000 a 1.000.000 | iteraciones | 70 | Computacional |
| max_MC_halfwidth | 0,5 pp al 95 % | pp | 71 | Sugerencia operativa |
| Pace40 = Pace48 x 40/48 | conversion | - | 101 | Aritmetica |
| Suma de minutos | 200 | minutos | 147 | Regla |
[COMPROBADO] Es el prompt mas "limpio" de la familia: ninguna constante predictiva con valor numerico (no hay K_games ni HCA por defecto, a diferencia de NBA l.57-58).

## 4. Fuentes de datos
WNBA.com/WNBA Stats oficial; Basketball Reference (WNBA), Her Hoop Stats; comunicaciones oficiales; calendario/logistica; books solo despues (l.77-81). Conflicto: fuente oficial segun campo, no "la cifra mas reciente" si es posterior al corte (l.83). [INFERENCIA] No fija periodicidad ni antiguedad maxima; sin reporte de disponibilidad -> "declarar sin confirmar" (l.420).

## 5. Cadena predictiva
1. Regularizacion (l.125): `w = n_eff / (n_eff + tau)`; `theta_reg = w × theta_obs + (1 − w) × theta_prior`. Sin prior ni tau: no afirmar regresion (l.129).
2. Ritmo (l.159): `Poss40_base = sqrt(Pace40_away_reg × Pace40_home_reg)`.
3. Eficiencia (l.173, 175): `Eff_away_base = Off_away × Def_home / League_ORtg`; `Eff_home_base = Off_home × Def_away / League_ORtg`; recomendado log-lineal calibrado (l.179).
4. Puntos (l.217-223): `mu_away_reg = Poss40_pred × Eff_away_final / 100 − HCA_points/2`; `mu_home_reg = Poss40_pred × Eff_home_final / 100 + HCA_points/2`; `margin_reg`, `total_reg`.
5. Distribucion (l.231-243): conjunta y discreta; opciones A (por posesion/cuarto), B (simulacion + discretizacion), C (bootstrap bivariante de residuos OOS). Prohibe normales continuas, sigma de NBA y rho manual (l.241).
6. OT (l.249-255): empate -> OT 5 min discreto; registrar P_OT; no repartir 50/50 si se publican spread/totales.
7. ML (l.263-265), spread (l.275-279), totales (l.287-293) con push explicito.
Mercados: ML, spread, totales. No team totals ni 1X2.

## 6. Auditoria matematica
- [INFERENCIA] Misma estructura multiplicativa que NBA; correcta como baseline. La regularizacion `n_eff/(n_eff+tau)` en posesiones (no en partidos) es mejor que `G/(G+K)` de NBA (l.127), y es adecuada para una liga de 40 partidos con rotaciones pequenas.
- [COMPROBADO] Coherencia: invariante 4-5 y 9 (l.431-436) obligan a que ambos equipos compartan posesiones y que total/margen provengan de los mismos marcadores. Push tratado (l.277-295). Suma a 1 (l.435).
- [INFERENCIA] Riesgo estadistico propio de la WNBA: muestra pequena (aprox. 40-44 partidos por equipo, 12-15 equipos [HIPOTESIS: no verificado en esta auditoria]); el prompt lo asume en l.127 y l.50 (expansion), pero exige 100.000-1.000.000 simulaciones mientras la varianza del modelo domina. Error MC 0,5 pp es mucho menor que la incertidumbre de parametros; el prompt lo reconoce (l.329).
- [INFERENCIA] Ausencia de numeros de dispersion en el prompt es correcta, pero en la practica provoca que el prompt, ejecutado sin dato de residuos, caiga siempre a INCOMPLETO. Es un diseno honesto, no un defecto.
- [COMPROBADO] Defecto menor: regla 6 prohibe coeficientes de NBA pero no define como obtener un HCA propio sin historico; l.201 "o no se aplica".
- Fuga temporal: control fuerte (l.43 "los backtests deben reproducir exactamente ese corte"; invariante 1).
- Sobreajuste: bajo (sin coeficientes). Datos faltantes: tipificados (l.52, 418-421). Incertidumbre: cuatro ejes separados (l.325-330).

## 7. Independencia del mercado
| Cita | Mencion | Clasificacion |
|---|---|---|
| l.39 | "El mercado nunca es input"; no usar hándicap/totales "como atajos para inferir puntuaciones" | Politica correcta |
| l.81, 297-321 | books/odds solo tras congelar | COMPARACION POSTERIOR LEGITIMA |
| l.43 | prohibe "cuota de cierre" conocida despues del as_of | Politica correcta |
| l.281 | spread evaluado con linea indicada por el usuario sin cuota | UMBRAL LEGITIMO |
| l.299 | congelar con `prediction_id`, `source_hash` antes de las cuotas | Congelacion previa: SI |
| l.307 | no-vig proporcional | COMPARACION POSTERIOR LEGITIMA |
| l.319 | CLV | COMPARACION POSTERIOR LEGITIMA |
| l.332 | benchmark externo no-vig "sin usarlo como feature" | COMPARACION POSTERIOR LEGITIMA |
[COMPROBADO] Ninguna ENTRADA PROHIBIDA. Es el prompt de la familia que explicita el atajo prohibido (l.39).

## 8. Validacion que propone
Backtest cronologico por temporadas/jornadas con datos estrictamente `as_of`, baseline simple, Brier y LogLoss (ML), calibracion, MAE/RMSE, log-score, spread/totales con pushes, intervalos, ablaciones y regimen (expansion, plantillas, playoffs) (l.332). [INFERENCIA] No fija tamano minimo ni umbral de aceptacion; con ~220-240 partidos por temporada [HIPOTESIS] la potencia estadistica es baja y el prompt no lo advierte.

## 9. Contraste con la plataforma
- [COMPROBADO] WNBA reutiliza `BasketballAdapter` (`adapters.py:165`) con override `registry.py:76-78`: `avg_total` 171, `total_sigma` 19, `margin_sigma` 14, `points_per_elo` 0.024, `scoring_half_life_days` 60. Resto de la familia: `elo_k` 20, `elo_home_adv` 70 (`registry.py:29-31`). Sin override en `ratings.yaml` (solo nba, `ratings.yaml:34`): **WNBA no tiene descanso activado** (`rest_points_per_day` por defecto 0.0, `adapters.py:44`).
- [COMPROBADO] Margen = Elo x points_per_elo; ML y spread por Normal(mu, 14); total por tasas de equipo (regresion 6 partidos) y Normal(.,19) (`adapters.py:60-80`, `distributions.py:32-68`). Sin Pace40, ORtg/DRtg, lesiones, OT, simulacion conjunta, push (se renormaliza fuera, `distributions.py:46-50`).
- [COMPROBADO] Escalas: el prompt exige no importar sigma de NBA (l.241); la plataforma si usa sigma propios medidos por liga (residual 13,6 comentado en `registry.py:76`); coherente con l.241 pero fijos y normales continuas, que el prompt prohibe (l.241).
- [COMPROBADO] `registry.py:57-75` documenta un sesgo de totales WNBA: el modelo proyectaba 167,7 vs 174,5 realizado y 30,66 % de Over frente a 43,77 %; "el residual sigue negativo" y el corte esta en auto-pausa por degradacion. [INFERENCIA] Justifica un challenger basado en eficiencia/ritmo (INTEGRAR).
- **Mercado en la construccion de la probabilidad:** [COMPROBADO] `market_shrink: 0.5` (`configs/default.yaml:17`) aplicado a todas las ligas via `daily.py:968-970`; `uncertainty_penalty: 0.35` (`default.yaml:26`). [COMPROBADO] En `registry.py:68-73` el parametro `scoring_half_life_days` de WNBA (60) se eligio por `tune_market_param` "medido en la linea REAL del mercado (mediana servida 177,5)": **la linea del mercado se uso para seleccionar/optimizar un hiperparametro del modelo**, y tambien el `avg_total` 171 se justifico con la "linea media de mercado = 175,1" (`registry.py:57-61`). Es optimizacion contra el mercado, ENTRADA prohibida bajo el principio del operador (aunque la evidencia citada tambien incluye totales observados 170,9/174,1, resultado deportivo legitimo).

## 10. Veredicto por componente
- Principio y congelacion previa: CONSERVAR.
- Regularizacion con n_eff en posesiones y tau entrenado: CONSERVAR; INTEGRAR (la plataforma usa un prior de 6 partidos fijo).
- Cadena Pace40 x ORtg/DRtg: INTEGRAR como challenger de totales WNBA.
- Distribucion conjunta discreta + OT: INTEGRAR (sustituye normales independientes).
- HCA sin valor por defecto: CONSERVAR; calibrar con datos WNBA (plataforma: 70 Elo x 0.024 = 1,68 puntos [INFERENCIA]).
- Regla de no importar parametros NBA: CONSERVAR.
- Falta de umbral de aceptacion y de potencia: CORREGIR (anadir tamano minimo y advertencia de n bajo).
- Plataforma: ajuste de hiperparametros contra la linea de mercado y `market_shrink`: DESCARTAR de la construccion de probabilidades; mantener como comparacion posterior.
