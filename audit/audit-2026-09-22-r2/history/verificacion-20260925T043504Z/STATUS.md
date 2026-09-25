# STATUS — ronda `audit-2026-09-22-r2`

- **Fases ejecutadas:** diagnóstico (Claude) y consolidación con un solo auditor.
- **Remediación autorizada (operador, 2026-09-22 noche):** `AUD-001` y `AUD-004`; después `AUD-002` y `AUD-003`. **No ejecutada:** verificación independiente.
- El `STATUS.md` de la ronda `audit-2026-09-22` está preservado en `audit/audit-2026-09-22/STATUS.md`.

| ID | Sev. | Prio | Remediación | Verificación | Evidencia | Próxima acción |
|---|---|---|---|---|---|---|
| `AUD-001` | HIGH | P0 | **corregido** (commits `c6f1971`, `d718fa1`, `af9d156`; push) | pendiente | Guarda: 0 líneas; CI `35804096043` success | Comprobar el run del 23/09 12:00 |
| `AUD-002` | HIGH | P1 | **corregido** (escritor estricto + reintento de `OSError` + centinela `prediction_gate.blocked` + recuperación con pestillo `bloqueo_de_lectura`; degradación con fallback desde el log) | pendiente | 2 revisiones Fable y 2 de Codex atendidas; 16 pruebas fallan contra `HEAD`; suite 2075 passed | Verificación independiente |
| `AUD-003` | MEDIUM | P1 | **corregido** (INFO en 42–50 cortes; `error` + orden de re-pre-registro sólo > 50; `fwer_bound` conservado) | pendiente | Pruebas 49/51 cortes | Verificación independiente |
| `AUD-004` | MEDIUM | P1 | **corregido** (restaurada desde `HEAD`; copia en el scratchpad de la sesión) | pendiente | 74/74 en los tests de contrato | Ninguna |
| `CLN-001` | — | P3 | **parcial** (47 directorios temporales regenerables de pytest/mypy borrados, ~245 MB) | — | Conservados: 8 con ACL denegada (NO_VERIFICABLE), 4 con documentos en la raíz, `pytest` (basetemp canónico), `sqp-agent`, `cache-audit-*`, `review-transient-*` y todos los ficheros sueltos | Inspeccionar los 8 denegados con la cuenta que los creó |

## IDs de la ronda `audit-2026-09-22` (revalidados; esto no sustituye a su verificación formal)

| ID (r22) | Estado revalidado |
|---|---|
| `AUD-007`, `AUD-002`, `AUD-003`, `AUD-004`, `AUD-005`, `AUD-006` | verificado-corregido; commiteado en `d718fa1`, CI verde |
| `AUD-001` | reabierto (premisa) → `AUD-003` r2 |
| `AUD-008` | persistente, fuera del repositorio (KI-056) |
| r18 `AUD-004` | persistente (KI-054) |
