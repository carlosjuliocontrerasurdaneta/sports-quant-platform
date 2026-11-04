# Informe del auditor Claude — ronda `audit-2026-11-03`

**Fecha:** 2026-11-03 (UTC −3 local). **Base:** `a5d186084e7bc5a42c055b420adcfa7a9a9b1ffe` (main). **Modo:** auditoría integral orquestada, solo lectura.
**Auditor:** Claude (único disponible; Codex/OpenAI no disponible: MCP `codex` CONNECTION_CLOSED). **No hubo segunda opinión.**

## 1. Resumen

- **0 CRITICAL, 0 HIGH, 7 MEDIUM, 19 LOW confirmados**, más 2 inferidos y 3 observaciones.
- **Atención inmediata (P1):** CLAUDE-002. El guard de árbol sucio abortó el run del 2026-11-02 (día sin liquidación ni picks) y **el de hoy 2026-11-03 a las 12:00 abortará igual** si no se aparta el trabajo sin commit del portero NHL. No es un fallo del guard (hace lo que debe), sino del modelo operativo: producción y desarrollo comparten árbol y el aborto no se reintenta.
- **Hallazgo cuantitativo principal (P2):** CLAUDE-001. La condición 2 del prediction gate (EV a stake plano > 0) promedia el EV de las dos caras de cada mercado y, en mercados de 2 vías a cuotas simétricas, vale −vig con independencia de la calidad del modelo: la regla rectora de salida del shadow no puede abrirse para spreads/totals aunque el modelo fuera excelente. El código implementa fielmente el criterio pre-registrado: el defecto está en el diseño del criterio y su corrección exige re-pre-registro y decisión del operador. Va en dirección conservadora (no arriesga dinero).
- **Lo demás** son defectos acotados: protección de pre-registros (CLAUDE-003, -009), atribución del informe OOS mensual (CLAUDE-004), coherencia precio de decisión / precio de ejecución latente hasta que un corte abra (CLAUDE-005), pérdida silenciosa de logs ante CSV corrupto (CLAUDE-006), monitorización ciega de tareas (CLAUDE-007) y mantenimiento.
- **Sin fugas temporales materiales** (leakage CRITICAL/HIGH/MEDIUM: ninguno), **sin secretos expuestos**, sin escrituras no atómicas en los stores principales, sin lookahead en el stream servido (0 filas con `generated_at >= start_time` en 68.866).
- Ningún resultado de esta auditoría demuestra ventaja predictiva ni rentabilidad.

## 2. Alcance, método y contaminación

Alcance pedido: arquitectura, código, seguridad, dependencias/integraciones, integridad de datos, modelos, simulación/numérico, calibración, backtesting/OOS, fugas temporales, probabilidad/edge/EV, riesgo/controles, automatizaciones/agentes/skills/hooks, pruebas/CI/recuperación.

**Método.** El coordinador (sesión principal) conoce conclusiones de rondas previas por la memoria del proyecto, así que el diagnóstico lo hicieron seis especialistas con **contexto limpio**, con prohibición expresa de leer `audit/`, `audits/`, `known-issues.md`, `session-summaries.md` y la bitácora. El coordinador revalidó contra el código cada candidato MEDIUM (ver §6) y solo después comparó con el histórico (§8).

| Área | Revisor primario | Modelo |
|---|---|---|
| Fugas temporales, features, calibración | `leakage-detector` | Fable 5.1 |
| Cuotas, devig, edge/EV, liquidación, Kelly, gates | `odds-market-auditor` | Fable 5.1 |
| Backtesting, OOS, scripts de investigación, pre-registros | `backtest-reviewer` | Fable 5.1 |
| Seguridad, secretos, dependencias, integraciones | `security-reviewer` | Sonnet 5.5 |
| Arquitectura, corrección, datos, almacenamiento, proveedores | general-purpose | Sonnet 5.5 |
| Automatización, BAT, tareas, hooks, skills, agentes, routing | general-purpose | Sonnet 5.5 |

**Cambios preexistentes en el árbol (no del auditor), fuera de alcance:** trabajo sin revisar del portero NHL (`M src/sqp/backtesting/engine.py`, `M src/sqp/domain/models.py`, `M src/sqp/sports/adapters.py`, `?? src/sqp/models/goalies.py`, `?? scripts/research/measure_goalie_nhl.py`, `?? tests/test_measure_goalie_nhl.py`). Los especialistas auditaron HEAD con `git show HEAD:<ruta>`. Limitación: `pytest`, `ruff` y `mypy` corren sobre el árbol de trabajo, que incluye ese trabajo.

**Herramientas.**

| Herramienta | Estado comprobado |
|---|---|
| Pyright LSP | Funciona: `documentSymbol` y `goToDefinition` (mismo fichero y entre ficheros, p. ej. `prediction_gate.py:89` → `settlement/quarter_line_fix.py:49`) verificados. `workspaceSymbol` agotó 60 s durante el indexado; `findReferences` devolvió solo el fichero abierto. Uso real: inspección de estructura y navegación por el coordinador; los especialistas no lo usaron. |
| Context7 | **No usado**: el servidor exige OAuth y no se completó. Ninguna afirmación de este informe procede de Context7. |
| graphify MCP | No disponible (CONNECT_TIMEOUT). |
| Codex MCP / auditor OpenAI | No disponible (CONNECTION_CLOSED). |
| `pip-audit` | Instalado (2.10.1) pero no ejecutado: requiere red. |

## 3. Cobertura

