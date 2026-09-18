# Diagnóstico independiente — auditor Claude — ronda `audit-2026-09-18`

Fecha: 2026-09-18 (08:30–09:30 UTC-3). Modelo: `claude-opus-5` (sesión única,
sin subagentes). Base: `59521643440213f6a7982b10e71d349a8d8dd088` (`main`,
sincronizado con `origin/main`: 0 por detrás / 0 por delante). Python 3.14.4,
win32. Contrato: `.claude/automation/audit-workflow.md`; loop
`.claude/loops/audit.md`; referencias de `.claude/skills/full-audit/references/`.

## Resumen

- **Confirmados: 4** (MEDIUM 2, LOW 2). P0: 0. P1: 0. P2: 2. P3: 2.
- Observaciones informativas: 6. Descartes: 2. No verificables: 3.
- Validaciones: suite completa **2191 passed, 1 skipped** (24:58, bajo carga
  concurrente); `ruff check` 0; `mypy src` 0 (105 ficheros); CI remoto
  **success** en HEAD (run 35301664397, 2026-09-18T03:02Z);
  `sync_agent_instructions.py --check` sincronizado;
  `validate_claude_model_routing.py` OK.
- Estado de los controles (no solo su configuración): 5 tareas `SQP_*` con
  último rc 0x0; gate de predicción default-deny (0/48 habilitados); monitor
  de degradación con 11 pausas vivas; 4 calibradores live sin defecto
  estructural; historial del Programador de tareas **deshabilitado**.
- Ninguna afirmación de rentabilidad: hit rate, ROI esperado y ROI realizado
  se distinguen en todo el informe; ninguno se demuestra positivo.

## Alcance, independencia y limitaciones

- Alcance: `src/sqp` (19.470 líneas, 105 módulos), `scripts/` (62),
  BAT/PS1/CMD operativos, `configs/`, `tests/` (133 ficheros), CI, hooks,
  sistema `.claude/` (34 skills, 11 agentes, 17 comandos, 30 loops), datos
  operativos **solo por agregados** (nombres, tamaños, cabeceras, conteos).
- Ronda ya inicializada por el coordinador (00:04 local) con
  `previous_round=audit-2026-09-16` preservada en `audit/audit-2026-09-16/`;
  **verificado por hash**: 22 ficheros idénticos a `HEAD:audit/latest/*`.
  No se reinició ni archivó la ronda; `claude/` estaba vacío.
- Contaminación declarada: el contexto de sesión incluye la memoria del
  proyecto (conclusiones de rondas anteriores, KI-053, decisiones). No se leyó
  `openai/REPORT.md` ni `audit/audit-2026-09-16/` hasta fijar conclusiones
  propias (paso 7). El hook `check-secrets.sh` señaló `openai/EVIDENCE.json:315`
  en cada comando; se inspeccionó **solo esa línea** con valor enmascarado
  (ver DESCARTE-1), sin leer hallazgos.
- Lectura denegada de `.env` y de `logs/` por vía directa (deny list del
  harness). Los logs se consultaron mediante scripts que devuelven únicamente
  agregados (fechas de cabecera, conteos), conforme a `CLAUDE.md`.
- Escritura no intencionada: `scripts/health_check.py` reescribe
  `data/output/pipeline_health.json` (artefacto de monitorización regenerable,
  ignorado por git) al ejecutarse; se ejecutó a las 09:01:42 para leer el
  estado. No se tocó ningún dato productivo, fuente, test ni configuración.
- No ejecutado: `pip-audit`, BATs, `codex review`, backfills, backtests,
  `train_*`. Sin subagentes (regla de `CLAUDE.md`).
- `.claude/automation/runtime/current-task.md` no se actualizó (fuera de los
  destinos de escritura del diagnóstico); su contenido es de 2026-09-13
  (`Status: closed`), por lo que el paso 1 de `/verification-gate` no dispone
  de criterios de aceptación vigentes para esta ronda.

## Matriz de cobertura

