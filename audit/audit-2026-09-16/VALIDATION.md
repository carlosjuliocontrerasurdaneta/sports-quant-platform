# Validación de la remediación — ronda `audit-2026-09-16`

Fecha: 2026-09-17. Intérprete: Python 3.14.4 (win32). Basetemp propio
`.codex-tmp/pytest-claude-20260917` salvo donde se indica.

## Línea base (antes de corregir)

| Comando | Resultado |
|---|---|
| `pytest -q -p no:cacheprovider --basetemp=.codex-tmp/pytest-claude-20260917 -m "not slow"` | 1936 passed, 225 deselected, exit 0 |
| `ruff check src scripts tests` | 0 |
| `mypy src` | 0 (105 ficheros) |
| Base Git | `44e48f2`; working tree sucio (57 entradas preexistentes) |

## Por lote

| ID | Comando | Antes | Después | Clasificación |
|---|---|---|---|---|
| AUD-001 | `pytest tests/test_distributions.py` | **10 failed**, 8 passed (los 10 casos de cuarto; los 4 de no-regresión pasan) | 18 passed | NEW test discriminante |
| AUD-001 | `pytest tests/test_distributions.py tests/test_settlement_math.py tests/test_distribution_validation.py` | — | 106 passed | OK |
| AUD-001 | `pytest -m "not slow" tests/test_{audit_pipeline_isolation,decision_probability,decision_probability_views,f5,independent_pricing,mlb_features,pipeline_demo,pricing_prompt_formulas,probable_pitchers_series,soccer_avg_goals}.py` | — | 166 passed, 5 deselected | OK |
| AUD-001 | Revisión escalada `fable` (Agent `independent-code-reviewer`, `model: "fable"`) | — | 0 defectos; 18.432 combinaciones (λ∈[0,05;6], dc_rho, dispersion_k, score_rho, spreads −3,75…3,75, totales 0,25…9,75, max_goals∈{1,2,3,15}) sin excepción; slack `1−w−p` = 0,0 exacto; `pytest` 18 + 136 + 85 passed; ruff/mypy 0 sobre los ficheros tocados | OK; 1 hallazgo adyacente no ticketeado (Normal, Δ ≤ 0,25 pp) |
| AUD-002 | Reproducción del diagnóstico (funciones del proyecto) | `realized_roi` 0,5 vs `_summarize` 0,0; mezcla 0,75 vs 1,50 | — | REPRODUCED (antes) |
| AUD-002 | `pytest tests/test_realized_roi_consistency.py` | no ejecutable sin parche (`stash` denegado por el clasificador; el módulo nuevo `realized_roi_parts` no existe en HEAD) | 3 passed | NEW test |
| AUD-002 | `pytest -m "not slow"` sobre tests de liquidación/ROI/informes/dashboard/backtest/bankroll (grep `settle|roi|report|html|dashboard|backtest|segment|audit|bankroll|ledger`) | — | 351 passed, 9 deselected (249 s) | OK |
| AUD-003 | `git archive HEAD` (44e48f2) → `sync_agent_instructions.py --check` / `pytest tests/test_agent_instruction_sync.py` / `tests/test_tennis_params.py` | rc 1 / 1 failed + 5 errors / 1 failed | tras `f93bdc1`: `--check` rc 0; 107 passed (`test_claude_system_contract`, `test_claude_model_routing`, `test_agent_instruction_sync`, `test_hook_targets`) tras el merge | PRE_EXISTING_FAILURE corregida |
| AUD-004 | `pytest --basetemp=.codex-tmp/pytest tests/audit/test_history_loader.py` | `PermissionError [WinError 5]` en setup | 4 passed (padre renombrado a `.codex-tmp/pytest.bloqueado-20260916`) | ENVIRONMENTAL, mitigada |
| AUD-004 | `takeown`, `icacls`, `Remove-Item`, `Rename-Item` sobre el residuo | — | acceso denegado (sin elevación) | bloqueado parcial (operador) |
| AUD-005 | `pytest tests/test_line_shopping.py tests/test_config_yaml_keys.py` | — | 21 passed (2 nuevos) | NEW test |
| AUD-006 | `echo '{"tool_name":"Bash","tool_input":{"command":"cat README.md"}}' \| python .claude/hooks/_targets.py --with-git \| wc -l` | árbol sucio entero (≥ 5 rutas) | 0 | REPRODUCED → corregido |
| AUD-006 | `pytest tests/test_hook_targets.py tests/test_audit_hooks.py` | — | 45 passed (2 nuevos) | OK |
| AUD-007 | `pytest tests/test_feature_shadow.py tests/test_distributions.py tests/test_settlement_math.py tests/test_settle_candidates.py` | — | 77 passed (1 nuevo) | OK |

## Global (tras todos los lotes, antes del merge)

| Comando | Resultado |
|---|---|
| `ruff check src scripts tests` | 1 error (E741 en el test nuevo) → corregido → All checks passed |
| `mypy src` | Success: no issues found in 105 source files |
| `pytest -q -p no:cacheprovider --basetemp=.codex-tmp/pytest-claude-20260917 -m "not slow" -q` | exit 0, 100 % (1958 seleccionados / 225 deselected) |

## Git

| Paso | Resultado |
|---|---|
| `f93bdc1` contrato de auditoría: fuentes canónicas, prompts regenerados y tests (completa 44e48f2) | 45 ficheros del trabajo preexistente del 2026-09-16 |
| `4f06b4f` remediación: AUD-001, 002, 005, 006, 007 | 16 ficheros, 5 tests nuevos |
| `git fetch` → `HEAD..origin/main` = 6, `origin/main..HEAD` = 3 | divergencia confirmada |
| `git merge origin/main` → `31cfdb0` | 3 conflictos en Obsidian (`Bitácora.md`, `Bitácora/2026-09-16.md`, `Tareas.md`) resueltos conservando ambos lados; `sync --check` rc 0 y 107 tests de contratos `.claude` verdes tras el merge |
| `git push origin main` | `a2ee66c..31cfdb0` |
| CI | run 35224249563: **success** (test 3.11, 3.12, 3.13, 3.14 y test-windows; `alerta-ci-rojo` skipped) |

## Corrección al diagnóstico

La tarea `SQP_Diario_Completo_Cdev` ejecuta `C:\dev\3\sports-quant-platform`
(`a2ee66c` = `origin/main`, guard scope limpio), **no este clon**
(`C:\dev\6`). La consecuencia «producción ejecuta código no validado» de
AUD-003 era incorrecta: el árbol divergente era el clon de trabajo. Producción
recibirá AUD-001/002/005/006/007 cuando `C:\dev\3` haga `git pull`, acción
sobre producción que queda para el operador.

## No ejecutado

Suite `slow` (225), `pip-audit` local (lo ejecuta el CI), BATs, `codex review`
(sin cuota hasta el 21/09 según la bitácora remota).
