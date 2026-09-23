# STATUS — ronda `audit-2026-09-22`

Estado por ID. Se preservan las columnas y la evidencia de las fases anteriores;
`FINDINGS.md` sigue siendo la línea base y no se reescribe.

- **Fases ejecutadas:** diagnóstico independiente (auditor Claude), consolidación
  y **remediación autorizada** (operador, 2026-09-22, fases 4 y 5).
- **Fase NO ejecutada:** verificación independiente.
- **Segunda opinión:** no hubo. La revisión cruzada de Codex tampoco pudo
  ejecutarse (`AUD-008`), así que **esta remediación no ha sido revisada por un
  tercero**.

| ID | Sev. | Prio | Remediación | Verificación | Evidencia | Próxima acción |
|---|---|---|---|---|---|---|
| `AUD-007` | MEDIUM | P1 | **corregido** | pendiente | `timeout` 600→1200 y autoacotado del script a 1080 s con rama propia para `rc 124`. Diagnóstico: 796,09 s medidos contra 600 s | Verificación independiente |
| `AUD-001` | MEDIUM | P2 | **corregido (parcial, por diseño)** | pendiente | `fwer_bound()`, aviso al superar `K`, `fwer_bound` en el registro. 3 pruebas nuevas, discriminantes | **Decisión del operador**: re-pre-registrar `K` o aceptar el desvío. El criterio sigue incumplido |
| `AUD-008` | MEDIUM | P2 | **no aplicable al repositorio** | pendiente | Causa fuera del árbol (runtime de Codex y plugin). Registrado como `KI-056` | Diagnosticar el runtime y decidir sobre la puerta `Stop` del plugin |
| `AUD-002` | MEDIUM | P2 | **corregido** | pendiente | `coverage_baseline()` + aviso bajo el 50 % de la mediana de 7 días; `candidates` y `coverage_baseline` en el resumen. 3 pruebas nuevas | Verificación independiente |
| `AUD-003` | LOW | P3 | **corregido** | pendiente | Guarda sobre coste previsto (`CREDITS_PER_EVENT`). Test viejo reescrito (codificaba el defecto) + uno parametrizado par/impar | Verificación independiente |
| `AUD-004` | LOW | P3 | **corregido** | pendiente | `REPLACE_RETRY_SECONDS` como constante; la prueba mide sólo `publish()` y se acota contra `3 ×` el plazo | Verificación independiente |
| `AUD-005` | LOW | P3 | **corregido** | pendiente | `summary()` enruta por `realized_roi_parts`/`staked_mask`. ROI real sin mover (−0,1526). 2 pruebas nuevas | Verificación independiente |
| `AUD-006` | LOW | P3 | **corregido** | pendiente | Familia `team_totals_credits` en la lista de purga; test con `mtime` explícito y comprobación de `spent_this_month` | Verificación independiente |

**Riesgo residual declarado en `AUD-001`:** la instrumentación hace visible el
incumplimiento; **no lo corrige**. `K`, `alpha`, `min_n` y el pestillo no se han
tocado a propósito —son el criterio pre-registrado y `CLAUDE.md` los clasifica
como clase de escalación—. Basta con que un corte alcance `n ≥ 300` para que
gaste su único test de entrada con un alpha que sobregira el presupuesto de
familia.

## IDs de la ronda `audit-2026-09-18`

Revalidados contra el código actual durante el diagnóstico de esta ronda. No se
reescribe su línea base.

| ID (r18) | Estado revalidado | Evidencia | Próxima acción |
|---|---|---|---|
| `AUD-001` | verificado-corregido | `scripts/gate_status.py` importa el criterio canónico | ninguna |
| `AUD-002` | verificado-corregido | `isinstance(payload, dict)` antes del `.get` en ambos lectores | ninguna |
| `AUD-003` | verificado-corregido | `calibration_methods.json` sin `mlb_h2h_pergame`; `promotion_log.csv:102` | ninguna |
| `AUD-004` | **reabierto / persistente** | `scheduled_tasks.history_enabled = false` (2026-09-21) | Habilitar el historial — proceso elevado, fuera del repositorio. Registrado como `KI-054` |
| `AUD-005` | verificado-corregido | `run_all.py` lee el veredicto del registro escrito | ninguna |
| `AUD-006` | verificado-corregido | `markets_for_family` devuelve `"h2h"` en tenis | ninguna |
| `AUD-007` | verificado-corregido | `_secret_literals._symbolic()`; sin reincidencia en sesión | ninguna |

**Regresiones introducidas por la remediación de la ronda 18:** ninguna detectada.

## Nota de alcance

Este `STATUS.md` sustituye al de la ronda `audit-2026-09-18`, preservado íntegro
en `audit/audit-2026-09-18/STATUS.md` (sha256 `745605ccc4bd6d11…`). Ningún
hallazgo de aquella ronda se ha alterado ni reescrito.
