# Familia baloncesto: PROMPT_191 NBA, WNBA, NCAAB, WNCAAB (v1.0)

Fecha: 2026-11-10. Informes individuales en `docs/prompts-audit/individual/`.

## 1. Diff entre prompts
- [COMPROBADO] Medido con un script (lineas no vacias, `difflib`): lineas literalmente identicas entre pares = 1 a 7 (NBA-WNBA 7; NBA-NCAAB 3; NBA-WNCAAB 1; WNBA-NCAAB 3; WNBA-WNCAAB 3; NCAAB-WNCAAB 2); razon de similitud secuencial 0,003 a 0,024. **No hay plantilla textual comun**: los cuatro son redacciones independientes.
- [INFERENCIA] Si hay plantilla *conceptual* comun (misma arquitectura): estados VALIDADO/EXPLORATORIO/INCOMPLETO; 21 fases; `as_of` y congelacion; `Eff = Off x Def / League_ORtg`; ritmo `sqrt(Pace_a x Pace_h)`; `mu = Poss x Eff/100 -/+ HCA/2`; distribucion conjunta (bootstrap de residuos o bivariante), OT recalculado, ML/spread/total con push; `EV = P_win(D-1) - P_loss`; `Edge_precio_pp = 100(P_win - (1-P_push)/D)`; CLV solo tras cierre. Formulas EV/edge identicas en los cuatro.
- Lo propio de cada uno:
  - NBA (433 l.): 48 min, Pace48, unica con `K_games = 20` y `HCA = +2.0` explicitos (l.57-58); OT con Poisson fallback (l.206); fases 12 (posesiones) y 13 (distribucion) separadas; fuentes NBA oficiales; incluye Cup/play-in.
  - WNBA (457 l.): 40 min, Pace40, regularizacion por posesiones `n_eff/(n_eff+tau)`, sin valores de HCA ni K; MC 100.000-1.000.000 y semiancho 0,5 pp (l.70-71); aviso de expansion; "no es una NBA reducida" (l.443).
  - NCAAB (506 l.): D-I, `AdjO/AdjD/AdjT` (KenPom/Torvik), `lambda`/`kappa` (l.94), separacion D-I vs no-D-I, torneos y sede neutral, NET/seed como contexto; dos mitades de 20.
  - WNCAAB (610 l.): como NCAAB pero con cuatro cuartos de 10, aproximacion de posesiones con c_FTA (l.159), formula log-lineal (l.282), reglamento como constantes (l.55-62), 20 pruebas de aceptacion y traza por fase; el mas extenso.

## 2. Contradicciones y diferencias materiales
- [COMPROBADO] **Periodos**: NCAAB declara dos mitades de 20 (l.20); WNCAAB cuatro cuartos de 10 (l.40, 57-59). Es correcto por reglamento (masculino en mitades, femenino en cuartos) [HIPOTESIS: reglamento no verificado en linea en esta auditoria]; ambos suman 40 min, pero **la plataforma los trata con la misma familia**.
- [COMPROBADO] **HCA**: NBA da +2.0 por defecto (l.58); WNBA, NCAAB y WNCAAB lo dejan sin valor y exigen calibracion. Politica inconsistente entre prompts.
- [COMPROBADO] **Regularizacion**: NBA usa partidos (`G/(G+K)`), los otros tres posesiones efectivas (`n_eff`/`N_posesiones_D1`) con hiperparametro entrenado.
- [COMPROBADO] **OT**: solo NBA da un fallback concreto (Poisson); WNBA, NCAAB, WNCAAB exigen modelo discreto y sin modelo no publican spread/totales; WNCAAB permite 50/50 solo para ML exploratorio (l.351), NCAAB y WNBA lo prohiben o lo restringen.
- [COMPROBADO] **Fases**: NBA tiene rotulos de fase distintos (Fase 12 posesiones/13 distribucion/14 OT) frente a WNBA (14 distribucion/15 OT) y WNCAAB/NCAAB (13/14 etc.): no hay numeracion comun para consumirlos programaticamente.
- [COMPROBADO] **Etiqueta de breakeven**: NCAAB l.311 `P_break_even_condicional = 1/D` frente a `(1-P_push)/D` incondicional en las otras tres: inconsistencia de nombre (la formula de EV coincide).
- [COMPROBADO] **Congelacion**: WNCAAB incluye `input_hash` y `locked=true`; NBA y WNBA `prediction_id`, `source_hash`; NCAAB lista contenido del snapshot sin hash obligatorio.
- [INFERENCIA] Sin contradiccion sobre mercado: los cuatro coinciden en que el mercado no es entrada.

