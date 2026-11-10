# Auditoría de PROMPT_191_ATP_v1_0 (tenis masculino individual)

Fuente: `C:\dev\Prompts\PROMPT_191_ATP_v1_0.md` (450 líneas). Fecha de la auditoría: 2026-11-10. Familia: `tenis` (ver `docs/prompts-audit/familias/tenis.md`).
Nota de método: `graphify` (MCP) estaba caído; se usó Grep/Read dirigidos. No se pudo leer `.env` (lectura denegada por el entorno), por lo que el valor efectivo de `MARKET_SHRINK` en producción **no es verificable** (ver §9).

## 1. Ficha

| Campo | Valor |
|---|---|
| Fichero | `PROMPT_191_ATP_v1_0.md` |
| Versión declarada | 1.0, especificación del 2026-11-10 (ATP:1-4) |
| Deporte / competición | Tenis masculino individual; ATP Tour 250/500/1000, ATP Finals y módulo aparte para Grand Slams masculinos (ATP:5) |
| Tamaño | 450 líneas |
| Rol | Motor cuantitativo de pricing pregame (ATP:12) |
| Objetivo | P(partido), P(1.er set), marcador de sets, distribución de juegos, Over/Under y hándicap de juegos y sets, P(tie-break), EV solo con cuota verificada (ATP:16-23) |
| Alcance | Solo singles ATP; excluye dobles, WTA, Challenger/ITF/Davis/exhibiciones salvo revisión (ATP:25) |
| Modos | Estado inicial EXPLORATORIO (ATP:6); fallbacks A/B/C/D (ATP:428-431); estados VALIDADO / NO CALCULADO / INCOMPLETO / EV NO EVALUABLE (ATP:49, 53, 55) |

## 2. Reglas y restricciones

- [COMPROBADO] 20 reglas absolutas (ATP:35-54). Las que gobiernan la cuantificación: AS-OF (ATP:36), MERCADO AISLADO (ATP:37), PUNTO≠JUEGO≠SET (ATP:40), DISTRIBUCIÓN ÚNICA (ATP:46), RETIRADAS (ATP:47), SIN COEFICIENTES ARBITRARIOS (ATP:51), ABSTENCIÓN (ATP:53).
- [COMPROBADO] Regla de excepción: Grand Slam masculino = BO5 con tie-break a 10 en el set decisivo (ATP:75); si la competición define otro formato, documentar `RULE_VARIANT` e implementarlo antes de proyectar (ATP:77).
- [COMPROBADO] Condición de «validado»: backtesting cronológico fuera de muestra con pruebas documentadas (ATP:49 regla 16; ATP:337-347).
- [COMPROBADO] Sin formato verificado no se publican probabilidades de partido ni totales (ATP:82).

## 3. Variables y parámetros

[COMPROBADO] El prompt **no contiene ningún coeficiente numérico de producción**; declara expresamente que los ejemplos no lo son (ATP:51). Las únicas constantes son de reglamento.

| Nombre | Valor | Unidad | Línea | Justificación |
|---|---|---|---|---|
| Sets BO3 / BO5 | 2 / 3 para ganar | sets | ATP:73-75, 265-266 | Reglamento; remite a fuente oficial |
| Tie-break regular | 7 puntos, margen 2 | puntos | ATP:76, 239 | Reglamento |
| Tie-break set decisivo Slam | 10 puntos, margen 2 | puntos | ATP:75, 240 | Reglamento (USTA citada en ATP:440; no verificado aquí) |
| 7-6 cuenta | 13 juegos | juegos | ATP:78, 290 | Convención contable |
| `alpha_prior`, `beta_prior`, `tau`, `p0` | a estimar con datos previos al corte | adim. | ATP:113-119 | Se exige estimarlos, no se dan valores |
| `p_ref_s`, `ServeStrength`, `ReturnStrength`, `beta_s` | a ajustar | logit | ATP:161-169 | Ajuste con histórico previo y regularización |
| Margen mínimo de diferencia fiable | 1 punto porcentual | pp | ATP:271 | Heurística sin derivación [INFERENCIA] |
| Tolerancia de normalización | «dentro de tolerancia» | n/d | ATP:259 | Sin valor numérico |
| Número de iteraciones Monte Carlo, semilla | no fijados | n/d | ATP:271 | Se exige registrarlos |

## 4. Fuentes de datos

