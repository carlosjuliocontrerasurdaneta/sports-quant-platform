# Known Issues

Format:
- ID:
- Severity:
- Description:
- Affected files:
- Proposed fix:
- Status:

- ID: KI-001
- Severity: Alta
- Description: Los ratings en modo live se construyen solo con la ventana de scores de 3 días de The Odds API (NBA: 1 resultado, WNBA: 9 el 2026-06-12). Las probabilidades estimadas resultantes no son confiables; el pipeline ya emite WARNING pero igual produce estimaciones.
- Affected files: src/sqp/pipeline/daily.py (fetch_scores daysFrom=3), adaptadores en src/sqp/sports/.
- Proposed fix: Backfill de historial de resultados de temporada completa por liga (fuente histórica propia, no el endpoint /scores) y fit de ratings desde ese histórico.
- Status: Resuelto (2026-06-12). Implementado: `scripts/backfill_results.py` (ESPN scoreboard API + MLB Stats API) → `data/historical/results_{league}.csv` (append-only, dedup por fecha/home/away) → `run_league` fusiona histórico + scores recientes. Backfill inicial: NBA 1395, WNBA 207, Liga MX 300 resultados. Caveat: nombres de equipos ESPN vs Odds API coinciden en NBA/WNBA (verificado); en soccer con acentos podría haber mismatches — el warning de confiabilidad por evento los delataría.

- ID: KI-002
- Severity: Media
- Description: Posible mismatch de nombres de equipos entre ESPN (histórico, con acentos: "Club América") y The Odds API (eventos live) en ligas de fútbol. Un mismatch deja al equipo con rating default y dispara el warning de confiabilidad por evento, pero degrada la estimación en silencio si no se revisa la columna `warning`. NBA/WNBA verificados sin mismatch.
- Affected files: src/sqp/providers/espn_results.py, src/sqp/sports/base.py (Elo keyed por nombre).
- Proposed fix: Normalización unicode (NFKD, sin acentos, casefold) en la frontera de fit/lookup de Elo cuando Liga MX se reactive y se pueda verificar empíricamente.
- Status: Abierto (2026-06-12). Verificable cuando el Apertura 2026 reactive `soccer_mexico_ligamx` (~después del 19-jul).

- ID: KI-003
- Severity: Alta
- Description: Con ratings de temporada completa el run live ya genera candidatos sobre min edge (2026-06-12: NBA 3, WNBA 15), pero el Elo baseline no tiene backtest walk-forward ni calibración validada sobre el nuevo histórico. Los edges estimados no deben usarse para apostar sin esa validación.
- Affected files: src/sqp/backtesting/engine.py, src/sqp/calibration/metrics.py, data/historical/.
- Proposed fix: Correr walk-forward backtest por liga sobre data/historical/, revisar Brier/calibración, ajustar elo_k/home_advantage por liga antes de operar candidatos.
- Status: Parcialmente resuelto (2026-06-12; actualizado 2026-06-22). Backtest corrido y `elo_home_adv` tuneado por liga (NBA 75, WNBA 30, Liga MX 45 en configs/leagues/ratings.yaml). Las tres ligas baten el baseline de tasa local (Brier: NBA 0.2100, WNBA 0.2292, Liga MX 0.2093). (a) VALIDACIÓN OOS DE PARÁMETROS HECHA (2026-06-22, scripts/validate_oos.py): MLB congelado en train (tilt 0.4 / home_adv 25) da ROI test +0.41% vs sin-tuning −3.28% (~+3.7pp) e IDÉNTICO a full_history → el tuning de MLB GENERALIZA, no es overfit. WNBA: params congelados = default de la familia → nada que validar, ROI test −2.13% (n=170, ruido). (b) Ya hay odds capturadas → ROI realizado existe, pero sigue ≈ break-even sobre proxy de cierre de un snapshot, cobertura limitada, sin IC: NO habilita operar. Pendiente: validar más ligas cuando acumulen odds; MLB totals sigue el mercado débil (pausado).

