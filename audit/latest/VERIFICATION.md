# Verificacion independiente - audit-2026-10-15

**Dictamen: VERIFICACION INCOMPLETA** (regla 2). Ningun P0/P1 abierto; el unico P1 (AUD-003) queda **verificado-corregido** con medicion sobre datos reales. Falta evidencia de AUD-002 y AUD-013, que solo un run de CI tras el push puede dar, y AUD-001 (P2) sigue abierto y bloqueado. Ninguna regresion demostrada. Este dictamen solo califica la remediacion evaluada: no garantiza ausencia de defectos ni rentabilidad.

## Alcance

- Linea base: `FINDINGS.md` (revision 2, 13 confirmados) y `BACKLOG.md`. Remediacion evaluada: `CHANGES.md`, `VALIDATION.md` y los 10 commits `65368c8..7861a7f` (HEAD `7861a7f`, sin push).
- Exclusiones (no son cierres): remediacion KI-073 del hook Stop, sin commit; documentacion de memoria y Obsidian.

## Metodologia e independencia

- Verificador: `claude-fable-5-1` (agente `independent-code-reviewer`), de solo lectura, sin participar en la remediacion y sin contexto de la sesion de remediacion. Coordinador (`claude-opus-5-5`, que coordino la remediacion): solo redacta estos entregables con la evidencia del verificador y aplica la regla de dictamen.
- Por ID: causa y activacion original reconstruidas, parche y llamadores leidos, escenario reproducido con el codigo actual cuando era seguro, tests relevantes ejecutados, y los tests nuevos ejecutados tambien sobre el arbol `65368c8` aislado con `git archive` (para demostrar que discriminan).
- Datos reales: solo agregados (`scratchpad/verif/v003.py`, `v001.py`, `vclv.py`).

## Estado por ID

