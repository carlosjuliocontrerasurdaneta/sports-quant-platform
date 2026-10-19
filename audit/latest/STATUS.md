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

## Pendientes del operador

1. Push de `main` y revisión del CI. Lo nuevo que verá por primera vez: los jobs `secret-scan` y `cierre-ci-verde`, y el lock ampliado.
2. Autorizar, por separado, si procede: reparar en disco los duplicados de AUD-003, re-graduar las filas de cuarto de AUD-008 y el residuo KI-071.
3. Decidir el reintento automático de `SQP_Diario_Completo_Cdev`. Requiere un proceso elevado, y su semántica ante un exit distinto de 0 relanzaría llamadas de pago.
4. **Recencia de totales, fase M (2027-01-31):** la instantánea `C:\dev\3\snapshots\bateria-ajustes-20261008`, con `H.json` y `pre_H`, no existe en esta máquina. Hay que localizarla antes de la fase M, que exige `--h-json` con SHA-256 `32a0e9e3…5348b1ac`. Registrado como **KI-075**. Según Fable, la fase M queda bloqueada hasta recuperarla, y repetir la fase H no vale sin enmienda.
5. Verificación independiente de la ronda (`audits/prompts/verificar-remediacion.md`).