| Área | Prio | Estado | Componentes | Método | Validación / estado observado | Limitaciones |
|---|---|---|---|---|---|---|
| Ejecución principal (run diario) | P0 | REVISADA | `scripts/run_all.py`, `pipeline/daily.py` (run_league, _finalize, caps), `pipeline/probabilities.py`, `risk/kelly.py`, `markets/edge.py` | lectura completa; trazado de flujo cuotas→consenso→no-vig→ajustes→calibración→edge→Kelly→gates→stake 0 | suite 2191 passed; `run_diario.log`: cabeceras 10,12,13,14,17-09 | no se ejecutó el run |
| Liquidación | P0 | REVISADA | `settlement/settle.py`, `settlement/runner.py`, `scripts/settle_all.py`, `pipeline/cleanup.py` | lectura completa de grading, dedup, superseded, voids, lock | tests de liquidación en suite; `settle_all.log` cabeceras 10,12,13,14,17-09 | — |
| Gates y riesgo | P0 | REVISADA | `risk/prediction_gate.py`, `risk/degradation.py`, `risk/bankroll.py`, `configs/default.yaml`, `Settings.load` | lectura; config efectiva impresa sin secretos; registros leídos por agregados | `prediction_gate.json` 17/09 15:09Z: 0/48 allowed, K=41, n_cortes=48; `degradation_pause.json` 11 pausas; `clv_gate.json` 0/50 | — |
| Calibración | P0 | REVISADA | `calibration/calibrator.py`, `calibration/data.py`, `calibration/pergame.py`, registro live/staging | lectura; `structural_defect` ejecutado sobre los 4 live | 4/4 sin defecto; **CLAUDE-001** | promoción no ejecutada |
| Modelos / adaptadores / backtest | P1 | REVISADA_PARCIALMENTE | `sports/adapters.py` (MLB), `backtesting/engine.py`, `features/mlb.py`, `models/ml_predict.py` | lectura de walk-forward (observe tras cambio de día, warmup) y del adaptador MLB | leakage no detectado en el walk-forward; `ml_predict` sin consumidores en el camino de picks (OBS-4) | `distributions.py`, `roi_engine.py`, `tuning.py` no releídos línea a línea |
| Proveedores / cuota | P1 | REVISADA | `providers/odds_api.py`, `pipeline/closing_capture.py`, `pipeline/budget.py`, `pipeline/revalidation.py` | lectura de timeouts (30 s), reintentos, cache TTL 6 h acotado a 90 min en el run, `force_refresh` en cierre | `capture_close.log`: 88 capturas, 1.320 créditos (15/captura) → **CLAUDE-003** | ESPN / MLB statsapi no releídos |
| Almacenamiento / atomicidad / concurrencia | P0 | REVISADA | `storage/lock.py`, `storage/served_store.py`, `storage/atomic.py` (por consumidores), `_persist_settled` | lectura de lock O_EXCL + stale + Windows PermissionError; RMW bajo lock en los 4 escritores | — | `odds_store.py`, `feature_store.py` no releídos |
| BAT / tareas programadas | P0 | REVISADA | `DIARIO_COMPLETO.bat`, `RUN_DIARIO_ALL.bat`, `SETTLE_ALL.bat`, `CAPTURE_CLOSE.bat`, `rotate_log.cmd` | lectura + `Get-ScheduledTask/Info` + agregados de logs | 5 tareas Ready, último rc 0x0; Diario 17/09 12:00; Capture: instancia de 23:30 reanudada a 08:39 (**OBS-2**); historial del Programador OFF (**CLAUDE-002**) | `BACKFILL_ALL.bat`, `VALIDATE_OOS.bat`, `REFRESH_ML.bat` no leídos |
| CI/CD | P1 | REVISADA | `.github/workflows/ci.yml` | lectura + `gh run list` | **success** en HEAD (35301664397); acciones sin pin a SHA (B-02 heredado, persistente) | — |
| Hooks de Claude Code | P1 | REVISADA | `settings.json`, 7 hooks, `_targets.py`, `_secret_literals.py` | lectura; observación del comportamiento real en sesión | **CLAUDE-004**; marcador `.tests-pending` (00:19) arma la suite al Stop de una sesión de solo lectura (OBS-3) | duración del subconjunto `not slow` en medición al cierre |
| Skills / loops / routing | P1 | REVISADA_PARCIALMENTE | 34 skills, comandos, loops, `MODEL_ROUTING`, prompts generados | frontmatter presente en 34/34; referencias `.claude/**` resueltas (solo rutas de runtime ausentes, esperado); `--check` sincronizado; routing OK | — | contenido de cada skill no revisado línea a línea |
| Tests | P1 | REVISADA | `tests/` | suite completa; inventario de skip/xfail (35 condicionales de entorno, 1 skipped real) | 2191 passed; sin xfail | flakiness no medida |
| Seguridad / secretos | P0 | REVISADA | `.gitignore`, ficheros versionados escaneados con el detector del proyecto, hooks | escaneo de todos los `.py/.yaml/.json/.bat/.ps1/.sh/.md/.lock` versionados | 0 secretos reales; 5 coincidencias en tests son fixtures del propio detector; `.env` ignorado (`.gitignore:4`) | `.env` no legible (por diseño) |
| Dependencias | P2 | REVISADA_PARCIALMENTE | `pyproject.toml`, `requirements.lock`, CI `pip-audit` | lectura | `pip-audit` corre en CI (verde) | no ejecutado en local |
| Datos operativos | P0 | REVISADA_PARCIALMENTE | `data/bets`, `data/calibration`, `data/predictions`, `data/models`, `data/odds` | solo nombres, tamaños y agregados JSON | `data/odds` 953 MB; 881/1578 liquidadas sin cierre (55,8 %) | contenido de CSV no cargado (regla del proyecto) |
| Rendimiento | P2 | REVISADA_PARCIALMENTE | `apply_calibration` (defecto estructural por llamada), carga de odds inerte | lectura | sin defecto demostrable | no perfilado |
| Documentación / Obsidian | P3 | REVISADA_PARCIALMENTE | `Obsidian/Tareas.md:104`, `Conocimiento/Calibración.md`, docstrings | solo lo necesario para CLAUDE-001 | contradicción registrada en CLAUDE-001 | resto EXCLUIDA (fuera del comportamiento del sistema) |
| Docker / Makefile | P3 | REVISADA | `Dockerfile`, `Makefile` | lectura | demo por defecto, usuario no root | no construido |
| Orquestación de especialistas | — | NO_APLICABLE | — | un solo auditor, sin delegación (regla de `CLAUDE.md`) | — | — |
| `logs/`, `.env` | — | NO_VERIFICABLE (directo) | — | agregados por script | — | acceso directo denegado |

