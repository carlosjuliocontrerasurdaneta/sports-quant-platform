# Diagnóstico independiente — Claude (Opus 5) — ronda `audit-2026-09-16`

- Fecha del diagnóstico: 2026-09-17 (UTC 11:30–12:20). Ronda inicializada el
  2026-09-16 con `claude/` vacío; se continúa la misma ronda sin reiniciarla ni
  archivarla (contrato: «un segundo auditor de la misma ronda no reinicia»).
- Base Git: `44e48f26045f734fc479a127a9eb35f776c6483c` (main, ahead 2 de la
  referencia local `origin/main` = `96a4749`). Árbol sucio: 57 entradas
  (34 tracked modificados/borrados/renombrados, 14 sin seguimiento), todas
  preexistentes y separadas de esta auditoría; `git status --porcelain -- src
  scripts configs *.bat` vacío (el guard de árbol de `DIARIO_COMPLETO.bat` pasa).
- Intérprete: Python 3.14.4 (numpy 2.4.4, pandas 3.0.2, scikit-learn 1.9.0).
- Modelo: `claude-opus-5`, sin subagentes (validación por segundo método en la
  misma sesión: lectura estática + reproducción con las funciones del proyecto
  + medición sobre datos, sólo agregados).
- Contaminación de contexto: durante el análisis principal NO se leyó ningún
  informe histórico ni `audit/latest/openai/reproduce.py`. Ese script (único
  residuo del auditor OpenAI; no hay `openai/REPORT.md`) se leyó al cerrar las
  conclusiones propias (paso 7) y sus tres hipótesis se trataron como
  `TOOL_DETECTED` y se revalidaron con código propio. La ronda anterior
  (`audit/audit-2026-09-13/`) se leyó sólo en el paso 7.
- Alcance: auditoría integral sobre el working tree (src/sqp, scripts, BAT,
  configs, tests, CI, hooks, `.claude` contratos, datos sólo por agregados).
  Cambios locales sin commitear incluidos.

## Resumen

7 hallazgos confirmados: 1 HIGH, 4 MEDIUM, 2 LOW. P0: 0. P1: 2. Sin
`CRITICAL`. La cadena dinero (odds → no-vig → edge → Kelly → liquidación →
ledger) está intacta para líneas enteras y de medio punto; el defecto de mayor
impacto es que el **pricing de líneas asiáticas de cuarto ignora la liquidación
a medias** que `settle.py` ya aplica desde AUD-MED-002 (CLAUDE-001), con
desviaciones de 7–13 pp que invierten el signo del EV en esos mercados.

Nada de esto autoriza correcciones. La auditoría no demuestra ventaja
predictiva ni rentabilidad: el gate de predicción tiene 0/48 cortes permitidos
y todo el stake real es 0.

## Inventario y matriz de cobertura

