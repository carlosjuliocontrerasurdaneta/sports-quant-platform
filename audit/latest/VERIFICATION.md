# VERIFICATION — ronda `audit-2026-10-18`

- **Fecha:** 2026-10-22.
- **Verificador:** agente nuevo `independent-code-reviewer` con `model: "fable"` (Fable 5.1), en solo lectura. Fue despachado por la sesión principal (`claude-opus-5-5`), que no implementó la remediación.
- **Procedimiento:** `audits/prompts/verificar-remediacion.md`.
- **Redacción:** la sesión principal transcribió el informe del verificador. No añadió conclusiones propias.

## Veredicto: APTO CON PENDIENTES

- El único P1, AUD-001, está corregido. El verificador lo reprodujo contra el histórico.
- No hay regresiones sobre AUD-001..AUD-017.
- Quedan dos asuntos operativos abiertos: el CI de `main` en rojo por un aviso nuevo de `certifi` (NEW-001), y el run diario del 21-10, que falló en la liquidación sin causa visible (NEW-002).
- Este dictamen califica solo la remediación evaluada. No afirma ventaja predictiva ni rentabilidad.

## 1. Alcance, base, metodología y limitaciones

### Base y alcance

- **Base:** `main` @ `2985c3db8cc2ac95259db998eba7fcaa82de8472`. El árbol estaba limpio al empezar y al terminar.
- **Remediación evaluada:** `ba6f3e3`, `777b429` y `0b7c640`.
- **Commits posteriores revisados en busca de regresiones:** `e939c22`, `3ab71e9`, `18826e2`, `f4537f5`, `f92e8e1`, `e2b1391` y `2985c3d`.
- **Fuente de verdad:** el código actual. `audit/latest/` es evidencia secundaria y `FINDINGS.md` es la línea base.

### Método

Para cada ID:

- inspección del diff y de los callers;
- reproducción cuando era segura;
- tests acotados;
- estado en vivo de los controles externos, mediante lecturas de `gh` y del Programador de tareas.

Los scripts y repos temporales quedaron fuera del repositorio.

### Exclusiones

- Sin llamadas a Odds API, `codex` ni servicios de pago.
- Sin escrituras en GitHub.
- No se re-ejecutó la liquidación ni el run diario.

### Limitaciones

- Sin lectura de `logs/**` ni de `.env`. Por eso NEW-002 no se pudo diagnosticar y AUD-011 no se pudo contrastar en el log.
- AUD-014 no se contrastó de nuevo con la documentación viva de Anthropic, porque no se permitían llamadas externas.

### Efecto lateral declarado

Un script de solo lectura de AUD-008 llamó a `ResultsStore.load` sin `SQP_LOG_DIR`. Eso añadió unas pocas líneas `WARNING ... game_id repetido descartadas al leer (AUD-003)` a `logs/sqp.log` de producción. No se tocó ningún otro fichero.

## 2. Estado por ID

