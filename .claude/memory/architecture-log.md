# Architecture Log

Format:
- Date:
- Component:
- Change:
- Reason:
- Validation:

## 2026-06-12 — Saneamiento de configuración .claude/

**Tipo:** fix-arquitectural
**Módulos afectados:** settings.json, settings.local.json, hooks/, agents/ (24 archivos), skills/ (sports-analytical-system, daily-operations, low-cost-mode, maximum-context-engineering, elite-principal-engineer), memory/agent-topology.md
**Cambio:** Migración a esquema oficial; hooks registrados en PostToolUse; frontmatter en agentes; extracción del .skill; fusión daily-run→daily-operations y bankroll-manager→risk-manager; eliminación de rutas absolutas.
**Validación:** JSON validados; bash -n en hooks; verificación de frontmatter en 24/24 agentes.

## 2026-06-12 — Guard de deporte inactivo en pipeline live

**Tipo:** mejora-operativa
**Módulos afectados:** src/sqp/providers/odds_api.py, src/sqp/pipeline/daily.py, tests/test_inactive_sport.py
**Cambio:** Nuevo `OddsAPIClient.is_sport_active()` con cache de /sports por cliente; `run_league` en live hace skip temprano con log (WARNING inactivo / ERROR key desconocido); cierre del pipeline (CSV + log resumen) extraído a `_finalize()` reutilizado por ambos caminos.
**Validación:** pytest tests/ -q → 18 passed (3 nuevos); run real `ligamx --mode live` emite el log de inactivo sin llamadas a odds/scores.

## 2026-06-12 — Subsistema de backfill de resultados históricos + RUN_DIARIO.bat

**Tipo:** feature
**Módulos afectados:** src/sqp/providers/espn_results.py (nuevo), src/sqp/storage/results_store.py (nuevo paquete), scripts/backfill_results.py (nuevo), src/sqp/pipeline/daily.py, RUN_DIARIO.bat (nuevo), tests/test_results_backfill.py (nuevo)
**Cambio:** `ESPNResultsProvider` (17 ligas, chunks de 30 días, solo completados) + `ResultsStore` (CSV append-only por liga, dedup (date, home, away), `ingested_at`) + CLI de backfill incremental. `run_league` live ahora fusiona histórico + ventana de 3 días vía `_merge_results` (histórico gana) y loggea `N stored + M recent` con umbral `MIN_RESULTS_FOR_RATINGS=50`. RUN_DIARIO.bat orquesta backfill (10 días, no bloqueante) + run live para LEAGUES=nba wnba ligamx.
**Razón:** KI-001 — ratings construidos solo con 3 días de /scores eran inservibles (NBA: 1 resultado).
**Validación:** pytest → 23 passed (5 nuevos); semilla real NBA 1395/WNBA 207/ligamx 300; RUN_DIARIO.bat de punta a punta con dedup verificado (0 filas nuevas al re-correr).

## 2026-06-12 — Backtest 3-way correcto + tuning de ratings por liga

**Tipo:** fix-metodológico + feature
**Módulos afectados:** src/sqp/backtesting/engine.py, src/sqp/backtesting/tuning.py (nuevo), scripts/backtest_history.py (nuevo), scripts/tune_ratings.py (nuevo), src/sqp/pipeline/daily.py (_league_meta), configs/leagues/ratings.yaml (nuevo), tests/test_backtest_tuning.py (nuevo)
**Cambio:** walk_forward_backtest condiciona P(local) a no-empate en ligas 3-way y reporta calibración del empate; tune_home_advantage hace grid search walk-forward de elo_home_adv; _league_meta fusiona overrides de ratings.yaml para cualquier liga (copia, no muta SPORT_KEYS); flujo: backfill → tune_ratings --write → backtest_history → run diario consume los overrides.
**Razón:** KI-003 — ECE de Liga MX inflado por scoring incondicional vs outcomes sin empates, y ventaja local única por familia.
**Validación:** pytest → 27 passed (4 nuevos); Liga MX Brier 0.2346→0.2093 y ECE 0.162→0.057; las tres ligas baten su baseline.

## 2026-06-12 — Ajuste Dixon-Coles en el modelo soccer

