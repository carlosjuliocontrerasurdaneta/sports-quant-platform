# Cambios — remediación autorizada, ronda `audit-2026-09-18`

Autorización: orden del operador en sesión («si, hazlo») sobre la propuesta
de remediar los 7 confirmados de `FINDINGS.md`. Fuente: `audit/latest/FINDINGS.md`
+ `BACKLOG.md`. Base al empezar: `5952164` (main, sincronizado), working tree
con solo `audit/` modificado; guard scope (`src scripts configs *.bat`) limpio.
Línea base de tests: 2191 passed / 1 skipped (suite completa), ruff 0, mypy 0.

Ejecutor: `claude-opus-5` (sesión principal). Revisión independiente en el
escalón `fable` para AUD-003 (clase «contrato de artefacto persistido /
parámetro de modelo»), ver `VALIDATION.md`.

Decisiones tomadas por el ejecutor bajo la orden global (registradas en
`.claude/memory/project-decisions.md`):
- AUD-003: **demover** la clave sandbox del registro live (cero cambio en las
  probabilidades servidas; restaura el contrato documentado), NO adoptarla
  bajo `mlb_h2h` (eso sigue siendo la tarea abierta de `Obsidian/Tareas.md:104`).
- AUD-004: la parte de host (habilitar el historial del Programador) exige
  elevación y el clasificador de permisos la denegó: queda **bloqueada** con
  el comando exacto documentado; la parte de código se aplicó.

