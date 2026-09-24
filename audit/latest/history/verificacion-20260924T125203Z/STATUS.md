# Estado por hallazgo · ronda `audit-2026-09-23`

Línea base: `FINDINGS.md` (sin modificar). Actualizado por la fase de **remediación** el 2026-09-23. La columna de verificación la rellena la fase de verificación independiente, que debe conservar las columnas anteriores.

| ID | Sev. | Prio. | Remediación | Verificación independiente | Evidencia | Próxima acción |
|---|---|---|---|---|---|---|
| AUD-001 | HIGH | P1 | IMPLEMENTADO | PENDIENTE | `CHANGES.md` §2; tests `test_orchestrator_safety.py`, `test_live_gate_integration.py` | Verificar; decidir el commit antes del run de las 12:00 (guard KI-036) |
| AUD-002 | HIGH | P1 | IMPLEMENTADO | PENDIENTE | `test_prediction_gate.py` (dos tests de concurrencia) | Verificar |
| AUD-003 | HIGH | P1 | **BLOQUEADO** | NO APLICA hasta desbloquear | FABLE-001 (CRITICAL, reproducido): el fallback por (local, visitante) ± 1 día liquidaba picks sin jugar con el marcador de otro partido. Revertido; tests de regresión | **Decisión del operador** sobre la identidad de eventos entre proveedores (abierta desde AUD-002, 2026-09-14) |
| AUD-004 | MEDIUM | P2 | IMPLEMENTADO | PENDIENTE | `test_candidate_history_fallback.py`; medición FABLE-002: 0 anulaciones en la primera pasada | Verificar |
| AUD-005 | MEDIUM | P2 | IMPLEMENTADO | PENDIENTE | `test_live_gate_integration.py::test_banca_cero_*` | Verificar |
| AUD-006 | MEDIUM | P2 | IMPLEMENTADO | PENDIENTE | `test_daily_picks.py`, `test_breakeven.py` | Verificar |
| AUD-007 | MEDIUM | P2 | IMPLEMENTADO | PENDIENTE | `test_calibrator.py` (objetivo del contrato; igualdad sin medias) | Verificar; no promueve nada |
| AUD-008 | MEDIUM | P2 | IMPLEMENTADO | PENDIENTE | `test_edge_information.py` | Verificar |
| AUD-009 | MEDIUM | P2 | IMPLEMENTADO | PENDIENTE | `test_store_concurrency.py` | Verificar; `log_pitcher_confirmation` queda como candidato de la misma clase |
| AUD-010 | MEDIUM | P2 | IMPLEMENTADO | PENDIENTE | `test_fip_boxscore_errors.py` | Verificar |
| AUD-011 | MEDIUM | P2 | IMPLEMENTADO | PENDIENTE | `test_audit_hooks.py::test_crossreview_*` | Verificar |
| AUD-012 | LOW | P3 | IMPLEMENTADO | PENDIENTE | `test_candidate_history_fallback.py::test_dos_generaciones_*` | Verificar |
| AUD-013 | LOW | P3 | IMPLEMENTADO | PENDIENTE | `test_gate_block_visibility.py` + comprobación de comportamiento en HEAD | Verificar |
| AUD-014 | LOW | P3 | IMPLEMENTADO | PENDIENTE | `test_monte_carlo.py` | Verificar |

**Resumen:** 13 implementados y pendientes de verificación, 1 bloqueado, 0 cerrados. **Nada commiteado.**