- [COMPROBADO] Jerarquía (ATP:86-91): 1) reglamento ATP/Slam/ITF; 2) calendario y resultados oficiales; 3) ATP Tour Stats por superficie; 4) datos punto a punto con licencia (Tennis Abstract, académicos); 5) sitios de torneo; 6) meteorología.
- [COMPROBADO] Cada variable se registra con `value, unit, sample_size, surface, time_window, source_url, retrieved_at, effective_at, as_of_eligible, quality_flag` (ATP:93).
- [COMPROBADO] Advierte cobertura distinta Challenger/qualies/Slams y prohíbe scraping contrario a condiciones (ATP:95). Periodicidad y frescura: solo el requisito `as_of` anterior al primer servicio (ATP:36, 103).
- [INFERENCIA] No define latencia máxima de las estadísticas ATP ni de la información médica; la «frescura» se limita al corte `as_of`.

## 5. Cadena predictiva

Fases 5-8 estiman `p_A`, `p_B`; fases 13-18 las propagan.

1. Priors (Fase 5): `p_adj = (wins + alpha_prior) / (trials + alpha_prior + beta_prior)` y `p_adj=(wins+tau*p0)/(trials+tau)` (ATP:114-117). Habilidades latentes de saque y resto por separado, jerárquicas por jugador, superficie, temporada, edad y oposición (ATP:111).
2. Servicio (Fase 6): `p_service = p_first_in * p_win_given_first_in + (1-p_first_in) * p_win_second_serve` (ATP:138).
3. Resto (Fase 7): `P(A gana al resto cuando saca B) = 1 - P(B gana al saque frente a A)` (ATP:153).
4. Matchup (Fase 8): `logit(p_{A_saque_vs_B}) = logit(p_ref_s) + ServeStrength_A_s - ReturnStrength_B_s + X_AB_s * beta_s` y su simétrica (ATP:161-163).
5. Juego (Fase 13): `Hold(p) = p^4*(1+4*q+10*q^2) + 20*p^3*q^3 * [p^2/(p^2+q^2)]` (ATP:223); `Break_A = 1 - Hold_B`, `Break_B = 1 - Hold_A` (ATP:231).
6. Tie-break (Fase 14): DP / cadena absorbente / simulación verificada; saque 1-2-2-…; prohíbe aproximar con `p_A/(p_A+p_B)` (ATP:241-245).
7. Set (Fase 15): estados `(juegos_A, juegos_B, siguiente_servidor, tie_break_rule)`; P(juego)=`Hold_A` si saca A, `1-Hold_B` si saca B (ATP:249-253).
8. Partido (Fase 16): estados con secuencia de sets y juegos acumulados; BO3/BO5; DP exacta preferida, si MC registrar semilla y error (ATP:263-271).
9. Mercados (Fases 17-18): ML, 1.er set, hándicap/total de sets, marcador exacto, P(≥1 TB); totales y hándicap de juegos con push, cuartos asiáticos por mitades de stake (ATP:277-299).
10. Distribuciones: puntos Bernoulli iid con `p` constante dentro del partido (declarado en ATP:225, 269). No hay empate; la prórroga no existe (el tie-break forma parte del set). Retiradas: separadas, probabilidades condicionales a completitud (ATP:307-311).
11. Producción: la lista de mercados completa (ML, sets, juegos, TB). No genera team totals (no aplicable al tenis).

## 6. Auditoría matemática

- [COMPROBADO] `Hold(p)` coincide con el cierre estándar del juego iid: 15 estados de victoria antes de deuce (`p^4(1+4q+10q^2)`), `C(6,3)=20` trayectorias a 3-3 y `p^2/(p^2+q^2)` desde deuce (ATP:223). [INFERENCIA] Es correcta para p constante; límites `Hold(0)=0`, `Hold(1)=1` por continuidad (el prompt no los trata; WTA sí, WTA:189, 364).
- [COMPROBADO] El prompt reconoce que iid es una identidad del modelo y no evidencia empírica (ATP:225) y que sin dependencia explícita declara «punto iid y p estacionario» (ATP:269).
- [INFERENCIA] Riesgo estructural: con puntos iid y `p` fijo por partido, la varianza de juegos y sets queda subestimada frente a la realidad (dependencia por marcador, lado de saque, fatiga). Efecto: totales de juegos y marcadores exactos sobreconfiados; el prompt lo mitiga solo pidiendo calibración de totales (ATP:341).
- [INFERENCIA] Identificabilidad del modelo logístico: `ServeStrength` y `ReturnStrength` por jugador y superficie con `p_ref_s` y `X*beta` sin restricción de suma cero (ATP:161-165); la WTA sí cita restricciones de identificabilidad (WTA:152). [RECOMENDACIÓN] Añadirlas.
- [COMPROBADO] Coherencia interna: exige P_A+P_B=1 condicional (ATP:273), suma de sets = 1 (ATP:259), Win/Push/Loss y Over/Under/Push sumando 1 (ATP:386-387), 7-6 = 13 juegos (ATP:78, 290), mismo espacio de trayectorias para ML, sets y juegos (ATP:46, 286). [INFERENCIA] El esquema es matemáticamente consistente; la consistencia ML/spread/total está garantizada si se calcula una sola distribución.
- [COMPROBADO] EV: `EV = P_win*(D-1) - P_loss`, `P_break_even = (1-P_push)/D`, `FairDecimal = (1-P_push)/P_win` (ATP:321-327). [INFERENCIA] Verificado algebraicamente: EV=0 ⇒ `P_win=(1-P_push)/D`. Correcto para contratos win/push/loss.
- [INFERENCIA] Coeficientes sin justificar: ninguno numérico; la única heurística arbitraria es el umbral de 1 pp (ATP:271).
- [INFERENCIA] Sobreajuste: el prompt exige ablaciones, rolling-origin y evitar duplicar ranking/Elo/H2H (ATP:122, 339-347). Fuga temporal: `as_of` y exclusión de ranking posterior (ATP:36, 103). Riesgo residual: ranking publicado semanalmente; ya contemplado.
- [COMPROBADO] Datos faltantes: tabla de fallbacks (ATP:428-431), con abstención (ATP:53). [INFERENCIA] No define cómo imputar `ReturnStrength` de un debutante más allá del pooling parcial (ATP:121).
- [INFERENCIA] Servidor inicial desconocido: pide escenarios o una mezcla justificada (ATP:257); la WTA fija por defecto 0,5/0,5 (WTA:197).