| Área | Prio | Estado | Componentes | Método | Validación / estado observado | Limitaciones |
|---|---|---|---|---|---|---|
| Mercado y riesgo (odds, vig, edge, Kelly, settlement_math) | P0 | REVISADA | `markets/odds.py`, `vig.py`, `edge.py`, `settlement_math.py`, `risk/kelly.py` | lectura completa + reproducción numérica | suite verde | — |
| Pricing por familia (Poisson/Normal) | P0 | REVISADA | `models/distributions.py`, `sports/adapters.py`, `pipeline/probabilities.py` | lectura + reproducción con `_grade` vs `poisson_match_probs` | **CLAUDE-001** | Normal (NBA/NFL) no reproducido para cuartos: no se cotizan |
| Liquidación y ledger | P0 | REVISADA | `settlement/settle.py`, `runner.py`, `risk/bankroll.py` (cabecera) | lectura + reproducción de medias | **CLAUDE-002** | `bankroll.py` sólo parcialmente leído |
| Pipeline diario | P0 | REVISADA | `pipeline/daily.py` (run_league, merge, freshness), `closing_capture.py`, BATs | lectura selectiva | guard de árbol pasa; gate 0/48 permitidos | `revalidation.py`, `intraday_scan.py`, `cleanup.py` no leídos en esta ronda (REVISADA_PARCIALMENTE) |
| Gate de predicción / degradación | P0 | REVISADA_PARCIALMENTE | `risk/prediction_gate.py` | lectura de umbrales y latch; registro actual (`generated_at` 2026-09-16T20:20Z, 48 cortes, 0 allowed, min_n 300, α 0,05/41) | — | `degradation.py`, `clv_gate.py` no leídos |
| Features / ML / research (commit 72d07d8) | P1 | REVISADA | `features/temporal.py`, `builders.py`, `mlb.py`, `research.py`, `evaluation/compare.py`, `feature_shadow.py`, `models/ml_train.py`, `storage/feature_store.py` | diff completo + lectura | tests de research/shadow verdes; ML no alimenta picks (verificado: sin `joblib`/blend ML en `daily.py`) | **CLAUDE-007**; OBS-1 |
| Calibración | P1 | REVISADA_PARCIALMENTE | `calibration/*` | sólo consumidores de `isin(["win","loss"])` y config (`method: auto`, `auto_promote: false`) | — | `calibrator.py` (991 líneas) no leído íntegro |
| Proveedores / cuota | P1 | REVISADA_PARCIALMENTE | `providers/*.py` timeouts, `closing_capture.py` presupuesto | grep de `timeout=` (todos acotados) + lectura | — | `odds_api.py`/`odds_cache.py` no leídos íntegros |
| Almacenamiento / atomicidad | P1 | REVISADA_PARCIALMENTE | `results_store.py`, `_persist_settled` (lock), `atomic.py` por uso | lectura | — | `served_store.py`, `lock.py` no leídos |
| Seguridad / secretos | P1 | REVISADA | `.gitignore`, `git ls-files` (0 ficheros de credenciales), hooks `check-secrets`, timeouts | inspección | — | `.env`/`.env.example` no inspeccionables (permiso denegado) |
| CI/CD (estado) | P1 | REVISADA | `.github/workflows/ci.yml`; `gh run list` | inventario + estado | **verde** en `origin/main` (a2ee66c, 2026-09-17T03:50Z); pero HEAD local no está en CI (**CLAUDE-003**) | acciones sin pin a SHA (B-02, persistente) |
| Tareas programadas (estado) | P1 | REVISADA | `Get-ScheduledTask SQP_*` | estado 2026-09-17 | S4U las 4 batch; `Diario_Completo` rc=1 el 09-16 12:00 (guard, corregido por 44e48f2), próximo 09-17 12:00; `Validate_OOS` rc=0 09-17 00:00; `Capture_Close` rc=0; `Backfill` rc=0 09-14 | `logs/` no inspeccionable (permiso denegado): último log del diario no leído |
| Centinela / salud | P1 | REVISADA_PARCIALMENTE | `run_status.py`, `health.py`, `data/output/pipeline_health.json` | lectura + estado | `status: OK` a 2026-09-16T20:20Z | `logs/run_status/*.json` no legibles (permiso) |
| Hooks Claude | P2 | REVISADA | `.claude/settings.json`, `hooks/*.sh`, `_targets.py` | cableado + reproducción | **CLAUDE-006** | — |
| Skills / loops / prompts / routing | P2 | REVISADA | `.claude/automation/audit-workflow.md`, `loops/audit.md`, `skills/full-audit/**`, `audits/prompts/*` | `sync_agent_instructions.py --check` (sincronizado, rc 0); escaneo de referencias rotas (9, todas históricas en `memory/`) | **CLAUDE-003** (fuentes sin trackear) | — |
| BAT operacionales | P1 | REVISADA | `DIARIO_COMPLETO`, `RUN_DIARIO_ALL`, `SETTLE_ALL`, `CAPTURE_CLOSE`, `BACKFILL_ALL`, `VALIDATE_OOS` | lectura | — | `REFRESH_ML`, `INSTALL_LOCAL`, `DEMO_INDEPENDENT`, `REVIEW_CALIBRATION_MLB_H2H` no leídos |
| Dependencias | P2 | REVISADA | `pyproject.toml`, `requirements.lock` (25 pins), `pip-audit` bloqueante en CI | inventario + CI verde | — | `pip-audit` no ejecutado localmente (red) |
| Docker | P3 | REVISADA | `Dockerfile` | lectura | documentado como demo; nadie la construye | no construida |
| Tests | P1 | REVISADA | 143 ficheros; suite rápida | `pytest -m "not slow"`: **1936 passed** (exit 0) | ruff 0, mypy 0 | `slow` (225) no ejecutados; ver CLAUDE-004 |
| Datos (integridad) | P0 | REVISADA_PARCIALMENTE | `settled_*.csv`, `graded_*.csv`, `prediction_gate.json` | agregados programáticos | 1.648 filas candidates (591 win/996 loss/24 push/34 void/3 half_win); 26.802 filas graded; 574 líneas de cuarto | sin scan de duplicados ni esquema completo |
| Obsidian / docs | P3 | EXCLUIDA | `Obsidian/**`, `docs/**` | — | — | fuera del alcance técnico; sólo se comprobó que `docs/prompts` v2→v3 no tiene consumidores |
| `logs/`, `.env` | — | NO_VERIFICABLE | — | — | — | acceso denegado por el clasificador de permisos de la sesión |