| ID | Prio. | Estado | Evidencia | Riesgo residual |
|---|---|---|---|---|
| AUD-001 | P1 | **verificado-corregido** | `HockeyAdapter.TIE_ADDS_GOAL=True` (`src/sqp/sports/adapters.py:277`) se pasa a `poisson_match_probs` (`:152`). La celda (k,k) se reparte en (k+1,k)/(k,k+1) (`distributions.py:283`) y los ritmos se reescalan (`_regulation_rates`). Reproducción contra `results_nhl.csv` desde 2023-10: n=4.664, 0 empates, 67,77 % de totales impares. Error de P(Over) frente al empírico en 4,5/5,5/6,5/7,5: −1,69/−0,51/−0,15/+1,07 pp, todos por debajo de 2 pp. El modelo anterior daba 0,735/0,579/0,419/0,278 frente a 0,781/0,558/0,444/0,244. El resultado no cambia con un reparto 50/50 o 52/48. Las vías de fútbol lanzan `ValueError`, así que el fútbol no cambia. Tests de distributions y nhl_tilt en verde | Comparación hecha con λ media, no con la mezcla por partido. h2h y puck line NHL se mueven décimas de pp (documentado) |
| AUD-002 | P2 | verificado-corregido | `RestModel.schedule`/`rest_days` toman el último partido, jugado o programado, estrictamente anterior. Lo llama `daily.py:869-870` antes de estimar; el walk-forward no lo llama. `test_rest.py` en verde | Solo conoce los partidos presentes en el feed de cuotas |
| AUD-003 | P2 | verificado-corregido (en la lectura) | `load` deduplica por `game_id` y se queda con la última fila por (date, ingested_at). `upsert` rechaza un `game_id` existente con fecha igual o anterior. MLB se queda con la última fecha del `gamePk`. La liquidación MLB empareja por `gamePk` | El CSV crudo conserva las filas, a propósito (Enmiendas 3(c) y 2). Un renombre de ESPN el mismo día conserva el nombre antiguo; falta el alias (preexistente) |
| AUD-004 | P2 | verificado-corregido | 28 casos del fichero en verde. Sonda propia con 10 variantes nuevas (`-am`, `--all`, `add -A` desde un subdirectorio, `:/`, `docs/../configs`, `'*.yaml'`, directorio, `cd .\configs`, `--git-dir/--work-tree`, `add -u`): las 10 salen con rc 2. Una ruta no sensible sale con rc 0 | La ofuscación deliberada sigue fuera del alcance declarado del candado |
| AUD-005 | P2 | **verificado-mitigado** | En vivo: RestartCount=3 y RestartInterval=PT15M. `check_daily_launch.py` está cableado en `CAPTURE_CLOSE.bat:38` (Capture_Close terminó con 0x0 el 22-10 a las 09:00) | El 21-10 la tarea terminó con 0x1 (centinela `stage=settle, exit_code=1`, 15:40:27Z) y no hubo filas servidas ese día: 18-10 1.091, 19-10 1.280, 20-10 1.324, 21-10 0. Ni el reintento ni el vigilante cubren un fallo de liquidación; solo queda el centinela. Causa NOT_VERIFIABLE (ver NEW-002) |
| AUD-006 | P2 | verificado-corregido | `gh api`: `secret_scanning` y `push_protection` están en `enabled`. `secret-scan` en verde en HEAD. `scan_tracked_secrets.py` sale con rc 0. El hook escanea `audit/` | `non_provider_patterns` y `validity_checks` siguen desactivados |
| AUD-007 | P2 | verificado-corregido | `timeout ${SQP_CROSSREVIEW_TIMEOUT_S:-540}`. Un rc 124 restaura el centinela. `timeout` resuelve a GNU coreutils 8.32, no al `timeout.exe` de Windows. El hook tiene 600 s | Sin `timeout` en el PATH se comporta como antes |
| AUD-008 | P3 | verificado-corregido | El corte `2026-09-13T12:36:34+00:00` coincide con `c578f52`. Se aplica en `prediction_gate._usable` y en los dos cargadores de `calibration/data.py`. Sobre `graded_*.csv`: 878 filas de cuarto, 572 antes del corte, 124 `regrade_aud008`. Las 302 filas posteriores emparejan con el histórico y **0** difieren de `_grade` | Conservador: también pierde muestra bien graduada de antes del corte |
| AUD-009 | P3 | verificado-corregido | `compute_clv` descarta un cierre con `captured_at ≤ generated_at` (`clv.py:93-102`), y ese módulo alimenta `clv_gate`. Test en verde | Los demás usos de `load_closing_odds` no calculan CLV, así que no aplica |
| AUD-010 | P3 | verificado-corregido | `est_edge_staked` está ponderado por stake, y el texto ya no compara `mean_est_edge` con el ROI. Test en verde | — |
| AUD-011 | P3 | verificado-corregido (código y test) | `SQP_LOG_DIR` en `logging_config.py`; `conftest.py` lo fija a un temporal. Test en verde | Sin lectura de `logs/sqp.log` |
| AUD-012 | P3 | verificado-corregido | Patrón `KEYED` y prefijos `ghp_`/`github_pat_`. Tests `test_aud012_*` en verde | Un hex suelto sin nombre no se detecta, a propósito |
| AUD-013 | P3 | verificado-corregido | Un fork sin `model` sale con exit 0 y un aviso (`require-dispatch-model.sh`). Tests en verde | — |
| AUD-014 | P3 | verificado-corregido (estático) | `MODEL_ROUTING.md:98` dice `claude-sonnet-5-5`/`claude-haiku-5-5`. Test de routing en verde | Sin contraste con la documentación viva |
| AUD-015 | P3 | verificado-corregido | Funciona en vivo: el #5 se abrió y se cerró solo, y el **#6 está abierto** con el rojo de `2985c3d` (NEW-001) | — |
| AUD-016 | P3 | verificado-corregido | `test_the_lock_pins_the_whole_installed_closure` en verde | `dependency-audit` está rojo por un aviso nuevo de `certifi`, ajeno al lock ampliado (NEW-001) |
| AUD-017 | P3 | **verificado-mitigado** | `_git_decide` en `resolve_t0`/`resolve_h`. Fichero completo con basetemp corto, 5 veces y con la suite en paralelo: 5 × 58 passed | `_git`, `git_show_or_none` y `git_status_porcelain` siguen convirtiendo cualquier error en `None`, igual que en `measure_el_modelo_manda.py` y `measure_tier_a_gap.py` |

