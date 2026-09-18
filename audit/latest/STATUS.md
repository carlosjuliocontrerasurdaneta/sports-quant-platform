# Estado por hallazgo — ronda `audit-2026-09-18`

Actualizado: 2026-09-18 (fase remediación). La línea base es `FINDINGS.md`;
esta tabla no la reescribe. La verificación independiente añadirá su columna
sin alterar las de remediación.

| ID | Sev | Prio | Remediación | Verificación | Evidencia | Próxima acción |
|---|---|---|---|---|---|---|
| AUD-001 | MEDIUM | P2 | corregido, pendiente de verificación (`scripts/gate_status.py` reescrito; skill actualizada) | pendiente | `tests/test_gate_status_cli.py` 6 passed; reproducción con HEAD: «PASAN EL GATE, n=300»; ahora n=1 `muestra_insuficiente`; CLI real: «ninguno (default-deny)» | verificar que ninguna otra vista reconstruye la regla |
| AUD-002 | MEDIUM | P2 | corregido, pendiente de verificación (dos lectores + fallback de `run_all`) | pendiente | `tests/test_registry_root_not_object.py` 13 failed → 21 passed | verificar el fallback con un registro real corrupto en temporal |
| AUD-003 | MEDIUM | P2 | corregido, pendiente de verificación (código + dato: `mlb_h2h_pergame` demovida, live = 3 claves; decisión: demover, no adoptar) | pendiente (revisión `fable` del cambio en `VALIDATION.md`) | `tests/test_sandbox_calibration_keys.py` 8 failed → 9 passed; `promotion_log.csv` +1 `demoted`; `health_check`: `_live_calibration_markets(mlb)` = spreads, totals | decisión aparte sobre la adopción per-game (`Tareas.md`) |
| AUD-004 | MEDIUM | P2 | **parcial**: código corregido (`scheduled_tasks` en health, runbook); host bloqueado (elevación denegada por el clasificador) | pendiente | `tests/test_health_scheduled_tasks.py` 7 passed; `health_check` real → WARN con el comando; consulta real al Programador OK (5 tareas, rc 0) | **operador (elevado)**: `wevtutil sl Microsoft-Windows-TaskScheduler/Operational /e:true`; KI-054 |
| AUD-005 | LOW | P3 | corregido, pendiente de verificación (`gate_allowed_markets`) | pendiente | test del pestillo/test consumido: tabla dice `mlb|h2h`, registro dice ninguno | ticket menor: doble `evaluate_markets` por run |
| AUD-006 | LOW | P3 | corregido, pendiente de verificación (`markets_for_family`) | pendiente | `tests/test_closing_capture_markets.py` 4 passed; HEAD reproducía `['h2h,spreads,totals']` en tenis | comprobar el coste por captura de tenis en el log de mañana (5 créditos) |
| AUD-007 | LOW | P3 | corregido, pendiente de verificación (hook + detector) | pendiente | `tests/test_audit_hooks.py` 60 passed (3 nuevos); `EVIDENCE.json:315` → 0 coincidencias; `src/` con literal → rc 2 | ninguna |

## Heredado / informativo

- B-02 (acciones CI sin pin a SHA): abierto, sin cambios en esta ronda.
- OBS-C1..C6, OBS-O1..O3: sin acción (ver `FINDINGS.md`).

## Bookkeeping

- `.claude/automation/runtime/current-task.md`: registro de la ronda añadido.
- `Obsidian/Bitácora/2026-09-18.md`, `Obsidian/Tareas.md` (sección de la ronda
  + tarea del operador + `:104` actualizada), `.claude/memory/{session-summaries,
  known-issues (KI-054), project-decisions}.md`: hechos en esta sesión.