| ID | Prio | Estado | Evidencia | Criterio | Riesgo residual |
|---|---|---|---|---|---|
| AUD-003 | P1 | **verificado-corregido** | Antiguo frente a actual sobre TODOS los snapshots `odds_*.csv`. NHL: 1.835 snapshots, 1.182 con Draw; con el codigo antiguo 1.150 sumaban < 0,95, con el actual fair(home)+fair(away) = 1 ± 2e-13 en todos y 0 mercados nuevos incompletos. NBA 460, NFL 3.443, WNBA 1.807, MLB 9.111, NCAAF 8.870 y tenis sin ningun cambio. Futbol (EPL, LaLiga, MLS) h2h a 3 vias, totals y spreads: 0 cambios. Cableado leido (`daily.py:877-934`, `revalidation.py:332`, `intraday_scan.py:135`). Tests nuevos sobre `65368c8`: 10 failed | Si | Filas servidas, ledger y gate intactos (decision del operador). `snapshot_consensus_price` en `markets/line_movement.py` y `audit/clv_movement.py` sin la exclusion: inerte hoy (`line_movement_penalty` y `line_velocity_penalty` = 0,0 en `configs/default.yaml:35,39`, sin override por liga ni entorno); volveria el sesgo si se activan. CLV historico NHL: impacto medido nulo (2 apuestas, CLV medio 0,2059 con ambos codigos). Sin test del cableado de `run_league` |
| AUD-001 | P2 | **bloqueado** (defecto presente) | `roi_engine.py` sin diff frente a `65368c8`; reproducido con el codigo actual: el resultado del 10 empareja `odds-jun11` y el del 11 queda sin cuotas. El diff rechazado prefiere la cuota equivocada en series de costa oeste (fecha local frente a `commence_time` UTC): la justificacion es plausible. La medida de 352 reasignaciones no se repitio | No | PnL y muestra de backtests y mediciones pueden estar mal emparejados (KI-074) |
| AUD-002 | P2 | **no verificable** (mitigado en local) | Clon `--no-tags --depth 1` de HEAD: 1 passed + 1 skipped con motivo explicito; con el tag local pasa. `fetch-depth: 0` y `fetch-tags: true` en `test` y `test-windows` (YAML parseado). `git ls-remote --tags origin`: 0 `prereg*` | No comprobable sin CI | Sin tags en origin, CI se salta la verificacion del ancla real |
| AUD-013 | P2 | **no verificable** | Job `dependency-audit` independiente, `pip-audit==2.10.1` (existe en PyPI), dentro de `needs` de `alerta-ci-rojo` | No comprobable sin un run de main | — |
| AUD-004 | P2 | **verificado-mitigado** | rc=1 si fallan todas las ligas intentadas, la revalidacion o el guard. Tests sobre `65368c8`: 8 failed. `CAPTURE_CLOSE.bat` leido: con rc≠0 va a `:error` (`run_status --fail`, `exit /b 1`) | Parcial | Un fallo PARCIAL de ligas sigue en rc=0 con warning. Con rc=1 se salta la captura de porteros NHL de esa pasada (DIARIO la sigue ejecutando, `DIARIO_COMPLETO.bat:196`); una revalidacion que falle de forma persistente las salta todas |
| AUD-005 | P2 | **verificado-corregido** | `failed_windows` en todas las salidas que abandonan una ventana; `_settle_tennis` fuerza `results_trusted=False` y bloquea `_void_stale_served`/`_with_stale_voids`; backfill rc=1. Tests sobre `65368c8`: 5 failed | Si | Una ventana que falle siempre congela las anulaciones de tenis (visible en el log) |
| AUD-006 | P2 | **verificado-corregido** | Matcher `Edit\|Write\|Bash\|PowerShell` en los tres hooks; `_targets.py` extrae la ruta de un payload PowerShell. Disparo real en la sesion: una llamada PowerShell que nombraba `Set-Content` actualizo el mtime de `.claude/.tests-pending` (10:53:30 → 10:54:10), antes de cualquier Bash | Si | `post-edit-format` sigue en `Edit\|Write` (asimetria documentada) |
| AUD-007 | P3 | **verificado-corregido** | `_norm_str` iguala None, NaN y "nan". Tests sobre `65368c8`: 2 failed | Si | Duplicados ya existentes en el log de produccion sin reparar |
| AUD-008 | P3 | **verificado-corregido** | Coste previsto (mercados × regiones) antes de cada `fetch_odds`; 5 regiones en `CAPTURE_CLOSE.bat`, coherente con `.closing_credits_*` reales de 305/310 (3, 4, 8, 9, 10 y 11/10) en saltos multiplos de 5 | Si | Tope conservador (cota superior) |
| AUD-009 | P3 | **verificado-corregido** | `_possible_local_days` [t−12 h, t+14 h]: 23:00Z del 11 → {11, 12} (se conserva el partido real); 02:00Z del 12 → {11, 12} (se descarta el duplicado); sin hora, ±1. Test sobre `65368c8`: 1 failed. Ningun caso encontrado de doble conteo o de perdida de un partido con hora | Si | Sin hora sigue la ambiguedad; doble jornada con solo el primer partido en el historico: el segundo se sigue descartando (comportamiento previo) |
| AUD-010 | P3 | **verificado-corregido** | `command -v codex` antes del `rm`; sin codex: aviso, centinela conservado, exit 0 | Si | — |
| AUD-011 | P3 | **verificado-corregido** | `GIT_CEILING_DIRECTORIES` en los tres tests; pasan con el basetemp DENTRO del repo (`.codex-tmp/pytest-verif-a1`), la activacion original | Si | — |
| AUD-012 | P3 | **verificado-mitigado** | Marca `.pending` alrededor de `append_snapshot`; `fetch_odds` es la ultima llamada al cliente antes de ese bloque (clave correcta). Tests sobre `65368c8`: 3 failed. 0 marcas huerfanas hoy en `data/cache/odds` | Si, en el escenario del hallazgo | Ventanas de duplicado INFERIDAS, no reproducidas: (a) muerte del proceso entre el append y la retirada de la marca; (b) `capture_close` usa `force_refresh=True` pero escribe en la cache (`odds_api.py:232`): si el run diario dejo la marca y antes del reintento dentro del TTL una captura de cierre refresca la misma clave, el reintento re-persiste un snapshot que la captura ya guardo. La muerte entre `put` y la marca sigue sin cubrirse |

