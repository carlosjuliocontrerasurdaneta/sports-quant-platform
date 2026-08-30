# Anclas canónicas del proyecto

Ubicaciones verificadas para no redescubrirlas en cada auditoría. **Son
punteros, no valores**: confirmar que la ruta sigue existiendo y leer el valor
del código o de la configuración. Nunca citar de memoria un umbral, una fórmula
ni un parámetro desde este archivo.

Si una ruta ya no existe, el hallazgo es que la ruta cambió: registrarlo y
actualizar este archivo en la fase de corrección, no adivinar la nueva.

## Estructura

| Capa | Ruta |
|---|---|
| Paquete Python | `src/sqp/` |
| Pruebas | `tests/` |
| Scripts operacionales | `scripts/` |
| Configuración | `configs/default.yaml`, `configs/leagues/`, `configs/venues.yaml` |
| Carga de configuración y precedencia | `src/sqp/config.py` |
| Entrada diaria del pipeline | `src/sqp/pipeline/daily.py`, `scripts/run_all.py` |
| Órdenes operativas | `SETTLE_ALL.bat` → `RUN_DIARIO_ALL.bat` (liquidación antes de generación) |

## Cuantitativo

| Área | Ruta |
|---|---|
| Cuotas, conversión y no-vig | `src/sqp/markets/odds.py`, `src/sqp/markets/vig.py` |
| Validez de precio (fuente única) | `is_usable_price` en `src/sqp/markets/odds.py` |
| Edge | `src/sqp/markets/edge.py` |
| Movimiento de línea | `src/sqp/markets/line_movement.py` |
| Calibración | `src/sqp/calibration/calibrator.py`, `data.py`, `metrics.py`, `pergame.py` |
| Backtesting y ROI | `src/sqp/backtesting/engine.py`, `src/sqp/backtesting/roi_engine.py` |
| Sintonización de ratings | `src/sqp/backtesting/tuning.py` |
| Etiquetas y evaluación | `src/sqp/evaluation/labels.py`, `compare.py`, `model_vs_market.py` |
| Información del edge | `src/sqp/evaluation/edge_information.py` |
| Segmentos de diagnóstico | `src/sqp/audit/segments.py` |
| CLV | `src/sqp/audit/clv.py` |
| Features | `src/sqp/features/` |
| Settlement | `src/sqp/settlement/` |
| Persistencia | `src/sqp/storage/` |
| Proveedores externos | `src/sqp/providers/` |

## Riesgo

| Gate o control | Ruta |
|---|---|
| Kelly y fracción | `src/sqp/risk/kelly.py` |
| Bankroll y exposición | `src/sqp/risk/bankroll.py` |
| Gate de CLV | `src/sqp/risk/clv_gate.py` |
| Gate de predicción | `src/sqp/risk/prediction_gate.py` |
| Monitor de degradación | `src/sqp/risk/degradation.py` |
| Salud del sistema | `src/sqp/monitoring/health.py`, `scripts/health_check.py` |

## Umbrales

Los umbrales de muestra vigentes y su origen están tabulados en
`.claude/loops/quant/STATES.md`. Esa tabla es la fuente; no duplicarla aquí ni
en el informe. Si un umbral necesario no aparece ni en el código, ni en la
configuración, ni en una decisión humana registrada **antes** de evaluar, el
hallazgo es `EVIDENCIA_NO_VERIFICABLE` con una propuesta de umbral.

## Contexto y memoria

| Qué | Ruta |
|---|---|
| Hallazgos previos y su estado | `.claude/memory/known-issues.md` |
| Historial de sesiones y auditorías | `.claude/memory/session-summaries.md` |
| Decisiones del proyecto | `.claude/memory/project-decisions.md` |
| Router de operaciones quant | `.claude/loops/quant/00-quant-operations-router.md` |
| Estados de salida de los loops | `.claude/loops/quant/STATES.md` |
| Política de modelos | `.claude/automation/MODEL_ROUTING.md` |
| Reglas de dominio | `.claude/rules/` |
| Contratos de `.claude` | `tests/test_claude_system_contract.py`, `tests/test_claude_model_routing.py` |

Los dos archivos de tests de contrato son de lectura obligada antes de tocar
cualquier cosa bajo `.claude/`: fijan la identidad byte a byte del bloque de
guardarraíles de los loops, el cierre por `/verification-gate`, la política de
modelos y la integridad referencial del routing. Modificar `.claude/` sin
ejecutarlos es cómo se introdujo el hallazgo `A-1` de la auditoría 2026-08-30.

## Invariantes de sistema a comprobar, no a asumir

Leer su valor real antes de razonar sobre él: `shadow_mode`, `pick_mode`,
bankroll y balance, `max_plausible_edge`, fracción de Kelly y
`calibration.auto_promote`. Un informe que los cite sin haberlos leído en esta
ejecución está inventando evidencia.
