# Auditoria individual: PROMPT_191_NCAAB_v1_0

Fecha: 2026-11-10. Citas `prompt:linea` = `C:\dev\Prompts\PROMPT_191_NCAAB_v1_0.md`.

## 1. Ficha
- Fichero: PROMPT_191_NCAAB_v1_0.md, 506 lineas. Version: v1.0 (l.1). Deporte: baloncesto universitario masculino NCAA Division I (l.5). Competicion: temporada regular, torneos de conferencia, NIT, NCAA Tournament (l.61).
- Rol: motor cuantitativo de prediccion y pricing pregame (l.5). Objetivo: ML, puntos esperados, spread, totales, EV (l.9-13). Alcance explicito: no aplicar a WNCAAB, NCAA II/III, NBA, WNBA (l.19). Regulacion: dos mitades de 20 minutos, OT de 5 (l.20).
- Modos: VALIDADO / EXPLORATORIO / INCOMPLETO (l.41-43), independientes de CalidadDatos (l.45). 21 fases (l.59-356) mas minimo viable y abstencion (l.360-375).

## 2. Reglas y restricciones
- [COMPROBADO] Reglas innegociables (l.19-29): 40 min y tempo por 40 (no 48, l.21); baseline con partidos entre equipos D-I, no-D-I separados (l.22); sin fuga temporal (l.23); sin invenciones (l.24); sin doble conteo (l.25); abstencion valida (l.26); no afirmar "10.000 o mas simulaciones" sin herramienta (l.27).
- Independencia: l.15 "No usar cuotas, lineas, consenso de pronosticadores ni movimientos de mercado como entradas".
- Pruebas automaticas previas (l.377-393), 15 puntos, incluido "Cuotas y lineas no son inputs" (l.389) y `AdjT` a 40 min (l.381).
- Validado (l.340-348): backtest temporal rolling/expanding, Brier, LogLoss, MAE/RMSE/sesgo, log-verosimilitud/CRPS discreto, ablaciones.
- Hay un minimo viable escalonado: medias -> probabilidades -> EV (l.360-375).

## 3. Variables y parametros
| Nombre | Valor | Unidad | Linea | Justificado |
|---|---|---|---|---|
| AdjO, AdjD | del proveedor | pts/100 pos | 72-74 | Si (KenPom/Torvik), acceso no presumido (l.50) |
| AdjT | del proveedor | pos/40 min | 75 | Si |
| LeagueAdjO, LeagueAdjT | estimar con datos D-I de la fecha | - | 76, 88 | Si |
| lambda | `N_posesiones_D1/(N_posesiones_D1+kappa)` | adim. | 94 | Formula si |
| kappa | "se estima con backtesting"; sin valor | posesiones | 96 | No hay valor |
| HCA_points | solo si calibrado; neutral 0 | pts margen | 162-170 | Sin valor |
| Poss_reg_raw | sqrt(AdjT_a*AdjT_h) | pos/40 | 130 | Hipotesis declarada |
| Monte Carlo | adaptativo, precision objetivo declarada | - | 231 | Sin numero fijo |
| sigma, rho, covarianza | estimar empiricamente; "No importar la dispersion de NBA" | - | 227 | Correcto |
[COMPROBADO] No hay constantes predictivas con valor numerico (como WNBA). Unico numero: "10.000" en l.27 como ejemplo de afirmacion falsa.

## 4. Fuentes de datos
NCAA.com/NCAA Stats; KenPom, BartTorvik/T-Rank "con acceso legitimo" (l.50); play-by-play/box scores; reportes de universidad/conferencia/prensa acreditada ("sin reporte no significa sano", l.52); books solo posterior (l.53). [INFERENCIA] Calidad: la mayor parte de ratings ajustados es de pago/cerrada; el prompt lo reconoce (l.50) y exige normalizacion al mezclar. Frescura: cada input con `fecha_corte`, `actualizacion` (l.55). Sin tolerancia maxima de antiguedad.

