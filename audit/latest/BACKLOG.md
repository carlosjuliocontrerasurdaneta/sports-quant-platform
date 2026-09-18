# Backlog — ronda `audit-2026-09-18`

Derivado de `FINDINGS.md` (línea base). Orden por prioridad, impacto,
dependencias y riesgo de la corrección. **Toda entrada está pendiente de
autorización**: consolidar no autoriza corregir. Los cambios que tocan
parámetros de modelo/calibración (AUD-003) o el host de producción (AUD-004)
requieren alcance específico del operador según `MODEL_ROUTING.md`
(clase «modelo/promoción» y «producción»).

| # | ID | Prio | Sev | Cambio mínimo | Archivos | Pruebas | Criterio de aceptación | Dependencias / riesgo | Autorización |
|---|---|---|---|---|---|---|---|---|---|
| 1 | AUD-002 | P2 | MEDIUM | En `load_prediction_gate` y `load_degradation_registry`, validar que la raíz sea `dict` antes de `.get` (patrón de `clv.load_clv_gate`); devolver `{}`. En `run_all.py`, envolver el fallback `paused_from_registry(load_degradation_registry(...))` para que un registro ilegible degrade a «sin auto-pausas» con aviso, nunca aborte | `src/sqp/risk/prediction_gate.py:544-547`; `src/sqp/risk/degradation.py` (`load_degradation_registry`); `scripts/run_all.py:190-194` | Tests parametrizados con `[]`, `null`, `1`, `"x"`, JSON roto, `markets` no dict → `{}` sin excepción, para ambos lectores; test de `run_all` (o del bloque extraído) con registro de degradación no objeto → continúa | Ningún registro sintácticamente válido puede lanzar desde los lectores; default-deny y «sin auto-pausas» conservados; caso objeto válido sin cambio de comportamiento | Ninguna; cambio local sin efecto en umbrales | pendiente |
| 2 | AUD-001 | P2 | MEDIUM | Reescribir `scripts/gate_status.py` para (a) mostrar el veredicto persistido (`load_prediction_gate` + `market_allowed`) y (b) el progreso mediante `evaluate_markets(ServedStore(ROOT).load_all_graded())`, eliminando la regla paralela; actualizar el docstring y `clv-shadow-exit/SKILL.md:61` (o apuntar a `update_prediction_gate.py --dry-run` si existe) | `scripts/gate_status.py`; `.claude/skills/clv-shadow-exit/SKILL.md:61`; prompts generados si la skill se sincroniza | Test del CLI con stream sintético: eventos repetidos, favoritos acertados peor que el no-vig, fecha anterior a `VALIDATION_START`, test consumido, pestillo → nunca «PASAN» cuando `market_allowed` es falso | La salida del script coincide exactamente con `prediction_gate.json` en `allowed`; el progreso usa `n` por unidad independiente | Independiente de #1; no cambia umbrales ni desbloquea mercados | pendiente |
| 3 | AUD-005 | P3 | LOW | En `run_all.py`, construir `ok` desde `load_prediction_gate(bets_dir)` + `market_allowed` DESPUÉS de `write_prediction_gate`; conservar `decided` solo para el resumen de progreso; evitar la doble llamada a `evaluate_markets` (que `write_prediction_gate` devuelva o exponga `decided`) | `scripts/run_all.py:296-313`; opcionalmente `src/sqp/risk/prediction_gate.py:428-470` | Test que capture el log con un registro previo `entry_test_at` consumido / `latched` → lista anunciada vacía | El mensaje «habilitados para stake real» coincide con el registro persistido | Después de #2 (comparten vocabulario de «progreso» vs «veredicto») | pendiente |
| 4 | AUD-003 | P2 | MEDIUM | (a) `promote_calibrators`: rechazar claves con `PERGAME_SUFFIX` salvo bandera explícita `--adopt-pergame` que las instale bajo `<liga>_h2h` tras `cross_evaluate_on_settled`; (b) demover `mlb_h2h_pergame` del registro live o adoptarla (decisión del operador), con rastro en `promotion_log.csv`; (c) `_live_calibration_markets` y la tarjeta del dashboard ignoran/marcan claves que `calibration_key` no produce; (d) `Obsidian/Tareas.md:104` refleja el estado real | `src/sqp/calibration/calibrator.py:745-843`; `src/sqp/calibration/pergame.py`; `src/sqp/monitoring/health.py:80-103`; `src/sqp/audit/html_report.py:259-275`; `data/models/calibration_methods.json` (dato); `Obsidian/Tareas.md` | Promoción completa con `x_h2h_pergame` en staging → live sin la clave; `_live_calibration_markets` con clave sandbox → no listada; `calibrate_probability("mlb","h2h")` con solo la sandbox → no-op | El registro live solo contiene claves resolubles; health/dashboard coinciden con lo servido | **Decisión de modelo** (adoptar vs demover) → escalón `fable` por clase; la parte (a)/(c)/(d) es código y no cambia umbrales | requiere alcance específico |
| 5 | AUD-004 | P2 | MEDIUM | Habilitar el historial del Programador (`wevtutil sl Microsoft-Windows-TaskScheduler/Operational /e:true`, elevación) y documentarlo en `set_tasks_unattended.ps1`/runbook; en `health_check` u `open_dashboard.ps1`, leer `LastTaskResult`/`NumberOfMissedRuns`/`LastRunTime` de las 5 tareas hacia `pipeline_health.json` con aviso si la diaria no corrió ayer | host (registro de eventos); `scripts/set_tasks_unattended.ps1`; `scripts/open_dashboard.ps1`; `src/sqp/monitoring/health.py` | Manual: tras habilitar, `Get-WinEvent` devuelve eventos 100/102 de la siguiente ejecución; test unitario del parser de estado de tareas con salida simulada | Una ausencia de run queda explicada por el registro del Programador o por el log del BAT | **Producción / elevación** (proceso ELEVADO aunque la cuenta sea admin, memoria `tareas-programador-s4u`) | requiere alcance específico |
| 6 | AUD-006 | P3 | LOW | En `capture_closing`, pasar `markets="h2h"` cuando `_league_meta(league)["family"] == "tennis"` (reutilizar la regla de `daily.py:704`, idealmente extraída a un helper compartido) | `src/sqp/pipeline/closing_capture.py:118`; `src/sqp/pipeline/daily.py:704` | Test de `capture_closing` con cliente falso que registre `markets` para una liga de tenis y otra de equipo | Tenis: 5 créditos por captura; resto sin cambio | Ninguna | pendiente |
| 7 | AUD-007 | P3 | LOW | (a) Excluir `audit/**` y `audits/**` del escaneo de `check-secrets.sh` (como `data/`, `logs/`) o escanear solo ficheros cuyo hash cambió desde el último aviso; (b) en `ASSIGNMENT`, descartar valores que sean el mismo identificador asignado o contengan `\r`/`\n` escapados | `.claude/hooks/check-secrets.sh`; `.claude/hooks/_secret_literals.py:8-12`; `tests/test_audit_hooks.py` | Añadir a `tests/test_audit_hooks.py` la línea reproducida (asignación reflexiva + CRLF escapado dentro de una cadena JSON) → 0 hallazgos; un secreto real en `src/` sigue detectándose | El aviso solo aparece para ficheros escritos en el turno y con literal real | Ninguna | pendiente |

