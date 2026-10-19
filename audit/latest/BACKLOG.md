# BACKLOG — ronda `audit-2026-10-18`

Este backlog sale de la consolidación de `FINDINGS.md`. Consolidar no autoriza corregir: cada lote necesita una autorización por ID o por grupo. Las columnas son:

- **Clase:** si el cambio cae en una clase de escalado (modelo, gate, umbral, artefacto persistido o cifra publicable). En ese caso exige revisión Fable antes del commit, según `MODEL_ROUTING.md` y `fable_gate`.
- **Externa:** si el cambio requiere una acción del operador fuera del repo.

| Orden | ID | Prio. | Cambio mínimo | Archivos | Pruebas / aceptación | Clase | Autorización pendiente | Depende de |
|---|---|---|---|---|---|---|---|---|
| 1 | AUD-001 | P1 | Totals a dos vías: la celda (k,k) cuenta como 2k+1 | `src/sqp/models/distributions.py` | P(Over) frente a empírico NHL < 2 pp en 4,5–7,5; fútbol invariante; alternancia eliminada | Modelo (probabilidad servida) → pre-registro y Fable | Sí: cambio de modelo | — |
| 2 | AUD-002 | P2 | Ajuste de descanso a 0 si el evento no es el siguiente partido de ambos, o usar el calendario de eventos | `src/sqp/models/rest.py`, `sports/adapters.py` | Evento a D+3 con partido en D+2; paridad con el walk-forward | Feature de modelo → Fable | Sí | — |
| 3 | AUD-004 | P2 | Normalizar `\`, resolver rutas contra `cwd`/`cd`, tratar `stage` como `add` | `.claude/hooks/fable_gate.py`, `tests/test_fable_gate.py` | Los 4 escapes reproducidos quedan bloqueados; los tests actuales siguen en verde | Ruta sensible del candado → Fable | Sí | Antes de cualquier commit de AUD-001/002/008 |
| 4 | AUD-003 | P2 | Deduplicar por `gamePk`/`game_id` y avisar de los renombres; añadir alias | `providers/mlb_statsapi.py`, `storage/results_store.py`, `configs/leagues/team_aliases.yaml` | Mismo `game_id` → 1 fila; aviso registrado | Datos persistidos (la reparación de las 143 filas es aparte) | Sí: código. Reparar datos requiere autorización expresa aparte | Antes de noviembre (ncaab/wncaab) |
| 5 | AUD-005 | P2 | Reintento acotado en la tarea diaria, o detector del hueco anterior en health_check | Tarea del Programador (elevado, S4U) y/o `monitoring/health.py` | Simulación de 0x8007045B → reintento o alerta | Operación de producción | Sí: proceso elevado y valores del operador | — |
| 6 | AUD-006 | P2 | Activar secret scanning y push protection, o un paso de escaneo en CI; escanear `audit/` con el filtro `_symbolic` | Ajustes de GitHub; `ci.yml`; `check-secrets.sh` | Hex falso en `audit/` detectado; push con secreto falso bloqueado | Externa (GitHub) | Sí | — |
| 7 | AUD-007 | P2 | `timeout 540` en `codex review`; con rc 124, recrear el centinela | `.claude/hooks/crossreview-on-stop.sh` | `codex` simulado lento → centinela presente y aviso | — | Sí | — |
| 8 | AUD-008 | P3 | `INVALID_BEFORE` para las filas con línea de cuarto anteriores a `c578f52` | `src/sqp/risk/prediction_gate.py` (+ filtro en `calibration/data.py`) | Fila −0,75 `win` previa queda fuera de `_usable` | Gate → Fable | Sí. Re-graduar: autorización expresa aparte | AUD-004 |
| 9 | AUD-009 | P3 | Exigir `close_captured_at > generated_at` | `audit/clv.py`, `backtesting/roi_engine.py` | Pick con un solo snapshot propio → `sin_cierre` | Métrica de gate (desactivado) → Fable si se reactiva | Sí | — |
| 10 | AUD-010 | P3 | Calcular `mean_est_edge` sobre la población con stake, o renombrar | `src/sqp/audit/report.py` | Test de mezcla con y sin stake | Cifra publicable → Fable | Sí | — |
| 11 | AUD-011 | P3 | Fixture autouse que desactive el handler de fichero | `tests/conftest.py` | La suite no hace crecer `logs/sqp.log` | — | Sí | — |
| 12 | AUD-012 | P3 | Ampliar los patrones del detector | `.claude/hooks/_secret_literals.py`, tests | Los casos de AUD-012 detectados | — | Sí | Con AUD-006 |
| 13 | AUD-013 | P3 | Dejar pasar `fork` con aviso | `.claude/hooks/require-dispatch-model.sh`, tests, `MODEL_ROUTING.md` | Caso fork rc 0 | Política de modelos | Sí | — |
| 14 | AUD-014 | P3 | Corregir los IDs tras verificar contra la documentación viva | `MODEL_ROUTING.md:98`, `tests/test_claude_model_routing.py:277` | Test en verde con los IDs vigentes | Política de modelos | Sí | — |
| 15 | AUD-015 | P3 | Cerrar #4; paso de cierre automático en verde | GitHub; `ci.yml` | Run verde → 0 issues `ci-rojo` abiertos | Externa | Sí | — |
| 16 | AUD-016 | P3 | Regenerar el lock con el cierre transitivo | `requirements.lock` | Cierre de 32 paquetes fijado; pip-audit limpio; CI en verde | Dependencias | Sí | — |
| 17 | AUD-017 | P3 | Diagnosticar y estabilizar el fixture git | `tests/research/test_measure_segment_market_weight.py` | 20 ejecuciones seguidas en verde | — | Sí | — |

## Acciones del operador que no son código

- Reparar los datos persistidos de AUD-003 (143 filas) y el residuo KI-071 (14 identidades). Las dos requieren autorización expresa.
- Cerrar el issue #4 (AUD-015) y activar los controles de GitHub (AUD-006).
- Hacer push de los 2 commits locales para que pasen por el CI.
- Resolver N-01 (permisos `allow` frente a `deny`) consultando la documentación oficial.

## Propuesta de lotes

1. **Lote A (P1, modelo):** AUD-001, con pre-registro y Fable. Antes conviene AUD-004, para que el candado cubra el commit.
2. **Lote B (P2, controles):** AUD-004, AUD-007, AUD-006/012 y AUD-013.
3. **Lote C (P2, datos y modelo):** AUD-003 y AUD-002.
4. **Lote D (P3, cuantitativos menores):** AUD-008, AUD-009 y AUD-010.
5. **Lote E (P3, mantenimiento):** AUD-011, AUD-014, AUD-015, AUD-016 y AUD-017.
6. **Operación:** AUD-005.