## 5. Cadena predictiva
1. Regularizacion (l.92-94): `Rating_shrunk = lambda * Rating_observado + (1-lambda) * Prior_plantilla`; `lambda = N_posesiones_D1 / (N_posesiones_D1 + kappa)`. Prior de inicio: continuidad de minutos, transferencias, freshman, entrenador (l.98).
2. Tempo (l.130): `Poss_reg_raw = sqrt(AdjT_away * AdjT_home)`.
3. Eficiencias (l.190, 192): `Eff_away_base = AdjO_away * AdjD_home / LeagueAdjO`; `Eff_home_base = AdjO_home * AdjD_away / LeagueAdjO`; mas `DeltaEff` validado (l.198-200).
4. Puntos (l.206-212): `Mu_away_reg = Poss_reg * Eff_away / 100 - HCA_points/2`; `Mu_home_reg = Poss_reg * Eff_home / 100 + HCA_points/2`; `Margin_reg`, `Total_reg`.
5. Distribucion (l.222-233): 1 por posesion/play-by-play; 2 remuestreo conjunto de residuos pregame recentrado; 3 bivariante discreto con momentos empiricos. Sin parametros -> solo medias.
6. OT (l.237-246): empates -> periodos de 5 min; medias finales recalculadas; sin modelo OT no publicar ML/spread/totales definitivos.
7. ML (l.250-254), spread (l.262-268), totales (l.276-284) con push.
Mercados: ML, spread, totales. NET y seed explicitamente excluidos como probabilidad (l.111, 491).

## 6. Auditoria matematica
- [INFERENCIA] Estructura multiplicativa estandar; usar AdjO/AdjD de tipo KenPom (ya ajustados por rival y sede) y multiplicar por AdjD/LeagueAdjO es consistente con la propia definicion de esos ratings. La regla anti doble conteo (l.25, 168) es adecuada.
- [COMPROBADO] Coherencia: suma 1 y push (l.256, 270, 284, 386-387); marcadores enteros no negativos (l.384). OT hasta desempatar (l.385).
- [INFERENCIA] Riesgo especifico NCAAB: la muestra D-I esta fuertemente desbalanceada (muchos partidos contra rivales mucho mas debiles; ~360 equipos), por tanto la varianza del margen es alta y no estacionaria entre favoritos fuertes y partidos parejos. Un unico sigma/dispersion constante subestima colas en palizas; el prompt pide condicionar el remuestreo por tempo, media y diferencia de fuerzas (l.224), que es la solucion correcta.
- [INFERENCIA] Con diferencias de calidad extremas la formula multiplicativa puede producir eficiencias poco realistas (garbage time); el prompt prohibe el recorte "salvo validaciones de integridad" (l.202) y pide verificar, no truncar (l.214). [RECOMENDACION] Anadir validacion por rangos historicos de eficiencia en lugar de limite fijo.
- [COMPROBADO] Posible incoherencia nominal: `P_break_even_condicional = 1/D` (l.311) frente al breakeven incondicional `(1 - P_push)/D` (l.317); son distintos y la etiqueta de l.311 puede confundir. Las formulas de EV y edge (l.315-317) son correctas.
- Fuga temporal: muy cuidada (l.23, 340; "estadisticas finales de temporada" y clasificaciones futuras prohibidas). Riesgo no cubierto: ratings tipo KenPom archivados hoy no reflejan el corte historico; el prompt lo menciona solo de forma general ("snapshots pregame", l.340).
- Sobreajuste: bajo en el prompt; el propio ajuste de kappa es un solo parametro. Datos faltantes: abstencion y escenarios IN/OUT sin inventar probabilidades (l.146-149).

