---
tags: [evidencia, edge, oos, clv, calibracion, sqp]
creada: 2026-09-07
actualizada: 2026-09-07
---

# Evidencia de edge — medición del 2026-09-07

Auditoría de evidencia con un único objetivo: **¿existe hoy algún (liga, mercado) con ventaja predictiva y económica demostrada sobre el mercado?**

**Respuesta: no. 0 PASS, 6 FAIL, 35 INSUFFICIENT sobre 41 cortes.**

Es la octava medición del proyecto que da cero, y la primera que lo cuantifica corte por corte con intervalos de confianza. Complementa a [[Validación OOS]] (que mide generalización de parámetros) y a [[CLV y selección adversa]] (que aporta la métrica de gating).

## Criterios aplicados

Uniformes a los 41 cortes del registro:

- **PASS** = IC de `brier_diff` bajo Bonferroni enteramente < 0 **Y** IC95 del ROI > 0 **Y** `n ≥ 300` partidos.
- **FAIL** = IC de `brier_diff` enteramente > 0 (mercado mejor) **O** IC95 del ROI enteramente < 0.
- **INSUFFICIENT** = el resto.

## Datos

| Elemento | Valor |
|---|---|
| Stream servido graduado | 22.652 filas win/loss, 2026-07-07 → 2026-09-07 |
| Apuestas liquidadas | 1.326 filas, 2026-06-15 → 2026-09-07 |
| Ventana OOS forward | `game_date > 2026-08-16` → 12.415 filas / 439 picks |
| Cobertura | **62 días, UNA temporada parcial** |

La ventana OOS es la posterior al pre-registro (`VALIDATION_START`, `prediction_gate.py:91`). Todo lo anterior es muestra de **descubrimiento**; usarla para validar es KI-019.

## Resultados

### Registro canónico

`data/bets/prediction_gate.json` (2026-09-07T20:38Z): **41 cortes, 41 en `muestra_insuficiente`, 0 `allowed`, 0 tests de entrada consumidos.** Máximo `n` = 195 (`mlb|h2h`) contra `min_n` = 300.

### Modelo vs mercado (Brier pareado, IC95 bootstrap por evento)

**0 de 25 cortes con IC enteramente < 0.** Cuatro con el mercado estrictamente mejor:

| Corte | ev | Brier modelo | Brier mercado | diff | IC95 |
|---|---|---|---|---|---|
| `mlb\|h2h` | 195 | 0,2401 | 0,2286 | **+0,0116** | [+0,0050, +0,0177] |
| `tennis_wta_us_open\|h2h` | 103 | 0,1784 | 0,1406 | **+0,0378** | [+0,0158, +0,0597] |
| `ncaaf\|spreads` | 47 | 0,3682 | 0,2501 | **+0,1182** | [+0,0379, +0,1947] |
| `ncaaf\|h2h` | 47 | 0,1665 | 0,0888 | **+0,0776** | [+0,0403, +0,1074] |

El log loss favorece al mercado en **todos** los cortes con `n` relevante.

### ROI

| Ventana | picks | ROI plano | IC95 | cortes con IC>0 |
|---|---|---|---|---|
| Descubrimiento | 868 | −11,22 % | [−19,41 %, −2,92 %] | 0 de 9 |
| **OOS** | 439 | **−23,71 %** | [−36,59 %, −9,47 %] | **0 de 5** |

**ROI realizado con dinero real: −15,26 %** sobre 150 apuestas (stake 552,14; PnL −84,25; 2026-06-15 → 2026-07-04). Desde el 2026-07-04 todo va a stake 0.

Los cortes que parecían positivos agregando ambas ventanas (`mlb|h2h` +12,0 %, `wnba|spreads` +16,4 %) están **todos** en descubrimiento y `mlb|h2h` se invierte a **−30,6 %** en OOS.

### CLV

617 emparejadas a cierre fiable, 690 sin cierre. Excluyendo el 30,1 % de empates exactos: **n=431, mediana +0,0000 %, media −0,345 %, tasa de batir el cierre 0,501, test de signo p = 1,000.** La regla de salida del shadow mode (`n≥100` y mediana>0) **no se cumple**.

### La escalera de edge sigue invertida

| Edge declarado | picks | ROI |
|---|---|---|
| 2–5 % | 242 | −8,9 % |
| 5–10 % | 461 | −7,7 % |
| 10–20 % | 348 | −14,1 % |
| >20 % | 250 | **−38,5 %** |

