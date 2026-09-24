# Estado por hallazgo · ronda `audit-2026-09-23`

Línea base: `FINDINGS.md` (sin modificar).

- **Remediación:** 2026-09-23, commit `33ba978`.
- **Verificación independiente:** 2026-09-24, en `fable` sobre `1a0f746`. Detalle en `VERIFICATION.md`.
- La versión previa de este fichero está en `history/verificacion-20260924T125203Z/STATUS.md`.

**Veredicto de la ronda: NO APTO**, por AUD-003 (P1, bloqueado).

| ID | Sev. | Prio. | Remediación | Verificación independiente | Evidencia | Próxima acción |
|---|---|---|---|---|---|---|
| AUD-001 | HIGH | P1 | IMPLEMENTADO | **VERIFICADO-CORREGIDO** | `CHANGES.md` §2; `VERIFICATION.md` §2 (prueba de extremo a extremo: stake 0 en HEAD, stakes > 0 en la base) | — (residual: `run_daily.py` manual) |
| AUD-002 | HIGH | P1 | IMPLEMENTADO | **VERIFICADO-CORREGIDO** | tests de concurrencia; revisión estructural del lock | — |
| AUD-003 | HIGH | P1 | **BLOQUEADO** | **ABIERTO** (escenario original reproducido; FABLE-001 no ocurre) | `VERIFICATION.md` §2; KI-057 | **Decisión del operador** sobre la identidad de eventos entre proveedores |
| AUD-004 | MEDIUM | P2 | IMPLEMENTADO | **VERIFICADO-MITIGADO** | test discriminante; FABLE-002: 0 casos en la primera pasada | Riesgo residual: `stale_void` irreversible de desplazados jugados (depende de AUD-003) |
| AUD-005 | MEDIUM | P2 | IMPLEMENTADO | **VERIFICADO-CORREGIDO** | 2 tests (edge y accuracy); topes de exposición seguros | — |
| AUD-006 | MEDIUM | P2 | IMPLEMENTADO | **VERIFICADO-CORREGIDO** | tests; `roi_esp` = `estimated_edge` | — |
| AUD-007 | MEDIUM | P2 | IMPLEMENTADO | **VERIFICADO-CORREGIDO** | 0,6667 sobre 100 filas; sin medias, bit a bit | — |
| AUD-008 | MEDIUM | P2 | IMPLEMENTADO | **VERIFICADO-CORREGIDO** | −0,3636 con n = 11, igual que el ledger | — |
| AUD-009 | MEDIUM | P2 | IMPLEMENTADO | **VERIFICADO-CORREGIDO** | 3 tests con barrera | Próxima ronda: `log_pitcher_confirmation` |
| AUD-010 | MEDIUM | P2 | IMPLEMENTADO | **VERIFICADO-CORREGIDO** | 4 casos | — |
| AUD-011 | MEDIUM | P2 | IMPLEMENTADO | **VERIFICADO-CORREGIDO** | `codex` falso: HEAD frente a base | Próxima ronda: borrado del marcador cuando falta `codex` |
| AUD-012 | LOW | P3 | IMPLEMENTADO | **VERIFICADO-CORREGIDO** | test; orden por nombre | Observación: fragilidad del test entre las 01:00 y las 03:00 UTC |
| AUD-013 | LOW | P3 | IMPLEMENTADO | **VERIFICADO-CORREGIDO** | aviso en health y mensaje en `gate_status` | — |
| AUD-014 | LOW | P3 | IMPLEMENTADO | **VERIFICADO-CORREGIDO** | MC 0,52349 frente a 0,52330 analítico | — |

**Fuera de la línea base:** KI-058, un defecto preexistente de la clase FABLE-001 en el stream servido (`_grade_served_from_history`). Reproducido por el verificador; propuesto MEDIUM/P2 para la próxima ronda.

**Resumen:** 12 verificados-corregidos, 1 verificado-mitigado, 1 abierto (P1). Sin regresiones.