## Hallazgos confirmados

### CLAUDE-001 — El pricing de líneas asiáticas de cuarto ignora la liquidación a medias
- Categoría: cuantitativo (probabilidad/EV). Severidad **HIGH**. Confianza HIGH. Evidencia **REPRODUCED**.
- Archivo: `src/sqp/models/distributions.py:236-239` y `:253-259`
  (`poisson_match_probs`); consumidores `sports/adapters.py:107-123`
  (`PoissonAdapter.estimate`: fútbol, hockey, béisbol) y
  `pipeline/probabilities.py:185-187`.
- Activación: cualquier línea `±x.25 / ±x.75` (spreads) o `x.25 / x.75`
  (totales) cotizada por el proveedor. Medido en `data/calibration/graded_*.csv`:
  574 de 26.802 filas (2,1 %), todas `spreads` de fútbol (-0,25/+0,25: 376;
  -0,75/+0,75: 140; ±1,25: 54; ±2,25: 2); en el ledger de candidates, 26 de 1.648.
- Problema: `cover` se calcula como `P(m > -line)` y `push` como
  `P(m == -line)`; con línea de cuarto `push` es siempre 0 y la probabilidad
  servida trata la línea como si fuera entera. La liquidación (`settle.py`,
  AUD-MED-002 desde 2026-09-13) sí reparte el stake entre las dos líneas
  adyacentes (`split_asian_line`), así que modelo y liquidación describen
  contratos distintos.
- Evidencia (reproducción con funciones del proyecto, λ = 1,5 / 1,0, rejilla 30):

  | mercado | modelo | prob. de decisión coherente con `_grade` | EV@1,95 modelo | EV@1,95 real |
  |---|---|---|---|---|
  | spreads local −0,25 | 0,488 | 0,561 | −0,049 | +0,081 |
  | spreads visitante +0,25 | 0,512 | 0,439 | −0,001 | −0,125 |
  | spreads local −0,75 | 0,488 | 0,418 | −0,049 | −0,163 |
  | spreads visitante +0,75 | 0,512 | 0,582 | −0,001 | +0,119 |
  | totals Over 2,25 | 0,456 | 0,523 | −0,110 | +0,018 |
  | totals Under 2,25 | 0,544 | 0,477 | +0,060 | −0,061 |
  | totals Over 2,75 | 0,456 | 0,391 | −0,110 | −0,212 |
  | totals Under 2,75 | 0,544 | 0,609 | +0,060 | +0,167 |

  Dirección: se **sobreestiman** los lados que ganan a medias en la línea
  entera adyacente (+x,25, −x,75, Under x,25, Over x,75) en ≈ ½·P(empate) o
  ½·P(margen exacto), y se subestiman los opuestos. En fútbol P(empate) ≈ 0,25
  → sesgo ≈ 12 pp, seis veces `min_edge` (0,02).
