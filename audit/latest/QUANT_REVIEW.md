# Revisión cuantitativa — Auditoría 2026-08-30

Todo lo que sigue son **probabilidades estimadas** y controles de proceso. No
constituye evidencia de rentabilidad. Esta auditoría **no midió** ventaja
predictiva y no la afirma.

## Cobertura de esta revisión: PARCIAL

Se verificaron controles de proceso e invariantes de código. **No** se ejecutó
backtesting, walk-forward ni medición de calibración sobre datos: eso exige
corridas largas y carga de datasets que el alcance de contexto no permitió.
Cualquier cifra de rendimiento debe salir de `04-daily-audit` o del motor de
backtesting, no de aquí.

## Verificado

### Validez de precios

`is_usable_price` (`src/sqp/markets/odds.py:7`) es fuente única de verdad y
rechaza `None`, NaN, ±inf y todo precio decimal ≤ 1.0 (sin pago). Consumido por
`markets/edge.py:65`, `markets/odds.py:31,38` y `pipeline/probabilities.py:35,62`.
Esto cierra el guard que `KI-019` dejaba anotado como pendiente.

### Separación de magnitudes

`markets/edge.py` mantiene separadas `raw_edge`, `penalty`, `adjusted_edge` y
`effective_probability`, y devuelve la penalización plegada en una probabilidad
efectiva para que también encoja el stake de Kelly y no sólo la decisión de
apostar. La distinción probabilidad estimada / implícita / edge se conserva en
el contrato del dataclass.

### Defensa contra el calibrador degenerado

`structural_defect` (`calibration/calibrator.py:155`) unifica en una sola
definición las tres condiciones que no necesitan etiquetas: monotonía, no
expansión a extremos y conservación de resolución. La condición de resolución
exige recorrido tanto en `[0,05, 0,95]` como en la banda operativa `[0,25,
0,75]`, precisamente porque un mapa puede comprar todo su recorrido en las colas
—donde casi no hay picks— y seguir siendo constante donde se decide.

Por qué importa: con la probabilidad fijada en una constante, `edge = p·cuota −
1` pasa a depender **sólo del precio**, y el mercado entero ordena sus picks por
cuota descendente. A la luz de la escalera de `min_edge` invertida, ésa es la
peor política conocida.

Se verificó que el criterio está cableado en las tres puertas: promoción
(`promote_calibrators`, que no lo salta ni con `force`), tablero
(`audit/html_report.py:228`) y registro live (`revalidate_live_registry`).

### Revalidación del registro live

`revalidate_live_registry()` se ejecuta al final de `train_market_calibrators`
(`calibrator.py:573`), alcanzable en el run diario por
`run_all.py:325` → `stage_calibrators_from_settled` → `train_market_calibrators`.
Es estrictamente conservador: sólo puede degradar a no-op, nunca instalar ni
ascender. En el peor caso un mercado se sirve en crudo, que es el
comportamiento por defecto.

Limitación anotada como `B-1`: la revalidación no corre si `calibration_enabled`
es falso o si el historial graduado viene vacío, porque
`stage_calibrators_from_settled` retorna antes. No observado; no corregido.

### Promoción bajo control humano

`configs/default.yaml:142` mantiene `auto_promote: false`, y
`test_default_configuration_requires_human_calibrator_promotion` lo fija como
contrato. El entrenamiento diario escribe **sólo** en staging; instalar en
producción sigue siendo un acto explícito y revisable.

## Estado del sistema leído en esta ejecución

`shadow_mode: false` (levantado el 2026-08-16 por decisión registrada),
`kelly_fraction: 0.08`, `min_edge: 0.02`, `max_stake_pct: 0.02`,
`max_daily_exposure_pct: 0.10`, `max_total_exposure_pct: 0.10`,
`max_plausible_edge: 0.075`, `bankroll: {initial: 1000, dynamic: true}`,
`calibration.auto_promote: false`.

Con `shadow_mode` levantado el sistema dimensiona stakes reales, lo que traslada
el peso de la seguridad a los gates. Esta auditoría **no** completó la revisión
línea a línea de `prediction_gate`, `clv_gate`, `degradation` ni `kelly`: quedan
`PARCIAL` y son la primera prioridad del backlog.

## Salud operativa

`scripts/health_check.py` → `WARN (0 errors, 1 warning)`. La advertencia son 2
filas servidas de `tennis_wta_monterrey_open` fuera de la ventana de scores
(>3 d), que no graduarán desde el feed diario. Acumulado histórico
irrecuperable: 152 filas (brasileirao 35, chile 49, mlb 54, tenis 2, wnba 12),
registrado como seguimiento y explícitamente no accionable.

## Lo que esta auditoría NO establece

No se midió hit rate observado frente a prometido, ni ROI esperado frente a
realizado, ni CLV, ni calibración sobre datos nuevos. **No hay ventaja
predictiva demostrada** y nada en este documento debe leerse como que la haya.
