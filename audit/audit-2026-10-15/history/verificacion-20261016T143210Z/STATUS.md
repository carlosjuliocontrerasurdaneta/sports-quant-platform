# Estado - audit-2026-10-15

Linea base: `FINDINGS.md` (revision 2) y `BACKLOG.md`, sin modificar. Detalle de cada cambio en `CHANGES.md`; evidencia en `VALIDATION.md`.
Fase actual: remediacion autorizada terminada (2026-10-16), commits locales sin push. Verificacion independiente: NO realizada.

| ID | Prioridad | Remediacion | Verificacion | Commit | Evidencia | Proxima accion |
|---|---|---|---|---|---|---|
| AUD-003 | P1 | IMPLEMENTADO | PENDIENTE | `ffc5ad3`, `6c560e6` | 12 tests (antes 10 failed); Fable APTO; NHL 422/422 suman 1 | Verificacion independiente; decision del operador sobre filas NHL servidas desde 2026-09-23 |
| AUD-001 | P2 | BLOQUEADO | NO_APLICA | — (revertido) | Regla propuesta reasignaba 352 resultados MLB | Diseñar identidad canonica (calendario / fecha local de la cuota) + revision Fable |
| AUD-002 | P2 | IMPLEMENTADO | PENDIENTE | `766cb8b` | Clon sin tags: antes 2 failed, despues 1 passed + 1 skipped | Push (operador) y run de CI; publicar tags para verificar el ancla real |
| AUD-013 | P2 | IMPLEMENTADO | PENDIENTE | `766cb8b` | YAML validado | Run de CI: pip-audit nunca `skipped` |
| AUD-004 | P2 | IMPLEMENTADO | PENDIENTE | `2e932df` | 12 casos (antes 8 failed) | Verificacion independiente |
| AUD-005 | P2 | IMPLEMENTADO | PENDIENTE | `63dd676` | 6 tests (antes 5 failed); Fable APTO | Verificacion independiente |
| AUD-006 | P2 | IMPLEMENTADO | PENDIENTE | `9b1608d` | Contrato antes 3 failed, despues 39 passed | Comprobar disparo real con PowerShell en una sesion nueva |
| AUD-007 | P3 | IMPLEMENTADO | PENDIENTE | `5205778` | 3 tests (antes 2 failed); Fable APTO | Verificacion independiente |
| AUD-008 | P3 | IMPLEMENTADO | PENDIENTE | `2e932df` | Caso 299+3>300; registro real 310/300 | Verificacion independiente |
| AUD-009 | P3 | IMPLEMENTADO | PENDIENTE | `4f0dffa` | 3 tests (antes 1 failed + 2 contrapruebas) | Verificacion independiente |
| AUD-010 | P3 | IMPLEMENTADO | PENDIENTE | `9b1608d` | Test dinamico sin codex (antes failed) | Verificacion independiente |
| AUD-011 | P3 | IMPLEMENTADO | PENDIENTE | `5ff1475` | Mismo basetemp: antes 3 failed, despues 3 passed | Verificacion independiente |
| AUD-012 | P3 | IMPLEMENTADO | PENDIENTE | `7861a7f` | 5 tests (antes 3 failed + 2 contrapruebas) | Verificacion independiente |
