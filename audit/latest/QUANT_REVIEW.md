# Revisión cuantitativa — Auditoría 2026-08-04

Todo lo que sigue son **probabilidades estimadas** y controles de proceso. No
hay en este documento ninguna afirmación de rentabilidad.

Alcance honesto de esta pasada: la revisión profunda por deporte/mercado se hizo
el 2026-07-29/31 y el 2026-08-02 (historial git de este archivo) y sus
conclusiones siguen vigentes. Esta auditoría **no ejecutó backtests, ni
`validate_oos.py`, ni reentrenó nada**: sus correcciones fueron de seguridad,
integridad y observabilidad. Lo que sigue es el estado verificado, no un
resultado nuevo.

## Hecho dominante

**No hay ventaja predictiva demostrada.** Esto no cambió con esta auditoría y
ninguna de sus correcciones lo afecta.

| Evidencia | Valor | Fuente |
|---|---|---|
| ROI realizado con dinero real | **−8.4% de banca** (915.75 = 1000 − 84.25 sobre 431 apuestas graduadas) | `configs/default.yaml:33` |
| ROI realizado MLB | **−27.6%** | `Obsidian/Estado del proyecto.md:54` |
| OOS de la regla edge/Kelly | **−5.32%** | auditoría 2026-08-02 |
| Mejor configuración medida | **≈ break-even** | `Obsidian/Conocimiento/Validación OOS.md:30` |
| Gate de CLV por (liga, mercado) | **VACÍO** — ningún mercado con mediana > 0 y n≥30 | `Estado del proyecto.md:47` |
| CLV sobre 326 emparejadas a cierre fresco | mediana **+0.0000%**, media **−0.24%**, beat-close 43.1% | bitácora 2026-08-02 |

La investigación del 2026-08-02 cerró la hipótesis de que el timing escondiera
CLV positivo: **respuesta negativa**. Excluyendo los picks con lead ≤150 min
(n=260), la mediana sigue en 0.0000%. Conclusión registrada y no refutada:
*falta señal, no medición*.

## Modo de selección y objetivo

- `pick_mode: edge` activo desde 2026-07-31 (`f6c2130`). El modo `accuracy`
  (07-28 → 07-31) se revirtió porque seleccionaba favoritos a cuotas 1.07–1.16,
  donde el punto de equilibrio es 93.5%: **subía el hit rate y perdía dinero por
  construcción**. Sigue disponible y conmutable, con sus advertencias vigentes.
- Todo hit rate se reporta contra `breakeven_probability(price) = 1/price`
  mediante las columnas `breakeven_hit_rate` y `hit_rate_margin`. Un hit rate
  absoluto no es una afirmación de rentabilidad.

## Riesgo — verificado sin cambios

Esta auditoría **no tocó** ninguno de estos parámetros:

| Control | Estado verificado |
|---|---|
| `shadow_mode` | `true` (`configs/default.yaml:100`) — todos los picks a stake 0 |
| `bankroll.initial` | 1000, dinámico; balance congelado 915.75 |
| `max_plausible_edge` | 0.075 |
| Exposición | dos capas: `max_daily_exposure_pct` por liga + `max_total_exposure_pct` global, ambas 0.10 |
| `clv_gate` | default-deny, `min_n` 30 |
| `degradation_monitor` | activo, `min_n` 30, ventana 60 días, con histéresis |
| Salida del shadow | mediana de CLV positiva + gate de Brier, **por mercado** |

Hallazgo relevante para el riesgo, corregido en esta auditoría: **C-2** habría
desarmado `shadow_mode`, el gate de CLV y las pausas si `configs/default.yaml`
no se resolvía. Ver `FINDINGS.md`.

## Calibración

- **Train ≠ promote.** `calibration.auto_promote: false` es el default
  autoritativo desde 2026-08-04; ningún calibrador entra en producción sin
  aprobación humana.
- Registro live casi vacío: **solo `mlb_h2h`** pasó todos los gates (isotónico,
  ECE OOS 0.117→0.037, 23 eventos de validación). El resto de la plataforma
  sirve probabilidades crudas — es un no-op por diseño, no un fallo.
- Gates vigentes: Brier OOS, monotonía, ≥15 eventos independientes, y el gate
  **anti-inflación a extremos** (`extreme_ok`) añadido el 07-13 tras un candidato
  `wnba_h2h` que pasaba ECE+Brier+monotonía mientras mapeaba 0.80→0.99.
- Un calibrador que mejora ECE pero empeora Brier OOS se descarta. Precedente
  registrado: `mlb_spreads` (ECE 0.1461→0.1076, Brier peor → rechazado).

## Leakage y validación temporal

Controles verificados como existentes en el código (no re-ejecutados):

- Fix del mismatch train/serve (2026-07-01): se entrena sobre
  `data/bets/settled_*.csv`, la distribución de servicio.
- `ServedStore` captura la distribución completa de probabilidades servidas, no
  solo los picks apostados, para entrenar sin sesgo de selección.
- Filtro de frescura del cierre (≤90 min del comienzo) en la auditoría de CLV.
- Backtest walk-forward con warmup 60; `validate_oos.py` congela parámetros en
  TRAIN y mide en TEST posterior.
- `intraday_gate.py`: en mercados con línea exige **match exacto de `point`**;
  si la línea se movió, la fila se omite en vez de re-preciarse contra otra línea.

**No puedo confirmar** la ausencia de leakage por inspección estática: requeriría
re-ejecutar el backtest y los tests de leakage, fuera del alcance de esta pasada.

## Tamaños de muestra e incertidumbre

| Medición | n | Estado |
|---|---|---|
| Gate de CLV por mercado | ≥30 requerido | ningún mercado lo alcanza con mediana > 0 |
| Gate intradía (#4) | **22 de 30** | **INSUFICIENTE** |
| Calibrador live `mlb_h2h` | 23 eventos de validación | promovido 07-13 |
| Apuestas con dinero real | 431 graduadas | histórico, cerrado |

El observatorio intradía v2 (2026-08-02) escanea h2h + spreads + totals, lo que
debería triplicar la acumulación por captura. La primera lectura del gate fue
INSUFICIENTE con dirección a favor (CLV intradía media +0.29% vs −2.08% de los
picks de las 11:00), pero **el positivo lo carga el tenis con n=4**: es ruido.
MLB intradía es plano (−0.04%, n=13).

Ninguna de estas cifras lleva intervalo de confianza. Todo el ROI OOS es sobre
proxy de cierre de un snapshot, sin intervalos → **no es rentabilidad
demostrada**.

## Elementos explícitamente no demostrados

1. Que algún modelo de la plataforma tenga edge sobre el mercado.
2. Que el CLV intradía sea positivo de forma sostenida (n insuficiente).
3. Que el segundo pase de revalidación mejore la selección (sin muestra).
4. Que el modo `accuracy` sea rentable (nunca tuvo backtest propio).
5. Que la ausencia de leakage esté verificada en esta pasada.

## Preparación

- **Shadow: PREPARADO.** La medición es completa y honesta.
- **Dinero real: NO PREPARADO.** Ningún (liga, mercado) pasa el gate de salida.