- Esperado: probabilidad de decisión `win_units/(win_units+loss_units)` y EV
  `win_units·(d−1) − loss_units` como ya define `markets/settlement_math.py`
  (API «de investigación» que no llega al pricing).
- Observado: edge fabricado en un lado y suprimido en el otro; en el stream
  graduado, 432 de las 574 filas de cuarto están en el lado sobreestimado
  (ambos lados se sirven, así que no es selección; en candidates 15/26).
- Causa raíz: `poisson_match_probs` sólo conoce `win/push/loss`; AUD-MED-002
  corrigió la liquidación sin tocar el pricing.
- Consecuencia: probabilidad estimada, edge, EV del tipster, Kelly y
  `model_probability` del gate de predicción inválidos para esas líneas. Las
  etiquetas de calibración anteriores al 2026-09-13 se graduaron con la misma
  semántica de línea entera (coherentes con el modelo pero no con el contrato
  real); las posteriores excluyen las medias (`isin(["win","loss"])`).
- Controles existentes: `max_plausible_edge` (0,075) recorta parte del edge
  fabricado; el gate mantiene stake 0. Ninguno corrige la probabilidad.
- Corrección mínima: en `poisson_match_probs` (o en `PoissonAdapter.estimate`),
  cuando `line*4` sea entero y `line*2` no, descomponer con `split_asian_line`,
  acumular masas `win/half_win/push/half_loss/loss` y devolver la probabilidad
  de decisión de `SettlementProbabilities`; documentar que `p·d−1` sólo iguala
  al EV cuando no hay masa push. Revisar también `estimate_f5` (adapters:210).
- Pruebas: test paramétrico que compare `poisson_match_probs` con la masa
  obtenida vía `_grade` para ±0,25/±0,75/2,25/2,75 (tolerancia 1e-9); test de
  no regresión para líneas enteras y de medio punto (byte-idéntico).
- Criterio de aceptación: desviación ≤ 1e-9 frente a la liquidación para cuartos;
  líneas no-cuarto sin cambio; `test_settlement_math` verde.
- Limitaciones: no se midió el impacto en ROI realizado porque el ledger sólo
  tiene 3 medias (stake 0). Escalado: cambia un parámetro de modelo → clase
  «modelo/estrategia» del principio rector; la decisión de aplicar es del operador.

### CLAUDE-002 — El ROI realizado se define de tres formas incompatibles tras introducir `half_win`/`half_loss`
- Categoría: cuantitativo (métrica publicable). Severidad **MEDIUM**. Confianza HIGH. Evidencia **REPRODUCED**.
- Archivos: `src/sqp/backtesting/roi_engine.py:411-430` (`_summarize`),
  `src/sqp/audit/html_report.py:177-179`, `src/sqp/audit/report.py:276-280`,
  `src/sqp/settlement/runner.py:681-690` (`realized_roi`, referencia).
- Activación: cualquier fila `half_win`/`half_loss` con stake > 0 (backtests
  con Kelly histórico ya la producen; el ledger real la producirá al salir del
  shadow). Hoy: 3 `half_win` en `settled_ligue1/seriea.csv`, stake 0 → impacto
  numérico nulo, defecto latente.
- Problema: `runner.realized_roi` incluye las medias en numerador y
  denominador; `roi_engine._summarize` y `html_report` suman **todo** el `pnl`
  pero sólo el stake de `win/loss`; `audit/report.py` excluye las medias de
  ambos.
- Evidencia (reproducción): una `half_win` (stake 20, precio 2,0) →
  `realized_roi` = 0,50; `_summarize` = 0,00 (`staked` 0, `pnl` 10). Mezcla
  con una `win` → 0,75 vs **1,50** (ROI duplicado).
