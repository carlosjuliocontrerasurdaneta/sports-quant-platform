---
tags: [arquitectura, sqp]
creada: 2026-07-08
actualizada: 2026-07-08
---

# Arquitectura del sistema

Código en `src/` (paquete `sqp`), scripts en `scripts/`, tests en `tests/` (321 al 2026-07-08), configs en `configs/`.

## Flujo de datos end-to-end (run diario)

```
Proveedores                Pipeline                     Salidas
───────────                ────────                     ───────
The Odds API (odds) ──┐
ESPN scoreboard     ──┼─→ run_all.py → daily.run_league ─→ candidates_<liga>.csv
MLB Stats API       ──┘      │                            predictions_<liga>.csv
                             │                            report_latest.html
                     ratings + señales (adapters)
                             │
                     calibración (registry live)
                             │
                     edge + penalización EV + caps de riesgo
                             │
                     shadow / clv_gate → stake final
```

Al día siguiente: `SETTLE_ALL` liquida contra resultados → `settled_<liga>.csv` → alimenta auditoría ROI, ledger de banca, CLV y entrenamiento de calibradores.

## Módulos principales (`src/sqp/`)

| Módulo | Responsabilidad |
|---|---|
| `providers/` | The Odds API, ESPN (resultados, tenis), MLB Stats API. Timeouts 30s, parsers defensivos |
| `sports/` | Adapters por familia (Poisson/soccer+MLB+NHL con Dixon-Coles, Normal-margin/basket+NFL, Tennis Elo); registry + normalización de nombres |
| `models/` | Distribuciones, Elo, park factor (ON en MLB), rest/B2B (OFF), starters (OFF) |
| `markets/` | Conversión de odds, de-vig (power/proporcional), edge + penalización EV (`adjusted_edge`) |
| `risk/` | Kelly con caps, ledger de banca (`bankroll.py`), **gate de CLV** (`clv_gate.py`, 2026-07-08) |
| `calibration/` | Calibradores por (liga, mercado), gates OOS, staging/promoción. Ver [[Conocimiento/Calibración]] |
| `pipeline/` | `daily.py` (orquestación por liga), `probabilities.py` (helpers) |
| `settlement/` | Liquidación idempotente, grading, persistencia atómica con reconciliación de esquema |
| `storage/` | ResultsStore (histórico append-only, game_id), StartersStore, ServedStore (stream de calibración), OddsStore |
| `backtesting/` | Engine walk-forward, tuning por grid, roi_engine (espejo del staking live) |
| `audit/` | Reporte ROI/CLV, dashboard HTML, patrones |

## Entrypoints

- **Producción**: `scripts/run_all.py` (multi-liga, guard de presupuesto, banca dinámica, reporte consolidado) vía `DIARIO_COMPLETO.bat`.
- `scripts/run_daily.py`: herramienta manual/demo, NO producción (KI-016).
- CLIs: `backfill_results`, `backfill_tennis_results`, `train_calibration`, `promote_calibration`, `validate_oos`, `tune_ratings`, `backtest_history`, `bankroll_status`.

## Decisiones estructurales clave

- Overrides por liga en `configs/leagues/ratings.yaml` (config, no código); borrar el YAML = rollback a defaults de familia.
- `settled_*.csv` es la **fuente única de verdad** para ROI, banca y calibración; escritura atómica + unión de columnas (auto-sana esquemas viejos).
- El gate de CLV se define en `risk/` sin imports del pipeline (evita ciclo daily → clv → roi_engine → daily); el registro lo escribe la auditoría CLV diaria.
- Dos capas de exposición: por liga (`max_daily`) + global (`max_total`).

Relacionado: [[Arquitectura/Automatización y operación]], [[Decisiones/Registro de decisiones]].
