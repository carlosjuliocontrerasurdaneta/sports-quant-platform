# Estado por hallazgo · ronda `audit-2026-09-23`

Línea base: `FINDINGS.md` (sin modificar).

- **Remediación:** 2026-09-23, commit `33ba978`.
- **Verificación independiente:** 2026-09-24, en `fable` sobre `1a0f746`. Detalle en `VERIFICATION.md`.
- La versión previa de este fichero está en `history/verificacion-20260924T125203Z/STATUS.md`.

**Veredicto de la ronda: APTO CON PENDIENTES** (verificación 3 sobre `cabe5ab` y su confirmación del delta REG-002/M14; `VERIFICATION.md` §9 y §9.1). Sin P0, P1 ni regresiones abiertas. Veredictos anteriores (NO APTO sobre `1a0f746` y `8b19c5d`) conservados en `VERIFICATION.md` §1-§8.

| ID | Sev. | Prio. | Remediación | Verificación independiente | Evidencia | Próxima acción |
|---|---|---|---|---|---|---|
| AUD-001 | HIGH | P1 | IMPLEMENTADO | **VERIFICADO-CORREGIDO** | `CHANGES.md` §2; `VERIFICATION.md` §2 (prueba de extremo a extremo: stake 0 en HEAD, stakes > 0 en la base) | — (residual: `run_daily.py` manual) |
| AUD-002 | HIGH | P1 | IMPLEMENTADO | **VERIFICADO-CORREGIDO** | tests de concurrencia; revisión estructural del lock | — |
| AUD-003 | HIGH | P1 | **IMPLEMENTADO** (ESPN: identidad exacta; MLB: calendario, KI-059; REG-002 corregido) | **VERIFICADO-MITIGADO** (verificación 3: MLB real `win +100` con calendario, ESPN `win`; 0 contradicciones con datos reales) | `CHANGES.md` §6-§8; `VERIFICATION.md` §8-§9.1 | Residual: en MLB se activa con el calendario (backfill); cobertura por el backfill diario (`CHANGES.md` §8) |
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

**Fuera de la línea base:** KI-058, un defecto preexistente de la clase FABLE-001 en el stream servido (`_grade_served_from_history`). Reproducido por el verificador. **Corregido en la remediación 2** para ligas ESPN (identidad exacta); MLB queda fuera del fallback (KI-059).

**Resumen:** 12 verificados-corregidos, 1 verificado-mitigado, 1 abierto (P1). Sin regresiones.

**Regresiones de la ronda:** REG-001 (LOW, test) verificado-corregido; REG-002 (MEDIUM/P2, MLB con inicio desfasado) verificado-corregido. **Hallazgo nuevo fuera de la línea base:** KI-060 (histórico ESPN parado desde el 14/09 por rangos rechazados), corregido en código en la remediación 4, pendiente de verificación.

**P3 «límites de uso de ESPN no documentados» (`CHANGES.md:287`), resuelto el 2026-09-25.**
- ESPN no publica límites: el endpoint no es oficial.
- Carga medida sobre el código y los BAT:
  - paso 0.5 diario: ~126 peticiones;
  - `BACKFILL_ALL` semanal: ~328;
  - siembra de 365 días: ~381 por liga.
  - La estimación de ~5-6 por liga no contaba el rango que ESPN rechaza con un 400.
- Observado: 0 respuestas 429 en `logs/backfill.log`.
- Documentado en el docstring de `src/sqp/providers/espn_results.py`.
- Corrección: los dos proveedores ESPN respetan ahora el `Retry-After` de un 429 (tope de 60 s). Antes reintentaban a los 2, 4 y 6 s. 4 tests nuevos; fallan con el código anterior.