## Fuera del backlog (informativo, sin autorización requerida para ignorar)

- OBS-C1 (48/50 cortes del gate): vigilar; el aviso de re-pre-registro ya
  existe en `write_prediction_gate`.
- OBS-C2 (disponibilidad del host, 55,8 % sin cierre): límite operativo; si
  se quiere cobertura nocturna, es una decisión de infraestructura, no de
  código.
- OBS-C3 (`.tests-pending` entre sesiones; 489,8 s vs 600 s): candidato a
  limpiar el marcador al inicio de sesión o subir el timeout; medir antes.
- OBS-C4 (`health_check` reporta modelos ML sin consumidor): etiqueta
  «experimental» en la salida.
- OBS-C6 (B-02, acciones CI sin pin): heredado, sigue abierto.
- OBS-O1..O3 (OpenAI): seguimiento.

## Validaciones recomendadas por lote

- Lote A (#1, #2, #3): `pytest tests/test_prediction_gate.py tests/test_live_gate_integration.py` + nuevos tests; `ruff`; `mypy`.
- Lote B (#4): `pytest tests/test_calibration_live.py tests/test_pergame_calibration.py tests/test_health.py tests/test_html_report.py` + nuevos; revisión `fable` de la decisión.
- Lote C (#5): manual en el host; `pytest tests/test_open_dashboard.py` si se toca el parser.
- Lote D (#6, #7): `pytest tests/test_clv.py tests/test_frescura_cuotas_diario.py tests/test_audit_hooks.py` + nuevos.
- Cierre: `pytest -q -p no:cacheprovider --basetemp=.codex-tmp/pytest`, `ruff check src scripts tests`, `mypy src`; BATs inspeccionados aparte.
