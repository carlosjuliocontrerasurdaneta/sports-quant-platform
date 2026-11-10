# Auditoria individual: PROMPT_191_WNCAAB_v1_0

Fecha: 2026-11-10. Citas `prompt:linea` = `C:\dev\Prompts\PROMPT_191_WNCAAB_v1_0.md`.

## 1. Ficha
- Fichero: PROMPT_191_WNCAAB_v1_0.md, 610 lineas. Version: v1.0 (l.1). Deporte: baloncesto universitario femenino NCAA Division I (l.4). Estado inicial: EXPLORATORIO (l.5). Mercados: ML, spread, total, solo con cuotas y reglas verificadas (l.6).
- Rol: motor de analisis y pricing pregame (l.13-20): posesiones y puntos de regulacion, distribucion conjunta de marcadores finales con OT, ML, spread, totales, EV.
- Estructura: Reglas absolutas (18, l.32-49), constantes reglamentarias (l.55-62), estados, jerarquia de fuentes, minimo viable, 21 fases con "Traza", formato y 20 pruebas de aceptacion (l.558-579).

## 2. Reglas y restricciones
- [COMPROBADO] Regla 3 (l.34): "Cero dependencia de mercado para estimar: no introducir cuotas, spreads, totales, movimientos de linea, picks, consenso, ranking de casas ni probabilidades implicitas en las fases deportivas." Es la formulacion mas completa de la familia.
- Regla 4 (l.35): escala propia; no copiar medias, sigmas, HCA, correlaciones, ritmos ni efectos de NBA/WNBA/NCAAB masculina. Reglas 9 (4 cuartos de 10 + OT de 5, l.40), 10 (push tres probabilidades), 11 (nada sin calculo real), 12 (sin cuota no hay EV), 16 (reproducibilidad), 17 (no falsear precision).
- Condicion de "validado" (l.440-452): cronologico por temporada, datos pregame archivados con fecha real, Brier/LogLoss/calibracion, MAE/RMSE, CRPS discreto, evaluacion por conferencia/fuerza rival/sede neutral/torneo, rivales no D-I, baseline, ablaciones, recalibracion.
- Aceptacion: 20 pruebas (l.558-579).

## 3. Variables y parametros
| Nombre | Valor | Unidad | Linea | Justificado |
|---|---|---|---|---|
| RegulationMinutes / RegulationPeriods / MinutesPerQuarter | 40 / 4 / 10 | min | 57-59 | Reglamento (verificar por temporada) |
| OvertimeMinutes | 5 | min | 60 | Reglamento |
| PlayersOnCourtPerTeam | 5 | - | 61 | Reglamento |
| ShotClock | 30 s | s | 62 | Reglamento; reinicios a verificar |
| c_FTA | 0.44 "solo como aproximacion explicita" | adim. | 159-161 | Parcial: metodo documentado/calibrado debe sustituirlo |
| tau, n_eff | entrenar | - | 183-189 | Sin valor |
| HCA_points | estimar WNCAAB controlando calidad; neutral 0 | pts margen | 247 | Sin valor |
| rho = 0.12, sigma_margin, sigma_total | citados como lo que NO hay que heredar | - | 336 | Prohibicion |
| Pace40 | 40 * posesiones / minutos_reales | pos/40 | 161 | Formula |
[COMPROBADO] Constantes predictivas con valor numerico: ninguna (c_FTA 0.44 es la unica y es solo para aproximar posesiones). Regla l.64: no fijar medias de liga, HCA, dispersion, etc.

## 4. Fuentes de datos
Jerarquia (l.78-86): 1 oficial NCAA/universidad/conferencia; 2 NCAA Statistics, box scores, play-by-play; 3 Her Hoop Stats, wehoop/SportsDataverse (si accesibles, "no suponer acceso"); 4 lesiones: universidades, comunicados, prensa con hora; "no asumir reporte universal" (l.84, 216); 5 cuotas solo despues. Conflicto: definicion, consistencia, cobertura y fecha antes que nombre del proveedor (l.88). [INFERENCIA] Calidad de datos femeninos menor que masculino (cobertura de tracking, lesiones) y el prompt lo asume; frescura via `as_of` y la advertencia de que una tabla consultada despues no prueba disponibilidad historica (l.33).

