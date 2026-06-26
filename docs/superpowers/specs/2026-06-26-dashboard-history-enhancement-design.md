# Diseño: Historial mejorado del dashboard + auto-open interactivo

Fecha: 2026-06-26
Estado: aprobado (pendiente de revisión final del usuario antes del plan de implementación)

## Objetivo

Al terminar el flujo diario, abrir automáticamente el dashboard (solo en sesión
interactiva). Ampliar la pestaña **Historial** para mostrar un historial general
con desglose por Fecha, Deporte, Línea, Home y Away, y tarjetas de totales
(Picks, Picks cerrados, Wins, Losses) que se recalculan con los filtros. Ocultar
de la vista los picks pasados que nunca se cerraron, sin borrar datos.

## Decisiones de producto (confirmadas con el usuario)

1. **"Ocultar picks no cerrados en el pasado" = solo filtrar la vista**, NO borrar
   del disco. `data/bets/` y `pick_history.csv` quedan intactos. Reversible.
   Respeta `data-integrity-rules`.
2. **Auto-open solo en sesión interactiva.** Bajo el Programador de tareas no se
   intenta abrir (evita el `0xC000013A` y la ausencia de escritorio). El
   `report_latest.html` se escribe siempre.
3. **Desglose = tabla plana con filtros + tarjetas de totales** que recalculan
   sobre el conjunto filtrado (extensión de la pestaña Historial actual).
4. **"Total Picks" = cerrados + abiertos vigentes.** "Picks cerrados" = liquidados.
   La distinción exige una fuente que incluya picks abiertos.
5. **Home/Away se persisten en la liquidación (approach A)** y se backfillean los
   liquidados pasados desde los snapshots de cuotas.
6. **Fecha = fecha del PARTIDO** (no la de generación del pick). Unifica la regla
   de ocultar (`fecha_partido < hoy AND sin result → ocultar`).
7. **Abiertos vigentes = solo accionables (stake > 0).** Homogéneo con los
   cerrados, que solo contienen apuestas realmente staked.

## Estado actual relevante

- `src/sqp/audit/html_report.py`: dashboard de 4 pestañas. `_history_section`
  ya lista liquidados (`load_all_settled`) con filtros Fecha/Deporte/Mercado y
  columnas Fecha/Deporte/Mercado/Selección/Línea/Cuota/Stake/Resultado/PnL/Edge/Prob.
- `src/sqp/audit/report.py`: `load_all_settled` (lee `settled_*.csv`),
  `load_all_candidates` (lee `candidates_*.csv`, **une home/away** desde
  `predictions_*.csv`), `rank_candidates` (accionables, stake>0).
- `settled_*.csv` esquema actual: `event_id, league, market, selection, line,
  price_decimal, bookmaker, estimated_probability, implied_probability_novig,
  estimated_edge, kelly_stake_pct, stake, data_label, model_probability, flags,
  generated_at, result, pnl, settled_at[, calibrated_probability, adjusted_edge,
  edge_penalty, books_count]`. **No tiene home/away ni fecha de partido.**
- `data/odds/odds_<league>_<YYYYMM>.csv`: snapshots con `captured_at, event_id,
  commence_time, home, away, market, outcome, point, price_decimal, bookmaker`.
  Mismo `event_id` de The Odds API que los settled → join fiable.
- Flujo diario: `DIARIO_COMPLETO.bat` → `SETTLE_ALL.bat` (settle) →
  `RUN_DIARIO_ALL.bat` → `run_all.py` (genera dashboard, escribe `report_latest.html`).
- `open_in_browser()` existe; `run_all.py --open-dashboard` existe pero
  `RUN_DIARIO_ALL.bat` lo omite a propósito (0xC000013A bajo el scheduler).

## Componentes

### C1 — Auto-open interactivo (`DIARIO_COMPLETO.bat`)

Tras el `call RUN_DIARIO_ALL.bat` exitoso, añadir:

```bat
if defined SESSIONNAME start "" "%~dp0data\predictions\report_latest.html"
```

- No-op bajo el Programador de tareas (SESSIONNAME no definido en sesión 0 / sin
  escritorio). Abre el bookmark estable en sesión interactiva.
- No se toca `run_all.py` ni `--open-dashboard` (la generación ya ocurre dentro).
- Patrón idéntico al fix de `REVIEW_CALIBRATION_MLB_H2H.bat`.

### C2 — Enriquecer la liquidación con home/away + fecha de partido (`settlement/runner.py`)

En `fetch_and_settle`, donde se califica cada apuesta contra el resultado del
partido (que ya contiene los equipos y la fecha del juego), persistir tres
columnas nuevas en la fila liquidada:

- `home` (equipo local)
- `away` (equipo visitante)
- `game_date` (fecha del partido, `YYYY-MM-DD`, derivada del commence/resultado)

Compatibilidad: columnas añadidas al final; los lectores existentes
(`load_all_settled`, auditoría) no se rompen. Filas antiguas sin estas columnas
se tratan como vacías hasta el backfill (C3).