- Consecuencia: `scripts/validate_oos.py` (mensual, `VALIDATE_OOS.bat`),
  `backtest_roi.py`, `oos_pitcher_mlb.py` y la tarjeta «ROI realizado» del
  dashboard publican cifras con conjuntos distintos en numerador y denominador.
- Causa raíz: remediación AUD-MED-002 (2026-09-13) actualizó `realized_roi` y
  dejó el resto de consumidores con `isin(["win","loss"])` + `pnl.sum()` global.
- Corrección mínima: una única función canónica (p. ej. `realized_roi` en
  `settlement/runner.py`) reutilizada por `_summarize`, `html_report` y
  `report.py`; decidir explícitamente si las medias cuentan (recomendado: sí,
  ambos lados, como el ledger de banca).
- Pruebas: caso de una media sola y mezcla media+win en los tres consumidores;
  candado que impida `pnl` global con `stake` filtrado.
- Aceptación: mismo ROI en los cuatro puntos para el mismo `settled`.

### CLAUDE-003 — HEAD no es autoconsistente y diverge del remoto: dos commits sin publicar dependen de ficheros sin trackear
- Categoría: integridad del repositorio / CI. Severidad **MEDIUM**. Confianza HIGH. Evidencia **REPRODUCED**.
- Archivos: commit `44e48f2` (`scripts/sync_agent_instructions.py`,
  `tests/test_agent_instruction_sync.py`) depende de
  `.claude/automation/audit-workflow.md` y `loop-guardrails.md` (sin trackear)
  y de los prompts regenerados de `audits/prompts/` (modificados, sin
  commitear); commit `72d07d8` añade `surface_elo` a `features/research.py`
  y rompe `tests/test_tennis_params.py::test_no_code_actually_handles_surface`
  (la corrección está sólo en el working tree).
- Evidencia: extracción limpia de HEAD (`git archive`) en scratchpad →
  `sync_agent_instructions.py --check` rc 1 (`FileNotFoundError:
  audit-workflow.md`); `pytest tests/test_agent_instruction_sync.py` → 1 failed,
  5 errors; `test_tennis_params.py` → 1 failed. Con el working tree completo la
  suite pasa (1936).
- Divergencia: `gh api compare 96a4749...main` → remoto 6 commits por delante
  (todos docs/Obsidian/memoria); HEAD local (2 commits con código) no existe en
  el remoto (404); `origin/main` local obsoleto (`96a4749`). `Obsidian/Tareas.md`
  y `Bitácora.md` modificados en ambos lados → conflicto al sincronizar.
- Consecuencia: al hacer push, CI en rojo; la máquina de producción ejecuta
  código (`feature_store.py`, `builders.py`, `ml_train.py`) que ninguna puerta
  ha validado en 3.11–3.13/Windows; el guard de árbol del BAT avisará hoy
  «6 commits por detrás» tras su `fetch`.
- Causa raíz: el guard de árbol (`src scripts configs *.bat`) presionó a
  commitear `scripts/` sin sus fuentes en `.claude/` (mensaje del propio commit).
- Corrección mínima: un commit coherente con las fuentes sin trackear, los
  prompts regenerados y los dos tests corregidos; `git fetch` + rebase/merge
  resolviendo los dos ficheros Obsidian; push y comprobar CI. Requiere
  autorización (commit/push).
- Pruebas: `sync_agent_instructions.py --check` y la suite sobre un checkout
  limpio del commit resultante; `gh run list` verde.

### CLAUDE-004 — Residuo inaccesible en `.codex-tmp/pytest/` rompe el comando canónico de validación
- Categoría: entorno de validación. Severidad **MEDIUM**. Confianza HIGH. Evidencia **REPRODUCED** (ENVIRONMENTAL_FAILURE).
- Archivo: directorio `.codex-tmp/pytest/openai-20260916-retry` (creado
  2026-09-16 17:50, ACL ilegible incluso para el propietario: `ls` y
  `Get-Acl` → acceso denegado).