`corr(edge declarado, PnL realizado) = **−0,105**` sobre n=1.307.

**Este es el número que importa.** No dice «aún no hay muestra»: dice que la cantidad que el sistema llama *edge* **predice pérdida**. Mientras siga negativa, más muestra no la convertirá en ventaja — habrá que cambiar de dónde sale la señal. Reproduce de forma independiente la escalera de `min_edge` del 2026-08-25.

Ninguna banda de cuota es positiva. Persistencia por temporada: **no evaluable** (62 días, una temporada parcial).

### El único candidato, refutado

`brasileirao|totals`, histórico completo: `brier_diff = −0,01453`, IC95 [−0,02873, −0,00055].

- Bajo **Bonferroni** (α = 0,05/41 = 0,001220): IC = [−0,03694, **+0,00797**] → cruza 0.
- En la **ventana OOS**: 22 eventos, diff −0,00701, IC95 [−0,03539, +0,01893] → no persiste.
- Con K=35 cortes a α=0,05 sin corregir se esperan **1,75** falsos positivos por azar. Se observó **1**.

## FAIL confirmados

`mlb|h2h`, `tennis_wta_us_open|h2h`, `ncaaf|h2h`, `ncaaf|spreads`, `ligamx|spreads`, `ligamx|h2h`.

## Qué falta antes de arriesgar capital

1. `n ≥ 300` partidos independientes **posteriores al 2026-08-16**. El mayor va por 195; a ~2,3 partidos/día en `mlb|h2h`, faltan ~45 días.
2. Superar el test de signo a **α = 0,001220**, no a 0,05.
3. EV positivo a stake plano en el mismo corte y ventana.
4. CLV mediano positivo con `n ≥ 100`. Hoy es 0,000 %.
5. Persistencia **entre temporadas**: estructuralmente imposible con 62 días.
6. Un ROI realizado positivo fuera de muestra.

## Defectos que podrían fabricar un falso positivo

1. **Multiplicidad.** Con 41 cortes a α=0,05, P(≥1 falso positivo | todos nulos) = **87,8 %**. Mitigado por Bonferroni y test único de entrada (`prediction_gate.py:101-108, 328-361`).
2. **Unidad no independiente.** El stream duplica ~2,19× y las dos caras de un mercado dan `d` idéntico. Corregido en `prediction_gate.py:226` y `one_row_per_pick`; cualquier análisis nuevo que no colapse lo reintroduce.
3. **Validar sobre la muestra del descubrimiento** (KI-019).
4. **Look-ahead residual del Elo intradía**: observa partidos del mismo día anteriores en la lista, ordenada solo por fecha (`daily.py:100`; documentado en `tests/test_backtest_parity.py:251`). Afecta a dobles jornadas; magnitud sin cuantificar.
5. **Backtest ≠ producción**: excluye calibrador live, cap global, banca dinámica, shadow y gate CLV (`roi_engine.py:24-31`).
6. **Cierre no fiable**: 30,1 % de las filas de CLV tienen entrada = cierre exacto, lo que empuja la mediana hacia 0.
7. **Calibrador degenerado**: un mapa constante pasa ECE, Brier y monotonía a la vez (precedente `wnba_totals`, 2026-08-28). Ver [[Calibración]].
8. **EV de longshot**: `ncaaf|h2h` declara `ev_flat = +1,1184` con tasa de acierto pareada 0,106 y ROI realizado −83,4 %. Un EV positivo sobre `p_model` sobreconfiada en cuotas altas es un falso positivo esperando ocurrir, y es visible en el propio registro del gate.

## Reproducción

Todo se calculó con las implementaciones canónicas del repositorio, no con fórmulas ad hoc:

- `sqp.risk.prediction_gate.evaluate_markets` — test de signo pareado, colapso a `(event_id, market)`
- `sqp.evaluation.model_vs_market.score_model_vs_market` — Brier/log loss + cluster bootstrap por evento
- `sqp.evaluation.edge_information.one_row_per_pick` — una fila por apuesta
- `sqp.audit.clv.compute_clv` / `finite_clv` / `clv_segments`
- `sqp.calibration.metrics.expected_calibration_error`
- Datasets: `data/calibration/graded_*.csv`, `data/bets/settled_*.csv`, `data/bets/prediction_gate.json`
