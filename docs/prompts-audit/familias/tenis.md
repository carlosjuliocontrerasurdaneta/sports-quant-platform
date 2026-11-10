# Familia `tenis`: PROMPT_191_ATP_v1_0 y PROMPT_191_WTA_v1_0

Fecha: 2026-11-10. Informes individuales: `docs/prompts-audit/individual/PROMPT_191_ATP_v1_0.md` y `docs/prompts-audit/individual/PROMPT_191_WTA_v1_0.md`.

## Diff entre los prompts

- [COMPROBADO] Tamaño: ATP 450 líneas, WTA 406. `diff` línea a línea devuelve 832 líneas de diferencia; por unicidad de líneas solo 7 coinciden literalmente de 320 (ATP) y 268 (WTA) líneas no vacías. No comparten texto de plantilla literal: comparten **estructura de 21 fases** y las mismas fórmulas.
- Plantilla común (mismo contenido con otra redacción) [INFERENCIA]: cadena servicio → resto → matchup logístico → `Hold(p)` → tie-break → DP de sets → DP de partido → mercados → congelación → EV → backtesting; 40 controles de consistencia; fallbacks; formato de salida.
- Fórmulas idénticas [COMPROBADO]: `Hold(p) = p^4*(1+4*q+10*q^2) + 20*p^3*q^3 * p^2/(p^2+q^2)` (ATP:223, WTA:185-186); identidad de servicio `p_service = f*a + (1-f)*b` (ATP:138, WTA:130); complementariedad saque/resto (ATP:153, WTA:141); EV `P_win*(D-1) - P_loss` y `P_break_even=(1-P_push)/D` (ATP:321-323, WTA:261-262).
- Específico ATP: BO3 y BO5 (3/4/5 sets, marcadores 3-0/3-1/3-2) (ATP:18, 266, 283); ATP Finals con fase de grupos (ATP:74); Slams con módulo de reglas separado (ATP:25); jerarquía de fuentes numerada (ATP:86-91); campos de registro por variable (ATP:93); término `X_AB_s * beta_s` (ATP:161); `FairDecimal` (ATP:327); regla de que las identificaciones prohíben mezclar con WTA (ATP:25); lista de baselines independientes (ATP:342); CLV (ATP:331).
- Específico WTA: solo BO3 (WTA:51, 79); restricciones de identificabilidad (WTA:152); `contexto_A`; P(torneo/avance de grupo) con simulación completa (WTA:24, 73); reglas «no trasladar parámetros ATP» (WTA:49); CRPS y MAE para juegos (WTA:274); fallback R de retiradas (WTA:388); criterios de VALIDADO con subgrupos y auditoría de retiradas (WTA:390-392); sorteo 0,5/0,5 por defecto del primer servidor (WTA:197); ranking WTA permitido como covariable (WTA:42, 106).

## Contradicciones

1. [COMPROBADO] Primer servidor desconocido: ATP exige escenarios o una mezcla «explícita y justificada», sin inventar el sorteo (ATP:257); WTA fija por defecto 0,5/0,5 bajo condiciones (WTA:197). Es la misma situación con tratamiento distinto.
2. [COMPROBADO] Ranking: ATP lo descarta como sustituto de las métricas de saque/resto y pide ablación (ATP:31, 122); WTA lo admite como covariable validada (WTA:42, 106). No se contradicen estrictamente, pero tienen distinto grado de apertura.
3. [COMPROBADO] Baselines: ATP exige Elo por superficie, hold/break empírico y prior de torneo (ATP:342); WTA no los lista (WTA:270-278).
4. [COMPROBADO] Matchup: ATP incluye `X_AB_s*beta_s` y no cita identificabilidad (ATP:161-165); WTA cita identificabilidad pero no `X*beta` (WTA:148-152). Ninguno contiene ambos.
5. [COMPROBADO] Formato de Grand Slam: ATP lo trata con módulo separado de BO5 (ATP:25, 75); WTA afirma BO3 para Slams femeninos (WTA:51, 79). Es consistente con el reglamento citado, pero ningún prompt verifica el reglamento de cada Slam [HIPÓTESIS: vigencia de tie-break a 10 no comprobada aquí].
6. [INFERENCIA] ATP pide una fórmula `FairDecimal` y WTA no; salidas de EV no homogéneas entre circuitos.

## Versiones y obsolescencia

- [COMPROBADO] Ambos son v1.0, estado EXPLORATORIO, con fecha reglamentaria 2026-11-10 (ATP:3-6, WTA:3-7).
- [COMPROBADO] Citan el «Reglamento ATP 2026» (ATP:435) y el «2026 WTA Rulebook» con PDF de fecha 2026-07-27 (WTA:83). Estas fuentes cambian por temporada y por evento; no se pudieron verificar offline [HIPÓTESIS].
- [INFERENCIA] El prompt WTA hereda un posible error tipográfico: `p_A = logistic(logit(p_A))` (WTA:154). El prompt ATP no tiene ese defecto.
- [INFERENCIA] La plataforma no lee ninguno de los dos; no hay obsolescencia de versión respecto de ella, sino ausencia de implementación (ver individuales §9).

## Tabla comparativa de constantes

| Prompt | Ganar partido | Tie-break normal | Tie-break set decisivo Slam | 7-6 en juegos | Hold(p) | Constantes de modelo | Umbral de fiabilidad | Primer servidor desconocido | Stake de línea .25/.75 |
|---|---|---|---|---|---|---|---|---|---|
| ATP | 2 sets en BO3 / 3 sets en BO5 (ATP:265-266) | 7 pts, margen 2 (ATP:76) | 10 pts, margen 2 (ATP:75) | 13 (ATP:78) | fórmula en ATP:223 | ninguna fijada; `tau`, `alpha`, `beta`, `beta_s` a estimar (ATP:119) | diferencia ≥1 pp (ATP:271) | escenarios o mezcla justificada (ATP:257) | dividir en dos líneas (ATP:296) |
| WTA | 2 sets en BO3 (WTA:79) | 7 pts, margen 2 (WTA:79) | 10 pts, margen 2 (WTA:79) | 13 (WTA:199) | fórmula en WTA:185-186 | ninguna fijada; `tau`, `p_prior` a estimar (WTA:118) | no definido | 0,5/0,5 por defecto (WTA:197) | 50 % a cada vecina (WTA:241) |

## Plataforma, común a los dos (resumen)

- [COMPROBADO] Un único `TennisAdapter` (Elo escalar, K=40, sin superficie) sirve ATP y WTA (`src/sqp/sports/adapters.py:318-338`, `src/sqp/sports/registry.py:52`). Solo `h2h` (`src/sqp/pipeline/daily.py:73`).
- [COMPROBADO] `market_shrink: 0.5` (`configs/default.yaml:17`) se aplica sin excepción de tenis en `src/sqp/pipeline/probabilities.py:274-318`: ENTRADA DE MERCADO en la probabilidad decisoria. Valor de `.env` no verificable.
- [COMPROBADO] Faltan por completo: superficie, estadística de saque/resto, Markov/DP, BO3/BO5, sets, juegos, tie-break, retiradas.
