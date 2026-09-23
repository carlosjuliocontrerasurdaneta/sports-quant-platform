# VALIDATION — ronda `audit-2026-09-22-r2` (diagnóstico)

Árbol evaluado: `main@9fa276a` + remediación r22 sin commit. El `VALIDATION.md` de r22 está preservado en `audit/audit-2026-09-22/`.

| Comando | rc | Resultado | Clasificación |
|---|---|---|---|
| `ruff check src scripts tests --no-cache` | 0 | `All checks passed!` | OK |
| `mypy src` | 0 | 106 ficheros, sin problemas | OK |
| `PYTHONPATH=src python -m pytest tests/ -q -p no:cacheprovider -m "not slow"` | 1 | **3 failed, 2049 passed, 225 deselected en 570,24 s** | `PRE_EXISTING_FAILURE`: los 3 son `AUD-004` (skill revertida antes de esta sesión) |
| `python scripts/sync_agent_instructions.py --check` | 0 | `synchronized` | OK |
| `python scripts/validate_claude_model_routing.py` | 0 | `OK` | OK |
| `gh run list --limit 5` | 0 | Último `35426317559` success sobre `9fa276a` | OK sobre `HEAD`; el diff sin commit **no** ha pasado por CI |
| `Get-ScheduledTask SQP_* \| Get-ScheduledTaskInfo` | 0 | Ninguna tarea del pipeline en fallo | OK |

Fallos de la suite:

- `tests/test_agent_instruction_sync.py::test_guardrails_remain_self_contained_in_each_general_loop`
- `tests/test_claude_system_contract.py::test_all_general_loops_finish_through_verification_gate`
- `tests/test_claude_system_contract.py::test_general_skills_share_an_identical_guardrail_block`

Esta es la **primera ejecución global** de la suite rápida sobre la remediación de r22. Todas sus pruebas pasan. No se ejecutó la suite `slow` ni `pip-audit`.

Desviación del contrato: pytest usó el temporal del sistema en lugar de `--basetemp=.codex-tmp/pytest`. Efecto: ninguna escritura dentro del árbol.
