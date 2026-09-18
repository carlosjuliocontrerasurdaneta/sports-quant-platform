# Validación — remediación, ronda `audit-2026-09-18`

Todas las ejecuciones con `-p no:cacheprovider` y `--basetemp` bajo `.codex-tmp/`
(ignorado). Python 3.14.4, win32. Base `5952164`.

## Línea base (antes de editar)

| Comando | rc | Resultado |
|---|---:|---|
| `pytest -q -p no:cacheprovider --basetemp=.codex-tmp/pytest -x` (suite completa) | 0 | 2191 passed, 1 skipped, 24:58 |
| `ruff check src scripts tests` | 0 | All checks passed |
| `mypy src` | 0 | 105 ficheros sin errores |

## Fallo antes / éxito después, por ID

| ID | Evidencia «antes» | Evidencia «después» |
|---|---|---|
| AUD-002 | `tests/test_registry_root_not_object.py` sobre HEAD: **13 failed**, 8 passed (6 gate + 6 degradación + helper inexistente) | 21 passed; `test_degradation.py` + `test_prediction_gate.py`: 93 passed |
| AUD-001 | `gate_status.py` de HEAD (`git show`) con 300 filas del mismo evento: «PASAN EL GATE … mlb\|h2h 300 hit_rate 1.0 … Pasan: 1» | `tests/test_gate_status_cli.py` 6 passed (n=1, `muestra_insuficiente`, sin «PASAN»); CLI contra datos reales: «Habilitados para stake real: ninguno (default-deny)»; `test_prediction_gate.py` 61 passed (incluye el candado del umbral en documentos) |
| AUD-005 | test `test_gate_allowed_markets_reads_persisted_verdict_not_pre_latch_table`: la tabla pre-pestillo anunciaba `mlb\|h2h` con test consumido (aserción explícita del comportamiento antiguo) | `gate_allowed_markets` → `[]`; 67 passed en el lote |
| AUD-006 | `closing_capture.py` de HEAD con cliente falso en tenis: `['h2h,spreads,totals']` | `tests/test_closing_capture_markets.py` 4 passed; `test_frescura_cuotas_diario.py` + `test_clv.py`: 31 passed |
| AUD-007 | 3 tests nuevos en `tests/test_audit_hooks.py`: **5 failed** (reflexivas/llamadas marcadas; `"api_key": "…"` en JSON no detectado; `audit/` escaneado) | 60 passed (`test_audit_hooks`, `test_hook_targets`, `test_portable_setup`); `python .claude/hooks/_secret_literals.py audit/latest/openai/EVIDENCE.json` → 0 coincidencias; el hook dejó de marcar ese fichero en los comandos siguientes |
| AUD-003 | `tests/test_sandbox_calibration_keys.py` sobre HEAD: **8 failed**, 1 passed | 12 passed (incl. candado sobre `data/models/calibration_methods.json` real, invariante en `_set_best_method`, rastro de sync y dry-run del CLI); lote `test_pergame_calibration` + `test_calibration_live` + `test_calibrator`: 72 passed; lote con `test_health` + `test_html_report`: 73 passed (2:58) |
| AUD-004 | — (control de host; sin test «antes») | `tests/test_health_scheduled_tasks.py` 7 passed; `test_health.py` 20 passed; `health_check.py` real → `WARN (0 errors, 1 warnings)`: aviso del historial con el comando; consulta real al Programador: 5 tareas, último rc 0 |

## Dato de producción (AUD-003)

`python scripts/promote_calibration.py --demote mlb_h2h_pergame --reason "AUD-003 …"`
(ejecutado antes de que el CLI exigiera `--yes`; ahora lo exige):
registro live antes `{mlb_h2h_pergame, mlb_spreads, mlb_totals, wnba_spreads}`
→ después `{mlb_spreads, mlb_totals, wnba_spreads}`; `mlb_h2h_pergame_calibration_beta.joblib`
retirado de `data/models/` (sigue en `staging/`); `promotion_log.csv` +1
(`demoted: AUD-003 …`). Reproducible por el candado
`test_live_registry_on_disk_has_no_sandbox_key`.

## Revisión independiente `fable` (AUD-003, clase «contrato de artefacto persistido»)

Agente `independent-code-reviewer` con `model: fable`, solo lectura. Verificó
(a) probabilidades/umbrales servidos intactos; (b) sin bypass en los llamadores
actuales; (c) sidecars borrados junto al `.joblib` (mejora respecto a HEAD);
(d) sin colisión de sufijo con mercados reales; (e) esquema del log conservado;
(f) test discriminante. Emitió 4 hallazgos, **todos atendidos en la misma
sesión**:

1. MEDIUM — `--demote` mutaba producción sin confirmación → ahora exige
   `--yes` (dry-run por defecto); test `test_cli_demote_is_dry_run_without_yes`.
2. LOW-MEDIUM — la democión por sincronización completa no dejaba rastro →
   `promote_calibrators(keys=None)` escribe `demoted: sync completa (...)`;
   test `test_full_sync_demotion_leaves_a_trail_in_promotion_log`.
3. LOW — el invariante vivía solo en la promoción → `_set_best_method`
   rechaza claves sandbox en live (`ValueError`); test
   `test_set_best_method_refuses_sandbox_key_in_live`.
4. Sugerencia (duplicación de la escritura del log): no aplicada (fuera del
   alcance mínimo; `_append_promotion_log` queda disponible para unificar).

Nota de proceso: el agente señaló que no recibió `run_id`/`review_tree` del
protocolo Cross-Review V2 y por eso no escribió `claude-body.json`; esta
revisión se usó como revisión de clase (routing), no como ronda V2.

## Validación global (después)

| Comando | rc | Resultado | Clasificación |
|---|---:|---|---|
| `pytest -q … --basetemp=.codex-tmp/pytest` (suite completa, 1.ª pasada tras la remediación) | 0 | 2246 passed, 2 failed, 1 skipped (15:35) | los 2 fallos (`test_cross_review_e2e_v2.py::test_a_gitignore_edit_still_moves_the_snapshot`, `::test_info_exclude_is_still_able_to_hide_content`) = **ENVIRONMENTAL_FAILURE**: `WinError 267` en `.codex-tmp/pytest/...` porque el revisor `fable` ejecutó pytest con el MISMO `--basetemp` en paralelo (pytest vacía el basetemp al arrancar). Reejecutados aislados: 2 passed |
| `pytest -q -p no:cacheprovider --basetemp=.codex-tmp/pytest-final` (suite completa, 2.ª pasada tras los ajustes de la revisión) | 0 | **2251 passed, 1 skipped** (13:58) | PASS (60 tests nuevos respecto a la línea base de 2191) |
| `ruff check src scripts tests` | 0 | All checks passed | — |
| `mypy src` | 0 | 105 ficheros sin errores | — |
| `python scripts/sync_agent_instructions.py --check` | 0 | synchronized (skill editada) | — |
| `git diff --check` | 0 | sin espacios finales; ficheros normalizados a LF | — |

## No ejecutado

BATs (inspeccionados: no cambian), `pip-audit` (CI), `codex review`, run real
del pipeline. La corrección queda **pendiente de verificación independiente**.