## 3. Regresiones y hallazgos nuevos

- **REG-###: ninguna.** Los commits posteriores son documentación, configuración y vistas (`execution.books: [pinnacle]`, `precio_ejec`/`roi_ejec` en `daily_picks.py`). No tocan el código de ningún ID.
- **NEW-001 (preexistente, P2, TOOL_DETECTED revisado): CI de `main` en rojo en `2985c3d`** (run 39502785011).
  - Solo falla `dependency-audit`: `certifi 2026.4.22`, GHSA-6q48-6c7w-9gw2, corregido en 2026.10.19.
  - `requirements.lock:30` lo fija desde julio, y producción usa la misma versión.
  - El issue #6 `ci-rojo` está abierto.
  - Corrección mínima: `certifi==2026.10.19`. Es un cambio de dependencias y necesita autorización.
- **NEW-002 (operativo, NOT_VERIFIABLE): el run diario del 21-10 abortó en la liquidación** (centinela `settle`, exit 1, 15:40Z) y no hubo picks ese día.
  - El 19-10 y el 20-10 corrieron con el código remediado y generaron picks.
  - No hay pruebas de que la remediación sea la causa. Hace falta leer el log del operador.
- **Observación (entorno Windows):** varios tests `--medir` fallan si `--basetemp` es largo, porque `git show` devuelve «Filename too long» (MAX_PATH).
  - No es AUD-017, pero el patrón es el mismo: `git_show_or_none` traga el error.
  - Resultado: el script aborta con un motivo falso.

## 4. Validación global

| Comando | Resultado |
|---|---|
| Tests acotados de los 17 IDs (19 ficheros) | **532 passed, rc=0** |
| `PYTHONPATH=src python -m pytest -q -p no:cacheprovider --basetemp=<scratchpad>` | **4 failed, 3377 passed, 1 skipped, rc=1** (1 h 01 min). Los 4 fallos son `tests/research/test_measure_segment_market_weight.py::test_medir_*`, de tipo **ENVIRONMENTAL_FAILURE**: MAX_PATH por el basetemp largo, reproducido con `git show`. Pasan 5 de 5 veces con basetemp corto |
| `pytest tests/research/test_measure_segment_market_weight.py` con basetemp corto (×5) | 58 passed × 5, rc=0 |
| `ruff check src scripts tests --no-cache` | All checks passed, rc=0 |
| `mypy src` | Success, 114 ficheros, rc=0 |
| `python scripts/scan_tracked_secrets.py` | rc=0 |
| `python scripts/sync_agent_instructions.py --check` | synchronized, rc=0 |
| CI en HEAD (`gh run view 39502785011`) | Linux ×4, `test-windows` y `secret-scan` en verde; **`dependency-audit` en rojo** (NEW-001) |

## 5. P0/P1 abiertos

Ninguno. AUD-001 está verificado-corregido. NEW-001 es P2.

## 6. Justificación del veredicto

La regla aplicable es la primera que se cumple.

1. **NO APTO no aplica:** no hay P0/P1 abiertos, ni regresiones, ni evidencia de corrección inválida.
2. **VERIFICACIÓN INCOMPLETA no aplica:** todos los IDs tienen evidencia de código y de tests ejecutados. Los fallos de la suite son de entorno, están explicados y pasan al re-ejecutarlos.
3. **APTO CON PENDIENTES aplica**, por lo que queda en seguimiento:
   - AUD-005 y AUD-017, que están mitigados;
   - NEW-001 y NEW-002;
   - AUD-011 y AUD-014, que no se contrastaron en vivo.

El verificador señala un caso límite: si se exigiera el contraste vivo de AUD-014, la regla 2 daría VERIFICACIÓN INCOMPLETA. Lo considera suficiente para un cambio documental LOW, y la sesión principal acepta ese criterio.

## 7. Próxima acción

1. **Operador:** revisar el log de la liquidación del 21-10 (NEW-002) y confirmar que el run del 22-10 a las 12:00 termina con 0x0.
2. **Con autorización:** subir `certifi` a 2026.10.19 en `requirements.lock` (NEW-001). Así `dependency-audit` vuelve a verde y `cierre-ci-verde` cierra el #6.
3. **Opcional (P3):** aplicar el patrón de `_git_decide` a `git_show_or_none`, a `git_status_porcelain` y a los scripts hermanos.