| Componente | Estado | Nota |
|---|---|---|
| `features/` (temporal, builders, common, rest_form, research, weather) | revisado | `features/mlb.py`: parcial (solo patrón `flush`) |
| `models/` elo, rest, starters, distributions, ml_train | revisado | fip, park, team_scoring, blend, independent, ml_predict: **no verificables** (no leídos) |
| `calibration/` calibrator, data | revisado | pergame, metrics: parcial |
| `markets/` odds, vig, edge, settlement_math, line_movement | revisado | |
| `settlement/` settle, quarter_line_fix | revisado | runner: parcial; liquidación de tenis: no verificable |
| `risk/` prediction_gate, kelly, topes | revisado | bankroll: parcial; degradation, clv_gate: **no verificables** en esta pasada (clv_gate `enabled: false`) |
| `evaluation/` tipster, compare, model_vs_market | revisado | |
| `pipeline/` daily (partes clave), probabilities, revalidation, intraday_scan, closing_capture | revisado | daily: 1111 l., no íntegro; budget, team_totals_capture, goalie_*: parcial |
| `backtesting/` engine (HEAD), roi_engine, tuning | revisado | |
| `storage/` atomic, lock, results/odds/served/schedule stores | revisado | starters, starter_fip, pitchers_capture, feature_store: parcial |
| `providers/` odds_api, odds_cache, espn_results | revisado | espn_tennis, mlb_statsapi, nhl_api, espn_goalies: parcial (timeouts verificados por grep) |
| `scripts/` run_all, validate_oos, update_prediction_gate, gate_status, model_vs_market*, compare_models, capture_closing_odds | revisado | |
| `scripts/research/` el_modelo_manda, tier_a_gap, segment_market_weight, intraday_gate_analysis | revisado | totals_recency, adjustment_battery: superficial; resto: no revisado en profundidad (experimentos cerrados) |
| `configs/` default.yaml, leagues/*.yaml | revisado | |
| BAT/PS1 diarios (DIARIO_COMPLETO, SETTLE_ALL, RUN_DIARIO_ALL, CAPTURE_CLOSE, wait_for_network) | revisado | BACKFILL, REFRESH_ML, VALIDATE_OOS, REVIEW_CALIBRATION, INSTALL_LOCAL, DEMO: parcial |
| Tareas programadas SQP_* | revisado (consulta `schtasks` de solo lectura) | |
| `.claude/` settings, hooks, automation, 35 skills, 24 agentes, 8 comandos | revisado | hooks comprobados solo vía tests |
| CI `.github/workflows/ci.yml`, Dockerfile, Makefile | revisado (estático) | ejecución en GitHub: **no verificable** (sin red) |
| Secretos en ficheros versionados | revisado | historial por contenido: **no verificable** (timeout); `.env`: lectura denegada, solo existencia/ignorado |
| Datos (`data/`) | revisado por agregados | results_*.csv (21 ligas), settled, served/graded, predictions, candidates, odds, intraday log |
| Recuperación (backups, restauración) | parcial | no se inspeccionaron `data/backups` ni scripts de restauración |

**Controles configurados vs comprobados en funcionamiento.**

| Control | Configurado | Comprobado funcionando |
|---|---|---|
| Guard de árbol sucio en `DIARIO_COMPLETO.bat` | sí | **sí** (abortó el 02-11, log + centinela) |
| Orden liquidación → generación | sí | sí (estructura del BAT; `:error_settle` aborta antes del run) |
| Centinelas `logs/run_status` | sí | sí (`guard_arbol.json`) |
| Health check de tareas programadas | sí | **no**: agota 30 s (CLAUDE-007) |
| Historial del Programador de tareas | no (deshabilitado) | — |
| `check_daily_launch.py` | sí | sí (log de CAPTURE_CLOSE) |
| Hook `fable_gate` | sí | sí en una ocasión (bloqueó/exigió línea FABLE-REVIEW el 2026-11-02 en esta sesión); tests verdes |
| Hook `require-dispatch-model.sh` | sí | sí (exige `model` al despachar en esta sesión) |
| Hook `check-secrets.sh` (PostToolUse) | sí | solo vía tests |
| Stop hook `run-tests-on-stop.sh` | sí | **sí** (ejecutó la suite rápida en esta sesión; ver OBS-003) |
| CI `secret-scan`, `dependency-audit` | sí | no verificable sin red |
| Guards temporales (`captured_at < commence_time`, `_already_started`) | sí | sí: 0 filas servidas en o tras el inicio; tests verdes |
| Calibrador colapsado (`_keeps_resolution`, `structural_defect`) | sí | sí: tests verdes, calibradores live sin colapso |
| Prediction gate (unidad, Bonferroni K=69, test único, pestillo, centinela) | sí | sí (tests + dry-run del 2026-11-02 sin ERROR de techo) |
| Escrituras atómicas y locks en stores | sí | sí por lectura y tests; 0 duplicados por clave natural en results/served/graded/settled |

## 4. Hallazgos confirmados

Formato por hallazgo: severidad · confianza · evidencia · prioridad. Origen = especialista que lo detectó.

### CLAUDE-001 — La condición 2 del prediction gate (EV plano > 0) no puede cumplirse en mercados de 2 vías equilibrados
- **MEDIUM · HIGH · REPRODUCED · P2** · categoría: validez estadística del gate de salida · origen ODDS-01.
- **Dónde:** `src/sqp/risk/prediction_gate.py` `_independent_units` (l. 306-317) y `_decide` (l. 324-336); `scripts/update_prediction_gate.py:80` carga el stream servido completo; `src/sqp/pipeline/daily.py:995-1020` registra **todas** las caras de cada mercado en el stream.
- **Activación:** cada evaluación del gate, en todo corte con ambas caras servidas (spreads/totals siempre; h2h también).
- **Problema:** `ev = p·(d−1) − (1−p)` se calcula por fila y se promedia dentro de (evento, mercado), mezclando las dos caras complementarias. A cuotas simétricas `d`, la media es `(d−2)/2 = −v/(1+v)` sea cual sea `p`; en general solo sube si el modelo se inclina al underdog.
- **Evidencia:** reproducción sintética del especialista (`scratchpad/repro_gate_ev.py`, llama a `evaluate_markets`): 400 eventos, ambas caras a 1,909, mercado 0,5, modelo 0,9 al ganador → `n=400, wins=400, p=3,9e-121, ev_flat=−0,0455, allowed=False, reason=ev_no_positivo`; el EV de la cara preferida por el modelo es +0,909. Revalidación del coordinador: `daily.py:995-1020` hace `served.append` de cada cara antes de cualquier filtro, y `_independent_units` agrupa por (event_id, market) y promedia `ev`. Los `ev_flat` publicados de los cortes agotados (≈ −0,049/−0,054) encajan con −vig.
- **Esperado:** una condición de EV que discrimine la calidad del modelo (p. ej. EV de la cara que el modelo elegiría por unidad, o EV realizado de los candidatos). **Observado:** condición estructuralmente inalcanzable para 2 vías simétricas.
- **Causa raíz:** el criterio pre-registrado (`docs/research/2026-08-16-preregistro-regla-de-salida.md`, condición 2, «sobre las mismas filas») se aplicó a filas que incluyen ambas caras; al pasar la unidad a (evento, mercado) la parte informativa se cancela.
- **Consecuencia:** conservadora (no arriesga dinero), pero bloquea estructuralmente la regla rectora de salida del shadow en spreads/totals y puede consumir el test único de un corte que sí bate al mercado en el signo (quedaría `agotado_test_unico` hasta liberación humana). En h2h premia modelos sesgados al underdog.
- **Controles existentes:** ninguno detecta la cancelación; no hay test con ambas caras y modelo bueno.
- **Corrección mínima:** **no es un cambio unilateral de código**: re-pre-registrar la condición 2 (decisión del operador, diseño y revisión Fable) antes de que algún corte alcance n ≥ 300 (`nhl|spreads` y `nhl|totals` iban por 219 el 2026-11-01).
- **Pruebas:** sintético con ambas caras y modelo bueno → la condición puede pasar; modelo igual al mercado → EV ≤ 0.
- **Limitaciones:** no se midió el EV alternativo sobre los datos reales (no se cargaron datasets).

### CLAUDE-002 — El guard de árbol sucio deja días enteros sin liquidar ni generar, sin reintento; se repetirá hoy
- **MEDIUM · HIGH · REPRODUCED · P1** · categoría: control operativo / disponibilidad · origen OPS-01.
- **Dónde:** `DIARIO_COMPLETO.bat` (guard `git status --porcelain -- src scripts configs *.bat`, rama `:error_arbol`).
- **Evidencia:** `logs/diario_completo.log`: «02-11-2026 12:04:14 … ABORTADO ANTES DE LIQUIDAR … M configs/default.yaml, M scripts/gate_status.py, M src/sqp/risk/prediction_gate.py»; centinela `logs/run_status/guard_arbol.json` (`failed_at 2026-11-02T15:05:30Z`); `schtasks`: `SQP_Diario_Completo_Cdev` último resultado 1, próxima 03-11 12:00; ningún run posterior en el log. A las 10:01 del 2026-11-03 `git status --porcelain -- src scripts configs "*.bat"` sigue mostrando 5 rutas (trabajo del portero NHL). 6 de los 7 últimos runs fueron OK.
- **Esperado:** el pipeline del dinero corre o se reintenta con aviso activo. **Observado:** aborto sin reintento; aviso solo en log, centinela y health.
- **Causa raíz:** producción ejecuta el árbol de trabajo (decisión del operador) y el guard aborta sin reprogramar.
- **Consecuencia:** el día de generación se pierde (irrecuperable); la liquidación se retrasa un día (no irreversible mientras el siguiente run corra: refresco `--days 3`).
- **Controles existentes:** centinela, health ERROR, `check_daily_launch.py`, escape `SQP_SKIP_TREE_GUARD=1`, y la mitigación de AUD-005 (`RestartCount=3/PT15M`) que **no cubre** un rc≠0 del guard.
- **Corrección mínima:** inmediata — apartar o commitear (con su revisión Fable) el trabajo de `src/` antes de las 12:00 (acción del operador; el `git stash` está denegado al agente por permisos). Estructural (decisión del operador): reintento diferido del guard o desarrollo en worktree aislado.
- **Pruebas:** test del BAT con árbol sucio simulado: centinela registrado, `data/` intacto; si se añade reintento, que se dispare.

### CLAUDE-003 — `update_prediction_gate.py` permite escribir el registro con `--min-n`/`--alpha` no canónicos y gasta el test único
- **MEDIUM · HIGH · REPRODUCED · P2** · categoría: protección de pre-registros · origen BT-02.
- **Dónde:** `scripts/update_prediction_gate.py:69-70` y `:103-104`; `src/sqp/risk/prediction_gate.py` (marca `entry_test_at` hacia l. 412; `agotado_test_unico` hacia l. 424; `write_prediction_gate` l. 506-530 no valida umbrales).
- **Evidencia:** reproducción sintética en directorio temporal (80 eventos): canónica → `muestra_insuficiente`, `entry_test_at=None`; con `min_n=50, alpha=0.05` → `no_bate_al_mercado`, `entry_test_at` marcado; canónica otra vez → `entry_test_at` persiste. Revalidación del coordinador: `write_prediction_gate(graded, …, min_n=args.min_n, alpha=args.alpha)` se ejecuta salvo `--dry-run`.
- **Consecuencia:** una ejecución manual con overrides consume en silencio el test único de todos los cortes con n ≥ min_n del override; con `--alpha 0.05` un corte podría quedar `allowed=True` con un α 69 veces más laxo hasta la siguiente pasada canónica. La ejecución diaria sin argumentos no lo activa.
- **Controles existentes:** el payload registra alpha y min_n; `--release` lo revierte a mano.
- **Corrección mínima:** salir con código 2 si los umbrales difieren de los canónicos sin `--dry-run`, y aserción equivalente en `write_prediction_gate`.
- **Pruebas:** test de CLI: override sin `--dry-run` → rc≠0 y `prediction_gate.json` intacto.
- **Limitación:** no se comprobó si alguna vez se usaron overrides en producción.

### CLAUDE-004 — `validate_oos.py`: «frozen_train» y «family_default» descartan los parámetros de liga no tuneados
- **MEDIUM · HIGH · STATICALLY_VERIFIED · P2** · categoría: validez del backtest / atribución OOS · origen BT-01.
- **Dónde:** `scripts/validate_oos.py:79` (`base: dict = {}`), `:81` y `:262` (`pitcher_bound: 0.0` forzado), docstring l. 24-27.
- **Evidencia:** revalidado por el coordinador. `_freeze_on_train` solo fija `tilt_scale`, `elo_home_adv` y `dc_rho`; `full_history` usa `meta["league_params"]` completo (mlb `pitcher_bound 0.05`, `park_bound 0.10`; nba `rest_points_per_day 0.795`; mls `elo_home_away_split`; fútbol `avg_total` por liga, 11 valores entre 2,40 y 3,37 frente al 2,7 de familia). El docstring («pitcher_bound is held at 0.0 in every config») es falso desde el 2026-09-26.
- **Consecuencia:** la corrida mensual (VALIDATE_OOS.bat) atribuye al tuneo diferencias que vienen de features apagadas. No afecta a producción.
- **Controles:** ninguno; ningún test cubre la composición de `_freeze_on_train`.
- **Corrección mínima:** `base = dict(meta.get("league_params") or {})` y sobrescribir solo las claves tuneadas; `family_default` = configuración canónica sin las claves tuneadas; corregir docstring.
- **Pruebas:** test unitario: el `frozen` de mlb contiene `park_bound` y `pitcher_bound` de `ratings.yaml`; el de fútbol, el `avg_total` de la liga.
- **Limitación:** efecto en ROI no cuantificado (no se ejecutó validate_oos).

### CLAUDE-005 — Edge, Kelly y liquidación usan la mediana del consenso aunque `execution.books: [pinnacle]` esté activo
- **MEDIUM (condicionado) · MEDIUM · STATICALLY_VERIFIED · P2** · categoría: coherencia precio de decisión/ejecución · origen ODDS-02.
- **Dónde:** `src/sqp/pipeline/daily.py:933` (`price = cons.get(key)`), `:961` (edge), `:979-983` (Kelly), `:1080` (`price_decimal=price`); `src/sqp/settlement/settle.py:149-153` (pnl); `pipeline/probabilities.py:488-547` (`_execution_prices`); `configs/default.yaml:171-173`.
- **Activación:** cuando un corte obtenga `allowed: true` (con `shadow_mode: false` el stake real se abre sin aprobación adicional).
- **Problema:** `execution_price` (Pinnacle) puede ser inferior a la mediana, pero edge, `min_edge`, Kelly, pnl del ledger, banca dinámica y ROI realizado usan la mediana, que no es una casa apostable.
- **Consecuencia:** un pick con edge positivo solo en la mediana llevaría stake con EV negativo en la casa real; el ledger divergiría del dinero real. Hoy latente (0 cortes abiertos).
- **Controles:** documentado como «decisión aparte del operador» (`daily.py:885-892`); la revalidación solo baja stakes.
- **Corrección mínima:** decidir antes de abrir stake real: exigir `min_edge` también sobre `execution_price`, o dimensionar y liquidar con él.
- **Pruebas:** candidato con mediana > Pinnacle y edge positivo solo en la mediana → stake 0 (o la regla elegida).

### CLAUDE-006 — `_append_log` borra el historial del log si el CSV tiene un error de parseo
- **MEDIUM · HIGH · REPRODUCED · P2** · categoría: integridad de datos · origen ARCH-01.
- **Dónde:** `src/sqp/pipeline/revalidation.py:73-85` (`except (EmptyDataError, ParserError): prior = pd.DataFrame()` en l. 78, luego `atomic_write_csv(new, path)`); llamado también por `pipeline/intraday_scan.py:172`.
- **Evidencia:** reproducción en directorio temporal: 100 filas buenas + 1 malformada → tras `_append_log([1 fila])` queda 1 fila (esperadas 102). Revalidado por el coordinador leyendo l. 73-85. El log real `intraday_edge_log.csv` tiene ≈16.012 filas y hoy parsea sin error.
- **Esperado:** cuarentena o propagación, como `served_store._quarantine` y `settlement/runner.py:657` (M-21). **Observado:** pérdida silenciosa.
- **Consecuencia:** pérdida de la serie del observatorio intradía (y del log de revalidación) si alguna vez se corrompe una fila. Probabilidad baja (escrituras atómicas).
- **Corrección mínima:** solo `EmptyDataError` equivale a vacío; `ParserError` → cuarentena + `log.error` (o propagar).
- **Pruebas:** CSV con fila malformada → no se pierden filas o queda `.corrupt.*`.

### CLAUDE-007 — El health check no consigue leer las tareas programadas (timeout de 30 s)
- **MEDIUM · HIGH · REPRODUCED + STATICALLY_VERIFIED · P2** · categoría: monitorización · origen OPS-02.
- **Dónde:** `src/sqp/monitoring/health.py:291` (`_scheduled_tasks_raw(timeout_s=30.0)`), consumo hacia l. 329-345.
- **Evidencia:** log de salud del 06-10, 13-10 y 02-11: «no se pudo consultar el Programador de tareas … timed out after 30.0 seconds». `schtasks /query /v` tardó > 120 s en esta máquina. El historial del Programador sigue deshabilitado.
- **Consecuencia:** el health no ve `LastTaskResult` ni ejecuciones perdidas; la detección de «tarea no lanzada» depende solo de `check_daily_launch.py` (que depende de CAPTURE_CLOSE).
- **Corrección mínima:** timeout 60–120 s o una sola llamada `schtasks /query /fo CSV /v`; el operador puede habilitar el historial (`wevtutil sl Microsoft-Windows-TaskScheduler/Operational /e:true`, consola elevada).
- **Pruebas:** `tests/test_health_scheduled_tasks.py` + caso de timeout.
- **Limitación:** la parte de la latencia atribuida a carga de la máquina es inferida.

### CLAUDE-008 — Registro de calibración: lectura-modificación-escritura sin lock y lectura fallida tratada como `{}`
- **LOW · MEDIUM · STATICALLY_VERIFIED · P3** · origen ARCH-02. `src/sqp/calibration/calibrator.py:309-320` (`_load_method_registry`) y `:384-409` (`_set_best_method`): sin `locked`, `OSError`/`JSONDecodeError` → `{}` y se reescribe con una sola clave; `UnicodeDecodeError` no capturado; raíz no objeto no validada. Consecuencia: borrar entradas live → probabilidades sin calibrar (la dirección insegura según l. 405). Controles: escritura atómica, salud reporta huérfanos, un solo proceso escritor en la práctica. Fix: lock + `read_json_retrying` + abortar si falla la lectura de un fichero existente. Pruebas: raíz lista, bytes no UTF-8, `OSError` simulado → el registro no se reduce.

### CLAUDE-009 — El techo `K_REPREGISTRO` solo emite `log.error`; no bloquea cortes fuera del universo pre-registrado
- **LOW · HIGH · STATICALLY_VERIFIED · P3** · origen BT-04. `src/sqp/risk/prediction_gate.py:604-610`. Con más de 84 cortes el registro se escribe y un corte nuevo con n ≥ 300 se evalúa con una cota FWER mayor que la declarada, contra §3.4 del re-pre-registro K=69 («antes de que ningún corte nuevo sea elegible»). El ERROR corrió del 2026-10-22 al 2026-11-02 sin bloquear. Fix: por encima del techo, `allowed=False` con razón `fuera_de_preregistro` para cortes cuyo test se consumiría. Prueba: 85 cortes sintéticos, uno con n ≥ 300 → no se consume su test.

### CLAUDE-010 — El tipster clasifica B/A líneas que el motor de riesgo descarta
- **LOW · HIGH · REPRODUCED · P3** · origen ODDS-04. `src/sqp/evaluation/tipster.py:73-91,125` usa EV crudo y la mediana; la selección usa `adjusted_edge` (`daily.py:964-983`). Repro: p=0,52, d=1,95, no-vig 0,49, 12 casas → tier `B` «ventaja positiva», `adjusted_edge` 0,0035 y stake 0. Fix: llevar `adjusted_edge` y `execution_price` al stream y usarlos en el tier, o etiquetar el tier como pre-penalización.

### CLAUDE-011 — `estimated_edge`/`min_edge` se expresan como EV condicionado a no-push
- **LOW · HIGH · STATICALLY_VERIFIED · P3** · origen ODDS-03. `daily.py:961`; `models/distributions.py:36-65,379-390` (HEAD). `p·d−1` con `p = pW/(pW+pL)` = `EV/(1−P(push))`; el signo no cambia y Kelly es exacto, pero el filtro es algo más laxo en números clave (NFL −3: −0,0140 frente a −0,0128) y «EV por unidad apostada» (`tipster.py:69`, `kelly.py:12`) no es literal. Fix: documentar como EV por unidad resuelta o usar `SettlementProbabilities.expected_value`.

### CLAUDE-012 — Backtest y walk-forward MLB usan el abridor almacenado (reescrito tras el partido) en lugar del probable disponible
- **LOW · MEDIUM · REPRODUCED + STATICALLY_VERIFIED · P3** · origen LEAK-01. `backtesting/engine.py:76-79` (HEAD), `backtesting/roi_engine.py:451`; `storage/starters.py:1-4` (re-ingesta reemplaza probable→real). Medido: 2 de 154 lados con identidad distinta real (77 de 449 eventos emparejados). Leve optimismo del walk-forward que fijó `pitcher_bound=0.05`. No hay fuga del resultado. Fix: documentar; si se re-tunea, usar la confirmación anterior al corte cuando exista.

### CLAUDE-013 — Gate intradía: el «cierre» no se exige posterior a la entrada y la unidad del test no es el evento
- **LOW · MEDIUM · STATICALLY_VERIFIED (impacto NOT_VERIFIABLE) · P3** · origen BT-03. `scripts/research/intraday_gate_analysis.py:34-45` (sin `captured_out`); `src/sqp/audit/intraday_gate.py:46,83-109`. 290 filas en 258 eventos (hipotéticos) y 976 en 684 (11:00): n inflado. Solo decide si construir la fase intradía. Fix: excluir cierres con captura ≤ entrada y colapsar por evento antes de `binomtest`.

### CLAUDE-014 — Permisos del proyecto: `gh pr merge` sin confirmación y deny de `.env` solo para la herramienta Read
- **LOW · HIGH · STATICALLY_VERIFIED · P3** · origen SEC-02 + OPS-05 (misma causa). `.claude/settings.json` `permissions.allow` incluye `Bash(gh pr merge *)`; `deny` de `Read(./.env*)` no cubre Bash/PowerShell (en esta ronda lo frenó el clasificador de auto mode, que no es control del proyecto). Repo público. Fix: retirar `gh pr merge *` del allow o confirmarlo como intencional; añadir denies para lectura de `.env*` por shell.

### CLAUDE-015 — Marcadores 0-0 de relleno en resultados antiguos de NHL/NFL/NBA
- **LOW · HIGH · REPRODUCED · P4** · origen ARCH-08. `providers/espn_results.py:216-221` solo filtra `completed`. NHL 10 filas (2002-04-06 a 2004-02-25), NFL 1, NBA 1 (`game_id` 400221449, duplicado de 220302006 con 95-109). Entran en el ajuste de ratings; impacto bajo por antigüedad. Fix: descartar 0-0 en deportes sin empate al parsear; la purga del store requiere autorización.

### CLAUDE-016 — Snapshots de cuotas con filas exactamente duplicadas
- **LOW · MEDIUM · REPRODUCED (recuento; causa NOT_VERIFIABLE) · P4** · origen ARCH-06. `storage/odds_store.py:41-71` (`append_snapshot` sin dedupe). `odds_mlb_202511.csv`: 1.410 filas, 30 únicas ×47, un solo `captured_at`; `odds_nba_202606.csv`: 128 duplicadas. Medianas no cambian. Fix: dedupe por clave de snapshot.

### CLAUDE-017 — Lectores JSON sin validación de raíz
- **LOW · HIGH · STATICALLY_VERIFIED · P4** · origen ARCH-03. `models/ml_train.py:81-90`, `storage/feature_store.py:167-170`, `evaluation/feature_shadow.py:299-303`: raíz no objeto o campo ausente → `AttributeError`/`KeyError` no controlado (fallo ruidoso, no corrupción). Fix: patrón `isinstance(payload, dict)` ya usado en degradation/clv_gate/health/run_status.

### CLAUDE-018 — Lock: carrera al romper un candado caducado; `finally` puede borrar el lock de otro
- **LOW · MEDIUM · STATICALLY_VERIFIED · P4** · origen ARCH-05. `storage/lock.py:72-120`: sin identidad del dueño antes de `unlink`. Solo ante un proceso colgado > 300 s (secciones críticas sub-segundo). Fix: pid/uuid en el lock y comprobarlo antes de borrar.

### CLAUDE-019 — `_parse_events` aborta la liga tras pagar la petición y closing_capture no descuenta esos créditos
- **LOW · MEDIUM · STATICALLY_VERIFIED · P4** · origen ARCH-07. `providers/odds_api.py:~237-270`, `pipeline/closing_capture.py:~150-160`. Un outcome malformado tira la liga; `requests_last` se lee solo tras éxito. Controles: `min_remaining` usa el saldo real; `failed_leagues` y rc=1. Fix: leer `requests_last` en `finally` y omitir elementos malformados con conteo.

### CLAUDE-020 — Calibración por cara sin renormalizar
- **LOW · HIGH · REPRODUCED · P4** · origen LEAK-02. `calibration/calibrator.py:1150-1157`. `f(p)+f(1−p)`: `wnba_spreads` 1,0019; `mlb_spreads` 1,0001; `mlb_totals` 1,0 (5 puntos). Impacto ≈0,001 en `p_decision` con `market_shrink=0.5`. Fix opcional: simetrizar al servir o añadir la complementariedad como condición diagnóstica.

### CLAUDE-021 — El gate excluye `half_win`/`half_loss` (selección condicionada al resultado en líneas de cuarto)
- **LOW · MEDIUM · STATICALLY_VERIFIED (impacto inferido) · P4** · origen BT-05. `prediction_gate.py:199`. 268 de 68.866 filas. Fix: y=0,5 o excluir la línea de cuarto completa sin depender del resultado.

### CLAUDE-022 — Copias de `data/backups` siguen en el historial del repo público
- **LOW · HIGH · STATICALLY_VERIFIED · P4** · origen SEC-01. Commit `18826e2` (2026-10-19): 11 ficheros de liquidación/calibración en `origin/main`; HEAD limpio (`f4537f5`), `.gitignore` los excluye. Sin credenciales. Fix: decisión del operador (aceptar o reescribir historial con force-push). Limitación: visibilidad actual del repo no verificada sin red.

### CLAUDE-023 — `requirements.lock` sin hashes
- **LOW · HIGH · STATICALLY_VERIFIED · P4** · origen SEC-03. 75 líneas, 0 `--hash`; `pyproject.toml` solo mínimos; `pytest-cov`/`coverage` fuera del lock. CVEs: NOT_VERIFIABLE (sin red; CI ejecuta `pip-audit`). Fix opcional: `pip-compile --generate-hashes`.

### CLAUDE-024 — Acciones de GitHub fijadas por tag
- **LOW · HIGH · STATICALLY_VERIFIED · P4** · origen SEC-04. `.github/workflows/ci.yml`: `actions/checkout@v4`, `actions/setup-python@v5`. Mitigan: `permissions: contents: read`, `pull_request` (no `_target`). Fix: fijar por SHA.

### CLAUDE-025 — Agentes del proyecto sin `tools:` y con `model: opus` fijo
- **LOW · MEDIUM · STATICALLY_VERIFIED · P4** · origen OPS-04. 24 ficheros en `.claude/agents/`; los revisores heredan Write/Edit/Bash. Mitiga `require-dispatch-model.sh` (obliga a pasar `model`). Fix: `tools:` mínimas en agentes de solo lectura.

### CLAUDE-026 — `american_to_decimal` acepta valores en (−100, 100)
- **LOW · HIGH · REPRODUCED · P4** · origen ODDS-06. `markets/odds.py:22-27`: `american_to_decimal(-50)=3.0`. Inalcanzable en producción (`odds_api.py:76-81` fuerza formato decimal). Fix: rechazar `abs(x) < 100` con test.

## 5. Inferidos y no verificables (no son defectos confirmados)

| ID | Evidencia | Descripción |
|---|---|---|
| CLAUDE-I01 (ODDS-05) | INFERRED, MEDIUM | La frescura de cuotas se mide por respuesta (`daily.py:779-786`), no por casa: una cotización obsoleta de una casa puede entrar en la mediana o ser `execution_price`. Sin campo `last_update` en `src/`; no se comprobó si el proveedor lo entrega. |
| CLAUDE-I02 (ARCH-04) | INFERRED, MEDIUM | `OddsCache.put` (`providers/odds_cache.py:107-109`) escribe con `write_text` no atómico; un lector concurrente vería JSON truncado → `None` → reintento pagado. Autocurativo; no demostrado en producción. |
| — | NOT_VERIFIABLE | Contenido de `.env`/`.env.example`; barrido de secretos por contenido del historial; ejecución real de CI/`secret-scan`/`dependency-audit`; CVEs de las versiones fijadas; degradation.py y clv_gate.py; liquidación de tenis; fip/park/team_scoring/blend/independent/ml_predict; recuperación desde backups; efecto en ROI de CLAUDE-004 y CLAUDE-001 sobre datos reales. |

## 6. Revalidación independiente del coordinador

| ID | Revalidación |
|---|---|
| CLAUDE-001 | Lectura de `daily.py:995-1020` (todas las caras al stream antes de filtros) y de `_independent_units`/`_decide`; coherente con la reproducción. |
| CLAUDE-002 | Lectura de `logs/diario_completo.log` (aborto 02-11) y `git status --porcelain -- src scripts configs "*.bat"` a las 10:01 del 03-11 (5 rutas). |
| CLAUDE-003 | Lectura de `update_prediction_gate.py:64-72,98-108`. |
| CLAUDE-004 | Lectura de `validate_oos.py:75-96,258-268`. |
| CLAUDE-006 | Lectura de `revalidation.py:70-91`. |
| CLAUDE-007 | `grep timeout_s src/sqp/monitoring/health.py` → l. 291 `timeout_s: float = 30.0`. |
| CLAUDE-005 | Aceptado con la evidencia estática del especialista (citas de línea concretas); no reproducido. |
| LOW | Aceptados con la evidencia del especialista; no revalidados uno a uno por el coordinador. |

## 7. Descartes relevantes

- Devig potencia/proporcional de 2 y 3 vías, mercados incompletos → default-deny; mediana real del consenso; liquidación de cuartos asiáticos (algebraica), push/void; ROI realizado con denominador único; Kelly exacto con push; gate (unidad, K=69, test único, pestillo, centinela, default-deny); nada abre stake sin gate; topes de exposición diarios (definición declarada).
- Fugas: corte `<` del mismo día, `_already_started` antes de servir, holdout de calibración por `event_id`, regresión de Elo antes de estimar, capa de ajustes y meteo inertes, sin splits aleatorios, distribuciones normalizadas, UTC coherente en descanso NBA.
- Backtesting: sin lookahead en el stream servido; duplicación por horizonte colapsada en gate y `model_vs_market`; pre-registros de investigación protegidos (T1, addendum, árbol limpio, semilla); rolling-origin correcto.
- Datos: 0 duplicados por clave natural en results/served/graded/settled; `game_id` repetidos ya descartados al leer; dobles jornadas legítimas; fecha local MLB compensada; 5 picks duplicados en settled_mlb del 2026-07-04 con stake 0 (diseño).
- Seguridad: sin secretos en 1.010 ficheros versionados (solo fixtures del detector); `joblib.load` con verificación sha256 de sidecar; solo `yaml.safe_load`; sin `eval/exec/shell=True`; providers con timeouts, redacción de la clave y reintentos acotados.
- Automatización: `sync_agent_instructions.py --check` rc=0; 0 referencias rotas en skills/comandos; fail-open documentado de `fable_gate` y `require-dispatch-model`; fallos de red de CAPTURE_CLOSE (31-10, 02-11) recuperados en la ejecución siguiente; orden liquidación → generación correcto.

## 8. Observaciones (no son defectos)

- **OBS-001 (OPS-03):** el trabajo del portero NHL toca rutas del candado `fable_gate` (`src/sqp/sports/adapters.py`, `src/sqp/models/**`) y no tiene línea FABLE-REVIEW de hoy: correcto mientras no se commitee.
- **OBS-002 (deriva documental):** `.claude/CLAUDE.md` habla de «las 12 skills quant» con bloque común; hay 19 skills con el bloque `## Reglas comunes` (sincronizado) y 6 deportivas con su propio `## Rules`.
- **OBS-003 (OPS-06 + coordinador):** tests de contrato lentos frente al presupuesto de los hooks: `test_claude_system_contract.py` + `test_fable_gate.py` (131) en 1.157 s con la máquina cargada (Stop hook: 1.200/1.080 s). `tests/test_audit_hooks.py::test_crossreview_salida_vacia_con_rc0_no_es_un_veredicto` agotó su timeout de 60 s en el Stop hook del coordinador (`ENVIRONMENTAL_FAILURE`); aislado pasa en 48,7 s, con poco margen.

## 9. Comparación histórica (después del diagnóstico)

Fuente: `audit/audit-2026-10-18/FINDINGS.md` y `STATUS.md` (copia verificada de la ronda anterior).

| Ronda anterior | Relación con esta ronda |
|---|---|
| AUD-005 (la tarea diaria no reintenta; «Verificado-mitigado») | **Persistente en otra forma:** CLAUDE-002 muestra que la mitigación (`RestartCount`) no cubre el aborto del guard. |
| AUD-009 (CLV con cierre ≤ entrada; corregido) | La corrección no se extendió al gate intradía: **CLAUDE-013 es nuevo** en otro consumidor. |
| AUD-016 (lock sin cierre transitivo; corregido) | Corregido; **CLAUDE-023** (hashes) es un aspecto distinto, nuevo. |
| AUD-003 (ResultsStore duplica `game_id`; corregido en lectura) | Sigue corregido: los `game_id` repetidos se descartan al leer (descartes §7). |
| AUD-008 (líneas de cuarto antes del arreglo; corregido) | Sigue corregido; **CLAUDE-021** (exclusión de `half_*` en el gate) es nuevo y distinto. |
| AUD-001, -002, -004, -006, -007, -010 a -015, -017 | Sin regresión observada en las áreas revisadas (no se revalidaron uno a uno). |
| Resto de esta ronda (CLAUDE-001, 003, 004, 005, 006, 007, 008–012, 014–020, 022, 024–026) | **Nuevos.** |

## 10. Validaciones y comandos

| Comando | Resultado | Clasificación |
|---|---|---|
| `ruff check src scripts tests` | rc=0, «All checks passed!» | OK (incluye el WIP del portero) |
| `mypy src` | rc=0, 117 ficheros | OK (incluye el WIP) |
| `pytest -q -p no:cacheprovider --basetemp=.codex-tmp/pytest-baseline` (suite completa) | ver `EVIDENCE.json` (`tests_initial`) | — |
| Especialistas: 226 tests (fugas/calibración), 214 (cuotas/gates), 151 (backtesting), 65 (storage/proveedores), 131 (contrato/fable_gate) | todos rc=0 | OK |
| Stop hook (suite rápida) | 1 fallo por timeout en `test_audit_hooks.py` | `ENVIRONMENTAL_FAILURE` (aislado: passed) |
| `python scripts/sync_agent_instructions.py --check` | rc=0 | OK |
| `schtasks /query /v` (solo lectura) | rc=0, > 120 s | OK |
| Reproducciones sintéticas (gate EV, overrides del gate, `_append_log`) | rc=0, en directorios temporales | — |

## 11. Plan priorizado (requiere autorización; nada implementado)

| Prioridad | IDs | Acción |
|---|---|---|
| **P1 — hoy antes de las 12:00** | CLAUDE-002 | Operador: apartar (stash) o commitear con revisión Fable el trabajo del portero NHL. Después decidir la solución estructural (reintento del guard o worktree). |
| **P2 — antes de que un corte llegue a n=300** | CLAUDE-001, CLAUDE-003 | Re-pre-registrar la condición 2 del gate (Fable + operador) y blindar los overrides del escritor. |
| **P2 — antes de abrir stake real** | CLAUDE-005 | Decidir la regla precio de decisión/ejecución. |
| P2 | CLAUDE-004, CLAUDE-006, CLAUDE-007 | Corregir `validate_oos`, cuarentena en `_append_log`, timeout/consulta del health. |
| P3 | CLAUDE-008 a CLAUDE-014 | Robustez del registro de calibración, techo K bloqueante, coherencia tipster/edge, documentación de LEAK-01, gate intradía, permisos. |
| P4 | CLAUDE-015 a CLAUDE-026 | Mantenimiento y endurecimiento. |

## 12. Limitaciones

- Auditor único (sin segunda opinión OpenAI). Context7 no usado (OAuth pendiente). Pyright usado solo para navegación puntual.
- Coberturas parciales y no verificables declaradas en §3 y §5; ningún área se declara cubierta al 100 %.
- El coordinador tiene contexto contaminado por la memoria del proyecto; el diagnóstico lo hicieron especialistas limpios y la comparación histórica se hizo al final.
- La máquina estuvo muy cargada (seis especialistas, suite completa y dos procesos `--parity-only` duplicados del trabajo del portero), lo que afecta a tiempos y a algún timeout.
- Datos solo por agregados; sin red; sin ejecutar BAT, `--medir`, validate_oos ni scripts que escriban en `data/`/`logs/`.
