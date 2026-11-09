# Verificación independiente — ronda `audit-2026-09-18`

Fecha: 2026-11-09. Verificador: escalón Fable (`claude-fable-5-1`) sin contexto del implementador, según `audits/prompts/verificar-remediacion.md`. Las pruebas las ejecutó el coordinador (Opus) porque el verificador trabajó solo con lectura.

## 1. Decisión

**APTO CON PENDIENTES.**

- No hay ningún P0/P1 abierto.
- AUD-001, 002, 003, 005, 006 y 007 están corregidos y siguen corregidos.
- AUD-004 sigue abierto: el código es correcto, pero depende de una acción del operador en el host.
- No se detectan regresiones.

## 2. Alcance y HEAD

- Hallazgos AUD-001 a AUD-007 de `FINDINGS.md` y `BACKLOG.md`. B-02, que es heredado, queda como no verificable aquí.
- Código verificado: `main` @ `a97c7b94870c7e68503748403c66f6ad3e556bb7`.
- Rondas posteriores que tocaron el mismo código: 09-22, 09-22-r2, 09-23, 10-15 y 10-18. Se verifica contra el HEAD actual.

## 3. Estado por hallazgo

| ID | Prioridad | Estado | Evidencia |
|---|---|---|---|
| AUD-001 | P2 | Corregido y sigue corregido | `scripts/gate_status.py:43-84,147-150` usa `load_prediction_gate`, `market_allowed`, `prediction_gate_block` y `evaluate_markets` sobre `ServedStore.load_all_graded()`, la misma muestra que `scripts/run_all.py`. No queda ninguna regla propia. Skill alineada: `.claude/skills/clv-shadow-exit/SKILL.md:65-68`. |
| AUD-002 | P2 | Corregido, superado y endurecido | La raíz JSON se valida como objeto en `prediction_gate.py:1060-1063` y `degradation.py:188-191`. El fallback pasa por `auto_pauses_from_persisted_registry` (`degradation.py:194-253`), rediseñado en la ronda 09-22-r2 y en KI-061/063/064. |
| AUD-003 | P2 | Corregido en código y datos | `calibrator.py:48-52,425,925-933,964-970,1016,1077`; `health.py:105,140`; `html_report.py:266-268`. `calibration_methods.json` no contiene claves sandbox. `promotion_log.csv` registra la fila `demoted` del 2026-09-18. |
| AUD-004 | P2 | Reabierto (persistente, en el host) | Mitigación en `health.py:294,315,353,475,575`. El `pipeline_health.json` del 2026-11-09 indica `scheduled_tasks.history_enabled: false`. Lo corresponde al operador desde una consola elevada (KI-054). |
| AUD-005 | P3 | Corregido; el residual se cierra en este mismo cambio | `run_all.py` anuncia lo habilitado con `gate_allowed_markets`. La doble llamada a `evaluate_markets` por run, que quedaba como residual, se elimina en la rama `fix/pendientes-20261109`. |
| AUD-006 | P3 | Corregido | Regla única `markets_for_family` (`daily.py:65`), usada por `daily.py:788` y `closing_capture.py:122,162`. |
| AUD-007 | P3 | Parte (a) superada; parte (b) vigente; síntoma corregido | Excluir `audit/` del escaneo se revirtió a propósito en la ronda 10-18 (AUD-006), por ser un repositorio público. La parte (b), `_symbolic` (`_secret_literals.py:41-69`), sigue suprimiendo el falso positivo. `tests/test_audit_hooks.py:90-137` lo fija. No es una regresión. |

## 4. Validación ejecutada

| Comando | Resultado |
|---|---|
| `PYTHONPATH=src python -m pytest -q -p no:cacheprovider --basetemp <scratch>/pt tests/test_gate_status_cli.py tests/test_registry_root_not_object.py tests/test_sandbox_calibration_keys.py tests/test_health_scheduled_tasks.py tests/test_closing_capture_markets.py tests/test_audit_hooks.py tests/test_prediction_gate.py tests/test_live_gate_integration.py` (en `main`, HEAD de arriba) | 206 passed en 172,87 s |
| Suite global, `ruff check src scripts tests` y `mypy src` sobre `0e4061c` (mismo código de `src` y `scripts` que `a97c7b9`, que solo añadió notas Obsidian) | 3.569 passed, 1 skipped; ruff y mypy limpios |

## 5. Pendientes

- **AUD-004 / KI-054 (operador, consola elevada):** `wevtutil sl Microsoft-Windows-TaskScheduler/Operational /e:true`.
- **AUD-003:** la adopción del calibrador per-game bajo `mlb_h2h` es una decisión de modelo y sigue abierta en `Obsidian/Tareas.md`.
- **AUD-006:** no se comprobaron en el log real los 5 créditos por captura de tenis.
