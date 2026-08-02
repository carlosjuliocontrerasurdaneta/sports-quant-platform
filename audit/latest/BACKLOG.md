# Backlog — Auditoría 2026-08-02

Lo que no se corrigió, por qué, y qué hace falta para cerrarlo.
Esfuerzo: S (< 1 h) · M (1–4 h) · L (> 4 h).

## Prioridad 1 — decisión del operador

| Ítem | Detalle | Esfuerzo | Riesgo | Criterio de aceptación | Decisión requerida |
|---|---|---|---|---|---|
| M-01: liquidar 87 filas pendientes | `python scripts/backfill_results.py --leagues brasileirao mlb --days 15` (ESPN/statsapi, GRATIS, append-only idempotente) y después `SETTLE_ALL.bat` (consume cuota The Odds API). Tenis: `scripts/backfill_tennis_results.py` | S | Bajo (flujo diario normal) | `health_check.py` sin WARN de filas pendientes | Sí — gasto de cuota |
| Commit de esta auditoría | 13 archivos modificados + 2 nuevos (ver CHANGES.md); diff revisado, suite verde | S | Bajo | Commit en main | Sí — sin autorización de commit vigente |

## Prioridad 2 — heredado, sigue abierto

| Ítem | Detalle | Esfuerzo | Riesgo | Criterio | Decisión |
|---|---|---|---|---|---|
| Guard de cuotas degeneradas `price_decimal = 1.0` | Hallazgo 07-24 (backlog previo): descartar líneas con precio ≤ 1.0 en ingestión o lectura | S | Bajo | Test con snapshot degenerado | No |
| M-7: permisos amplios en `settings.local.json` | `pip install *`, `python -` — archivo local del usuario | S | Bajo | Permisos acotados | Sí (archivo del usuario) |
| M-24: regiones del backfill histórico | Alinear `--regions` con el run vivo quintuplica el costo por llamada | S | Medio (gasto) | Decisión documentada | Sí (gasto) |
| Timing de entrada vs masa CLV=0.00 | Hipótesis del 07-27 sin investigar | M | Bajo | Análisis con timestamps de captura | No |
| KI-016: destino de `run_daily.py` | Depreciar o mantener como demo | S | Bajo | Decisión + docs | Sí |
| KI-002 / KI-005 / KI-006 / NFL OOS | Sin cambios desde la auditoría anterior (ver `.claude/memory/known-issues.md`) | M–L | — | — | Parcial |

## Prioridad 3 — mejoras opcionales

| Ítem | Detalle | Esfuerzo |
|---|---|---|
| Check de consistencia docs↔config | Comparar `picks.mode` real contra README/Estado del proyecto (evitaría otra A-01) | S |
| `_register` atómico | La escritura del registry sigue siendo no atómica (write_text directo); el patrón atómico ya existe en los stores | S |
| CI: matriz a 3.14 | Cuando setup-python lo sirva estable (nota ya en ci.yml) | S |