## 7. Independencia del mercado
| Cita | Mencion | Clasificacion |
|---|---|---|
| l.15 | no usar cuotas/lineas/consenso/movimientos como entradas | Politica correcta |
| l.53 | casas solo comparacion posterior | COMPARACION POSTERIOR LEGITIMA |
| l.111 | NET como contexto / benchmark externo, nunca conversion a probabilidades | Politica correcta (NET no es mercado) |
| l.272, 286 | spread/totales sin linea: cuantiles del margen/total | UMBRAL LEGITIMO |
| l.288-300 | congelar snapshot inmutable antes del mercado | Congelacion previa: SI |
| l.304-323 | cuotas, EV, edge, sin vig | COMPARACION POSTERIOR LEGITIMA |
| l.324 | movimiento y consenso "auditoria externa, no modifica" | COMPARACION POSTERIOR LEGITIMA |
| l.345 | EV/CLV/comparacion contra mercado sin vig en backtest | COMPARACION POSTERIOR LEGITIMA |
[COMPROBADO] Sin ENTRADA PROHIBIDA. [INFERENCIA] Matiz: KenPom/Torvik publican tambien "predicciones" y las ratings de eficiencia son estadisticas, no mercado; aceptable.

## 8. Validacion que propone
Rolling/expanding sin leakage; Brier, LogLoss y calibracion para ML; MAE/RMSE/sesgo/cobertura para puntos; log-verosimilitud/CRPS discreto; spread/totales por rangos de linea con pushes; ablaciones (AdjO/AdjD/AdjT, +plantilla, +4F, +descanso, +sede, +matchup); EV con incertidumbre y CLV (l.340-348). No usar NET/seed. [INFERENCIA] No fija tamano minimo ni umbral numerico de aceptacion.

## 9. Contraste con la plataforma
- [COMPROBADO] NCAAB usa `BasketballAdapter` con override `registry.py:95`: `avg_total` 145, `total_sigma` 18, `margin_sigma` 16 (comentario "residuales 17.7 / 15.6"); hereda `points_per_elo` 0.028, `elo_k` 20, `elo_home_adv` 70 de la familia (`registry.py:29-31`) y no tiene override de descanso ni de recencia (`scoring_half_life_days` no esta en `registry.py:95`, por defecto 0.0, `adapters.py:41`). [INFERENCIA] Hereda el `points_per_elo` y `elo_home_adv` de NBA sin evidencia de re-estimacion; en una liga con margenes de otra escala esto es sospechoso.
- [COMPROBADO] Margen por Elo (sin AdjO/AdjD/AdjT), total por tasas de equipo, normales continuas e independientes (`adapters.py:60-80`, `distributions.py:32-68`). Sin filtro D-I vs no-D-I visible, sin tempo, plantillas, transferencias, sede neutral, torneos, OT, push (se renormaliza, `distributions.py:46-50`). La sede neutral requeriria cero ventaja local; [HIPOTESIS] la plataforma no lo distingue en Elo (no verifique el origen del flag neutral).
- **Mercado:** [COMPROBADO] `market_shrink 0.5` (`default.yaml:17`) y `uncertainty_penalty 0.35` (`default.yaml:26`) a todas las ligas (`daily.py:968-970`): ENTRADA de mercado en la probabilidad de decision. [COMPROBADO] Los `margin_sigma`/`total_sigma` de NCAAB provienen de residuales walk-forward sobre resultados (`registry.py:21-28, 95`), no del mercado.
- Faltante principal: todo el bloque AdjO/AdjD/AdjT, prior de plantilla, bootstrap, OT.

## 10. Veredicto por componente
- Independencia del mercado y orden de congelacion: CONSERVAR.
- Universo D-I y separacion de no-D-I: INTEGRAR (la plataforma puede estar mezclando partidos desbalanceados en Elo).
- Regularizacion lambda/kappa por posesiones: OPTIMIZAR (kappa por backtest).
- Cadena AdjO/AdjD/AdjT: INTEGRAR como challenger; depende de licencia de datos (KenPom de pago), por lo que [RECOMENDACION] priorizar Torvik o estimacion propia desde box scores.
- Distribucion conjunta con remuestreo condicionado: INTEGRAR; es el reemplazo adecuado de sigma constantes.
- Etiqueta P_break_even_condicional (l.311): CORREGIR.
- NET/seed fuera del modelo: CONSERVAR.
- Plataforma: parametros heredados de NBA (`points_per_elo`, `elo_home_adv`) CORREGIR; `market_shrink` DESCARTAR de la construccion de probabilidades.