## 3. Versiones y obsolescencia
- [COMPROBADO] Todos "v1.0"; solo NBA declara la version en el titulo como "Version 1.0" (l.2). NBA referencia el Injury Report 2026-27 (l.431) y WNBA el calendario 2026 (l.455): referencias con fecha que caducan.
- [HIPOTESIS] NCAAB declara "no incluye parametros entrenados ni un backtest" (l.506); los demas no lo declaran pero tampoco los incluyen.
- [INFERENCIA] Referencias de URLs de reglas/estadisticas pueden cambiar (el propio NBA pide "consultar versiones vigentes", l.427).

## 4. Tabla comparativa de constantes
| Prompt | Min reg. | Escala ritmo | HCA por defecto | K / tau / kappa | Pace base | OT fallback | MC | Sigma/rho |
|---|---|---|---|---|---|---|---|---|
| NBA | 48 (4x12) | Pace48 | +2.0 pts margen (l.58) | K_games = 20 (l.57) | sqrt(Pa x Ph) (l.123) | Poisson(5/48 mu) (l.206) | 100.000 (l.59) | no imponer (l.60) |
| WNBA | 40 (4x10) | Pace40 | sin valor (l.66) | tau entrenado (l.65) | sqrt (l.159) | entrenar (l.69) | 100.000-1.000.000; 0,5 pp (l.70-71) | estimar OOS (l.68) |
| NCAAB | 40 (2x20) | AdjT/40 | sin valor (l.162) | kappa por backtest (l.96) | sqrt (l.130) | parametros entrenados o fallback etiquetado (l.240) | adaptativo (l.231) | empirico (l.227) |
| WNCAAB | 40 (4x10) | Pace40 | sin valor (l.247) | tau entrenado (l.183) | sqrt (l.257) | mecanismo explicito (l.346) | semilla/n_iter (l.338) | prohibido heredar rho = 0.12 (l.336) |

## 5. Contraste de plataforma (resumen de familia)
- [COMPROBADO] Las cuatro ligas usan `BasketballAdapter` (`src/sqp/sports/adapters.py:165`, `NormalMarginAdapter` l.29). Parametros en `src/sqp/sports/registry.py:29-31` (familia: `points_per_elo` 0.028, `margin_sigma` 13.0, `avg_total` 224, `total_sigma` 22, `elo_k` 20, `elo_home_adv` 70) y overrides l.76 (wnba), l.92 (nba), l.95-96 (ncaab/wncaab).
- Tabla de produccion: NBA solo `scoring_half_life_days` 180 y `rest_points_per_day` 0.795 (`ratings.yaml:34-40`); WNBA 171/19/14, ppe 0.024, half-life 60; NCAAB 145/18/16; WNCAAB 132/17/18; NCAAB y WNCAAB heredan `points_per_elo` 0.028 y `elo_home_adv` 70 de NBA (violan la regla 4 del WNCAAB, l.35).
- [COMPROBADO] Ninguna de las cuatro implementa Pace, ORtg/DRtg, lesiones, distribucion conjunta, OT ni simulacion; margen y total son normales independientes (`distributions.py:32-68`), con push renormalizado fuera (l.46-50, 62-66).
- **Mercado como entrada (plataforma):** [COMPROBADO] `market_shrink` 0.5 (`configs/default.yaml:17`) y `uncertainty_penalty` 0.35 (`default.yaml:26`) via `src/sqp/pipeline/daily.py:968-970`, todas las ligas. [COMPROBADO] Hiperparametros WNBA justificados contra la linea de mercado (`registry.py:57-73`, `tune_market_param`, "linea REAL del mercado"). [HIPOTESIS] Calibradores entrenados sobre historial de picks (`calibrator.py:714`) con sesgo de seleccion por edge de mercado; no verificado.
- Hay evidencia propia que respalda al prompt: el modelo Normal de WNBA muestra sesgo de totales (167,7 vs 174,5, `registry.py:68-73`) y el de NBA 32,5 pp de sesgo sin decaimiento (`registry.py:79-91`).

## 6. Prioridades para la familia
1. [RECOMENDACION] Separar probabilidad del modelo de la probabilidad de decision (`market_shrink`): conservar la primera sin mezcla de mercado.
2. [RECOMENDACION] Re-estimar `points_per_elo` y `elo_home_adv` para NCAAB/WNCAAB; hoy heredados de NBA.
3. [RECOMENDACION] Challenger Pace x ORtg/DRtg con distribucion conjunta y OT, empezando por totales WNBA/NBA.
4. [RECOMENDACION] Homogeneizar entre prompts: HCA por defecto, numeracion de fases, etiqueta de breakeven, tamano minimo de backtest.
