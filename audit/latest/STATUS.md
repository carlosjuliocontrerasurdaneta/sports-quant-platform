# STATUS — ronda `audit-2026-10-18`

- **Fase actual:** remediación aplicada y validada por el implementador. **Pendiente de verificación independiente**: no es un PASS, y no demuestra ninguna ventaja predictiva.
- **Alcance:** AUD-001..AUD-017, todo autorizado por el operador el 2026-10-18.
- **Revisión previa al commit:** Fable (`model: "fable"`), en tres rondas más una verificación final. Las líneas de veredicto están en `.claude/automation/runtime/current-task.md`.

| ID | Prio. | Estado |
|---|---|---|
| AUD-001 | P1 | Corregido; pendiente de verificación |
| AUD-002 | P2 | Corregido; pendiente de verificación |
| AUD-003 | P2 | Código corregido; pendiente de verificación. **Datos en disco sin reparar** (148 filas crudas; se deduplican al leer): falta autorización expresa |
| AUD-004 | P2 | Corregido; pendiente de verificación |
| AUD-005 | P2 | Parcial: vigilante independiente activo. El reintento del Programador (`RestartCount`) queda como decisión del operador |
| AUD-006 | P2 | Corregido: GitHub con secret scanning y push protection activados, job `secret-scan`, el hook escanea `audit/` |
| AUD-007 | P2 | Corregido; pendiente de verificación |
| AUD-008 | P3 | Exclusión aplicada en el gate y la calibración, con addenda en cinco pre-registros. **Re-graduar el stream** queda fuera: falta autorización expresa |
| AUD-009 | P3 | Corregido; pendiente de verificación |
| AUD-010 | P3 | Corregido; pendiente de verificación |
| AUD-011 | P3 | Corregido; pendiente de verificación |
| AUD-012 | P3 | Corregido; pendiente de verificación |
| AUD-013 | P3 | Corregido; pendiente de verificación |
| AUD-014 | P3 | Corregido (IDs verificados en vivo el 2026-10-18) |
| AUD-015 | P3 | Corregido: #4 cerrado; el job `cierre-ci-verde` se comprobará en el primer run de main |
| AUD-016 | P3 | Corregido en local; falta confirmar el CI en Linux y en 3.11–3.14 tras el push |
| AUD-017 | P3 | Mitigado (`_git_decide`); la causa sigue sin reproducirse sin carga |

## Autorización del operador (2026-10-19, «Te autorizo») y lo que se hizo

1. **Push** de `main` (`32e1b2f..ba6f3e3`), sin bloqueos de la push protection. Primer CI: `secret-scan`, `dependency-audit` y `test-windows` en verde. Las 4 patas Linux de `test` fallaron por 2 tests de AUD-004 que usaban una ruta Windows (`\tmp\...`) en Linux: defecto del test, no del hook. Corregido. `alerta-ci-rojo` abrió su issue como debe, y `cierre-ci-verde` lo cerrará en el próximo run verde.
2. **KI-075 resuelto:** la instantánea H estaba en la papelera de reciclaje. Se copió de vuelta y su SHA y su `codigo_sha256` cuadran.
3. **Reintento de la tarea diaria (AUD-005):** `scripts/set_daily_retry.ps1` (RestartCount 3, cada 15 min; la caché de cuotas de 6 h evita gastar créditos). Necesita UAC, así que lo ejecuta el operador.
4. **Reparación de datos:** `scripts/repair_audit_20261018.py`, con dry-run por defecto, copia de seguridad, SHA tomado al planificar y comprobado bajo lock. Revisión de Fable:
   - **AUD-003 NO se repara en disco.** Rompería la Enmienda 3(c) de la batería y la Enmienda 2 de recencia, y `load` ya deduplica al leer. Queda resuelto en la lectura.
   - **KI-071:** 9 filas (stake 0).
   - **AUD-008:** 124 filas del stream re-graduadas a medias (pnl 0). El ledger tiene 0 filas emparejables y no cambia.
   - El clasificador del modo automático no permite ejecutarlo a Claude, así que lo ejecuta el operador.

## Pendientes

1. Que el operador ejecute `scripts/set_daily_retry.ps1` (UAC) y `scripts/repair_audit_20261018.py` (dry-run y después `--apply`, fuera de las ventanas de SETTLE y DIARIO).
2. Confirmar el CI en verde tras el arreglo del test (AUD-015/016).
3. Verificación independiente de la ronda (`audits/prompts/verificar-remediacion.md`).