| ID | Estado inicial | Causa | Archivos | Cambio | Prueba discriminante | Aceptación | Riesgo residual | Estado final |
|---|---|---|---|---|---|---|---|---|
| AUD-002 | confirmado (revalidado: ambos lectores sin comprobar la raíz; fallback de `run_all` fuera del `try`) | validación sintáctica sin validación de tipo | `src/sqp/risk/prediction_gate.py` (`load_prediction_gate`), `src/sqp/risk/degradation.py` (`load_degradation_registry`, nueva `auto_pauses_from_persisted_registry`, logger), `scripts/run_all.py` (fallback) | raíz comprobada antes de `.get` (patrón de `clv_gate`); el fallback de `run_all` pasa por un helper que nunca lanza | `tests/test_registry_root_not_object.py` (13 failed antes → 21 passed después) | `[]`, `null`, `1`, `"x"`, `true`, `markets` no dict → `{}` sin excepción en los dos lectores; objeto válido sin cambio | ninguno conocido | corregido, pendiente de verificación |
| AUD-001 | confirmado (regla paralela reproducida con la versión de HEAD: 300 filas del mismo evento → «PASAN EL GATE, n=300») | script con su propia regla | `scripts/gate_status.py` (reescrito), `.claude/skills/clv-shadow-exit/SKILL.md:61` | el CLI muestra [1] veredicto persistido (`load_prediction_gate`+`market_allowed`) y [2] progreso con `evaluate_markets` sobre `load_all_graded()`; sin regla paralela; docstring con el umbral vigente | `tests/test_gate_status_cli.py` (escenario OpenAI → n=1, `muestra_insuficiente`, sin «PASAN»; pestillo respetado; ventana; `--min-n` solo filtra; candado sin `binomtest`/`pick_history`) | salida coincide con `prediction_gate.json`; ejecutado contra datos reales: «Habilitados: ninguno (default-deny)» | `prompts` sincronizados (`--check` OK) | corregido, pendiente de verificación |
| AUD-005 | confirmado (revalidado en `run_all.py:307-313`) | anuncio desde la tabla pre-pestillo | `scripts/run_all.py`, `src/sqp/risk/prediction_gate.py` (nueva `gate_allowed_markets`) | el log anuncia habilitados leyendo el registro escrito (con pestillo); `decided` solo para progreso | `tests/test_gate_status_cli.py::test_gate_allowed_markets_reads_persisted_verdict_not_pre_latch_table` (corte elegible con test consumido: tabla dice `mlb|h2h`, registro dice ninguno) | mensaje == registro | doble `evaluate_markets` por run se mantiene (coste menor; cambiar la firma de `write_prediction_gate` afectaría a 29 llamadas) | corregido, pendiente de verificación |
| AUD-003 | confirmado (registro live y staging con `mlb_h2h_pergame`; `promotion_log.csv:102`) | promoción sin distinguir claves sandbox | `src/sqp/calibration/calibrator.py` (`PERGAME_SUFFIX`, `is_sandbox_key`, rechazo en `promote_calibrators`, democión en sync completa y en `auto_promote`, nueva `demote_calibrators`, `_append_promotion_log`, borrado de sidecars), `src/sqp/calibration/pergame.py` (reexporta el sufijo), `src/sqp/monitoring/health.py` (`_live_calibration_markets` ignora sandbox; `_orphan_calibration_entries` la señala), `src/sqp/audit/html_report.py` (filtra y avisa), `scripts/promote_calibration.py` (`--demote/--reason`), `Obsidian/Tareas.md:104`; **dato**: `data/models/calibration_methods.json` (live: 3 claves), `mlb_h2h_pergame_calibration_beta.joblib` retirado de live (sigue en staging), `promotion_log.csv` +1 fila `demoted` | ver columnas anteriores | `tests/test_sandbox_calibration_keys.py` (8 failed antes → 9 passed después, incluido el candado sobre el dato real) | registro live solo con claves resolubles; health/dashboard coherentes; `calibrate_probability("mlb","h2h")` no-op explícito | la adopción per-game sigue pendiente de decisión (tarea abierta). Revisión `fable`: 4 hallazgos, 3 aplicados en sesión (`--demote` exige `--yes`; rastro `demoted: sync completa`; `_set_best_method` rechaza sandbox en live) + 1 sugerencia no aplicada (ver `VALIDATION.md`) | corregido, pendiente de verificación |
| AUD-004 | confirmado (`IsEnabled=False`) | historial del Programador apagado; sin rastro independiente del BAT | `src/sqp/monitoring/health.py` (`scheduled_tasks_status`, `_scheduled_tasks_raw`, bloque `scheduled_tasks` en `pipeline_health.json`, solo para `root == ROOT` en Windows), `scripts/set_tasks_unattended.ps1` (runbook del comando elevado) | health expone `LastRunTime`/`LastTaskResult`/`Missed` de las 5 tareas y avisa: historial apagado, diaria sin lanzarse > 1,5 d (distinto de «falló»), rc ≠ 0, tarea ausente | `tests/test_health_scheduled_tasks.py` (7 passed); `health_check.py` real: `WARN (0 errors, 1 warnings)` con el aviso del historial | una ausencia de lanzamiento queda visible y explicada como tal | **parcial/bloqueado**: `wevtutil sl … /e:true` requiere consola elevada; el clasificador denegó ejecutarlo. El operador debe ejecutarlo; hasta entonces `health_check` sale WARN a propósito | parcial (código corregido; host pendiente del operador) |
| AUD-006 | confirmado (HEAD: tenis → `h2h,spreads,totals`) | mercados de la captura no alineados con la generación | `src/sqp/pipeline/daily.py` (`markets_for_family`, regla única), `src/sqp/pipeline/closing_capture.py` | la captura pide los mercados de la familia | `tests/test_closing_capture_markets.py` (reproducción con HEAD: `['h2h,spreads,totals']`; ahora `h2h` en tenis) | tenis 5 créditos/captura | ninguno | corregido, pendiente de verificación |
| AUD-007 | confirmado (reproducido en sesión; también al escribir el informe) | `--with-git` re-escanea `git status`; `ASSIGNMENT` acepta asignaciones reflexivas y CRLF escapado | `.claude/hooks/check-secrets.sh` (excluye `audit/`, `audits/`), `.claude/hooks/_secret_literals.py` (`_symbolic`: reflexiva/llamada/CRLF; nombre entre comillas admitido para JSON) | ver anterior | `tests/test_audit_hooks.py` (+3 tests: reflexivas no marcan; literales reales sí, incluido JSON `"api_key": "…"`; `audit/` excluido y `src/` sigue bloqueando) | `EVIDENCE.json:315` → 0 coincidencias; `src/` con literal → rc 2 | los fixtures de `tests/test_audit_hooks.py` siguen marcándose (esperado: contienen literales de prueba). **Corrección posterior (revisión de Codex al cierre, `codex review`):** la primera exclusión `*/audit/*` sin anclar también casaba con `src/sqp/audit/` (paquete de producción) y lo dejaba sin escanear; se ancló a la raíz (`audit/*\|audits/*` relativo a `CLAUDE_PROJECT_DIR`) y el test cubre `src/sqp/audit/html_report.py` y `scripts/audit_team_names.py` → rc 2 | corregido, pendiente de verificación |

## Efectos de hooks observados

- `post-edit-format.sh` (ruff `--fix`) eliminó un import no usado en
  `html_report.py` cuando se añadió antes de su uso; se reordenaron los
  edits. Ningún otro autofix.
- `check-secrets.sh`: tras AUD-007 ya no marca `audit/latest/openai/EVIDENCE.json`;
  sigue marcando los fixtures de `tests/test_audit_hooks.py` (esperado).
- Ficheros reescritos con Python quedaron en CRLF; se normalizaron a LF
  (`.gitattributes`: `eol=lf`) sin cambio de contenido.

## Fuera de alcance (no tocado)

- Adopción del calibrador per-game bajo `mlb_h2h` (decisión de modelo aparte).
- Habilitar el historial del Programador (elevación; comando en
  `scripts/set_tasks_unattended.ps1` y en el aviso de `health_check`).
- OBS-C1..C6 y OBS-O1..O3 (informativas).
