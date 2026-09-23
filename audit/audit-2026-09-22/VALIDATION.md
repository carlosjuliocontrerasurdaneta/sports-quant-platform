# VALIDATION — ronda `audit-2026-09-22`

**Fase de remediación: NO EJECUTADA**, así que no hay validación de correcciones
que registrar.

Las validaciones ejecutadas durante el **diagnóstico** están registradas con su
comando, código de salida y clasificación en `claude/EVIDENCE.json` y resumidas
en `claude/REPORT.md` §9. En síntesis:

| Comando | Código | Resultado | Clasificación |
|---|---|---|---|
| `ruff check src scripts tests` | 0 | `All checks passed!` | OK |
| `mypy src` | 0 | `Success: no issues found in 106 source files` | OK |
| `pytest -q -p no:cacheprovider --basetemp=.codex-tmp/pytest-aud0922` | 1 | 1 failed, 2263 passed, 1 skipped en 4031,25 s | `ENVIRONMENTAL_FAILURE` (ver `AUD-004`) |
| El mismo test, aislado, ×5 | 0 | 4 passed en 11,03 / 10,06 / 12,50 / 8,82 / 12,14 s | OK |
| `PYTHONPATH=src pytest tests/ -q -x --maxfail=1 -m "not slow"` | 0 | 2040 passed, 225 deselected en **796,09 s** | evidencia de `AUD-007` |
| `pip-audit -r requirements.lock` | 0 | `No known vulnerabilities found` | OK |
| `scripts/sync_agent_instructions.py --check` | 0 | `Agent instructions: synchronized` | OK |
| `gh run list --branch main --limit 8` | 0 | Último run `35426317559` **success** sobre el commit base | OK — CI verde |
| `Get-ScheduledTask SQP_* \| Get-ScheduledTaskInfo` | 0 | 5 tareas, ninguna en fallo | OK |

**El único fallo de la suite está clasificado, no ocultado.**
`tests/test_audit_atomic_readers.py::test_reader_contention_preserves_atomicity[False-csv]`
falló por un `assert` de reloj de pared (4,485 s frente a un límite de 4 s) con
la máquina ejecutando en paralelo la tarea diaria, el dashboard y `pip-audit`:
la suite tardó 4031 s frente a los 838 s de la ronda anterior. Reejecutado
aislado cinco veces, verde en las cinco. Se clasifica como
`ENVIRONMENTAL_FAILURE` **y además** se reporta como defecto de determinismo
(`AUD-004`): no se ha debilitado ni desactivado ninguna aserción.

---

Este fichero sustituye al `VALIDATION.md` de la ronda `audit-2026-09-18`,
preservado íntegro en `audit/audit-2026-09-18/VALIDATION.md`
(sha256 `f7b05eece5e034ec…`).
