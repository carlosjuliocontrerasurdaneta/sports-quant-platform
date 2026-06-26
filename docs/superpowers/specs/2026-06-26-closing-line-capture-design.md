# Diseño: captura de línea de cierre (closing-line capture)

Fecha: 2026-06-26
Estado: aprobado (pendiente de revisión final del usuario antes del plan)

## Objetivo

Capturar un segundo snapshot de cuotas **cerca del inicio de cada partido
apostado** ("línea de cierre"), para que el **CLV (Closing Line Value)** sea
medible. Hoy el sistema captura UN solo snapshot por evento (al generar los
picks por la mañana), así que `load_closing_odds` toma ese mismo snapshot como
"cierre" → el CLV sale ~0 por construcción y no se puede saber si el sistema
tiene edge real o si las pérdidas son varianza. Con una línea de cierre real,
`scripts/clv_analysis.py` (ya existente) mide CLV de verdad y, en semanas, dice
si el edge es real.

## Motivación (de esta sesión, 2026-06-26)

- En vivo: 156 apuestas liquidadas, acierto 44.2%, **ROI realizado −13.3%**
  (MLB −26%). Probabilidad estimada media 0.525 vs acierto real 0.442 →
  modelo sobreconfiado.
- El backtest OOS de MLB da +7.8% pero en vivo da −26%. Como entrada = cierre
  (un solo snapshot), el CLV no distingue precio/timing de varianza.
- Ver `[[oos-generalization-findings]]` y `[[dashboard-history-fast-follow]]`.

## Decisiones (confirmadas con el usuario)

1. **Estrategia: horaria, solo ligas con picks abiertos.** Una tarea cada hora
   captura cuotas frescas solo de ligas con `candidates_*.csv` abiertos cuyo
   partido apostado arranca pronto.
2. **Ventana: 120 minutos.** Se captura una liga cuando alguno de sus eventos
   apostados comienza dentro de los próximos 120 min.
3. **Regiones/mercados = los del run diario** (`us,eu,uk,au` × `h2h,spreads,
   totals`) para que el consenso de cierre se calcule sobre el MISMO conjunto de
   casas que la entrada (CLV apples-to-apples).
4. **Tope diario de créditos = 300/día** (`MAX_CLOSING_CREDITS_DAY`, default
   300; parametrizable). Además cede ante `requests_remaining` bajo: nunca le
   quita cuota al run de la mañana.

## Estado actual relevante

- `OddsStore.append_snapshot(league, events, captured_at=None)`
  (`src/sqp/storage/odds_store.py`): persiste un snapshot (filas con
  `captured_at, event_id, commence_time, home, away, market, outcome, point,
  price_decimal, bookmaker`). **Ya soporta múltiples snapshots por evento** —
  no requiere cambios.
- `OddsAPIClient` (`src/sqp/providers/odds_api.py`): `fetch_odds(league_id,
  sport_key, markets)` baja una liga (cada `EventOdds.event.start_time` =
  commence). Soporta `force_refresh` (saltar caché) en el `__init__`.
  `requests_remaining` / `requests_last` (créditos restantes / costo de la
  última llamada) se actualizan desde headers. `is_sport_active` no consume
  cuota.
- `load_closing_odds(root, league)`
  (`src/sqp/backtesting/roi_engine.py`): toma el último snapshot **estrictamente
  antes de commence**. Una vez existan snapshots de cierre, los usa solo. NO se
  toca.
- `scripts/clv_analysis.py`: ya mide CLV entrada-vs-cierre. NO se toca.
- `predictions_<league>.csv` tiene `event_id` + `start_time`;
  `candidates_<league>.csv` tiene `event_id` (los eventos apostados, sin
  `start_time`). El join da el commence de cada evento apostado sin gastar cuota.
- Tareas programadas existentes: 5 `SQP_*_Cdev` (ver `[[cdev-production-migration]]`).

## Componentes

### C1 — Lógica de captura (`src/sqp/pipeline/closing_capture.py`)

Funciones puras y testeables:

- `leagues_with_imminent_bets(predictions_dir, now, window_min=120) ->
  dict[str, list[str]]`
  Para cada `candidates_<league>.csv` no vacío: lee `predictions_<league>.csv`,
  cruza por `event_id`, y devuelve `{league: [event_ids cuyo start_time está en
  (now, now + window_min)]}`. Ligas sin evento inminente se omiten. No usa API.