## Hallazgos confirmados

### CLAUDE-001 — El registro live de calibración contiene la clave sandbox `mlb_h2h_pergame`; `mlb_h2h` se sirve en crudo mientras health y dashboard lo cuentan como calibrado

- Categoría: contrato / calibración. Severidad: **MEDIUM**. Confianza: HIGH.
  Evidencia: **STATICALLY_VERIFIED**. Prioridad: P2.
- Archivos: `data/models/calibration_methods.json` (claves
  `mlb_h2h_pergame, mlb_spreads, mlb_totals, wnba_spreads`);
  `data/models/promotion_log.csv:102`
  (`2026-08-23T04:31:09Z,mlb_h2h_pergame,promoted,beta`);
  `data/models/staging/calibration_methods.json` (sigue conteniendo la clave);
  `src/sqp/calibration/pergame.py:20-23,54-57`; `calibrator.py:976-991`
  (`calibration_key` → `"mlb_h2h"`), `calibrator.py:745-790`
  (`promote_calibrators(keys=None)` promueve **todo** staging);
  `src/sqp/monitoring/health.py:80-103` (`_live_calibration_markets` →
  `["h2h_pergame","spreads","totals"]`); `audit/html_report.py:259-275`
  (`En produccion: 4`); `Obsidian/Tareas.md:104` («candidato per-game
  `mlb_h2h_pergame` (staged)»).
