# STATUS — ronda `audit-2026-10-18`

- **Fase actual:** verificación independiente hecha el 2026-10-22 (`independent-code-reviewer`, Fable, solo lectura sobre `2985c3d`). **Veredicto: APTO CON PENDIENTES** (ver `VERIFICATION.md`). Califica solo la remediación evaluada; no demuestra ninguna ventaja predictiva.
- **Alcance:** AUD-001..AUD-017, todo autorizado por el operador el 2026-10-18.
- **Revisión previa al commit:** Fable (`model: "fable"`), en tres rondas más una verificación final. Las líneas de veredicto están en `.claude/automation/runtime/current-task.md`.

| ID | Prio. | Estado |
|---|---|---|
| AUD-001 | P1 | Verificado-corregido (reproducido contra el histórico NHL, error de P(Over) < 2 pp) |
| AUD-002 | P2 | Verificado-corregido |
| AUD-003 | P2 | Verificado-corregido en la lectura. Las 148 filas crudas se conservan a propósito (Enmiendas 3(c) y 2) |
| AUD-004 | P2 | Verificado-corregido (28 casos + 10 variantes nuevas bloqueadas) |
| AUD-005 | P2 | Verificado-mitigado: RestartCount=3/PT15M en vivo, pero ni el reintento ni el vigilante cubren un fallo de liquidación (21-10, NEW-002) |
| AUD-006 | P2 | Verificado-corregido (secret scanning y push protection en `enabled`) |
| AUD-007 | P2 | Verificado-corregido |
| AUD-008 | P3 | Verificado-corregido (0 filas posteriores al corte difieren de `_grade`). Stream re-graduado el 19-10 (124 filas `regrade_aud008`) |
| AUD-009 | P3 | Verificado-corregido |
| AUD-010 | P3 | Verificado-corregido |
| AUD-011 | P3 | Verificado-corregido en código y test; `logs/sqp.log` no inspeccionado |
| AUD-012 | P3 | Verificado-corregido |
| AUD-013 | P3 | Verificado-corregido |
| AUD-014 | P3 | Verificado-corregido (estático; sin contraste vivo) |
| AUD-015 | P3 | Verificado-corregido en vivo (#5 abierto y cerrado; #6 abierto por NEW-001) |
| AUD-016 | P3 | Verificado-corregido (el rojo actual de `dependency-audit` es NEW-001, ajeno al lock ampliado) |
| AUD-017 | P3 | Verificado-mitigado (`_git_decide`); `git_show_or_none` y `git_status_porcelain` siguen tragando errores |

## Autorización del operador (2026-10-19, «Te autorizo») y lo que se hizo

1. **Push** de `main` (`32e1b2f..ba6f3e3`), sin bloqueos de la push protection. Primer CI: `secret-scan`, `dependency-audit` y `test-windows` en verde. Las 4 patas Linux de `test` fallaron por 2 tests de AUD-004 que usaban una ruta Windows (`\tmp\...`) en Linux: defecto del test, no del hook. Corregido. `alerta-ci-rojo` abrió su issue como debe, y `cierre-ci-verde` lo cerrará en el próximo run verde.
2. **KI-075 resuelto:** la instantánea H estaba en la papelera de reciclaje. Se copió de vuelta y su SHA y su `codigo_sha256` cuadran.
3. **Reintento de la tarea diaria (AUD-005):** `scripts/set_daily_retry.ps1` (RestartCount 3, cada 15 min; la caché de cuotas de 6 h evita gastar créditos). Necesita UAC, así que lo ejecuta el operador.
4. **Reparación de datos:** `scripts/repair_audit_20261018.py`, con dry-run por defecto, copia de seguridad, SHA tomado al planificar y comprobado bajo lock. Revisión de Fable:
   - **AUD-003 NO se repara en disco.** Rompería la Enmienda 3(c) de la batería y la Enmienda 2 de recencia, y `load` ya deduplica al leer. Queda resuelto en la lectura.
   - **KI-071:** 9 filas (stake 0).
   - **AUD-008:** 124 filas del stream re-graduadas a medias (pnl 0). El ledger tiene 0 filas emparejables y no cambia.
   - El clasificador del modo automático no permite ejecutarlo a Claude, así que lo ejecuta el operador.

## Ejecutado por el operador (2026-10-19)

- `set_daily_retry.ps1`: RestartCount=3, RestartInterval=PT15M (código 0).
- `repair_audit_20261018.py`: el dry-run coincidió con lo esperado; `--apply` dejó el manifiesto en `aplicado`, 10 ficheros con su copia SHA-verificada, KI-071 con 0 duplicados y AUD-008 con 124 filas re-graduadas. Verificado por Claude en solo lectura.

## Verificación independiente (2026-10-22)

Hecha con `audits/prompts/verificar-remediacion.md`: veredicto **APTO CON PENDIENTES**, 0 P0/P1 abiertos, 0 regresiones. Detalle en `VERIFICATION.md`; el STATUS anterior está en `history/verificacion-20261022T131053Z/`.

## Pendientes

1. **NEW-002 (operador):** el run diario del 21-10 abortó en la liquidación (centinela `settle`, exit 1) y no hubo picks ese día. Revisar el log y confirmar que el run del 22-10 termina con 0x0.
2. **NEW-001 (P2, necesita autorización):** CI de `main` en rojo por `certifi 2026.4.22` (GHSA-6q48-6c7w-9gw2). Subir `requirements.lock` a `certifi==2026.10.19`; `cierre-ci-verde` cerrará el #6.
3. **AUD-005 y AUD-017** quedan mitigados, no cerrados.
4. **Opcional (P3):** aplicar `_git_decide` a `git_show_or_none`, a `git_status_porcelain` y a los scripts hermanos.