## Regresiones

Ninguna demostrada; no se asigna `REG-###`. La ventana (b) de AUD-012 es un riesgo inferido (seguimiento P3).

## Validacion global

| Comando | rc | Resultado |
|---|---|---|
| Suite completa en HEAD `7861a7f` (fase de remediacion, ver `VALIDATION.md`) | 0 | 3252 passed, 1 skipped in 4021.60s |
| pytest de los 13 ficheros de test tocados (verificador, basetemp en `.codex-tmp`) | 0 | 344 passed |
| Regresion de la zona afectada (backtest_markets, backtest_parity, closing_capture_markets, clv, clv_gate, clv_movement, decision_probability, novig_incomplete, odds_cache, revalidation, roi_engine, team_totals_capture) | 0 | 138 passed |
| Tests nuevos sobre el arbol `65368c8` aislado | 1 | 29 failed / 24 passed: 003 10, 004 8, 005 5, 007 2, 009 1, 012 3 (coincide con lo declarado) |
| Clon sin tags, tests de AUD-002 | 0 | 1 passed, 1 skipped |
| `ruff check src scripts tests` | 0 | limpio |
| `mypy` (10 modulos tocados; `mypy src` completo en `VALIDATION.md`) | 0 | limpio |

## P0/P1 abiertos

Ninguno. Abiertos de prioridad P2: AUD-001 (bloqueado), AUD-002 y AUD-013 (pendientes de CI).

## Discrepancia sobre el dictamen

El verificador propuso **APTO CON PENDIENTES**. El coordinador aplica la regla 2: la regla 1 no aplica (sin P0/P1 abiertos ni regresion grave) y falta evidencia de dos hallazgos del alcance (AUD-002, AUD-013). El propio contrato fija «sin bloqueo confirmado + evidencia faltante → VERIFICACION INCOMPLETA». La discrepancia es solo de regla; la evidencia del verificador se adopta integra.

## Limitaciones

- Sin push: CI de HEAD no ejecutado y tags `prereg*` ausentes de origin.
- No se ejecutaron BAT ni APIs de pago; AUD-004/008 se verificaron por lectura de codigo y registros de creditos.
- AUD-001: la medida de 352 reasignaciones no se repitio; se valoro razonando sobre el diff.
- Efectos colaterales del verificador: un comando de prueba que nombraba `src/sqp/risk/kelly.py` creo `.claude/.crossreview-pending` (ya consumido por el hook de Stop; ningun fichero escrito) y toco el mtime de `.claude/.tests-pending`; basetemps en `.codex-tmp/pytest-verif-a1` y `-a2`. `git status` sin cambios.

## Proxima accion

1. Operador: push de `main` y publicacion de los tags `prereg-*` (escrituras externas no autorizadas en esta fase). Despues, comprobar el run: el test del ancla real sin skip y `dependency-audit` en success/failure, nunca skipped. Con eso, AUD-002 y AUD-013 pueden pasar a verificados y el dictamen puede recalcularse.
2. AUD-001: diseñar la identidad canonica del partido (calendario o fecha local de la cuota por huso) con revision Fable.
3. Operador: decision sobre las filas NHL h2h servidas desde 2026-09-23 (AUD-003).
4. Seguimiento P3: exclusion de Draw en `snapshot_consensus_price` antes de activar penalizaciones de movimiento; estado degradado ante fallo parcial de ligas en `capture_close`; cubrir la ventana (b) de AUD-012.