- Activación: cualquier `scripts/promote_calibration.py` sin `--keys`
  (promoción completa) adopta la clave sandbox; ya ocurrió el 2026-08-23.
- Problema: `pergame.py` fija el contrato «entrenamiento bajo la clave SANDBOX
  `<liga>_h2h_pergame` y SOLO en staging: produccion aplica `<liga>_h2h`, asi
  que un candidato per-game jamas llega a live por este camino; adoptarlo es
  una decision aparte». `promote_calibrators` no distingue la clave sandbox y
  la promovió. Producción resuelve `calibrate_probability(p, "mlb", "h2h")` →
  `calibration_key` = `mlb_h2h` → ausente del registro → **no-op** (crudo).
- Esperado: o bien la adopción explícita (copia a `mlb_h2h` tras la
  evaluación cruzada que exige el docstring), o bien que el registro live no
  contenga claves que ningún consumidor resuelve.
- Observado: registro live con 4 entradas, de las que 1 es inerte;
  `health_check.py` imprime `mlb … calibration=True` y `_live_calibration_markets`
  devuelve un «mercado» `h2h_pergame`; el dashboard cuenta 4 «En produccion»;
  `Tareas.md` lo sigue llamando staged.
- Causa raíz: la promoción opera sobre el registro de staging completo y la
  clave sandbox se escribe en ese mismo registro (`train_pergame_calibrator`).
- Consecuencia: el moneyline MLB —el mercado para el que se construyó el
  calibrador per-game (sobreconfianza en bins 0,5–0,7, `Conocimiento/Calibración.md:22`)—
  se sirve sin calibrar, con el operador y las vistas creyendo lo contrario.
  Impacto acotado hoy: el gate de predicción usa `model_probability` pura y
  todos los stakes son 0 (default-deny), así que no afecta al dinero ni al
  gate; afecta a `p_decision`, al `estimated_edge` servido y al ranking de
  picks de `mlb|h2h`.
- Controles existentes: `structural_defect` (no aplica, el mapa es válido);
  `_orphan_calibration_entries` (no aplica: el artefacto existe). Ninguno
  detecta una clave sin consumidor.
- Corrección mínima (requiere decisión del operador — parámetro de modelo):
  (a) `promote_calibrators` rechaza claves con `PERGAME_SUFFIX` salvo bandera
  explícita de adopción que las instale bajo `<liga>_h2h`; (b) demover
  `mlb_h2h_pergame` del registro live (o adoptarla) y reflejarlo en
  `promotion_log.csv`; (c) `_live_calibration_markets` y la tarjeta del
  dashboard ignoran o marcan claves que `calibration_key` nunca produce; (d)
  actualizar `Tareas.md:104`.
- Pruebas: test que promueva un staging con `x_h2h_pergame` y verifique que
  el live no la contiene sin la bandera; test de `_live_calibration_markets`
  con la clave sandbox → no listada; test de `calibrate_probability("mlb","h2h")`
  con solo `mlb_h2h_pergame` en el registro → no-op documentado.
- Aceptación: el registro live solo contiene claves resolubles por
  `calibration_key`; health/dashboard coinciden con lo que sirve el pipeline.
- Limitaciones: no se reproduce en ejecución (bastaría llamar a
  `calibrate_probability(0.6,"mlb","h2h")` y comparar con
  `apply_calibration` bajo la clave sandbox; no se hizo para no cargar
  artefactos pickle adicionales).

### CLAUDE-002 — El historial del Programador de tareas está deshabilitado: una tarea que no llega a lanzarse no deja rastro diagnosticable

- Categoría: observabilidad / control. Severidad: **MEDIUM**. Confianza: HIGH.
  Evidencia: **STATICALLY_VERIFIED** (estado del sistema). Prioridad: P2.