- `capture_closing(predictions_dir, settings, *, window_min=120,
  max_credits=300, now=None, client=None) -> dict`
  Orquesta: para cada liga de `leagues_with_imminent_bets`, si el presupuesto lo
  permite (`spent_credits + estimated_cost <= max_credits` y
  `requests_remaining` por encima del margen de seguridad), hace
  `fetch_odds(force_refresh=True)`, filtra a los `event_id` apostados, y
  `OddsStore.append_snapshot`. Acumula créditos gastados (`requests_last`).
  Devuelve un resumen `{captured: {league: n_lines}, skipped_budget: [...],
  credits_spent: int}`. Best-effort: una excepción por liga se loguea y no
  aborta el resto.

Notas:
- El cliente se construye con `force_refresh=True` y las regiones del run diario.
- Filtrar los eventos al subconjunto apostado mantiene los snapshots magros
  (solo se persisten las líneas de los partidos que importan para el CLV).

### C2 — CLI (`scripts/capture_closing_odds.py`)

Wrapper headless: carga `Settings`, llama `capture_closing(...)`, loguea el
resumen (ligas capturadas, líneas, créditos gastados, ligas saltadas por
presupuesto). Args opcionales `--window-min` y `--max-credits` (defaults 120 /
300, o `MAX_CLOSING_CREDITS_DAY`).

### C3 — Batch (`CAPTURE_CLOSE.bat`)

Wrapper fino: `setlocal`, `cd /d %~dp0`, `PYTHONPATH=src`,
`ODDS_API_REGIONS=us,eu,uk,au`, `mkdir logs`, log a `logs\capture_close.log`,
`python scripts\capture_closing_odds.py >> logs\capture_close.log 2>&1`, con
`if errorlevel 1 goto :error` y bloque `:error` (patrón de los otros .bat). NO
abre navegador.

### C4 — Tarea programada `SQP_Capture_Close_Cdev`

Disparador **horario** (cada 1 hora), comando
`cmd /c "C:\dev\sports-quant-platform\CAPTURE_CLOSE.bat"`, misma config que las
otras `_Cdev`: usuario Richard, LogonType Interactive, RunLevel Limited,
StartWhenAvailable, MultipleInstances IgnoreNew, límite 72h. Creada con
PowerShell `New-ScheduledTask*` + `Register-ScheduledTask`.

## Flujo de datos

```
cada hora: SQP_Capture_Close_Cdev -> CAPTURE_CLOSE.bat -> capture_closing_odds.py
  leagues_with_imminent_bets(predictions, now, 120)   # sin cuota
    para cada liga con evento en <120 min:
      presupuesto OK? --no--> skip (log)
        |sí
      OddsAPIClient(force_refresh).fetch_odds -> filtrar event_ids -> append_snapshot
  -> data/odds/odds_<league>_<YYYYMM>.csv gana un snapshot 'de cierre'
días después:
  clv_analysis.py / realized_roi_backtest YA usan el último snapshot pre-commence
  -> CLV medible
```

## Manejo de errores y presupuesto

- Best-effort: cualquier fallo de fetch se loguea y continúa; nunca bloquea.
- `append_snapshot` es aditivo (idempotente en el sentido de que una captura
  repetida solo añade filas con otro `captured_at`; el CLV usa la última).
- Tope diario: `capture_closing` para de gastar al alcanzar `max_credits`. El
  conteo diario se deriva de las llamadas dentro de la corrida; como cada
  ejecución horaria es un proceso nuevo, el "diario" se aproxima por
  ejecución-horaria salvo que se persista un contador. **Decisión de
  implementación**: persistir el gasto del día en un archivo ligero
  (`data/odds/.closing_credits_<YYYYMMDD>`) para que el tope sea realmente
  diario across las 24 ejecuciones; el plan lo detalla.
- Si `requests_remaining` (de la última llamada conocida) está por debajo de un
  margen, se omite la captura para no competir con el run de la mañana.

## Qué NO cambia

- `OddsStore`, `load_closing_odds`, `realized_roi_backtest`, `clv_analysis.py`,
  el run diario, el modelo, el staking: sin cambios. Esta feature solo AÑADE
  snapshots; el resto de la cadena ya los aprovecha.

## Tests

- `leagues_with_imminent_bets`: evento dentro de ventana → incluido; fuera →
  excluido; liga sin candidates → omitida; reloj `now` inyectado.
- `capture_closing`: respeta `max_credits` (corta cuando se supera); salta
  cuando `requests_remaining` está bajo; persiste solo los `event_id` apostados;
  best-effort ante excepción de una liga. `OddsAPIClient` y `OddsStore`
  mockeados (sin red, sin disco real salvo tmp).
- Contador diario de créditos: acumula across ejecuciones simuladas del mismo
  día; resetea en día nuevo.

## Lenguaje obligatorio

El CLV es diagnóstico, no promesa: el snapshot de cierre es un proxy (consenso
mediano, cobertura limitada). Mantener "probabilidad estimada / edge estimado /
ROI realizado / CLV" como medidas separadas; ninguna garantía de profit.
