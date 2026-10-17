# Estado - audit-2026-10-15

Linea base: `FINDINGS.md` (revision 2) y `BACKLOG.md`, sin modificar. Remediacion: `CHANGES.md` y `VALIDATION.md` (2026-10-16, commits locales sin push). Verificacion independiente: `VERIFICATION.md` (2026-10-16), dictamen **VERIFICACION INCOMPLETA**. Version de remediacion de este fichero preservada en `history/verificacion-20261016T143210Z/`.

| ID | Prioridad | Remediacion | Verificacion | Commit | Evidencia | Proxima accion |
|---|---|---|---|---|---|---|
| AUD-003 | P1 | IMPLEMENTADO | VERIFICADO-CORREGIDO | `ffc5ad3`, `6c560e6` | NHL 1.835 snapshots: suma 1 ± 2e-13 en todos (antes 1.150 < 0,95); 0 cambios en el resto de ligas, totals y spreads; tests nuevos sobre la base: 10 failed | Operador: filas NHL servidas desde 2026-09-23. Seguimiento: exclusion en `snapshot_consensus_price` antes de activar penalizaciones de movimiento |
| AUD-001 | P2 | BLOQUEADO | BLOQUEADO (defecto presente) | — (revertido) | Reproducido con el codigo actual; la regla rechazada reasignaba 352 resultados MLB | Diseñar la identidad canonica del partido, con revision Fable (KI-074) |
| AUD-002 | P2 | IMPLEMENTADO | NO VERIFICABLE (mitigado en local) | `766cb8b` | Clon sin tags: 1 passed + 1 skipped con motivo; 0 tags en origin | Push y publicacion de tags (operador); comprobar el run de CI |
| AUD-013 | P2 | IMPLEMENTADO | NO VERIFICABLE | `766cb8b` | Job propio, pip-audit 2.10.1 fijado | Run de CI: pip-audit nunca `skipped` |
| AUD-004 | P2 | IMPLEMENTADO | VERIFICADO-MITIGADO | `2e932df` | Tests sobre la base: 8 failed; BAT leido | Seguimiento: fallo parcial de ligas sigue en rc=0; captura de porteros NHL saltada con rc=1 |
| AUD-005 | P2 | IMPLEMENTADO | VERIFICADO-CORREGIDO | `63dd676` | Tests sobre la base: 5 failed | — |
| AUD-006 | P2 | IMPLEMENTADO | VERIFICADO-CORREGIDO | `9b1608d` | Disparo real con PowerShell en sesion | — |
| AUD-007 | P3 | IMPLEMENTADO | VERIFICADO-CORREGIDO | `5205778` | Tests sobre la base: 2 failed | Duplicados historicos sin reparar (operador) |
| AUD-008 | P3 | IMPLEMENTADO | VERIFICADO-CORREGIDO | `2e932df` | Coste previsto coherente con `.closing_credits_*` | — |
| AUD-009 | P3 | IMPLEMENTADO | VERIFICADO-CORREGIDO | `4f0dffa` | Tests sobre la base: 1 failed; casos de borde revisados | — |
| AUD-010 | P3 | IMPLEMENTADO | VERIFICADO-CORREGIDO | `9b1608d` | `command -v codex` antes del `rm` | — |
| AUD-011 | P3 | IMPLEMENTADO | VERIFICADO-CORREGIDO | `5ff1475` | Pasan con basetemp dentro del repo | — |
| AUD-012 | P3 | IMPLEMENTADO | VERIFICADO-MITIGADO | `7861a7f` | Tests sobre la base: 3 failed; 0 marcas huerfanas | Seguimiento: ventanas de duplicado inferidas (a) y (b) |

## Seguimiento posterior a la verificacion (2026-10-16/17)

Commits posteriores a `VERIFICATION.md`; no tienen verificacion independiente. Las columnas de arriba no se tocan.

| ID | Commit | Que cierra |
|---|---|---|
| AUD-003 | `22da441` | El gate descarta nhl\|h2h generado antes de `ffc5ad3`; enmienda `docs/research/2026-10-16-enmienda-gate-nhl-h2h-aud003.md` (Fable APTO CON CAMBIOS) |
| AUD-003 | `3e9b7aa` | Movimiento de linea sin casas con Draw en ligas a 2 vias (seguimiento P3) |
| AUD-003 | este cierre | Addenda 2026-10-17 en los tres pre-registros que leen el stream servido (MM, peso del mercado, brecha tier A): excluyen nhl\|h2h anterior a `ffc5ad3`; N, T0/T1 y calendario intactos (Fable APTO) |
| AUD-013 | `1f4d300` | urllib3 2.8.0 en el lockfile (primer run real de dependency-audit); produccion actualizada a 2.8.0 el 2026-10-17 |
| AUD-004 | `4b4ca2e` | Fallo parcial de ligas da rc=1; porteros NHL se capturan igual |
| AUD-012 | `57906ff` | Ventana (b): `FileCache.put` retira la marca pendiente |
| AUD-001 | `813292d` | `match_results` 1:1 por (pareja, fecha canonica): MLB 2.247 emparejados, 0 cruces (Fable APTO CON CAMBIOS); residual cerrado 2026-10-17 (KI-074) |

Sigue pendiente del operador: publicar los tags `prereg-*` (AUD-002) y una verificacion independiente de estos commits.