### C3 — Script de backfill (`scripts/backfill_settled_teams.py`)

Para cada `data/bets/settled_<league>.csv`:
1. Cargar las filas.
2. Construir un mapa `event_id → (home, away, commence_date)` desde
   `data/odds/odds_<league>_*.csv` (cualquier fila del evento; son constantes).
3. Rellenar `home`/`away`/`game_date` SOLO en filas que estén vacías (idempotente).
4. Reescribir el CSV preservando el resto de columnas.

- No gasta cuota de API (trabaja sobre datos guardados).
- Filas cuyo `event_id` no esté en los snapshots quedan vacías (cosmético); se
  reporta el conteo de no resueltas.

### C4 — Loader de unión para el historial (`report.py`)

Nueva función `load_history(predictions_dir, bets_dir) -> pd.DataFrame` que une:

- **Cerrados**: `load_all_settled(bets_dir)`. Campos: home, away, line, market,
  selection, price_decimal, stake, result, pnl, game_date (o fallback).
- **Abiertos vigentes**: `rank_candidates(load_all_candidates(predictions_dir))`
  (stake>0). `result` vacío. `game_date` = fecha de `start_time`/commence.

Salida normalizada con columnas comunes y una bandera `is_closed`
(`result` no vacío). Sin solape: los candidatos de hoy aún no están liquidados.

Fecha de fila (`fecha`):
- Cerrados: `game_date` (de C2/C3); si falta, fallback a `generated_at[:10]`.
- Abiertos: `start_time[:10]`.

### C5 — Vista Historial ampliada (`html_report.py`, `_history_section`)

Sustituir la fuente (`load_all_settled`) por `load_history(...)`.

**Columnas**: Fecha · Deporte · **Mercado** · Línea · Home · Away · Selección ·
Cuota · Stake · Resultado · PnL. Se conserva **Mercado** (necesario para
interpretar Línea/Selección). Se retiran del Historial las columnas Edge est. y
Prob. est. actuales (pertenecen a la pestaña Picks del Día / Auditoría; el
Historial se centra en el resultado realizado, no en la estimación previa).

**Filtros (desglose)**: Deporte · Línea · Home · Away · Desde/Hasta (Fecha).
Cada fila lleva `data-fecha`, `data-league`, `data-line`, `data-home`, `data-away`.

**Tarjetas de totales** (recalculan en cliente sobre las filas visibles):
- **Picks** = filas visibles
- **Picks cerrados** = filas visibles con `result` en (win/loss/push/void)
- **Wins** = `result == win`
- **Losses** = `result == loss`

**Regla de ocultar (no destructiva)**: en el render, NO emitir filas abiertas
(`result` vacío) cuyo `game_date < hoy`. Equivalente: una fila se muestra si
`is_closed` OR `game_date >= hoy`. Implementación en el servidor (Python) al
construir las filas, de modo que la fila pasada-sin-cerrar nunca llega al HTML.

## Flujo de datos

```
SETTLE_ALL → settle_all.py → fetch_and_settle (C2: escribe home/away/game_date)
RUN_DIARIO → run_all.py → html_dashboard → _history_section → load_history (C4)
                                                              → render + ocultar (C5)
                                                              → report_latest.html
DIARIO_COMPLETO.bat (C1): if defined SESSIONNAME → abre report_latest.html
backfill (C3): una vez, rellena los 165 liquidados pasados
```

## Manejo de errores

- C1: el `start` guardado nunca rompe el flujo (run ya terminó; `start` es
  detached).
- C2: si falta el equipo/fecha en el resultado, se escribe vacío (no aborta la
  liquidación, que es idempotente).
- C3: filas no resueltas se dejan vacías y se reportan; idempotente.
- C4/C5: si una fuente está vacía, se usa la otra; si ambas vacías, mensaje
  "sin historial".

## Qué NO cambia

- No se borra ni muta `data/bets/` ni `pick_history.csv` (solo se AÑADEN columnas).
- Pestañas Picks del Día / Auditoría / Patrones sin cambios.
- `run_all.py`, guard de presupuesto, motor de riesgo: sin cambios.

## Tests

- `load_history`: unión sin solape; normalización de columnas; `is_closed`.
- Regla de ocultar: fila abierta con `game_date` pasada → no aparece; abierta de
  hoy → aparece; cerrada pasada → aparece.
- Conteos de tarjetas: Picks / Picks cerrados / Wins / Losses sobre un set mixto.
- C2: la fila liquidada incluye home/away/game_date.
- C3: backfill idempotente; rellena vacíos; no pisa existentes; reporta no resueltas.
- Lenguaje de apuestas: el historial sigue mostrando probabilidad estimada / edge
  estimado / ROI realizado por separado (regla `betting-output-rules`).

## Lenguaje obligatorio

Mantener "probabilidad estimada", "edge estimado" y "ROI realizado" separados;
ninguna certeza ni profit garantizado en la UI.
