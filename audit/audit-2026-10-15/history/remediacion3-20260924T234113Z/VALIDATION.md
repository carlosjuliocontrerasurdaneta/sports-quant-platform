# Validación de la remediación · ronda `audit-2026-09-23`

Evidencia real de esta sesión (2026-09-23). Todas las ejecuciones usaron `-p no:cacheprovider` con un `--basetemp` propio bajo `.codex-tmp/`.

## 1. Línea base, antes de tocar código

| Comando | Resultado |
|---|---|
| `ruff check src scripts tests` | exit 0 |
| `mypy src` | exit 0, 106 ficheros |
| pytest focalizado de los componentes afectados (gate, run_all, liquidación, stores, FIP, daily_picks, reports, calibrador, edge_information, MC, hooks, health, gate_status, kelly, banca, pipeline) | **511 passed** |
| Suite completa en HEAD (diagnóstico Claude, misma base) | 2299 passed, 1 skipped |

**Limitación:** la línea base focalizada se lanzó en segundo plano y la primera edición (un import, que el autofix retiró acto seguido) coincidió con su inicio. La suite completa del diagnóstico, sobre el mismo código de HEAD, respalda la línea base.

## 2. Método «falla antes / pasa después»

- **Antes:** el código de HEAD se exportó con `git archive HEAD src scripts configs .claude/hooks` a `scratchpad/head_tree/`. Los tests se ejecutaron con `PYTHONPATH=<head>/src` y `-o pythonpath=`, porque `pyproject` antepone `src/` del repo. Los tests que cargan scripts por ruta se copiaron apuntando `ROOT` a ese árbol.
- **Después:** los mismos tests contra el árbol de trabajo.

| ID | Antes (HEAD) | Después | Naturaleza del fallo en HEAD |
|---|---|---|---|
| AUD-002 | 2 failed | pasan | comportamiento: `latched` False tras la carrera; la liberación devuelve False |
| AUD-001 | 4 failed | pasan | interfaz (`_refresh_prediction_gate` y `gate_deny_all` no existen). La evidencia de comportamiento es el arnés R-GATES de OpenAI (4 picks con stake contra la autorización de ayer) |
| AUD-004 / AUD-012 | 2 failed (+ AUD-003 retirado) | pasan | comportamiento: desplazado sin fila liquidada; una sola copia de archivo |
| AUD-009 | 3 failed | pasan | comportamiento: la escritura B se pierde en los 3 stores |
| AUD-010 | 4 failed | pasan (+1 contraprueba) | comportamiento: fila vacía emitida y FIP borrados |
| AUD-005 | 2 failed | pasan | comportamiento: 0 candidatos con banca 0 en las ramas edge y accuracy |
| AUD-006 | 3 failed | pasan | comportamiento: probabilidad cruda en orden, filtro y `mean_est_prob` |
| AUD-013 | fallo de import | pasan | interfaz; comprobación de comportamiento aparte (§3) |
| AUD-011 | 2 failed | pasan (+2 contrapruebas iguales en ambos lados) | comportamiento: exit 0 sin aviso y marcador perdido |
| AUD-007 | 4 failed | pasan (+1 contraprueba) | comportamiento: 80 filas con objetivo 0,75; sin `weight` |
| AUD-008 | 2 failed | pasan (+2 contrapruebas) | comportamiento: ROI +1,0 sobre n = 1 |
| AUD-014 | 7 failed | pasan (+2 contrapruebas) | comportamiento: Over 0,4565 frente a 0,5233 |

## 3. AUD-013: comprobación de comportamiento en HEAD

Script `scratchpad/aud013_before.py`, con un registro legible y un centinela presentes:

- `generate_health_report`: 0 avisos sobre el centinela.
- `gate_status`: «registro ausente o ilegible -> default-deny…».

## 4. Revisión independiente (Fable) y correcciones posteriores

- **Lo que ejecutó el revisor:** 294 tests del diff, que pasan en el árbol de trabajo (38 fallan en HEAD).
- **FABLE-001, reproducido por el implementador:** `scratchpad/repro_fable/test_repro_future.py` fallaba (`g2` liquidado como `loss`, pnl −100). Tras retirar el fallback **pasa** (1 passed).
- **Tras las correcciones:**
  - liquidación: 123 passed;
  - calibrador + `edge_information`: 77 passed.

## 5. Medición FABLE-002 (solo lectura, agregados)

`scratchpad/medir_fable002.py` sobre `data/predictions/archive` y `data/bets/settled_*`, a fecha 2026-09-23:

- 85 desplazados sin liquidar;
- 0 expirarían en la primera pasada;
- 84 son partidos futuros;
- 0 sin `start_time`.

## 6. Validación final

| Comando | Resultado | Clasificación |
|---|---|---|
| `ruff check src scripts tests` | exit 0 | OK |
| `mypy src` | exit 0, 106 ficheros | OK |
| `pytest -q -p no:cacheprovider --basetemp=.codex-tmp/pytest-rem-final` (suite completa, código definitivo) | **2350 passed, 1 skipped**, 20 min 52 s, exit 0 | OK |
| `python scripts/sync_agent_instructions.py --check` | exit 0 | OK |
| `python scripts/validate_claude_model_routing.py` | exit 0 | OK |
| Inspección de BAT (`DIARIO_COMPLETO`, `RUN_DIARIO_ALL`, `SETTLE_ALL`) | sin cambios necesarios: SETTLE → `run_all --mode live` sin `--no-report` | OK |
| Guard KI-036 (`DIARIO_COMPLETO.bat:73`) | **el árbol está sucio en `src/` y `scripts/`: el run programado ABORTARÁ hasta que se commitee** | riesgo operativo |

- Una suite completa intermedia (2351 passed, 1 skipped) corrió sobre el código **con** el fallback de AUD-003. Queda superada por la final.
- Ninguna `NEW_REGRESSION` ni `PRE_EXISTING_FAILURE` observada.
- CI remoto: NOT_VERIFIABLE, porque no hay push.
- No se ejecutó ningún BAT, operación productiva ni proveedor.

## 7. Remediación 2 (2026-09-24): identidad exacta

| Comando / evidencia | Resultado |
|---|---|
| Medición de convención de fecha (`scratchpad/medir_identidad.py`) y conversión ET para MLB | ESPN: mismo día UTC. MLB: 655 coinciden y 0 no coinciden |
| Efecto en seco sobre datos reales (`scratchpad/medir_efecto_identidad.py`) | 3 pendientes empezados, 0 graduables; 0 `stale_void` reconciliables |
| `tests/settlement/test_candidate_history_fallback.py` contra `6676e9a` | 8 failed y 8 passed (las que pasan son contrapruebas) |
| Reproducción del verificador `verif_served_series.py` (KI-058) | `6676e9a`: `gN` graduado como `loss`. Código nuevo: 0 graduadas |
| Reproducción de Fable `repro_r2.py` | A de punta a punta: `void`; B (Tokio): `{}`; C (ET nocturno): correcto |
| `tests/settlement` + `test_settle_candidates.py` + `test_settle_persist.py` | 134 passed |
| `ruff check src scripts tests` / `mypy src` | exit 0 / 106 ficheros OK |
| Suite completa v1 y v2 (ambas superadas) | 2355 passed, 1 skipped / 2360 passed, 1 skipped |
| Suite completa v3 (código final) | ver el manifest (`remediation_2.tests`) |