## 7. Independencia del mercado

| Cita | Mención | Clasificación |
|---|---|---|
| ATP:12 | Comparar con cuotas «solo después de congelar» | COMPARACIÓN POSTERIOR LEGÍTIMA |
| ATP:29 | «La cuota jamás es una entrada» | Regla de independencia |
| ATP:37 | MERCADO AISLADO: ni cuotas, pronósticos de casas, líneas, picks ni movimientos | Regla de independencia |
| ATP:22, 49, 315-333 | EV, edge, odds, CLV | COMPARACIÓN POSTERIOR LEGÍTIMA |
| ATP:296-299, 408-409 | Líneas de totales y hándicap | UMBRAL LEGÍTIMO (se evalúa P sobre la distribución del modelo) |
| ATP:342 | Baselines «sin usar mercado como predictor» | Regla de independencia |
| ATP:430 | Fallback C: «solo ranking/odds/H2H…» ⇒ NO CALCULADO | Regla de independencia (odds no cuentan como base suficiente) |
| ATP:423 | Ranking de jornada con cuotas por EV | COMPARACIÓN POSTERIOR LEGÍTIMA |

- [COMPROBADO] No hay ninguna ENTRADA PROHIBIDA en el prompt. Congela las probabilidades antes de consultar el mercado y fija el contenido a congelar (ATP:315-317) y «No ajustar `p_A` o `p_B` para acercarse a cuotas» (ATP:317).
- [INFERENCIA] Matiz: «ranking ATP» y «cabezas de serie» se descartan como sustitutos pero no se prohíben como covariables (ATP:31); los cabezas de serie derivan del ranking, no del mercado. Sin riesgo de contaminación por mercado.

## 8. Validación propuesta

- [COMPROBADO] Rolling-origin por fecha de partido, reconstrucción de disponibilidad, train/val/test cronológicos, evaluación por superficie, nivel y BO3/BO5 (ATP:339-340).
- [COMPROBADO] Métricas: Log Loss, Brier, calibración/ECE, distribución de sets, juegos totales, probabilidad de TB, cobertura de intervalos (ATP:341).
- [COMPROBADO] Baselines: ratings saque/resto sin matchup, Elo por superficie, hold/break empírico, prior de torneo, sin mercado (ATP:342). Ablaciones (ATP:343). Sesgo de cobertura y retiradas (ATP:344-346).
- [INFERENCIA] Falta: tamaño muestral mínimo para declarar VALIDADO, umbrales numéricos de aceptación (el prompt no inventa umbrales, coherente con la regla de no inventar), y prueba de cobertura específica de totales de juegos frente a cuantiles (CRPS, que la WTA sí incluye: WTA:274).

## 9. Contraste con la plataforma