**Tipo:** upgrade de modelo
**Módulos afectados:** src/sqp/models/distributions.py, src/sqp/sports/adapters.py, src/sqp/sports/registry.py, src/sqp/backtesting/engine.py (log_loss_threeway), src/sqp/backtesting/tuning.py (tune_dc_rho), scripts/tune_ratings.py, scripts/backtest_history.py, configs/leagues/ratings.yaml, tests/test_backtest_tuning.py
**Cambio:** tau Dixon-Coles (1997) para marcadores ≤1 en la grilla de poisson_match_probs (param dc_rho, clamp ≥0, renormalización); engine reporta log loss multiclase 1X2; tuning de rho por liga integrado al flujo tune_ratings --write → ratings.yaml → _league_meta → adapter.
**Razón:** KI-004 — subestimación estructural del empate del Poisson independiente en ligas de pocos goles.
**Validación:** pytest → 30 passed (3 nuevos); Liga MX dc_rho=−0.10: empate 0.2366→0.2589 vs obs. 0.2542, log loss 3-way 1.0206→1.0194, Brier binario intacto.

## 2026-06-12 — ESPN_PATHS por configuración + estrategia day_by_day para NCAA

**Tipo:** fix de proveedor + ampliación de cobertura
**Módulos afectados:** src/sqp/providers/espn_results.py, tests/test_results_backfill.py, data/historical/ (19 ligas pobladas)
**Cambio:** ESPN_PATHS pasa de `dict[str, str]` a `dict[str, dict]` con `path`, `day_by_day` y `params` opcionales; `_fetch` unificado tolera 404 como "sin partidos"; ncaab/wncaab consultan día a día con groups=50 (rangos → 404 y default top-25 en el scoreboard universitario); ligas nuevas: chile (chi.1), uwcl (uefa.wchampions), ambas verificadas empíricamente.
**Razón:** Descarga completa de históricos reales; los defaults del endpoint ESPN ocultaban >90% de los partidos NCAA.
**Validación:** pytest → 31 passed; NCAAB 6,300 resultados (consistente con D-I completa); conteos de ligas europeas exactos vs calendario (380 EPL/La Liga/Serie A, 306 Bundesliga).

## 2026-06-12 — Store v2 (game_id) + saneamiento del provider MLB

**Tipo:** fix de integridad de datos
**Módulos afectados:** src/sqp/storage/results_store.py (esquema v2), src/sqp/providers/mlb_statsapi.py, src/sqp/providers/espn_results.py, src/sqp/pipeline/daily.py (_merge_results), tests/test_results_backfill.py, data/historical/ (19 stores regenerados)
**Cambio:** (1) MLB excluye pospuestos/cancelados/suspendidos y juegos sin score (24 empates 0-0 fabricados eliminados); (2) game_id del vendor en cada fila, KEY de dedup (date, home, away, game_id) con migración legacy automática; (3) merge histórico/recientes: dedup por game_id intra-fuente, por (día, home, away) inter-fuente con histórico ganando.
**Razón:** Audit de falsos empates MLB destapó scores inventados por default y colapso de doubleheaders (21 juegos reales perdidos).
**Validación:** pytest → 35 passed; MLB regenerado 2,439 filas (2,418 + 21 doubleheaders, cuadre exacto), 0 empates.

## 2026-06-12 — Grillas custom en tune_ratings y cierre de óptimos en frontera

**Tipo:** mejora de tooling + recalibración
**Módulos afectados:** scripts/tune_ratings.py (--ha-grid, --rho-grid), configs/leagues/ratings.yaml (9 ligas)
**Cambio:** Flags de grilla custom por parámetro; re-tune de las ligas en frontera con grillas ampliadas (college hasta 300, tramo negativo −90…+30 para MLB/NHL/Serie A como diagnóstico, dc_rho −0.35…+0.35). Valores finales: NCAAF 180, NCAAB 150, MLB/NHL/Serie A 0, EPL −0.20, Bundesliga −0.25, La Liga +0.05, UCL +0.30, Chile +0.35.
**Razón:** KI-007 — 10 parámetros en bordes de grilla no eran óptimos confiables.
**Validación:** pytest → 35 passed; curvas convexas con óptimo interior en todos los casos salvo Chile (parada deliberada documentada en decisiones).

## 2026-06-12 — Infraestructura de abridores MLB + hook observe()