- Evidencia: `Get-WinEvent -ListLog 'Microsoft-Windows-TaskScheduler/Operational'`
  → `IsEnabled=False Records=2`; consulta de eventos de 9 días → «No se
  encontraron eventos». `Get-ScheduledTaskInfo` conserva solo `LastRunTime`
  y `LastTaskResult`. Cabeceras de `logs/run_diario.log` y `settle_all.log`:
  10, 12, 13, 14, 17-09; `diario_completo.log`: 10, 12 (×2), 13, 14, 17-09.
  Es decir, **no hay rastro de lanzamiento el 11, 15 ni 16-09**, y la causa
  (máquina apagada, tarea no disparada, fallo previo al primer `echo`) no puede
  establecerse desde el sistema.
- Activación: cualquier día en que `SQP_Diario_Completo_Cdev` no complete su
  primera línea de log.
- Esperado: el propio Programador registra inicio/fin/código por instancia
  (eventos 100/102/103/201/203), independientemente del BAT.
- Observado: el único registro independiente del proceso es
  `pipeline_liveness` (health), que se ejecuta al iniciar sesión
  (`open_dashboard.ps1`) o dentro del propio run; dice **que** no hubo run,
  no **por qué**.
- Causa raíz: el log operativo del Programador está desactivado (valor por
  defecto de Windows en algunas ediciones).
- Consecuencia: repetición del patrón documentado en AUD-MED-001 (2026-09-08):
  «la ausencia de rastro convierte un fallo en un fallo indiagnosticable».
  Tres días sin run en ocho (11, 15, 16-09) sin causa establecida.
- Controles existentes: `pipeline_liveness` (detecta), `:log` del BAT (solo
  si el BAT arranca), `run_status` (solo desde la rama `:error`).
- Corrección mínima: habilitar el historial
  (`wevtutil sl Microsoft-Windows-TaskScheduler/Operational /e:true`, requiere
  elevación; documentarlo en el runbook de `set_tasks_unattended.ps1`) y que
  `health_check`/`open_dashboard.ps1` lean `NumberOfMissedRuns`/`LastTaskResult`
  de las 5 tareas para incluirlos en `pipeline_health.json`.
- Pruebas: manual (no automatizable en CI): tras habilitar, `Get-WinEvent`
  devuelve eventos 100/102 de la siguiente ejecución.
- Aceptación: una ausencia de run queda explicada por el registro del
  Programador o por el propio log del BAT.
- Limitaciones: la causa de los tres días sin run no se pudo establecer
  (NOT_VERIFIABLE); el 15/16-09 consta en memoria como incidente conocido,
  el 11-09 no.

### CLAUDE-003 — La captura de cierre en tenis pide tres mercados (15 créditos) cuando el run diario solo genera h2h (5 créditos)

- Categoría: cuota / integración externa. Severidad: **LOW**. Confianza: HIGH.
  Evidencia: **STATICALLY_VERIFIED**. Prioridad: P3.
- Archivos: `src/sqp/pipeline/closing_capture.py:118`
  (`client.fetch_odds(league, sport_key)` sin `markets`);
  `providers/odds_api.py:288` (default `"h2h,spreads,totals"`);
  `pipeline/daily.py:704` (`markets = "h2h" if family == "tennis"`);
  `pipeline/budget.py:33-38` (coste = mercados × regiones).
- Evidencia: `capture_close.log` (agregado): 88 capturas con crédito, 1.320
  créditos → 15 por captura (5 regiones × 3 mercados) en todas las ligas;
  22 capturas de tenis (`tennis_wta_guadalajara_open` 19, `tennis_wta_us_open` 3)
  = 330 créditos frente a 110 si se pidiera solo h2h.
- Esperado: la captura de cierre pide los mismos mercados que generó picks
  (h2h en tenis).
- Consecuencia: ~220 créditos de más en el periodo del log (~8 días) sobre un
  plan de 20.000/mes y un tope diario de cierre de 300; además el snapshot de
  cierre de tenis incluye mercados que ningún pick usa.
- Corrección mínima: pasar `markets` según `_league_meta(league)["family"]`
  (reutilizar la regla de `daily.py`). Prueba: test de `capture_closing` con
  cliente falso que registre `markets` para una liga de tenis.