- [COMPROBADO] Adapter de tenis: `src/sqp/sports/adapters.py:318-338`. Es Elo por jugador de tour completo, `estimate` devuelve `p = elo.expected_home_win(home, away, neutral=True)` y `1-p`. El docstring declara «NO modela la superficie» y que los mercados de juegos/totales requieren un modelo de juego «phase 3 extension» (`adapters.py:321-329`).
- [COMPROBADO] Parámetros de producción por defecto del código: `"tennis": {"elo_k": 40, "elo_home_adv": 0}` (`src/sqp/sports/registry.py:52`), medido walk-forward sobre 16.663 partidos ATP+WTA (`registry.py:48-51`). Elo base 1500 (`src/sqp/models/elo.py:21`), esperanza `1/(1+10^(-diff/400))` (`elo.py:72`). No hay entrada de tenis en `configs/leagues/ratings.yaml` ni en `configs/leagues/*.yaml` (grep sin resultados); los torneos de tenis se descubren dinámicamente (`src/sqp/pipeline/daily.py:83-88`, `scripts/run_all.py:48-73`).
- [COMPROBADO] Datos: resultados ESPN por tour (`daily.py:657-667`, `src/sqp/providers/espn_tennis.py`); solo ganador/marcador, sin estadísticas de saque/resto. Mercados pedidos: solo `h2h` (`daily.py:73`).
- [COMPROBADO] No existen en `src/`: `elo_on_surface`, `surface_elo` como modelo de producción (solo el nombre en la lista de insumos de investigación `src/sqp/features/research.py:31-32`), ni Hold/Break, tie-break, DP de sets/partido, BO3/BO5, totales de juegos ni hándicap de juegos o sets.
- [COMPROBADO] Implementado: Elo con orientación local/visitante aleatorizada en la investigación para evitar sesgo «ganador=home» (`research.py:175-185`); liquidación por nombre y fecha con ESPN (`src/sqp/settlement/settle.py`, `runner.py:192`).
- Faltan (respecto al prompt): superficie, estadística punto a punto, modelo jerárquico servicio/resto, Markov, DP, mercados de sets y juegos, retiradas, formato Slam BO5.
- Difieren: la plataforma estima solo moneyline con un Elo escalar; el prompt exige una cadena puntos→partido.
- **Uso del mercado en la construcción de probabilidades (tenis)** [COMPROBADO]: `_decision_probability` mezcla `p_decision = (1-shrink)*cal(p_model) + shrink*fair` con `fair` = probabilidad sin margen de las cuotas (`src/sqp/pipeline/probabilities.py:274-318`), invocada desde `daily.py:969-970` para todas las familias sin excepción de tenis. Valor por defecto `market_shrink: 0.5` (`configs/default.yaml:17`, `src/sqp/config.py:118, 466-467`). No se encontró exención del tenis. El valor efectivo en producción podría venir de `.env` (`MARKET_SHRINK`, `config.py:466`) y **no es verificable** (lectura de `.env` denegada). Además `adjusted_edge` penaliza el edge por la distancia modelo-mercado (`daily.py:978-985`, `uncertainty_penalty: 0.35`, `configs/default.yaml:26`). Esto es **ENTRADA PROHIBIDA** según el principio del operador si `p_decision` se usa como probabilidad publicada. [HIPÓTESIS] `p_used` guardado puede ser la mezcla cruda (`probabilities.py:289-291`), por lo que el contenido de las columnas servidas debe revisarse.
- [COMPROBADO] Calibrador: se calibra `_p_adj` (pre-blend) y se entrena sobre `adjusted_probability` frente a resultados (`probabilities.py:274-301`, `src/sqp/calibration/data.py:76`), no contra el mercado: legítimo.
- [HIPÓTESIS] `src/sqp/evaluation/feature_shadow.py:325` lee cuotas de tenis para evaluación en sombra; no se ha leído el cuerpo y se asume comparación posterior.

## 10. Veredicto por componente

| Componente | Veredicto | Motivo |
|---|---|---|
| Principio y reglas de independencia del mercado (Fases 20, reglas 3, 14, 15) | CONSERVAR | Alineados con el principio del operador; la plataforma es la que incumple |
| Fórmula `Hold(p)` y DP de set/partido (Fases 13, 15, 16) | CONSERVAR | Matemáticamente correcta bajo iid |
| Supuesto iid con `p` constante | CORREGIR | Subestima varianza de juegos y sets; añadir dependencia por marcador y validar cobertura de totales |
| Modelo logístico de matchup (Fase 8) | CORREGIR | Falta restricción de identificabilidad (cf. WTA:152) |
| Priors Beta-Binomial (Fase 5) | CONSERVAR | Sin valores inventados; requiere estimación |
| Tie-breaks 7/10 y orden de saque (Fase 14) | CONSERVAR | Verificar la vigencia por Slam (no comprobada aquí) |
| Retiradas y liquidación (Fase 19) | CONSERVAR | Separa capa deportiva y contractual |
| Umbral de 1 pp (ATP:271) | OPTIMIZAR | Heurística; sustituir por el error Monte Carlo calculado |
| Validación (Fase 21) | OPTIMIZAR | Añadir CRPS y cobertura de cuantiles de juegos |
| Adapter de tenis de la plataforma | INTEGRAR | Reemplazar Elo escalar por la cadena servicio/resto/Markov para producir sets, juegos y TB |
| `market_shrink` aplicado al tenis | CORREGIR | Entrada de mercado en la probabilidad; poner a 0 o excluir tenis y mostrar mercado solo después de congelar |
