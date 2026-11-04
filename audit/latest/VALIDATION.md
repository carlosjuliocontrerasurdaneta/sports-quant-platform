# VALIDATION: remediación de la ronda `audit-2026-11-03`

Aquí solo figura evidencia real: comandos ejecutados, su resultado y dónde se ejecutaron. Todos los pytest llevan `-p no:cacheprovider --basetemp=.codex-tmp/<x>`.

## Línea base (diagnóstico, 2026-11-03)

- Suite completa: 3434 passed y 1 skipped.
- `ruff`: rc=0.
- `mypy`: rc=0.
- Detalle en `MANIFEST.json` → `tests_initial`.

## Por lote

### O (`ead24b2`), en el worktree del implementador

- `tests/test_diario_espera_arbol.py`: 4 escenarios, con el BAT real copiado a un repo temporal.
- Ese test junto con `test_bat_files_integrity`, `test_run_status` y `test_orchestrator_safety`: 100 passed.
- `tests/test_health_scheduled_tasks.py`: 8 passed.
- `test_claude_system_contract`, `test_agent_instruction_sync`, `test_claude_model_routing` y `test_hook_targets`: 114 passed.
- `scripts/sync_agent_instructions.py --check`: rc=0.
- `.claude/settings.json`: el coordinador comparó los conjuntos de permisos antes y después.
  - Solo se quita `Bash(gh pr merge *)` del allow.
  - Se añaden 12 deny.
  - El resto de claves no cambia.
- El coordinador revisó el diff del BAT.

### Q (`77110b4`)

- Primera pasada del implementador: 1 failed, el esperado antes del arreglo de AUD-013.
- Después, `test_intraday_gate.py`: 11 passed.
- Re-ejecución del coordinador en el worktree: `test_intraday_gate`, `test_intraday_scan`, `test_validate_oos_frozen_params` y `test_validate_oos_exit_code` dan **31 passed**.

### D (`df015bf`)

- Implementador: 286 passed y 1 skipped en los tests del componente.
- **Revisión Fable (APTO):** 177 passed. Cubre los 4 tests nuevos más `test_revalidation`, `test_odds`, `test_odds_store`, `test_results_backfill`, `test_calibrator` y `test_storage`.
- Medición de AUD-020 sobre los calibradores vivos, solo lectura y solo agregados:

  | Calibrador | gap |
  |---|---|
  | wnba_spreads | 0,0019 |
  | mlb_spreads | 0,0004 |
  | mlb_totals | 0,0000 |

### G2 (`1e50400`)

- **Revisión Fable (APTO CON CAMBIOS):** 355 passed.
- Tras aplicar los cambios:
  - `test_audit_g2_precio`, `test_served_store`, `test_served_market_shrink`, `test_reports` y `test_html_report`: 72 passed.
  - Test real de reconciliación de cabecera: 12 passed. La reproducción de Fable pasa de 3 reescrituras completas a 1.

### G1 (`914707c`)

- **Revisión Fable (APTO CON CAMBIOS):** 131 passed.
- 13 tests nuevos fallan sobre la base `aa8db2f` (comprobado con `git archive`).
- Producción migra sin transiciones.
- Hay 0 líneas de cuarto en los seis cortes agotados y en `nhl|*`.
- Tras los 4 LOW, en el worktree: `test_prediction_gate`, `test_gate_status_cli`, `test_claude_system_contract` y `test_config_yaml_keys` dan 139 passed.

### Integración en `main` (coordinador)

- Tests de gate, precio y contrato combinados, tras G1, G2 y D: **188 passed**.
- `ruff check src scripts tests`: All checks passed.
- `mypy src`: Success, 116 ficheros.

## Suite completa sobre `main`

1. **Primera ejecución (`1e50400`/`914707c`), con `-x`:** detenida por el hook de parada en `tests/test_accuracy_mode.py::test_accuracy_mode_demo_pipeline_selects_by_probability`.
   - Causa: la guarda de AUD-005 anula el stake plano del modo accuracy cuando el EV en la casa de ejecución es ≤ 0. Ese es el criterio de aceptación de AUD-005.
   - El test fijaba el contrato anterior. Producción usa el modo edge: accuracy se revirtió el 2026-07-31, y en modo edge la guarda no se activa.
   - Arreglo (`1832272`): el test aísla la guarda, y un test nuevo fija su efecto.
2. **Segunda ejecución (`1832272`), sin `-x`:** **1 failed, 3500 passed, 1 skipped** en 52 min.
   - Falló `tests/research/test_measure_tier_a_gap.py::test_load_frozen_classifier_isolates_sources_when_hashes_diverge`.
   - Causa: AUD-010 añadía «(pre-penalización)» también a las llamadas antiguas a `classify()` sin `ev_riesgo`. Esas llamadas incluyen el clasificador congelado del pre-registro tier A.
   - Arreglo (`4d10703`): el sufijo solo aparece cuando se pasa `ev_riesgo` y es NaN. Test nuevo: `test_classify_sin_ev_riesgo_conserva_el_motivo_de_siempre`.
   - Tras el arreglo, `test_audit_g2_precio`, `test_tipster`, `tests/research/test_measure_tier_a_gap`, `test_reports` y `test_html_report` dan **153 passed**.
3. **Tercera ejecución (`4d10703`):** ver el anexo al final.

## Fuera de la validación

- No se ejecutaron el BAT de producción, `validate_oos` completo ni `scripts/research/intraday_gate_analysis.py`: leen o escriben `data/`.
- Las pruebas de «falla antes» son razonadas en la mayoría de los IDs de O, Q, D y G2. G1 sí se comprobó contra la base.
- El CI real se comprueba tras el push (AUD-024: acciones fijadas por SHA).
- No hubo verificación independiente: es la siguiente fase.

## Anexo: tercera ejecución de la suite completa (`4d10703`)

- Comando: `python -m pytest -q -p no:cacheprovider --basetemp=.codex-tmp/full-rem3`, sin `-x`, sobre `main` en `4d10703`.
- Resultado: **3502 passed, 1 skipped, 6 warnings** en 3438,61 s (57 min 18 s). Ningún fallo.
- Respecto a la línea base (3434 passed): 68 tests más, que son los nuevos de esta remediación.
- Los avisos son `RuntimeWarning` ya conocidos de `tie_adds_goal` en `adapters.py:146`, emitidos por `test_market_tuning`. No están relacionados con esta ronda.