- Evidencia: `pytest -q -p no:cacheprovider --basetemp=.codex-tmp/pytest -m
  "not slow" -x` → primer test con `tmp_path` falla en setup:
  `PermissionError: [WinError 5]` al limpiar el basetemp. Es exactamente el
  comando de `Makefile:test`, `AGENTS.md` y el contrato de auditoría (KI-037).
  Con `--basetemp=.codex-tmp/pytest-claude-20260917` la suite pasa.
- Consecuencia: cualquier auditor o remediador que siga el comando documentado
  obtiene un fallo ambiental antes del primer test con fixture temporal.
- Corrección mínima: eliminar el directorio con privilegios (`takeown`/`icacls`
  o desde el sandbox que lo creó) — decisión del operador; alternativamente
  documentar un sub-basetemp por auditor.

### CLAUDE-005 — `execution.books` se documenta como activable pero el pipeline nunca lo consume
- Categoría: configuración/contrato. Severidad **MEDIUM** (condicionada). Confianza HIGH. Evidencia **STATICALLY_VERIFIED**.
- Archivos: `configs/default.yaml:150-163` («`books` vacío = DESACTIVADO…»),
  `src/sqp/config.py:489-493` (carga `ExecutionConfig`, valida `max_uplift`),
  `src/sqp/pipeline/probabilities.py:368-420` (`_execution_prices`),
  `src/sqp/pipeline/daily.py:794,890,954` (siempre `consensus_median`).
- Evidencia: `_execution_prices` no tiene ningún llamador fuera de
  `tests/test_line_shopping.py`. El commit `9dfb4cc` registra la decisión
  «NO se cablea en daily.py» — es una decisión documentada, no un olvido — pero
  el yaml y `Settings` presentan la clave como operativa.
- Consecuencia: si el operador declara casas accesibles (`books` o
  `EXECUTION_BOOKS`), el precio de ejecución no cambia y no hay aviso. Hoy
  `books: []` → impacto nulo.
- Corrección mínima (sin contradecir la decisión): anotar en el yaml y en
  `Settings.validate` que la clave está **sin cablear** y avisar si se
  declara no vacía; o cablearla bajo decisión explícita del operador (cambia
  precios de ejecución → clase de escalado).
- Pruebas: test que fije el estado elegido (aviso o cableado).

### CLAUDE-006 — Con el árbol sucio, cualquier `Bash` de solo lectura arma el centinela de tests
- Categoría: hooks/operación. Severidad **LOW**. Confianza HIGH. Evidencia **REPRODUCED**.
- Archivos: `.claude/hooks/mark-tests-pending.sh` (`_targets.py --with-git`,
  fuente 3), `.claude/hooks/run-tests-on-stop.sh` (suite completa `-m "not
  slow"`, timeout 600 s).
- Evidencia: `echo '{"tool_name":"Bash","tool_input":{"command":"cat
  README.md"}}' | python .claude/hooks/_targets.py --with-git` devuelve el
  árbol sucio entero (incl. `tests/*.py`); `.claude/.tests-pending` armado a
  las 08:52 de hoy por esta sesión de solo lectura.
- Consecuencia: cada `Stop` de una sesión de auditoría paga la suite (~7 min)
  mientras existan modificaciones preexistentes en `src/tests/scripts` — el
  mismo coste que AUD-MED-007 eliminó para la fuente 2, reintroducido por la
  fuente 3. Es una elección documentada («sobre-disparar es barato») cuyo coste
  real con un árbol crónicamente sucio no se midió.
- Corrección mínima: en la fuente 3 considerar sólo ficheros cuyo estado en
  `git status` cambió durante el turno (comparar contra un snapshot al
  `PreToolUse`), o excluir la fuente 3 cuando el comando no contiene operadores
  de escritura.