- ID: KI-004
- Severity: Media
- Description: El Poisson independiente subestima el empate en Liga MX (estimado 0.237 vs observado 0.254 en 240 partidos walk-forward). Limitación estructural conocida del modelo: no captura la correlación de marcadores bajos.
- Affected files: src/sqp/sports/adapters.py (PoissonAdapter), src/sqp/models/distributions.py.
- Proposed fix: Ajuste Dixon-Coles (tau para marcadores ≤1) como primer upgrade del modelo soccer; mayor ganancia esperada en ligas de pocos goles.
- Status: Resuelto (2026-06-12). Implementado `dc_rho` en poisson_match_probs (tau DC-1997, renormalizado) + tune_dc_rho por log loss 3-way. Liga MX: dc_rho=−0.10 → empate estimado 0.2589 vs observado 0.2542 (gap cerrado desde −1.8pts). Persistido en configs/leagues/ratings.yaml; el run diario lo consume automáticamente. Caveat: in-sample sobre 240 partidos — re-validar cuando el Apertura 2026 reactive la liga.

- ID: KI-005
- Severity: Baja
- Description: La Frauen-Bundesliga (configurada en configs/leagues/soccer.yaml) no tiene vendor de resultados históricos: no existe en el catálogo de ESPN (verificado contra las 244 ligas soccer de sports.core.api.espn.com el 2026-06-12; sí existen eng.w.1, esp.w.1, fra.w.1, ned.w.1). Sin histórico, sus ratings dependerán solo de la ventana de 3 días de The Odds API.
- Affected files: src/sqp/providers/espn_results.py (documentado en ESPN_PATHS), configs/leagues/soccer.yaml.
- Proposed fix: Integrar un vendor alternativo para esa liga (p. ej. football-data u otro con cobertura femenina alemana) implementando ResultsProvider.
- Status: Abierto (2026-06-12).

- ID: KI-006
- Severity: Alta
- Description: MLB pierde contra el baseline de tasa local en backtest walk-forward (Brier 0.2500 vs 0.2491, sobreconfianza en ambas colas: underdogs est. 0.27 ganan 47%) incluso con datos limpios; NHL apenas empata (0.2482 vs 0.2496). El Elo puro de equipo no captura al abridor (MLB) ni al portero (NHL). Ambos tunearon elo_home_adv=0 (borde).
- Affected files: src/sqp/sports/adapters.py (PoissonAdapter), src/sqp/providers/mlb_statsapi.py (fetch_probable_pitchers ya existe, sin uso en el modelo).
- Proposed fix: Features de abridor/bullpen para MLB y portero/xG para NHL como ajustes a lambda (roadmap de los skills quant-baseball-mlb y quant-hockey-nhl). NO operar candidatos MLB/NHL hasta entonces.
- Status: Parcialmente resuelto (2026-06-12). MLB: la sobreconfianza era del tilt_scale (0.8→0.4 tuneado): Brier 0.2474 ya bate el baseline 0.2491, ECE 0.019. El feature de abridor v1 (RA por apertura) fue RECHAZADO por evidencia (empeora en todo el grid) y está apagado (pitcher_bound 0.0); la infraestructura queda lista para v2 con FIP por apertura desde boxscores. NHL sigue abierto (portero/xG pendiente). Batir al baseline trivial NO es batir al mercado: mantener no-operar hasta validar ROI con odds reales. Actualización 2026-06-15: KI-009 (H2) cerró un contribuyente real al "pitcher no mueve el estimado" (fallo silencioso por nombres divergentes entre vendors). H4 INVESTIGADO con datos reales: el "factor pitcher = 1.0" NO es bug — es por diseño (`pitcher_bound: 0.0` en ratings.yaml apaga el v1). El pipeline está sano: results_mlb=8371 (todas con game_id), 4933 con starters adjuntos, 438 pitchers con ≥3 starts, league_mean 4.513; forzando bound=0.35 los 438 factores se mueven (0.66–1.35). NO reactivar bound>0 con el v1 (RA, ya rechazado); el upgrade real es v2 FIP por apertura. Demostración: factor de supresor = 1.0000 (bound 0) vs 0.6500 (bound 0.35). Actualización 2026-06-16: v2 (FIP por apertura) CONSTRUIDO y VALIDADO — resultado NEGATIVO. Backfill de 2.438 starts (boxscore MLB), walk-forward sobre la temporada con FIP (2.130 juegos): FIP solo EMPATA al baseline (mejor en bound 0.05: log-loss 0.6874→0.6867, −0.0007; Brier 0.2471→0.2468) y empeora monotónicamente desde 0.10; ECE empeora (0.0225→0.0278). La ganancia (−0.0007) está por DEBAJO del margen de aceptación del proyecto (0.002), asi que v2 NO se activa (pitcher_signal sigue "ra", pitcher_bound 0.0). FIP es menos malo que v1 (RA) pero el Elo de equipo + tilt ya captura la señal. Infra + datos quedan para un v3 mejor especificado (FIP con ajuste por oponente / recencia / matchup). Commit bce6b1b. Actualización 2026-06-22: KI-006 es sobre el moneyline/margen (abridor/portero) y SIGUE abierto ahí. Pero la PRIMERA señal por deporte que bate al baseline ya existe en OTRO mercado: el factor de PARQUE para MLB totals (sqp.models.park, mlb.park_bound 0.10) da vuelta totals de −17.1% a +2.8% OOS (held-out confirma) — ver session-summaries/architecture-log 2026-06-22. El moneyline MLB sigue sin señal específica validada (abridor rechazado v1/v2).