**Tipo:** feature de modelo (v1 apagada por evidencia) + extensión de arquitectura
**Módulos afectados:** src/sqp/models/starters.py (nuevo), src/sqp/domain/models.py (Event.pitchers), src/sqp/sports/base.py (observe()), src/sqp/sports/adapters.py (BaseballAdapter), src/sqp/backtesting/engine.py, src/sqp/providers/mlb_statsapi.py (fetch_starters), src/sqp/storage/starters.py (nuevo), scripts/backfill_starters.py (nuevo), scripts/tune_mlb_pitcher.py (nuevo), src/sqp/pipeline/daily.py, tests/test_pitcher_features.py (nuevo)
**Cambio:** SportAdapter.observe(result) como punto único de aprendizaje secuencial (Elo + extensiones por familia; engine y fit_results lo usan — backtest y producción aprenden idéntico). BaseballAdapter ajusta lambdas por factor de abridor acotado y flaggea abridor desconocido (sin candidatos). Mapa gamePk→abridor con refresco newest-wins. tilt_scale MLB 0.4 persistido.
**Razón:** KI-006 (MLB). El factor v1 fue rechazado por walk-forward; el valor quedó en el flag de seguridad, la tubería para FIP v2 y el hallazgo del tilt.
**Validación:** pytest → 39 passed; cobertura de abridores 99.8%; Brier MLB 0.2501→0.2474 (vía tilt), bate baseline por primera vez.

## 2026-06-16 — Vertical de tenis end-to-end (cierre del hueco de auditoria)

**Tipo:** nueva vertical de deporte (generacion + resultados + liquidacion + auditoria)
**Modulos afectados:** src/sqp/providers/espn_tennis.py (nuevo), src/sqp/pipeline/daily.py (_league_meta tenis, _tennis_results, _fetch_recent_scores extraido, fetch h2h-only), src/sqp/settlement/runner.py (_settle_tennis, tennis_scores_map, _persist_settled), scripts/run_all.py (_active_tennis), tests/test_tennis.py (nuevo)
**Cambio:** The Odds API no da scores de tenis, asi que el tenis no se podia liquidar ni auditar (ademas no estaba cableado en la generacion). Ahora: (1) generacion por clave de torneo (has_scores=False, family=tennis), Elo de jugador TOUR-WIDE ajustado con resultados ESPN (atp/wta), solo singles + moneyline; (2) proveedor ESPN tenis con parser torneo->groupings->partidos; (3) liquidacion por nombre de jugador normalizado + fecha (no hay event_id comun entre proveedores), recuperando jugadores/fecha de predictions_<liga>.csv, con marcadores sinteticos 1-0 que reutilizan settle_candidates + la auditoria existente; (4) descubrimiento de torneos activos via /sports (gratis) en el run diario.
**Razon:** cerrar el hueco de AUDITABILIDAD del tenis (no habilita operar: falta cierre real/OOS).
**Validacion:** pytest 118->122 (4 tests nuevos: parser, filtro since, tour_from_league, casado nombre+fecha). Verificado en vivo: ATP Halle Open 12 eventos / 8 candidatos desde 6145 resultados ESPN; liquidacion corre sin errores (0 ahora porque los partidos aun no se juegan; gradua en el SETTLE_ALL al completarse).
**Riesgo:** ESPN es endpoint NO oficial (parser defensivo + tests lo mitigan; vigilar el log). Depende del orden settle(09:00)->run(10:00) para recuperar jugadores/fecha de predictions.

## 2026-06-16 — Infraestructura v2 de abridor (FIP por apertura), APAGADA por validacion

**Tipo:** feature de modelo (v2, construida + validada + apagada por evidencia) + extension de datos
**Modulos afectados:** src/sqp/models/fip.py (nuevo), src/sqp/providers/mlb_statsapi.py (fetch_starter_fip), src/sqp/storage/starter_fip.py (nuevo), src/sqp/sports/adapters.py (BaseballAdapter.pitcher_signal), src/sqp/pipeline/daily.py (attach FIP), scripts/backfill_starter_fip.py (nuevo), tests/test_fip.py (nuevo)
**Cambio:** Senal de abridor FIP (independiente de fildeo/ofensiva rival) por apertura desde boxscore MLB; reutiliza el mismo StarterRatings acotado cambiando solo la FUENTE. pitcher_signal ("fip"|"ra") evita mezclar escalas en el pool. Backfill one-off (~2.440 boxscores, gratis): starter_fip_mlb.csv = 2.438 filas.
**Razon:** KI-006 — v1 (RA) rechazado por mezclar bullpen + ofensiva rival; FIP era el upgrade documentado.
**Validacion:** walk-forward sobre la temporada con FIP (2.130 juegos): FIP solo EMPATA al baseline (mejor bound 0.05: log-loss −0.0007, < margen 0.002; ECE empeora). NO se activa: pitcher_signal queda "ra", mlb.pitcher_bound 0.0. Produccion sin cambios. 128 tests verdes. Infra + datos quedan listos para un v3 mejor especificado.