### CLAUDE-007 — `feature_shadow.load_protocol` huella `ROOT` mientras `train` huella `--data-root`
- Categoría: lógica (herramienta de investigación). Severidad **LOW**. Confianza HIGH. Evidencia **STATICALLY_VERIFIED**.
- Archivos: `src/sqp/evaluation/feature_shadow.py:100,137` (`fingerprint(root)`)
  vs `:168` (`fingerprint(ROOT)`); `scripts/feature_shadow.py:25,46-53`
  (`--data-root`, por defecto `ROOT`).
- Activación: `--data-root` distinto de `ROOT` (p. ej. espejo de datos sin
  `src/sqp`): `train` persiste la huella del árbol de datos y `capture`/
  `evaluate` fallan siempre con «experiment code/configuration changed».
- Corrección mínima: `fingerprint(ROOT)` en ambos sitios (la huella es del
  código, no del directorio de datos) y un test con `root` ≠ `ROOT`.

## Inferidos / no verificables

- **NV-1** Estado del último run del diario (`logs/diario_completo.log`,
  `logs/run_status/*.json`): acceso denegado en esta sesión. Evidencia indirecta:
  `Get-ScheduledTaskInfo` rc=1 el 2026-09-16 12:00 y `pipeline_health.json`
  `status: OK` a las 20:20Z del mismo día.
- **NV-2** `.env` de producción (presencia, `KELLY_FRACTION`): no inspeccionable.
- **NV-3** Suite `slow` (225 tests) no ejecutada en esta ronda.

## Observaciones (no defectos)

- **OBS-1** Diferencia train/serve introducida por `72d07d8`: los datasets ML
  excluyen resultados del mismo día UTC; el run diario ajusta ratings con
  scores completados del mismo día (`_fetch_recent_scores`). Sin impacto en
  picks (el ML no los alimenta); a tener en cuenta si algún día se promueve.
- **OBS-2** Gate de predicción: 48 cortes evaluados con K=41 pre-registrado
  (límite 50). El FWER efectivo es 48·α ≈ 5,9 %; a 2 cortes del re-pre-registro.
- **OBS-3** `test_pricing_prompt_formulas.py` evalúa con `eval` fórmulas
  extraídas de Markdown del repositorio (entrada controlada; aceptable).
- **OBS-4** `SQP_Dashboard_Cdev` LastTaskResult 267014 (0x41306, terminada por
  el usuario): esperado para una tarea interactiva.

## Descartes

- **OPENAI-003 («line shopping ignorado») como defecto de pipeline**: la no
  integración es una decisión registrada (`9dfb4cc`). Se conserva únicamente la
  contradicción documental (CLAUDE-005).
- Grading de líneas de cuarto en `settle.py`: verificado correcto
  (−0,75/+1 → half_win; 2,25/Under/2 → half_loss).
- `remove_vig_power`, `kelly_fraction_stake`, `adjusted_edge`: sin defecto
  (finitud, rangos y fallback documentados).
- Referencias rotas en `.claude/**`: 9, todas en `memory/` a entregables de
  fases pasadas o ficheros runtime; no afectan a skills activas.
- Borrado de `docs/prompts/*-pricing-v2.md`: sin consumidores fuera de
  manifiestos históricos (`BUILD_INFO.json`, hashes de rondas anteriores).

## Comparación con la ronda anterior (`audit-2026-09-13`, leída en el paso 7)