- ID: KI-007
- Severity: Media
- Description: Varios parámetros tuneados quedaron en bordes de grilla y no son óptimos confiables: elo_home_adv 150 (techo) en NCAAF y NCAAB; 0 (piso) en MLB, NHL y Serie A; dc_rho −0.20 (piso) en EPL y Bundesliga; +0.05 (techo) en La Liga, UCL y Chile.
- Affected files: src/sqp/backtesting/tuning.py (DEFAULT_HOME_ADV_GRID, DEFAULT_DC_RHO_GRID), configs/leagues/ratings.yaml.
- Proposed fix: Ampliar grillas (home_adv hasta ~250 para college; dc_rho hasta ±0.35 con validación del rango de no-negatividad del tau) y re-tunear solo las ligas en frontera.
- Status: Resuelto (2026-06-12). Flags --ha-grid/--rho-grid en tune_ratings.py; 9 ligas re-tuneadas. NCAAF 180, Bundesliga dc_rho −0.25, UCL +0.30 (óptimos interiores nuevos); NCAAB 150, EPL −0.20, La Liga +0.05 confirmados; MLB/NHL/Serie A 0 confirmado con tramo negativo disponible (la localía Elo no aporta bajo este modelo). Residuo: Chile dc_rho +0.35 en frontera con parada deliberada (curva plana, muestra de ~30 empates atípicamente baja vs histórico de la liga) — re-validar UCL/Chile con temporada nueva; rho positivo en soccer es sospechoso de artefacto muestral.