## 5. Cadena predictiva
1. Posesiones desde box score (l.159): `Poss_est ≈ FGA - ORB + TOV + c_FTA * FTA`; `Pace40 = 40 * posesiones / minutos_reales` (l.161).
2. Regularizacion (l.183-185): `w = n_eff / (n_eff + tau)`; `Rating_reg = w*Rating_observado + (1-w)*Rating_prior`.
3. Ritmo (l.257): `Poss40_base = sqrt(Pace40_away * Pace40_home)`; alternativa `Poss40_pred = f(...)`.
4. Eficiencia (l.274-276): `Eff_away = AdjO_away * AdjD_home / League_ORtg`; `Eff_home = AdjO_home * AdjD_away / League_ORtg`; alternativa log-lineal (l.282): `log(Eff_i) = alpha + beta_O * log(AdjO_i / League_ORtg) + beta_D * log(AdjD_rival / League_ORtg) + gamma' * X_contexto`.
5. Puntos (l.308-314): `Points_away_reg = Poss40_pred * Eff_away / 100 - HCA_points/2`; `Points_home_reg = Poss40_pred * Eff_home / 100 + HCA_points/2`; margen y total.
6. Distribucion (l.328-336): A simulacion por posesiones entrenada; B remuestreo bivariante de residuos OOS condicionado; C bivariante entero parametrizado. Sin dispersion -> sin porcentajes.
7. OT (l.344-351): OT de 5 min repetido; "No resolver empates asignandolos al visitante o local"; el 50/50 solo vale para ML exploratorio, no para spread/totales.
8. ML (l.359-361), spread/totales con push (l.373-387).
9. EV (l.412-418): `EV = P_win * (D - 1) - P_loss`; `BreakEven_unconditional = (1 - P_push) / D`; `Edge_precio_pp = 100 * (P_win - BreakEven_unconditional)`.
Mercados: ML, spread, totales. Sin team totals.

## 6. Auditoria matematica
- [INFERENCIA] Misma arquitectura que NCAAB, con formula log-lineal calibrada ya explicitada (l.282): mejor que los demas prompts de la familia.
- [COMPROBADO] Coherencia interna: suma a 1 y push (l.387, 560-561), enteros no negativos, OT hasta cero empates (l.562-563), regulacion no etiquetada como final (l.565).
- [INFERENCIA] Aproximacion de posesiones con 0.44 FTA: es el estandar (Oliver); el prompt exige justificarla (prueba 11, l.573).
- [INFERENCIA] El 50/50 de desempates "para ML exploratorio simetrico" (l.351) sesga ML para favoritos en regulacion: cuando hay empate es mas probable el favorito en OT; mitad-mitad subestima al favorito. Impacto pequeno pero real: P(empate) en 40 min ~ 3-4 % [HIPOTESIS]. [RECOMENDACION] Prohibirlo tambien para ML o ponderar por Elo/fuerza.
- [INFERENCIA] Mayor varianza que en NBA y fuerte heterogeneidad por conferencias; el prompt exige validar por conferencia, sede neutral y rival no-D-I (l.446-447), correcto.
- [COMPROBADO] Riesgo de fuga: control fuerte con "datos pregame archivados con su fecha real de disponibilidad" (l.443) y regla 2 (l.33).
- Sobreajuste: bajo; mas riesgo practico de INCOMPLETO por falta de datos femeninos. Datos faltantes: abstencion (regla 14, l.45), escenarios IN/OUT con probabilidades solo si hay base (l.219).
- Incertidumbre: separada (DataQuality, ValidationStatus, ModelUncertainty, MarketQuality, l.435-438).
- Defecto menor: encabezados de traza [FASE 10] etc. alineados; no se detecto desfase.