| ID previo | Estado | Evidencia propia |
|---|---|---|
| AUD-HIGH-001 (repositorio) | corregido; **nuevo riesgo** CLAUDE-003 | Git operativo, CI verde en remoto; divergencia local/remoto |
| AUD-HIGH-002 (tareas «solo interactivo») | corregido | `LogonType S4U` en las 4 tareas batch (2026-09-17) |
| AUD-MED-002 (medias) | corregido en liquidación; **incompleto** aguas abajo | CLAUDE-002; y ahora incoherente con el pricing: CLAUDE-001 |
| AUD-MED-005 (`:lista` en `:error_run`) | corregido | `DIARIO_COMPLETO.bat` |
| AUD-MED-007 (`_targets.py`) | corregido parcialmente | CLAUDE-006 (fuente 3) |
| B-01 (`VALIDATE_OOS`) | corregido | rc=0 el 2026-09-17 00:00 |
| B-02 (pin de acciones CI) | persistente | `ci.yml` usa `@v4/@v5` |
| B-08 (`record_run_failure` sin lock) | resuelto por diseño | ficheros por etapa, sin sección crítica |
| CL-02 (`wnba_totals_calibration_iso.joblib`) | persistente (inerte) | sigue en `data/models/` |

## Validaciones y comandos

| Comando | Resultado | Clasificación |
|---|---|---|
| `pytest -q -p no:cacheprovider --basetemp=.codex-tmp/pytest -m "not slow" -x` | ERROR setup (`PermissionError` en basetemp) | ENVIRONMENTAL_FAILURE → CLAUDE-004 |
| `pytest -q -p no:cacheprovider --basetemp=.codex-tmp/pytest-claude-20260917 -m "not slow"` | 1936 passed, 225 deselected, exit 0 | OK |
| `ruff check src scripts tests` | All checks passed | OK |
| `mypy src` | Success: 105 ficheros | OK |
| `python scripts/sync_agent_instructions.py --check` | synchronized, rc 0 (working tree) / rc 1 (HEAD limpio) | OK / CLAUDE-003 |
| `pytest tests/test_agent_instruction_sync.py` sobre `git archive HEAD` | 1 failed, 5 errors | PRE_EXISTING_FAILURE (HEAD) → CLAUDE-003 |
| `pytest tests/test_tennis_params.py …` sobre `git archive HEAD` | 1 failed | PRE_EXISTING_FAILURE (HEAD) → CLAUDE-003 |
| `gh run list --branch main --limit 3` | success ×3 (último 2026-09-17T03:50Z) | OK |
| `gh api compare 96a4749...main` | ahead_by 6 / behind 0; `compare 44e48f2...main` → 404 | CLAUDE-003 |
| `Get-ScheduledTask SQP_*` | ver matriz | OK |
| Reproducción pricing vs `_grade` (código propio) | tabla CLAUDE-001 | REPRODUCED |
| Reproducción ROI medias | 0,5 vs 0,0; 0,75 vs 1,5 | REPRODUCED |

No se ejecutaron: suite `slow`, `pip-audit` local, BAT alguno, `codex review`.
No se instalaron dependencias ni se consumió cuota de pago. Ningún fichero del
proyecto fue modificado fuera de `audit/latest/` (y el registro de tarea).

## Plan priorizado (propuesta; requiere autorización por ID)

1. **P1 CLAUDE-003** — commit coherente + sincronizar con `origin/main` + push + CI verde.
2. **P1 CLAUDE-001** — probabilidad de decisión coherente con la liquidación para líneas de cuarto (clase de escalado: parámetro de modelo).
3. **P2 CLAUDE-002** — una sola definición de ROI realizado; antes del `VALIDATE_OOS` del 2026-10-01.
4. **P2 CLAUDE-004** — eliminar el residuo inaccesible (operador).
5. **P2 CLAUDE-005** — aviso/documentación de `execution.books` sin cablear (o cableado bajo decisión).
6. **P3 CLAUDE-006**, **P3 CLAUDE-007**.

## Riesgos residuales y limitaciones

- Un solo auditor: sin segunda opinión independiente (el auditor OpenAI dejó
  sólo un script; sus hipótesis se revalidaron aquí, dos confirmadas y una
  reclasificada).
- Cobertura parcial declarada en la matriz (calibrador, revalidación,
  degradación, served_store, odds_api, BATs secundarios).
- `logs/` y `.env` no verificables por permisos de la sesión.
- Esta auditoría no demuestra ventaja predictiva, rentabilidad ni ausencia de
  defectos en áreas no revisadas.