- ID: KI-008
- Severity: Alta (riesgo de capital)
- Description: `max_daily_exposure_pct` (def. 10%) estaba definido y cargado en config pero NUNCA se aplicaba en el pipeline; solo el cap por apuesta (`max_stake_pct` 2%) acotaba un stake individual. Un día con muchas señales podía comprometer mucho más que el límite de exposición de la política.
- Affected files: src/sqp/pipeline/daily.py, src/sqp/config.py, configs/default.yaml.
- Proposed fix: Tras construir candidatos, sumar stakes positivos del día y, si superan bankroll*cap_pct, escalar proporcionalmente con flag de auditoría.
- Status: Resuelto (2026-06-15, H1, commit 609eb95). Nuevo `_apply_daily_exposure_cap`: escalado proporcional de stake y kelly%, marca `daily_exposure_scaled`, excluye filas stake 0; `_finalize` cuenta no-accionables por `stake<=0`. Tests en tests/test_daily_exposure.py (4). Nota de política: el escalado es proporcional entre todos los stakes positivos; priorizar por edge sería un cambio aparte. `max_daily_exposure_pct` solo configurable por YAML.

- ID: KI-009
- Severity: Alta
- Description: `_attach_probable_pitchers` emparejaba la clave `(home, away)` con nombres CRUDOS; los eventos vienen de The Odds API y los probable pitchers de la MLB Stats API, que escriben los equipos distinto (puntuación, mayúsculas, acentos). Para cualquier equipo con grafía divergente entre vendors el pitcher no se adjuntaba EN SILENCIO → evento marcado "starter unknown" → sin candidatos MLB. Contribuyente directo de KI-006 (factor pitcher sin efecto). Riesgo vivo con la reubicación de los Athletics.
- Affected files: src/sqp/pipeline/daily.py (_attach_probable_pitchers), src/sqp/sports/team_names.py.
- Proposed fix: Aplicar el normalizador del adaptador a ambos lados de la clave (igual que ya hacía _merge_results).
- Status: Resuelto (2026-06-15, H2, commit d0102f1). `_attach_probable_pitchers` recibe `normalize` y normaliza ambos lados; run_league pasa `adapter.normalize`. Test de nombres divergentes en tests/test_probable_pitchers_series.py. NO cierra KI-006: la otra rama (población de StarterRatings / procedencia de game_id) sigue abierta como H4.

- ID: KI-010
- Severity: Media
- Description: El tenis no se podia auditar: The Odds API no entrega scores de tenis, y ademas el tenis no estaba cableado en la generacion (TennisAdapter existia pero _league_meta/_supported_leagues lo excluian). Sin generacion ni resultados, no habia nada que liquidar.
- Affected files: src/sqp/providers/espn_tennis.py (nuevo), src/sqp/pipeline/daily.py, src/sqp/settlement/runner.py, scripts/run_all.py.
- Proposed fix: vertical completa con resultados ESPN (atp/wta) y liquidacion por nombre+fecha.
- Status: Resuelto (2026-06-16). Generacion por clave de torneo (Elo de jugador tour-wide desde ESPN, singles + moneyline), proveedor ESPN tenis (parser torneo->groupings->partidos), liquidacion por nombre normalizado + fecha reutilizando settle_candidates, descubrimiento de torneos activos via /sports. Verificado en vivo (ATP Halle 12 eventos/8 candidatos). 4 tests nuevos. CAVEAT: cierra AUDITABILIDAD, no habilita operar (sin cierre real/OOS); ESPN es endpoint no oficial.

- ID: KI-011
- Severity: Media (integridad de datos / auditabilidad)
- Description: `_persist_settled` apendaba filas a `settled_<liga>.csv` con `mode="a"` y `header=not out.exists()`, sin reconciliar columnas. Cuando el esquema de `BetCandidate` crece (se añadió `calibrated_probability` entre `model_probability` y `flags`), los `settled_*.csv` previos quedan con un header viejo (19 cols, sin esa columna) y las filas nuevas se escriben en el orden nuevo bajo el header viejo → cada valor se desalinea al releer. El CSV alimenta build_pick_history → entrenamiento de calibradores, así que la corrupción se propaga en silencio a la auditoría de ROI y a la calibración.
- Affected files: src/sqp/settlement/runner.py (_persist_settled).
- Proposed fix: tomar la unión de columnas (orden del archivo previo + campos nuevos) y reescribir el archivo alineado en vez de apendar a ciegas.
- Status: Resuelto (2026-06-21, auditoría full-audit, commit `7e233f7`). CONFIRMADO contra los headers reales de los 7 settled_*.csv existentes (todos sin `calibrated_probability`). Fix reescribe con unión de columnas y auto-sana archivos de esquema viejo. Regresión en tests/test_settle_persist.py (drift de esquema + idempotencia del dedup). pytest 167 passed.

