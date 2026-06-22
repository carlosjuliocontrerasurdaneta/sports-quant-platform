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