- Limitaciones: The Odds API cobra por mercado ofrecido; si un torneo no
  ofrece spreads/totals el sobrecoste real sería menor (no verificado).

### CLAUDE-004 — `check-secrets.sh` con `--with-git` re-escanea en cada comando todo el `git status` y marca como secreto código fuente embebido en JSON

- Categoría: hooks / falso positivo persistente. Severidad: **LOW**.
  Confianza: HIGH. Evidencia: **REPRODUCED** (en esta sesión). Prioridad: P3.
- Archivos: `.claude/hooks/check-secrets.sh` (`_targets.py --with-git` en
  `PostToolUse` para `Edit|Write|Bash`), `.claude/hooks/_secret_literals.py:8-12`
  (`ASSIGNMENT` acepta valores sin comillas de ≥8 caracteres).
- Evidencia: en >15 comandos Bash de esta sesión el hook devolvió
  `audit/latest/openai/EVIDENCE.json:315: literal sospechoso`. La línea 315 es
  un campo `"output"` de 20.006 caracteres con código fuente de `odds_api.py`
  escapado; la coincidencia es la asignación `self.<clave> = <clave>` de
  `odds_api.py:80` seguida de `\r\n` escapado (el valor capturado es el propio
  identificador más los 4 caracteres de escape, 11 en total). No es un
  secreto (DESCARTE-1). El fichero no es de esta sesión ni fue tocado por ella.
  Al escribir este informe, el hook marcó también las dos líneas que citaban
  la coincidencia: reproducción adicional.
- Esperado: el hook señala ficheros que el turno escribió; un identificador
  asignado a sí mismo no es un literal.
- Consecuencia: alarma repetida que no cambia con ninguna acción del auditor
  (el fichero pertenece al otro auditor) — el mismo modo de fallo que el
  proyecto documenta en `discovery-coverage.md` («una alarma que suena sin
  motivo es una alarma que se aprende a ignorar»). Un secreto real en un
  fichero nuevo quedaría enterrado entre repeticiones.
- Corrección mínima: (a) excluir `audit/**` del escaneo (como ya se excluyen
  `data/`, `logs/`), o escanear solo ficheros cuyo hash cambió desde el último
  aviso; (b) en `ASSIGNMENT`, descartar valores que sean identificadores
  iguales al nombre asignado o que contengan `\r`/`\n` escapados.
- Pruebas: extender `tests/test_audit_hooks.py` con la línea reproducida
  (la asignación `self.<clave> = <clave>` de `odds_api.py:80` seguida de
  `\r\n` escapado, dentro de una cadena JSON) → 0 hallazgos.

## Observaciones informativas (no defectos)

- **OBS-1** Gate de predicción: 48 cortes evaluados con `K=41` fijo
  (`PREDICTION_GATE_K`), umbral de re-pre-registro 50. FWER bajo el nulo
  ≈ 1−(1−0,05/41)^48 ≈ 5,7 % (dentro del +22 % aceptado). 6 cortes son torneos
  de tenis (n máx. 110, nunca alcanzan 300 dentro de un torneo); dos torneos
  más disparan el aviso de re-pre-registro. Mayor n: `mlb|h2h` y `mlb|spreads`
  231/300.
- **OBS-2** Disponibilidad de la máquina: `capture_close.log` registra 26, 5,
  17, 25, 17, 0, 6, 28 capturas los días 10–17-09 (máximo teórico 48/día);
  ninguna entre 00:00 y 08:30 del 18-09; la instancia lanzada a las 23:30 del
  17-09 escribió su primera línea Python a las 08:39 del 18-09 (proceso
  suspendido ~9 h). Consecuencia medible: 881 de 1.578 liquidadas (55,8 %)
  sin cierre emparejado (`clv_20260917.md`) → CLV informativo y revalidación
  pre-partido sin cobertura nocturna. No es defecto de código; es un límite
  operativo del host (INFERRED en cuanto a la causa).
