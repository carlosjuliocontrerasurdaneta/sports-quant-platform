# Validacion de la remediacion - audit-2026-10-15

Evidencia real de la fase de remediacion (2026-10-16). HEAD final `7861a7f` sobre la base `65368c8`; el arbol conserva sin commit la remediacion KI-073 (fuera de alcance). Todos los pytest con `-p no:cacheprovider`, `PYTHONPATH=src` y basetemp unico bajo `.codex-tmp/`.

## Validacion global (HEAD 7861a7f)

| Comando | rc | Resultado | Clasificacion |
|---|---|---|---|
| `python -m pytest -q -p no:cacheprovider --basetemp=.codex-tmp/pytest-rem-final` (suite completa) | 0 | **3252 passed, 1 skipped in 4021.60s** | OK. Los 3 ENVIRONMENTAL_FAILURE de la base (AUD-011) ya no aparecen con el basetemp dentro del repo |
| `ruff check src scripts tests` | 0 | All checks passed | OK |
| `mypy src` | 0 | Success: no issues found in 113 source files | OK |
| `python scripts/sync_agent_instructions.py --check` | 0 | synchronized | OK |
| `python scripts/validate_claude_model_routing.py` | 0 | OK | OK |
| `git status --porcelain -- src scripts configs *.bat` | 0 | vacio | La guarda de arbol sucio de `DIARIO_COMPLETO.bat:73` no abortara el run diario |

Base de comparacion (2026-10-15, HEAD 65368c8, fuente Claude): 3201 passed, 1 skipped, 3 ENVIRONMENTAL_FAILURE. Diferencia de +51 tests = tests nuevos de esta remediacion.

## Por lote: fallo antes / exito despues

| ID | Antes (codigo de HEAD previo) | Despues | Relacionados |
|---|---|---|---|
| AUD-003 | `tests/test_aud003_two_way_draw.py`: 10 failed / 2 passed | 12 passed | 830 passed (48 ficheros de probabilities/daily/revalidation/clv/roi_engine); intradia: 1 failed → 43 passed |
| AUD-002 | Clon `--no-tags --depth 1` de HEAD: 2 failed | 1 passed + 1 skipped (motivo explicito) | Local con tag: 116 passed |
| AUD-013 | — | YAML validado con `yaml.safe_load`: jobs `test, dependency-audit, test-windows, alerta-ci-rojo`; `needs` incluye `dependency-audit` | Ejecucion en GitHub: NOT_VERIFIABLE (sin push) |
| AUD-004/008 | `tests/pipeline/test_closing_capture_aud004.py`: 8 failed / 4 passed | 12 passed | 43 passed (closing + clv) |
| AUD-005 | 5 failed / 1 passed | 6 passed | 171 passed; revision Fable 9 + 362 passed |
| AUD-007 | 2 failed / 1 passed | 3 passed | 147 passed |
| AUD-006 | Contratos con settings de HEAD: 3 failed / 3 passed | 39 passed | 246 passed (routing, codex_review, astra, hook_targets) |
| AUD-010 | Test dinamico con hook de HEAD: 1 failed | 26 passed (`test_audit_hooks.py`) | idem |
| AUD-011 | Mismo basetemp, tests de HEAD: 3 failed | 3 passed | Suite completa sin fallos ambientales |
| AUD-009 | 1 failed / 2 passed (las 2 son contrapruebas) | 3 passed | 91 passed (run diario, team_names, AUD-003) |
| AUD-012 | 3 failed / 2 passed (contrapruebas) | 5 passed | 119 passed (cache, cliente, frescura, line shopping, gate, team totals, run diario) |
| AUD-001 | Reproduccion: `{'2026-06-10': 'odds-jun11', '2026-06-11': None}` | **Sin cambio (BLOQUEADO)** | Medicion de la regla rechazada sobre datos reales: MLB 606 asignaciones distintas (254 sin emparejar, 352 reasignadas); NBA 0; NHL 0 |

## Mediciones sobre datos reales usadas en la aceptacion

- AUD-003 (revision Fable, script `scratchpad/aud003_measure.py`): ultimo snapshot h2h por evento de todos los `data/odds/odds_*.csv` a 2 vias y tenis. NHL fair(home)+fair(away) = 1,000000 en 422/422 (antes 120/422 < 0,95, minimo 0,36); 0 eventos incompletos nuevos por el chequeo `outcomes` en mlb 2454, nba 262, ncaaf 730, nfl 379, nhl 422, wnba 390 y tenis 2002 eventos.
- AUD-008: `.closing_credits_20261011` = 310 con tope 300; totales diarios multiplos de 5, coherentes con mercados × regiones.
- AUD-001: `scratchpad/aud001_impact.py` (`load_closing_odds` + `results_{mlb,nba,nhl}.csv`, sin escrituras).

## Efectos observados de hooks

- `post-edit-format.sh` (`ruff check --fix`) borro imports anadidos antes de usarlos (AUD-003 en probabilities/revalidation; AUD-003 H1 en intraday_scan); repuestos y validados.
- `check-secrets` aviso sobre `tests/test_audit_hooks.py` (fixtures de claves falsas preexistentes); sin secretos reales.
- Ningun hook modifico ficheros fuera de los editados.

## No ejecutado / NOT_VERIFIABLE

- CI de GitHub del nuevo HEAD y pip-audit (sin push; red de pago no usada).
- Disparo real de los hooks PostToolUse con PowerShell (requiere sesion nueva).
- BAT, pipelines y APIs reales (no ejecutados).
