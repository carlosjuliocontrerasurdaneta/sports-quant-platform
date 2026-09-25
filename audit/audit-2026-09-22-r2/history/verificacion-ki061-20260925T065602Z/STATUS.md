# STATUS — ronda `audit-2026-09-22-r2`

- **Fases ejecutadas:** diagnóstico (Claude) y consolidación con un solo auditor.
- **Remediación autorizada (operador, 2026-09-22 noche):** `AUD-001` y `AUD-004`; después `AUD-002` y `AUD-003`. **Verificación independiente: ejecutada el 2026-09-25** (`VERIFICATION.md`), veredicto **APTO CON PENDIENTES**. Versión previa de este fichero en `history/verificacion-20260925T043504Z/`.
- El `STATUS.md` de la ronda `audit-2026-09-22` está preservado en `audit/audit-2026-09-22/STATUS.md`.

| ID | Sev. | Prio | Remediación | Verificación | Evidencia | Próxima acción |
|---|---|---|---|---|---|---|
| `AUD-001` | HIGH | P0 | **corregido** (commits `c6f1971`, `d718fa1`, `af9d156`; push) | **VERIFICADO-CORREGIDO** | Guarda: 0 líneas; CI `35804096043` success | Comprobar el run del 23/09 12:00 |
| `AUD-002` | HIGH | P1 | **corregido** (escritor estricto + reintento de `OSError` + centinela `prediction_gate.blocked` + recuperación con pestillo `bloqueo_de_lectura`; degradación con fallback desde el log) | **VERIFICADO-MITIGADO** (residual: fallo correlacionado del centinela; ver REG-001) | 2 revisiones Fable y 2 de Codex atendidas; 16 pruebas fallan contra `HEAD`; suite 2075 passed | Verificación independiente |
| `AUD-003` | MEDIUM | P1 | **corregido** (INFO en 42–50 cortes; `error` + orden de re-pre-registro sólo > 50; `fwer_bound` conservado) | **VERIFICADO-CORREGIDO** | Pruebas 49/51 cortes | Verificación independiente |
| `AUD-004` | MEDIUM | P1 | **corregido** (restaurada desde `HEAD`; copia en el scratchpad de la sesión) | **VERIFICADO-CORREGIDO** | 74/74 en los tests de contrato | Ninguna |
| `CLN-001` | — | P3 | **parcial** (47 directorios temporales regenerables de pytest/mypy borrados, ~245 MB) | — | Conservados: 8 con ACL denegada (NO_VERIFICABLE), 4 con documentos en la raíz, `pytest` (basetemp canónico), `sqp-agent`, `cache-audit-*`, `review-transient-*` y todos los ficheros sueltos | Inspeccionar los 8 denegados con la cuenta que los creó |

## IDs de la ronda `audit-2026-09-22` (revalidados; esto no sustituye a su verificación formal)

| ID (r22) | Estado revalidado |
|---|---|
| `AUD-007`, `AUD-002`, `AUD-003`, `AUD-004`, `AUD-005`, `AUD-006` | verificado-corregido; commiteado en `d718fa1`, CI verde |
| `AUD-001` | reabierto (premisa) → `AUD-003` r2 |
| `AUD-008` | persistente, fuera del repositorio (KI-056) |
| r18 `AUD-004` | persistente (KI-054) |

**Regresión encontrada en la verificación:** REG-001 (MEDIUM/P2, ligada a AUD-002). Con `degradation_pause.json` ilegible, un mercado que se degrada por primera vez no se pausa. Próxima acción: corrección y test. **Aviso operativo:** 52 cortes en el gate (> 50): re-pre-registro pendiente del operador.

**REG-001 (KI-061), remediado el 2026-09-25** (versión previa de este fichero en `history/remediacion-reg001-20260925T045722Z/`).
- Con el registro de degradación ilegible, el fallback evalúa el gate de hoy (mismos umbrales que el monitor, pasados desde `run_all`) sobre el estado reconstruido desde `degradation_log.csv`, y no escribe nada.
- Antes, con un mercado degradado HOY y el registro corrupto, devolvía solo `{'nba': ['h2h']}`. Ahora devuelve `{'mlb': ['totals'], 'nba': ['h2h']}`.
- Tests: `test_degradation.py::test_fallback_con_registro_ilegible_pausa_un_mercado_que_se_degrada_ahora` y `::test_fallback_conserva_la_histeresis_del_log`.
- Estado: **IMPLEMENTADO, pendiente de verificación independiente**.
