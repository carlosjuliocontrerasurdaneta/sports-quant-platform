# Remediacion - audit-2026-10-15

- **Fase:** remediacion autorizada. Orden del operador (2026-10-16): «Todos los confirmados» (AUD-001..013), commits locales **sin push**.
- **Coordinador:** `claude-opus-5-5`. Implementacion: Sonnet (AUD-001, AUD-004/008, AUD-005, AUD-007), Fable (AUD-003, clase de escalado), Opus (AUD-002/013, 006/010, 009, 011, 012). Revision Fable previa al commit en rutas sensibles del candado (`fable-gate.json`): AUD-003, AUD-005, AUD-007 — las tres **APTO** (lineas `FABLE-REVIEW` en `.claude/automation/runtime/current-task.md`).
- **Base:** `main` en `65368c815530bf179c5780db78a9fe196996802d`. Cambios preexistentes sin commit (remediacion KI-073 del hook Stop: marcador `heavy` en 11 tests, `_stop_tests.py`, `pyproject.toml`, memoria, Obsidian) **conservados y excluidos de todos los commits**: en los tests compartidos se hizo stage de HEAD + solo los hunks de esta remediacion.
- **Lineas base intactas:** `FINDINGS.md` y `BACKLOG.md` no se modifican en esta fase. Versiones previas de CHANGES/VALIDATION/STATUS/VERIFICATION/MANIFEST (de la ronda 2026-09-23) preservadas en `history/remediacion-20261016T120517Z/` (hashes verificados).
- **Estado final de cada ID:** pendiente de verificacion independiente, salvo AUD-001 (BLOQUEADO). Nada de esto declara el proyecto libre de errores.

## Commits

| Commit | IDs | Resumen |
|---|---|---|
| `766cb8b` | AUD-002, AUD-013 | Checkout con tags; test del ancla real con skip explicito; test sintetico con doble; pip-audit en job propio fijado |
| `2e932df` | AUD-004, AUD-008 | `capture_close` rc=1 si fallan todas las ligas, la revalidacion o el guard; coste previsto antes de pedir |
| `63dd676` | AUD-005 | `failed_windows` en tenis; sin anulaciones por expiracion con ventanas fallidas; backfill rc=1 |
| `5205778` | AUD-007 | Normalizacion de abridores ausentes en el log de confirmacion |
| `9b1608d` | AUD-006, AUD-010 | Matchers PostToolUse con PowerShell; `crossreview-on-stop` conserva el centinela sin `codex` |
| `5ff1475` | AUD-011 | `GIT_CEILING_DIRECTORIES` en las 3 pruebas de no-repositorio |
| `ffc5ad3` | AUD-003 | Exclusion de casas con Draw en h2h de ligas a 2 vias (consenso, conteos, dispersion, ejecucion, revalidacion) |
| `6c560e6` | AUD-003 (H1) | Misma exclusion en el observatorio intradia (observacion de la revision Fable) |
| `4f0dffa` | AUD-009 | `_merge_results` acota la tolerancia por el instante UTC del resultado reciente |
| `7861a7f` | AUD-012 | Marca de snapshot pendiente: un cache hit recupera el snapshot no persistido |

## Por ID

### AUD-003 - P1 - Casas con Draw en el h2h de ligas a 2 vias
- **Estado inicial:** confirmado (REPRODUCED; revalidado 2026-10-16: 331/346 pares NHL servidos < 0,95).
- **Causa:** consenso por (market, outcome, point) sin distinguir contratos; `_novig_probs` aceptaba mas claves de las del mercado.
- **Archivos:** `src/sqp/pipeline/probabilities.py`, `src/sqp/pipeline/daily.py`, `src/sqp/pipeline/revalidation.py`, `src/sqp/pipeline/intraday_scan.py`; tests `tests/test_aud003_two_way_draw.py`, `tests/test_intraday_scan.py`.
- **Cambio:** `_eligible_lines` unico; ligas a 2 vias (three_way explicito desde el run diario, derivado de `SPORT_KEYS` si no se pasa) excluyen TODAS las lineas h2h de una casa que cotiza Draw. `_novig_probs` a 2 vias exige 2 claves sin Draw y, con `outcomes=(home, away)`, los lados del evento; si no, mercado incompleto (camino default-deny existente). Futbol, totals y spreads sin cambio.
- **Prueba:** 12 tests nuevos (antes 10 failed / 2 passed; despues 12 passed); 830 relacionados; intradia antes failed / despues passed.
- **Aceptacion:** revision Fable APTO midiendo con todos los `odds_*.csv`: NHL fair(home)+fair(away) = 1,000000 en 422/422 eventos (antes 120 < 0,95); 0 eventos incompletos por el chequeo de lados en mlb, nba, ncaaf, nfl, nhl, wnba y tenis.
- **Riesgos residuales:** filas ya servidas, ledger y `prediction_gate.json` intactos — **decision del operador** (marcar, excluir o reconstruir desde 2026-09-23). `markets/line_movement.py` y `audit/clv_movement.py` no aplican la exclusion: inertes hoy (penalizaciones de movimiento a 0,0 en `configs/default.yaml`). 11 eventos NHL quedan con ≤ 2 casas (penalizacion por mercado fino). La serie NHL servida cambia desde el proximo run. Sin test del cableado de `run_league` (se prueban las funciones).
- **Estado final:** pendiente de verificacion.