## 2026-06-21 — CI (GitHub Actions) + ruff config

**Tipo:** infraestructura / calidad
**Módulos afectados:** .github/workflows/ci.yml (nuevo), pyproject.toml ([tool.ruff]), src/sqp/logging_config.py, src/sqp/features/builders.py
**Cambio:** Workflow CI en push/PR (Python 3.11+3.12, pip cache) que corre `ruff check src tests` + `pytest -q`. Config de ruff (perdido en la re-importación): default+pyflakes, ignora E701/E702 (estilo compacto deliberado). Corregidos los 2 hallazgos reales de ruff.
**Validación:** ruff limpio; `pytest -q` sin PYTHONPATH (usa pythonpath=["src"] de pyproject) → 167 passed; YAML válido. Sin remoto aún: se activará al añadir uno.

## 2026-06-21 — Penalización de EV por desacuerdo modelo-mercado (portada del proyecto 2, ACTIVADA)

**Tipo:** control de riesgo / realismo de edge
**Módulos afectados:** src/sqp/markets/edge.py (nuevo), src/sqp/config.py (RiskConfig +5 coef), src/sqp/domain/models.py (BetCandidate +adjusted_edge/edge_penalty/books_count), src/sqp/pipeline/daily.py (_consensus_counts + cableado), src/sqp/backtesting/roi_engine.py (espejo), configs/default.yaml, tests/test_edge.py (nuevo)
**Cambio:** `adjusted_edge(p, d, market, books, ...)` recorta el EV por `gap*uncertainty_penalty` (+anomalía si gap>0.06, +pocos books) y lo pliega en `p_eff=p-penalty/d` que alimenta edge+Kelly (achica el stake). `estimated_edge` se mantiene RAW. Coeficientes 0 = no-op; default.yaml los activa con los valores del proyecto 2 (0.35/0.06/0.02/0.015/2).
**Razón:** KI-012 — edges sobreconfiados (media 8.5% post-shrink, ECE crudo 0.198).
**Validación:** no-op probado (suite idéntica con defaults). Activación gateada por walk-forward sobre odds capturadas (1654 apuestas): ROI agregado −0.74%→+0.37%, exposición ~a la mitad. 173 passed. NO cierra KI-012 (sigue ≈ break-even, in-sample en parámetros).

## 2026-06-21 — Ledger de bankroll para staking dinámico (OFF por defecto)

**Tipo:** fidelidad de staking / gestión de riesgo
**Módulos afectados:** src/sqp/risk/bankroll.py (nuevo), src/sqp/config.py (flag bankroll_dynamic + bankroll.initial yaml), scripts/run_all.py (inyección live), scripts/bankroll_status.py (nuevo), tests/test_bankroll.py (nuevo)
**Cambio:** `BankrollLedger` deriva el balance corriente = inicial + PnL realizado (settled_*.csv, data_label=="real") + ajustes manuales (bankroll_adjustments.csv). Solo el entrypoint live lo inyecta cuando `bankroll_dynamic` está ON; demo y run_league directo usan el inicial (tests deterministas). equity_curve/summary/max_drawdown + CLI de auditoría.
**Razón:** KI-013 — bankroll estático ignoraba el PnL realizado; Kelly y el cap de exposición dimensionaban sobre capital nominal.
**Validación:** 179 passed (6 nuevos). Balance real verificado por el CLI: 937.28 (1000 − 62.72 sobre 93 apuestas). OFF por defecto → staking byte-idéntico; pendiente activar en producción tras verificar contra la liquidación real.

## 2026-06-22 — OOS de tenis (resultados tour-wide + matching order-insensible)

**Tipo:** habilitación de evaluación / extensión de datos
**Módulos afectados:** scripts/backfill_tennis_results.py (nuevo), src/sqp/backtesting/roi_engine.py (_pair_key/_match_index/_match_result + flag por family), scripts/validate_oos.py (rama tenis), tests/test_roi_engine.py
**Cambio:** El tenis daba 0 OOS (sin resultados en ResultsStore + matching ordenado sin home/away). Ahora: backfill persiste resultados ESPN tour-wide bajo la clave de tour (results_atp.csv/results_wta.csv, home=winner 1-0 neutral), el roi_engine empareja order-insensible (frozenset) cuando family=="tennis" reusando la reorientación de marcadores existente, y validate_oos carga resultados tour-wide y omite el freezing (Elo neutral). Deportes de equipo conservan matching ordenado.
**Razón:** cerrar el hueco de OOS de tenis (el Elo es por jugador tour-wide; las odds son por torneo).
**Validación:** ATP 6205 / WTA 8503 resultados cargados; Halle 26/9, Queen's 20/3, German Open 15/4; Wimbledon 0 (calendario); Bad Homburg 0 (KI-014). 181 passed (+2). ROI = ruido (capacidad, no señal). CSV fuera de git.