- **OBS-3** `.claude/.tests-pending` existe desde las 00:19 (otra sesión); el
  hook Stop ejecutará `pytest -m "not slow"` (sin `-p no:cacheprovider`) al
  cerrar esta sesión de solo lectura. AUD-006 (ronda anterior) redujo el
  disparo, pero el marcador persiste entre sesiones. Estado del control:
  el subconjunto `not slow` tardó **489,8 s (1967 passed, 225 deselected)**
  bajo carga concurrente, frente al timeout de 600 s del hook: cabe, con un
  margen del 18 % que una máquina ocupada puede consumir.
- **OBS-4** `models/ml_predict.py` y los `*_moneyline_model.joblib` no tienen
  consumidor en el camino de picks; `health_check` los reporta
  (`moneyline_model=True`) como si fueran vivos. Código experimental separado
  de producción, coherente con la política; la tarjeta es engañosa a la lectura.
- **OBS-5** `apply_calibration` ejecuta `structural_defect` (tres barridos)
  en **cada** llamada por candidato; correcto y seguro, coste no medido.
- **OBS-6** B-02 heredado persiste: acciones del CI en `@v4`/`@v5` sin pin a SHA.

## Descartes

- **DESCARTE-1** «Secreto en `audit/latest/openai/EVIDENCE.json:315`»
  (TOOL_DETECTED por el hook): DISMISSED. Valor capturado = identificador
  `api_key` + `\r\n` escapado dentro de código fuente citado. Sin secreto.
- **DESCARTE-2** Coincidencias del detector en `tests/test_audit_hooks.py:29-31,49`
  y `tests/test_portable_setup.py:36`: fixtures del propio detector y de
  `.env` temporal; DISMISSED.

## No verificables

- **NV-1** Causa de los días sin run (11, 15, 16-09): sin historial del
  Programador (CLAUDE-002).
- **NV-2** Contenido de `.env` (por diseño); la configuración efectiva se
  imprimió desde `Settings.load()` sin secretos y coincide con `default.yaml`.
- **NV-3** Coste real de spreads/totals en torneos de tenis en The Odds API
  (CLAUDE-003 asume el modelo de `budget.py`).

## Comparación histórica (ronda `audit-2026-09-16`, leída tras fijar conclusiones)

- AUD-001..AUD-007: `STATUS.md` los declara verificados-corregidos o cerrados
  por decisión. No se reabre ninguno: el código actual conserva
  `realized_roi_parts` como definición única (AUD-002), HEAD es
  autoconsistente y sincronizado (AUD-003), `.codex-tmp` sin residuo (AUD-004),
  `execution.books` avisa y no cablea (AUD-005), `--with-git` solo en escritura
  para el marcador de tests (AUD-006; OBS-3 es su residuo entre sesiones).
- Heredado B-02: persistente (OBS-6). CL-02: cerrado (confirmado:
  `data/models/retired/wnba_totals_calibration_iso.joblib`).
- CLAUDE-001..004: **nuevos** (la ronda del 13-09 listó `mlb_h2h_pergame/beta`
  en el registro live sin señalarlo).
- Adyacente de la ronda anterior (pricing Normal con líneas de cuarto, ≤0,32 pp):
  no revalidado en esta ronda (fuera del recorrido).

## Plan priorizado

1. P2 CLAUDE-001 — decisión del operador (adoptar o demover) + candado en
   `promote_calibrators` + coherencia de health/dashboard/Tareas.
2. P2 CLAUDE-002 — habilitar historial del Programador (elevación) + exponer
   `LastTaskResult`/`NumberOfMissedRuns` en `pipeline_health.json`.
3. P3 CLAUDE-003 — `markets` por familia en `capture_closing`.
4. P3 CLAUDE-004 — excluir `audit/**` del hook y endurecer `ASSIGNMENT`.

## Riesgos residuales

- El gate de predicción sigue en default-deny; nada de lo anterior cambia esa
  situación ni la debe cambiar sin el criterio pre-registrado.
- La cobertura de cierre (~44 %) limita cualquier medición futura de CLV.
- Auditoría completa ≠ código corregido ni ventaja predictiva demostrada.