### AUD-002 - P2 - CI exige un tag que el checkout no obtiene
- **Estado inicial:** confirmado (CI de main en failure; 0 tags `prereg*` en origin).
- **Archivos:** `.github/workflows/ci.yml`, `tests/research/test_measure_tier_a_gap.py`.
- **Cambio:** `fetch-depth: 0` + `fetch-tags: true` en `test` y `test-windows`. El test sintetico de `run_medir` usa un doble de `git_tag_message`; el de integracion del ancla real se salta con motivo explicito si el tag no esta y exige mensaje no vacio.
- **Prueba:** clon `--no-tags` de HEAD: antes 2 failed; despues 1 passed + 1 skipped con motivo. Local con tag: 116 passed.
- **Riesgos residuales:** mientras el operador no publique los tags en origin (escritura externa, no autorizada), CI **no verifica** el ancla real (skip visible). CI del nuevo HEAD no se ha ejecutado (sin push).
- **Estado final:** pendiente de verificacion (requiere un run de CI tras push).

### AUD-013 - P2 - pip-audit dependia del exito de pytest
- **Archivos:** `.github/workflows/ci.yml`.
- **Cambio:** job `dependency-audit` independiente, `pip-audit==2.10.1` (version actual del indice PyPI consultada en solo lectura), incluido en `needs` de `alerta-ci-rojo`.
- **Prueba:** YAML validado (jobs y `needs`); ejecucion real NOT_VERIFIABLE sin push.
- **Estado final:** pendiente de verificacion.

### AUD-004 - P2 - capture_close siempre rc=0
- **Archivos:** `scripts/capture_closing_odds.py`, `src/sqp/pipeline/closing_capture.py`, `tests/pipeline/test_closing_capture_aud004.py`.
- **Cambio:** resumen con `attempted` y `failed_leagues`; rc=1 si fallan todas las ligas intentadas, la revalidacion o el guard de abridores, tras ejecutar todos los pasos. Intradia sigue best-effort.
- **Prueba:** 12 casos; contra HEAD 8 failed / 4 passed; despues 43 passed con closing y clv.
- **Riesgos residuales:** con rc=1 `CAPTURE_CLOSE.bat` registra el fallo y salta la captura de porteros NHL de esa pasada (efecto ya existente con cualquier rc≠0); tras una revalidacion fallida persistente la tarea marcara fallo cada pasada (la visibilidad que pedia el hallazgo).
- **Estado final:** pendiente de verificacion.

### AUD-008 - P3 - La captura rebasaba el tope diario
- **Cambio:** coste previsto (mercados × regiones, modelo documentado en `odds_api.py`) antes de pedir; reconciliacion con `requests_last`.
- **Evidencia adicional:** `.closing_credits_20261011` = 310 con tope 300 (rebasamiento real).
- **Riesgo residual:** el tope es ahora conservador: con 5 regiones una liga cuesta 15 creditos y puede omitirse si quedan menos.
- **Estado final:** pendiente de verificacion.

### AUD-005 - P2 - Tenis confiaba en resultados parciales
- **Archivos:** `src/sqp/providers/espn_tennis.py`, `src/sqp/settlement/runner.py`, `scripts/backfill_tennis_results.py`, tests nuevos de proveedor y settlement.
- **Cambio:** `failed_windows` (contrato de `ESPNResultsProvider`); `results_trusted=False` con ventanas fallidas (se gradua lo que tiene resultado; no se anula por expiracion); backfill rc=1.
- **Prueba:** antes 5 failed / 1 passed; despues 6 passed; 171 relacionados; Fable 9 + 362.
- **Riesgo residual:** una ventana que falle siempre frena las anulaciones de tenis mientras dure (visible en log y salud). rc=1 del backfill: aviso en DIARIO, no bloquea la generacion.
- **Estado final:** pendiente de verificacion.

### AUD-006 - P2 - Hooks PostToolUse sin PowerShell
- **Archivos:** `.claude/settings.json`, `tests/test_hook_targets.py`.
- **Cambio:** matcher `Edit|Write|Bash|PowerShell` para check-secrets, mark-tests-pending y mark-crossreview-pending; post-edit-format sigue en `Edit|Write` (asimetria documentada).
- **Prueba:** contra settings de HEAD 3 failed; despues 39 passed. Disparo real con el harness: NOT_VERIFIABLE en esta sesion (los hooks se releen al abrir sesion).
- **Estado final:** pendiente de verificacion.