- ID: KI-012
- Severity: Alta (calidad cuantitativa)
- Description: Los edges estimados son irreales por sobreconfianza del modelo. Sobre 93 apuestas liquidadas: edge medio +8.5% (post shrink 0.5), máx +26%, con ROI realizado fuertemente negativo en h2h (−37%) y spreads (−19%); calibración del modelo crudo ECE 0.198 (predice ~20pts por encima de la frecuencia observada). El mercado no-vig calibra mucho mejor (ECE 0.076). En la muestra sesgada, el shrink óptimo tiende a 1 (el modelo no aporta sobre el mercado).
- Affected files: src/sqp/sports/adapters.py (Elo+scoring), src/sqp/markets/edge.py, configs/default.yaml (risk), configs/leagues/ratings.yaml.
- Proposed fix: (1) penalización de EV por desacuerdo modelo-mercado portada del proyecto 2 — IMPLEMENTADA y activada; (2) calibración por (liga,mercado) temporal con muestra suficiente; (3) señales específicas por deporte para generar edge real; (4) evaluar techo max_plausible_edge 0.075.
- Status: MITIGADO, no cerrado (2026-06-21). Penalización de EV activada (sqp.markets.edge): walk-forward sobre odds capturadas (1654 apuestas) ROI agregado −0.74%→+0.37% y exposición ~a la mitad. Pero el sistema sigue ≈ break-even, in-sample en parámetros, sobre proxy de cierre de un snapshot y sin IC. No hay ventaja demostrada; requiere más muestra OOS. Ver KI-001/KI-003 (validación de rentabilidad) y la falta de odds históricas. Actualización 2026-06-23 (proposed fix #2, calibración por liga/mercado): `train_calibration.py --rebuild` ejecutado. SOLO `mlb_spreads` persistió un calibrador (raw ECE 0.0839 → iso 0.0810 / beta 0.0711); `mlb_h2h` (0.1019→0.1182, n_val 38) y `mlb_totals` (0.0484→0.1130, n_val 35) los DESCARTÓ el gate auto-sanador por empeorar el ECE OOS (quedan no-op). Con calibración ya enabled, spreads MLB se calibra live. La sobreconfianza per-game del moneyline (auditoría 2026-06-23: ECE per-game 0.0188 sobre 8.383 juegos, bins favorito 0.5–0.7 sobreconfiados) NO se corrige así: el calibrador entrena sobre graded bets por mercado (h2h ~186, chico/sesgado), no sobre el set per-game. El h2h MLB sigue siendo el mercado de peor ROI (−31% en el settle del día) sin calibración aplicable. Actualización (mismo día): se añadió `method: auto` (selección por liga/mercado vía data/models/calibration_methods.json) → mlb_spreads usa beta (ECE 0.0711), nhl_h2h usa isotonic; ambos calibran a la vez sin el trade-off del método global. Ver project-decisions 2026-06-23.

- ID: KI-013
- Severity: Media (fidelidad de staking)
- Description: El bankroll usado para dimensionar (Kelly + cap de exposición) era estático (`BANKROLL=1000`), ignorando el PnL realizado; el staking no reflejaba la banca real.
- Affected files: src/sqp/config.py, scripts/run_all.py, src/sqp/risk/kelly.py (consumidor).
- Proposed fix: ledger que derive el balance corriente de settled_*.csv + ajustes manuales e inyectarlo en el run live.
- Status: RESUELTO (2026-06-22, commits `baa5f78` + `0af8106`). `BankrollLedger` (src/sqp/risk/bankroll.py) + flag `bankroll_dynamic` + CLI `scripts/bankroll_status.py`. Balance verificado por CLI (937.28 = 1000 − 62.72 sobre 93 apuestas, consistente con la auditoría) y ACTIVADO en configs/default.yaml (`bankroll: {initial:1000, dynamic:true}`). El run live dimensiona sobre la banca corriente; demo/tests usan el inicial. Conciliación final contra el saldo real de la casa de apuestas queda al usuario (ajustes en data/bets/bankroll_adjustments.csv).

- ID: KI-014
- Severity: Baja (cobertura OOS de tenis) — NO es defecto
- Description: En el OOS de tenis, WTA Bad Homburg mostraba 0 eventos emparejados. INVESTIGADO (2026-06-22): NO es mismatch de nombres. Los 6 partidos están fechados 2026-06-21/22 y los resultados ESPN cargados terminan en 2026-06-21 (los de hoy aún no completados/publicados; un refresh trajo 0 filas nuevas). Las 4 jugadoras verificadas normalizan bien y existen en resultados (Eala 73, Mertens 46, Tauson 44, Shnaider 51 filas); las parejas presentes son enfrentamientos PREVIOS en otros torneos (Eala/Mertens 04-24, Li/Alexandrova 2025), correctamente descartados por la ventana de ±1 día (evita falsos positivos cross-torneo).
- Affected files: ninguno (comportamiento esperado). Diagnóstico sobre data/odds + data/historical/results_wta.csv.
- Proposed fix: no requiere cambio de código. Re-correr scripts/backfill_tennis_results.py tras completarse el torneo y los partidos emparejarán. Mismo caso de calendario que NFL/Wimbledon (odds de partidos aún no jugados).
- Status: CERRADO / no-bug (2026-06-22). El matching de tenis funciona correctamente.

- ID: KI-015
- Severity: Media (higiene de repo / entorno)
- Description: Las skills de terceros vendadas `.claude/skills/markitdown-main` (163 archivos) y `.claude/skills/superpowers-main` (172) — 335 trackeados, ~70% de `.claude` — desaparecen físicamente del disco de forma intermitente (el repo vive bajo OneDrive, que probablemente las deshidrata/online-only). `git status` las muestra como borradas; un `git restore` no persiste (vuelven a desaparecer). No son código del producto SQP (incluyen Dockerfiles, JS, shell, binarios de test).
- Affected files: `.claude/skills/markitdown-main/**`, `.claude/skills/superpowers-main/**`.
- Proposed fix: sacarlas del repo del producto → mover a `~/.claude/skills/` (nivel usuario, fuera de OneDrive) o a un submódulo/git-ignore; documentar la decisión. NO borrar sin confirmación del usuario (las restauró explícitamente el 2026-06-23). Mientras tanto: nunca incluirlas en commits (usar `git add` por ruta específica).
- Status: ABIERTO (2026-06-23, auditoría). Diferido A2: requiere decisión del usuario. Tag: onedrive-vendored-skills.

- ID: KI-016
- Severity: Baja (operacional)
- Description: Entrypoints diarios paralelos: `scripts/run_daily.py` (manual, --sports explícito, sin guard/calibración/banca/reporte) vs `scripts/run_all.py` (producción, vía RUN_DIARIO_ALL.bat). Dockerfile/Makefile usan run_daily para demo. README presentaba run_daily como EL entrypoint (corregido 2026-06-23).
- Affected files: scripts/run_daily.py, scripts/run_all.py, Dockerfile, Makefile.
- Proposed fix: docstrings + README ya aclaran (commit fa86c0c). Pendiente opcional: decidir si run_daily se deprecia o se mantiene como herramienta manual/demo.
- Status: MITIGADO (2026-06-23, docs). Decisión de consolidación pendiente (M1).