## 2026-06-22 — Interactividad client-side del reporte HTML

**Tipo:** UX / reporte
**Módulos afectados:** src/sqp/audit/html_report.py (template + _history_section reescrito + JS), tests/test_html_report.py
**Cambio:** Pills toggleables por deporte en Picks (multi-select, reemplaza el dropdown #fSport); orden por columna genérico (makeSortable/initSortable, numeric-aware) en todas las tablas .grid server-rendered salvo la de picks (que tiene su propio sorter); filtros de Historial por deporte/mercado/rango-de-fecha con filas data-* y contador en vivo. initSortable/initHistory corren al inicio de init() (funcionan sin picks). Sigue autónomo (sin assets externos).
**Razón:** pedido del usuario, replicando el reporte del proyecto 2 pero para todos los deportes; las tablas de Auditoría/Patrones/Historial eran estáticas.
**Validación:** 183 passed (+2). ruff limpio. report_latest.html regenerado con datos reales (21 picks, 4 ligas).

## 2026-06-22 — Factor de parque MLB (primera señal por deporte, totales)

**Tipo:** feature de modelo (señal específica por deporte, validada + activada)
**Módulos afectados:** src/sqp/models/park.py (nuevo), src/sqp/sports/adapters.py (BaseballAdapter), configs/leagues/ratings.yaml (mlb.park_bound), configs/default.yaml (un-pause totals), tests/test_park.py (nuevo), tests/test_pipeline_demo.py
**Cambio:** `ParkFactors` estima el entorno de carreras del parque (totales de local vs de visita del equipo local → aísla el parque), regresado/acotado/leakage-safe; BaseballAdapter lo actualiza en observe y escala AMBAS lambdas en _rates (mueve Over/Under, no el moneyline). Gated por `park_bound` (0.0 = no-op). Activado 0.10 para MLB + mlb/totals des-pausado.
**Razón:** MLB totals era el mercado débil (OOS −17.1%, pausado). El Elo+scoring de equipo no captura el parque.
**Validación:** OOS sobre odds capturadas (config de producción): totals −17.1%→+2.8%, MLB global +2.4%→+7.8%; held-out (≥2026-05-09) −15.9%→+3.8%/+7.0% → generaliza. 187 passed (+4). PRIMERA señal por deporte que bate al baseline (el abridor solo empataba, KI-006). Una temporada / snapshot proxy → no rentabilidad demostrada.

## 2026-06-22 — Señal de rest/B2B basketball, construida y APAGADA por OOS

**Tipo:** feature de modelo (señal por deporte, construida + validada + apagada por evidencia)
**Módulos afectados:** src/sqp/models/rest.py (nuevo), src/sqp/sports/adapters.py (NormalMarginAdapter), tests/test_rest.py (nuevo)
**Cambio:** `RestModel` ajusta el margen esperado del local por `points_per_day*(descanso_local − descanso_visita)` (acotado, leakage-safe, last-game-date por equipo); NormalMarginAdapter lo actualiza en observe y suma el ajuste a mu_margin en estimate (mueve moneyline/spread, no el total). Gated por `rest_points_per_day` (0.0 = no-op). NO activado en ninguna liga.
**Razón:** apuntaba a WNBA spreads (OOS −11.3%, el mercado débil restante).
**Validación:** OOS NEGATIVO — la ventana completa lucía bien (spreads −6%→+18%) pero no generaliza en held-out (rppd 1.0 empeora −38%→−48%; no-monótono) sobre muestras minúsculas (22-25 ALL, 7-10 held-out). Mismo patrón de ruido de WNBA. Queda como infra dormida (no-op) para re-validar con más cobertura OOS. 192 passed (+5). Producción byte-idéntica.

## 2026-07-28 — Modo de selección de picks conmutable (edge | accuracy)

La selección de candidatos en `run_league` deja de ser única (Kelly sobre
min_edge) y pasa a un modo configurable (`Settings.pick_mode`): "accuracy"
selecciona por probabilidad de decisión calibrada >= umbral, solo h2h, stake
plano; "edge" conserva el camino clásico intacto. El helper puro
`_accuracy_selected` (daily.py) encapsula la regla. La revalidación por edge
reconoce el flag `accuracy_mode` y salta esos picks. `segments.py` gana
`_decision_prob` (calibrada con fallback a estimada) como base única de
banda/gap/Brier del modelo. Sin módulos nuevos; el served stream y la
liquidación no cambian.

## 2026-08-04 — Remediación integrada del sistema de loops de Claude Code

**Tipo:** arquitectura operativa / seguridad / documentación
**Módulos afectados:** `CLAUDE.md`, `.claude/automation/`, `.claude/loops/`, `.claude/hooks/route-model.py`, `.claude/settings.local.json`, `scripts/claude_project_health.py`, `configs/default.yaml`, tests y bóveda Obsidian.
**Cambio:** Fable 5 queda como modelo principal autorizado y separado de los modelos de subagentes; routing explícito para los 13 loops cuantitativos; protocolo de loops de apoyo; máquina de estados sin contradicción por IDs; lifecycle/result separados en `current-task.md`; promoción de calibradores humana por defecto; permisos locales saneados; NUL bytes eliminados del `CLAUDE.md` raíz.
**Razón:** la auditoría integrada encontró divergencias entre configuración ejecutable, decision engine, hooks, estados y políticas de aprobación.
**Validación:** compilación Python, validación JSON/YAML/rutas/NUL, pruebas focalizadas y suite completa. Ruff y Mypy no estaban disponibles en el entorno de remediación.
**Riesgo:** no se verificó la disponibilidad externa del identificador Fable 5 contra una instalación real de Claude Code; la coherencia del repositorio sí queda probada.

## 2026-08-04/05 — Auditoría integral: fail-fast de configuración, fallback histórico de tenis y guard de evidencia

**Tipo:** seguridad / integridad de datos / control de proceso
**Módulos afectados:** `src/sqp/config.py`, `src/sqp/settlement/runner.py`, `src/sqp/monitoring/health.py`, `scripts/settle_all.py`, `scripts/claude_project_health.py`, `pyproject.toml`, `.gitignore`, `.claude/automation/`, tests y bóveda Obsidian.

**Cambios estructurales:**
1. `Settings.load()` pasa de fail-open a **fail-fast**: sin `configs/default.yaml` lanza `FileNotFoundError` en vez de caer a defaults inseguros (`shadow_mode=False`, gate de CLV apagado, `max_plausible_edge` 0.15 vs 0.075). Cierra la clase de fallo B-08 en la ruta de archivo.
2. La liquidación de tenis gana **fallback histórico**: `_settle_tennis` ahora llama a `_grade_served_from_history`, y este resuelve la clave del histórico por TOUR (`tour_from_league`) en vez de por liga. Antes ninguna fila servida de tenis se graduaba por esa vía y se anulaba por `stale_void` con el resultado ya en disco.
3. El abort del día en `settle_all` deja de ser global: solo aborta si una liga fallida retiene picks comenzados sin liquidar (el guard M2 por liga de `run_all` ya cubría el riesgo).
4. Nuevo contrato de evidencia: `pass_result_missing_evidence()` convierte en **error** un `current-task.md` que declare `Result: PASS|DONE` sin las secciones de comandos y artefactos que `STATES.md` exige.
5. `claude-opus-5` sustituye a `claude-fable-5` como modelo principal (decisión del operador), con política, registro y test alineados en un candado a tres bandas.

**Razón:** la auditoría encontró que la documentación del día declaraba un estado (suite verde, herramientas ausentes) que la ejecución real contradecía, y que dos rutas de código —carga de configuración y liquidación de tenis— fallaban hacia el lado inseguro sin aviso.

**Validación:** `pytest` 625 passed (desde 612 con 5 en rojo), `ruff check` limpio, `mypy src` 89 archivos sin issues, `pip check` limpio, `compileall` OK, health check WARN(1). `pip-audit` no ejecutado localmente (lo cubre el CI). `ruff format` declarado NO adoptado.

**Riesgo:** `gh` no autenticado en el entorno, así que el resultado del CI de la rama no se verificó y no se abrió PR; la rama `fix/claude-audit-20260804` no está mergeada a `main`.