### AUD-010 - P3 - crossreview-on-stop perdia el centinela sin codex
- **Archivos:** `.claude/hooks/crossreview-on-stop.sh`, `tests/test_audit_hooks.py`.
- **Cambio:** comprobar `codex` antes del `rm`; sin codex: aviso, centinela conservado, exit 0.
- **Prueba:** test dinamico con PATH sin codex: antes failed; despues 26 passed; contratos del hook 246 passed.
- **Estado final:** pendiente de verificacion.

### AUD-007 - P3 - Log de abridores duplicaba filas
- **Archivos:** `src/sqp/storage/starters.py`, `tests/test_aud007_pitcher_log.py`.
- **Cambio:** comparacion con `_norm_str`. El `with locked(p)` propuesto por el implementador se **retiro**: la carrera es INFERRED y el lock podia lanzar `LockNoAdquiridoError` dentro del run diario (`daily.py:270-272`, sin try).
- **Prueba:** antes 2 failed / 1 passed; despues 3 passed; 147 relacionados.
- **Riesgo residual:** filas duplicadas ya existentes en el log de produccion no se reparan.
- **Estado final:** pendiente de verificacion.

### AUD-009 - P3 - _merge_results descartaba partidos reales
- **Archivos:** `src/sqp/pipeline/daily.py`, `tests/test_results_backfill.py`.
- **Cambio:** con hora en la fila reciente (`commence_time` de /scores), solo se descarta si el historico cubre una fecha local POSIBLE de ese instante ([t-12 h, t+14 h]); sin hora se conserva el ±1 dia.
- **Prueba:** contra HEAD 1 failed / 2 passed (contrapruebas: el nocturno de costa oeste se sigue descartando; sin hora se conserva); despues 91 passed con los tests del run diario.
- **Riesgo residual:** sin hora el caso sigue siendo ambiguo y se mantiene el comportamiento conservador.
- **Estado final:** pendiente de verificacion.

### AUD-011 - P3 - Pruebas de no-repositorio heredaban el Git del proyecto
- **Archivos:** `tests/test_fable_gate.py`, `tests/test_measure_tilt_nhl.py`.
- **Cambio:** `GIT_CEILING_DIRECTORIES` en el padre de `tmp_path`; ninguna asercion tocada; el basetemp sigue dentro del repo (KI-037).
- **Prueba:** mismo basetemp: antes 3 failed; despues 3 passed.
- **Estado final:** pendiente de verificacion.

### AUD-012 - P3 - La cache daba por persistido un snapshot que pudo fallar
- **Archivos:** `src/sqp/providers/odds_cache.py`, `src/sqp/providers/odds_api.py`, `src/sqp/pipeline/daily.py`, `tests/test_aud012_snapshot_pending.py`.
- **Cambio:** marca de snapshot pendiente puesta y retirada solo por el run diario; un cache hit con la marca persiste el snapshot con su instante real de adquisicion. Sin marca, comportamiento previo (sin duplicados de entradas antiguas ni de otros consumidores).
- **Prueba:** contra HEAD 3 failed / 2 passed (contrapruebas); despues 5 passed; 119 relacionados.
- **Riesgo residual:** muerte del proceso entre `put` de la cache y la marca (ventana minima) no se cubre; escritura no atomica de la cache sigue INFERRED.
- **Estado final:** pendiente de verificacion.

### AUD-001 - P2 - El matcher del backtest consume cuotas de otro dia — **BLOQUEADO**
- **Estado inicial:** confirmado (reproducido de nuevo el 2026-10-16).
- **Intento:** regla «un candidato a ±1 dia no se toma si otro resultado de la misma pareja cae exactamente en el dia del candidato» (implementacion Sonnet; tests propios en verde).
- **Por que se rechazo:** medido sobre datos reales (`scratchpad/aud001_impact.py`, comparando el matcher previo y el nuevo con `load_closing_odds` y `results_*.csv`): **MLB 606 asignaciones distintas, 254 resultados sin emparejar y 352 REASIGNADOS a otras cuotas**; NBA y NHL 0 cambios. En MLB el historico usa la fecha local oficial y las cuotas el `commence_time` UTC: en una serie de costa oeste completa la regla cruzaba etiquetas en casi cada partido — peor que el defecto. Cambio revertido (`roi_engine.py` = HEAD); diff y test guardados como evidencia en el scratchpad de la sesion (`aud001_rechazado.diff`, `test_aud001_matcher.py`).
- **Que falta:** una identidad canonica del partido (calendario MLB / `schedule_*.csv`, o la fecha LOCAL de la cuota derivada de su instante y del huso de la liga) antes de cualquier preferencia por coincidencia exacta. Es una decision de diseño cuantitativo (afecta backtests y mediciones registradas): requiere diseño y revision Fable.
- **Estado final:** BLOQUEADO, sin cambio de codigo.