## 7. Independencia del mercado
| Cita | Mencion | Clasificacion |
|---|---|---|
| l.24, 34 | mercado nunca variable; prohibe odds, spreads, totales, movimientos, consenso, probabilidades implicitas | Politica correcta |
| l.86, 408 | odds solo tras congelar | COMPARACION POSTERIOR LEGITIMA |
| l.387 | sin linea, cuantiles del total calculados | UMBRAL LEGITIMO |
| l.391-402, 580 | snapshot inmutable (`input_hash`, `locked=true`, l.404) antes del mercado | Congelacion previa: SI |
| l.412-429 | EV, edge, desvig, CLV | COMPARACION POSTERIOR LEGITIMA |
| l.427 | movimiento de linea no altera probabilidades | Politica correcta |
[COMPROBADO] Sin ENTRADA PROHIBIDA. NET/AP/seed tampoco entran como expectativa de anotacion (l.169).

## 8. Validacion que propone
Entrenamiento y validacion cronologica por temporada; datos pregame archivados; Brier/LogLoss/calibracion; MAE/RMSE; log-verosimilitud/CRPS discreto; evaluacion por conferencia, fortaleza, neutral, tramo de temporada, grandes favoritos y torneo; baseline AdjO/AdjD/Tempo; ablaciones; recalibracion y control de deterioro (l.440-452). Aclara "No utilizar record de aciertos como unico criterio" (l.452). [INFERENCIA] Sin tamano minimo ni umbral numerico.

## 9. Contraste con la plataforma
- [COMPROBADO] WNCAAB usa `BasketballAdapter`; override en `registry.py:96`: `avg_total` 132, `total_sigma` 17, `margin_sigma` 18 (residuales 17.0 / 18.2). Hereda `points_per_elo` 0.028, `elo_k` 20, `elo_home_adv` 70 (`registry.py:29-31`) y no tiene descanso ni recencia (`ratings.yaml` solo contiene `nba`, `ratings.yaml:34`). [INFERENCIA] Es el prompt cuya regla 4 (no copiar parametros de otras ligas, l.35) la plataforma incumple en `points_per_elo` y `elo_home_adv`, heredados de NBA.
- [COMPROBADO] Margen Normal(Elo x ppe, 18); total Normal con tasas de equipo; sin Pace40, AdjO/AdjD, plantilla/lesiones, sede neutral diferenciada, OT, conjunta, push (`adapters.py:60-80`, `distributions.py:32-68`). Cuatro cuartos vs dos mitades: irrelevante para el modelo actual.
- **Mercado:** [COMPROBADO] `market_shrink 0.5` (`default.yaml:17`) y `uncertainty_penalty 0.35` (`default.yaml:26`) aplicados via `daily.py:968-970` tambien a WNCAAB: mercado como ENTRADA en la probabilidad de decision. [COMPROBADO] Sus sigma y avg_total provienen de residuales de resultados (`registry.py:96`), sin cita de mercado.
- Faltantes: todo el bloque de ratings ajustados, priors de plantilla, simulacion, OT, snapshot con `input_hash`.

## 10. Veredicto por componente
- Regla de cero dependencia del mercado y congelacion: CONSERVAR.
- Regla de escala propia (l.35): CONSERVAR; y CORREGIR la plataforma en WNCAAB (`points_per_elo`, `elo_home_adv`).
- Formula log-lineal calibrada (l.282): INTEGRAR como modelo objetivo (es la mejor de la familia).
- Aproximacion de posesiones FGA-ORB+TOV+0.44FTA: CONSERVAR con calibracion de c_FTA.
- 50/50 en desempates para ML exploratorio (l.351): CORREGIR.
- Distribucion conjunta + OT: INTEGRAR.
- Validacion por conferencia/neutral/no-D-I: CONSERVAR; anadir tamano minimo: OPTIMIZAR.
- Dependencia de wehoop/Her Hoop Stats (acceso incierto): OPTIMIZAR (definir fallback verificable).
- Plataforma `market_shrink`: DESCARTAR de la construccion de probabilidades.
