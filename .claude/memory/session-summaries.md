# Session Summaries

## 2026-06-12 — Run diario live + guard de deporte inactivo

**Trabajo realizado:**
- Run live `--sports nba wnba ligamx`: NBA 1 evento, WNBA 6 eventos, 0 candidatos sobre min edge en todos; ligamx devolvió 0 eventos.
- Diagnóstico ligamx: el sport_key `soccer_mexico_ligamx` es correcto pero The Odds API lo reporta `active: false` (fuera de temporada: Clausura terminó en mayo y el Mundial 2026 pausa el fútbol doméstico hasta ~19-jul). No es bug. Casi todas las ligas europeas también están inactivas estas semanas.
- Implementado guard de deporte inactivo: `OddsAPIClient.is_sport_active()` (cacheado, usa /sports que no consume cuota) + skip con log claro en `run_league` (WARNING si inactivo, ERROR si el key no existe en la API). Refactor: cierre del pipeline extraído a `_finalize()`.

**Archivos:** `src/sqp/providers/odds_api.py`, `src/sqp/pipeline/daily.py`, `tests/test_inactive_sport.py` (nuevo, 3 tests).

**Validación:** `pytest tests/ -q` → 18 passed; run real de ligamx live muestra el nuevo log y CSV vacío sin llamadas extra.

**Pendiente:** backfill de resultados de temporada completa para ratings (NBA con 1 resultado, WNBA con 9 — estimaciones no confiables con ventana de 3 días del API).

## 2026-06-12 (cont.) — Backfill de resultados históricos + RUN_DIARIO.bat

**Trabajo realizado:**
- Implementado KI-001 (cerrado): subsistema de backfill de resultados históricos.
  - `src/sqp/providers/espn_results.py`: ESPN scoreboard API (público, sin key), 17 ligas mapeadas, chunks de 30 días, solo partidos completados.
  - `src/sqp/storage/results_store.py`: CSV append-only por liga en `data/historical/`, dedup por (date, home, away), filas existentes nunca se mutan, `ingested_at` por fila.
  - `scripts/backfill_results.py`: CLI re-ejecutable e incremental; MLB usa MLB Stats API, resto ESPN.
  - `run_league` (live): fusiona histórico + scores de 3 días del API (histórico gana), WARNING si <50 resultados (`MIN_RESULTS_FOR_RATINGS`).
- Semilla inicial: NBA 1,395 / WNBA 207 / Liga MX 300 resultados (300 días).
- Creado `RUN_DIARIO.bat` en la raíz del repo (no existía): backfill incremental 10 días (no bloqueante) + pipeline live; ligas en `set LEAGUES=nba wnba ligamx`.
- Hallazgo: el RUN_DIARIO.bat de `Proyectos\38\bat_scripts\` es de OTRA plataforma (`.venv`, `bat_scripts\`, `picks_report.py`); no se tocó. Aclarar si 38 es versión vieja.

**Archivos:** `src/sqp/providers/espn_results.py` (nuevo), `src/sqp/storage/` (nuevo), `scripts/backfill_results.py` (nuevo), `src/sqp/pipeline/daily.py`, `tests/test_results_backfill.py` (nuevo, 5 tests), `RUN_DIARIO.bat` (nuevo).

**Validación:** `pytest tests/ -q` → 23 passed; backfill real ejecutado; RUN_DIARIO.bat corrido de punta a punta (dedup verificado: 0 filas nuevas al re-correr; ligamx 0 resultados por fuera de temporada, no aborta); nombres ESPN vs Odds API coinciden en NBA/WNBA (0 warnings de confiabilidad).

**Pendiente:** backtest walk-forward + calibración sobre el nuevo histórico antes de confiar en candidatos (NBA 3, WNBA 15 generados hoy); posible normalización de acentos en nombres de equipos de fútbol.

## 2026-06-12 (cont. 2) — Backtest walk-forward, fix 3-way y tuning de ventaja local

**Trabajo realizado:**
- `scripts/backtest_history.py` (nuevo): walk-forward sobre `data/historical/` por liga, con baseline de tasa local in-sample y calibración del empate.
- Primer run reveló bug metodológico del engine en ligas 3-way: evaluaba P(local) incondicional contra outcomes sin empates → ECE inflado (Liga MX 0.162). Corregido en `engine.py`: scoring con P(local | no empate) + reporte separado de calibración del empate.
- `sqp/backtesting/tuning.py` + `scripts/tune_ratings.py` (nuevos): grid search walk-forward de `elo_home_adv` por liga, scored por log loss; `--write` persiste en `configs/leagues/ratings.yaml`.
- `_league_meta` ahora fusiona `configs/leagues/ratings.yaml` (overrides por liga para cualquier deporte, sin mutar SPORT_KEYS) → aplican al run diario automáticamente.
- Valores tuneados: NBA 75 (default 70), WNBA 30, Liga MX 45.

**Métricas finales (Brier / ECE / vs baseline):** NBA 0.2100 / 0.032 / gana (0.2468); WNBA 0.2292 / 0.076 / gana (0.2491); Liga MX 0.2093 / 0.057 / gana (0.2281, antes perdía).

**Hallazgo:** empate Liga MX subestimado (est. 0.237 vs obs. 0.254) — limitación conocida del Poisson independiente; siguiente upgrade: Dixon-Coles (KI-004).

**Archivos:** `src/sqp/backtesting/engine.py`, `src/sqp/backtesting/tuning.py` (nuevo), `scripts/backtest_history.py` (nuevo), `scripts/tune_ratings.py` (nuevo), `src/sqp/pipeline/daily.py`, `configs/leagues/ratings.yaml` (nuevo), `tests/test_backtest_tuning.py` (nuevo, 4 tests).

**Validación:** pytest → 27 passed; tuning y backtest corridos sobre histórico real.

**Caveats:** tuning in-sample (re-validar con partidos nuevos); calibración ≠ ROI realizado (faltan odds históricas reales).

## 2026-06-12 (cont. 3) — Ajuste Dixon-Coles (KI-004 cerrado)

**Trabajo realizado:**
- `_dixon_coles_tau()` en `distributions.py`: corrección DC-1997 para marcadores ≤1 aplicada a la grilla conjunta de `poisson_match_probs` vía parámetro `dc_rho` (clamp a 0, renormalización posterior; `dc_rho=0` es no-op).
- `dc_rho` fluye por params (adapter → registry, default soccer 0.0) y se tunea por liga: `tune_dc_rho()` con grid (−0.20…+0.05) scored por el nuevo `log_loss_threeway` (multiclase 1X2) agregado al engine — la métrica binaria condicional es ciega a la masa del empate.
- `scripts/tune_ratings.py` tunea `dc_rho` automáticamente en ligas 3-way (con la ventaja local tuneada como base) y lo persiste en `ratings.yaml` (merge conserva otras ligas; verificado).
- Liga MX tuneada: `dc_rho = −0.10`. Empate estimado 0.2366 → 0.2589 vs observado 0.2542 (gap −1.8pts → +0.5pts). Log loss 3-way 1.0206 → 1.0194. Brier binario intacto (0.2091), como debe ser.

**Archivos:** `src/sqp/models/distributions.py`, `src/sqp/sports/adapters.py`, `src/sqp/sports/registry.py`, `src/sqp/backtesting/engine.py`, `src/sqp/backtesting/tuning.py`, `scripts/tune_ratings.py`, `scripts/backtest_history.py`, `configs/leagues/ratings.yaml`, `tests/test_backtest_tuning.py` (3 tests nuevos).

**Validación:** pytest → 30 passed; tuning y backtest reales sobre histórico Liga MX.

**Caveats:** rho in-sample (240 partidos); re-validar al reactivarse Liga MX (Apertura, ~post 19-jul-2026). El run diario ya consume dc_rho automáticamente vía ratings.yaml.

## 2026-06-12 (cont. 4) — Descarga de históricos reales para todas las ligas

**Trabajo realizado:**
- Backfill 365 días para las 19 ligas con vendor disponible. Totales: MLB 2,464 / NBA 1,400 / NHL 1,500 / NCAAF 958 / NCAAB 6,300 / WNBA 362 / NFL 335 / EPL 380 / La Liga 380 / Serie A 380 / Bundesliga 306 / Ligue 1 305 / MLS 506 / Brasileirão 447 / Liga MX 337 / Chile 251 / UCL 189 / UWCL 75. WNCAAB quedó corriendo en background al cierre de esta entrada.
- Fix de proveedor: ESPN devuelve 404 (no lista vacía) en rangos sin partidos → ahora chunk vacío (test agregado).
- Fix NCAA: el scoreboard universitario rechaza rangos de fechas (404) y por defecto devuelve solo top-25 → `ESPN_PATHS` pasó de strings a configs por liga con `day_by_day: true` + `params: {groups: 50}` para ncaab/wncaab (División I completa; verificado: 155 vs 18 partidos en día de muestra).
- Slugs nuevos verificados empíricamente contra el catálogo de ESPN (244 ligas soccer): `chile` → `soccer/chi.1`, `uwcl` → `soccer/uefa.wchampions`.
- Hallazgo: la Frauen-Bundesliga NO existe en el catálogo ESPN (sí eng.w.1, esp.w.1, fra.w.1, ned.w.1) → KI-005, necesita otro vendor.

**Archivos:** `src/sqp/providers/espn_results.py` (404 tolerante, day_by_day, groups, 2 ligas nuevas), `tests/test_results_backfill.py` (+1 test), `data/historical/results_*.csv` (19 ligas).

**Validación:** pytest → 31 passed; conteos por liga consistentes con calendarios reales (EPL/La Liga/Serie A = 380 exacto, Bundesliga 306, NBA 1,400 con playoffs).

**Pendiente:** confirmar cierre de WNCAAB (background); tune_ratings para las ligas recién pobladas cuando se vayan a operar.

## 2026-06-12 (cont. 5) — Tuning masivo en curso (estado al guardar)

**Trabajo realizado:**
- WNCAAB backfill confirmado: 6,030 resultados (D-I completa). Histórico de 365 días completo para las 19 ligas con vendor.
- Lanzado en background `tune_ratings --write` para 14 ligas nuevas: mlb nfl nhl ncaaf ncaab epl laliga bundesliga seriea ligue1 ucl mls brasileirao chile (las soccer incluyen dc_rho automático).
- UWCL deliberadamente SIN tunear: 75 resultados − warmup 60 = 15 partidos evaluables, insuficiente para persistir parámetros; usa defaults de familia hasta acumular histórico.
- Regla operativa aplicada: no correr dos `tune_ratings --write` concurrentes (read-modify-write sobre ratings.yaml puede pisar entradas); WNCAAB se tuneará secuencialmente al terminar el batch.

**Estado al guardar:** batch de tuning corriendo (MLB, la liga más pesada, va primero; stdout con buffer — sin output parcial visible).

**Pendiente (cadena acordada):** (1) cierre del batch de 14 ligas → (2) tune_ratings wncaab --write → (3) backtest_history de todas las ligas tuneadas con overrides aplicados → reportar tabla completa de métricas.

## 2026-06-12 (cont. 6) — Tuning/backtest de 18 ligas, audit MLB y fix de doubleheaders

**Tuning completado (18 ligas en ratings.yaml):** NBA 75, WNBA 30, WNCAAB 105 (óptimo interior limpio, n=5,970), NFL 45, NCAAF 150*, NCAAB 150*, MLB 0*, NHL 0*, EPL 15/dc −0.20*, La Liga 45/dc +0.05*, Bundesliga 30/dc −0.20*, Serie A 0*/dc −0.10, Ligue 1 30/dc −0.10, UCL 15/dc +0.05*, MLS 30/dc 0, Brasileirão 75/dc 0, Chile 30/dc +0.05*, Liga MX 45/dc −0.10. (* = valor en borde de grilla, no confiable → KI-007.)

**Backtest walk-forward (18 ligas):** 16 baten el baseline de tasa local. Mejores: WNCAAB Brier 0.1880 (baseline 0.2348), Bundesliga 0.1948, NCAAB 0.1977. Problemas: MLB PIERDE vs baseline (0.2500 vs 0.2491, sobreconfianza en colas — confirmado también con datos limpios) → KI-006; NHL empate técnico (0.2482 vs 0.2496) → KI-006; NCAAF ECE 0.107.

**Audit falsos empates MLB (cerrado):** causa raíz verificada — statsapi marca pospuestos con abstractGameState=Final, detailedState=Postponed y SIN campo score; el provider los rellenaba con `.get("score", 0)` → 24 juegos 0-0 fabricados. Fix en mlb_statsapi.py (filtro detailedState + score obligatorio, sin defaults) + test con payload real. CSV regenerado: 2,418 filas, 0 empates (cuadre exacto).

**Fix dedup doubleheaders (cerrado):** la clave (date, home, away) colapsaba 21 juegos reales de MLB (los makeups de los pospuestos). Esquema v2 del store: game_id por fila (gamePk statsapi / id ESPN / id Odds API), KEY=(date,home,away,game_id), migración legacy automática; _merge_results deduplica por game_id dentro de cada fuente pero por (día,home,away) entre fuentes (ids no comparables; histórico gana — evita doble conteo en el solape de 3 días). Verificado: MLB regenerado con 2,439 filas (2,418+21 exacto).

**Validación:** pytest → 35 passed (3 tests nuevos de doubleheaders/migración + 1 de pospuestos).

**Estado al guardar:** regeneración de los 19 stores con esquema v2 corriendo en background (8/19 al guardar; luego re-tune + backtest MLB).

**Archivos:** src/sqp/providers/mlb_statsapi.py, src/sqp/providers/espn_results.py, src/sqp/storage/results_store.py, src/sqp/pipeline/daily.py, configs/leagues/ratings.yaml (18 ligas), tests/test_results_backfill.py, data/historical/ (regenerándose).

## 2026-06-12 (cont. 7) — Grillas ampliadas y re-tune de las 9 ligas en frontera (KI-007 cerrado)

**Trabajo realizado:**
- Regeneración v2 completada: 19/19 stores con game_id, conteos exactos (MLB 2,439 = 2,418+21 doubleheaders). Backtest final MLB sobre datos perfectos: Brier 0.2501 vs baseline 0.2491 — KI-006 confirmado sobre datos limpios (la falla es del modelo, no de los datos).
- `scripts/tune_ratings.py`: nuevos flags `--ha-grid` y `--rho-grid` para grillas custom.
- Re-tune de las 9 ligas en frontera. Resultados: NCAAF 150→180 (interior, convexo); NCAAB 150 confirmado; MLB/NHL/Serie A 0 confirmado CON tramo negativo disponible (−90…−15 pierden → 0 es óptimo verdadero, la localía Elo no aporta bajo este modelo); EPL −0.20 confirmado interior; Bundesliga −0.20→−0.25; La Liga +0.05 confirmado; UCL +0.05→+0.30 (gap del empate cerrado); Chile +0.05→+0.35.
- Chile quedó técnicamente en frontera (+0.35) con parada deliberada: curva plana (0.9739→0.9729), gap cerrado (est 0.165 vs obs 0.157), y la tasa de empates de la muestra (0.157, ~30 empates) es atípicamente baja vs lo histórico de la liga (~0.25+) — extender más sería ajustar ruido. Rho positivos de UCL/Chile marcados como sospechosos de artefacto muestral: re-validar con temporada nueva.

**Validación:** pytest → 35 passed; todos los grupos persistidos en ratings.yaml (escrituras secuenciales, sin conflicto).

**Archivos:** scripts/tune_ratings.py, configs/leagues/ratings.yaml (9 ligas actualizadas/confirmadas).

**Pendientes priorizados:** KI-006 (features abridor MLB / portero NHL — cuello de botella real), KI-002 (nombres soccer al reactivarse Liga MX ~post 19-jul), re-validación out-of-sample de todos los parámetros con partidos nuevos, KI-005 (vendor Frauen-Bundesliga).

## 2026-06-12 (cont. 8) — Feature de abridor MLB (v1 rechazado por datos, tilt_scale fue el fix real) + plan de odds históricas

**Feature de abridor implementado y evaluado:**
- Infraestructura completa: `models/starters.py` (StarterRatings: RA por apertura, regresión a media, bound ±35%), `Event.home_pitcher/away_pitcher`, hook `observe()` en SportAdapter (idéntico en backtest y producción), `storage/starters.py` (mapa gamePk→abridor, newest-wins), `scripts/backfill_starters.py` (cobertura 99.8%: 2,475/2,479), attach en daily/backtest/tuning, probables live por nombres, flag "Starter unknown" → cero candidatos (regla del skill).
- VEREDICTO v1: rechazado por evidencia — grid 4 priors × 4 bounds: bound=0 gana en todo, monotónico. La señal RA mezcla bullpen/ofensa rival. Persistido `pitcher_bound: 0.0` (apagado). Upgrade claro: FIP por apertura desde boxscores (~2,400 requests one-off); la tubería ya lo recibe.
- HALLAZGO REAL: la sobreconfianza de MLB venía de `tilt_scale` 0.8 → tuneado a 0.4 (óptimo interior verificado 0.1–0.5): Brier 0.2501→0.2474 (BATE el baseline 0.2491 por primera vez), ECE 0.039→0.019. `scripts/tune_mlb_pitcher.py` (nuevo, dos etapas).
- Validación: pytest → 39 passed (4 tests nuevos).

**Plan de odds históricas (hechos verificados con requests reales):**
- The Odds API histórico: 401 en plan gratuito (HISTORICAL_UNAVAILABLE_ON_FREE_USAGE_PLAN). Cuota: 440/500 restante del mes.
- football-data.co.uk: GRATIS y verificado — E0.csv (EPL) y MEX.csv (Liga MX multi-temporada con cierre de Pinnacle PSCH/PSCD/PSCA + Max/Avg de mercado). Sin UCL ni Chile.
- Bloques: A) captura propia diaria de odds (forward, out-of-sample por construcción, costo 0 — OJO cuota: us,eu ≈ 540 créditos/mes > 500 → bajar a 1 región); B) histórico soccer multi-temporada de football-data (ROI realizado vs cierre Pinnacle, alias de nombres como riesgo principal); C) US majors histórico = decisión de pago, posponer hasta que B muestre edge.
- Reglas anti-sesgo del backtest ROI: solo cierre/pre-commence, book real (no best-line retrospectivo), flat y Kelly por separado, IC bootstrap, separar siempre estimada/implícita/no-vig/edge/ROI esperado/ROI realizado.

**Estado del proyecto (evaluación honesta entregada):** datos e infraestructura sólidos; calibración decente en 17/18 ligas (MLB ya bate baseline, NHL sigue en empate técnico); CERO validación de rentabilidad (sin odds históricas no hay ROI realizado); todo in-sample; A1 en curso.

## 2026-06-15 — Auditoría integral (skill full-audit): H1/H2/H3/H5 corregidos, rama lista para PR

**Auditoría (Fases 1-3):** revisión de markets/risk/calibration/simulation/distributions/adapters/providers/pipeline/settlement/config, scripts, BAT y tests sin escanear data/. Núcleo cuantitativo verificado correcto (odds, de-vig power/proporcional, Kelly con caps, continuity-correction, idempotencia de liquidación, timeouts en todos los requests). 5 hallazgos; 2 importantes, 3 menores.

**Correcciones implementadas (rama `fix/mlb-series-probable-pitchers`, 4 commits, sobre el fix previo de starters por juego):**
- **H2 `d0102f1`** — `_attach_probable_pitchers` emparejaba la clave `(home, away)` con nombres CRUDOS; eventos vienen de The Odds API y pitchers de MLB Stats API (grafías distintas) → fallo silencioso → evento "starter unknown" → sin candidatos MLB. Fix: pasa `adapter.normalize` y normaliza ambos lados (como ya hacía `_merge_results`). Contribuyente del bug del factor pitcher (KI-006 / [[mlb-pitcher-factor-no-effect]]).
- **H1 `609eb95`** — `max_daily_exposure_pct` (10%) estaba en config pero NUNCA se aplicaba; solo el cap por apuesta (2%) acotaba un stake. Nuevo `_apply_daily_exposure_cap`: escala proporcionalmente stakes positivos del día para respetar `bankroll*cap_pct`, marca recortados `daily_exposure_scaled`, excluye filas stake 0. `_finalize` cuenta no-accionables por `stake<=0`.
- **H3 `d03a84e`** — eliminado `SETTLE_WNBA.bat` redundante (cubierto por SETTLE_ALL.bat).
- **H5 `a16172e`** — documentada en los BAT la dependencia de orden settle→run (el run diario sobrescribe candidates_*.csv).

**Validación:** pytest → 111 passed (106 previos + 5 nuevos: tests/test_daily_exposure.py ×4, +1 caso de nombres divergentes en test_probable_pitchers_series.py). Ruff limpio. Split de commits: reset de daily.py a HEAD y reaplicación por etapas; verificado `diff` idéntico al estado validado.

**Descubrimiento de repo (importante):** al pushear, GitHub respondió "This repository moved": el repo `-elo` fue RENOMBRADO a `sports-quant-platform`. Verificado con `git ls-remote` que es NUESTRO repo (remote main = f6b5919 commit nuestro; rama remota = HEAD local a16172e) — contradecía la memoria que asumía dos repos separados. `origin` repuntado a la URL canónica nueva. Memoria [[git-remote-elo]] actualizada.

**Estado al guardar:** rama pushada con upstream, lista para PR (gh no instalado → PR manual en github.com/.../pull/new/fix/mlb-series-probable-pitchers; título y cuerpo entregados).

**Pendiente:** H4 (factor pitcher sin efecto) sigue abierto — requiere traza con datos reales sobre la población de StarterRatings (procedencia de game_id entre ResultsStore y StartersStore); H2 elimina un contribuyente pero no cierra el bug.

## 2026-06-21 — Auditoría integral (skill full-audit) sobre el codebase re-importado: 5 hallazgos corregidos y mergeados a master

**Contexto:** repo re-importado (commits `efabc00` "Import remaining codebase", `70c21f9`). Auditoría de solo lectura (Fases 1-3) sin escanear data/: arquitectura, 7 BAT, scripts, config, tests, deps, integraciones. Baseline pytest 165 passed. Núcleo cuantitativo re-verificado correcto (odds, de-vig power/proporcional con fallback, Kelly con caps, Poisson/Normal con continuity-correction y renormalización de grilla truncada, Dixon-Coles, grading de liquidación, timeouts 30s en todos los requests, `.env` NO trackeado — solo `.env.example`). **Sin bugs críticos.**

**Hallazgos (5) — todos corregidos en rama `audit/settlement-schema-and-ops-fixes`, commit `7e233f7`, mergeada `--no-ff` a master `085c1ef`, rama borrada:**
- **I-1 (importante, CONFIRMADO) `settlement/runner.py`** — `_persist_settled` apendaba con `mode="a"` sin reconciliar columnas. Verificado contra headers reales: los 7 `settled_*.csv` existentes tienen 19 columnas terminando en `...model_probability,flags,generated_at,...` SIN `calibrated_probability`, que el `BetCandidate` actual inserta entre `model_probability` y `flags`. El próximo append habría desalineado cada valor al releer (corrompiendo la auditoría de ROI y los inputs de calibración vía build_pick_history). Fix: unión de columnas (orden previo + campos nuevos) y reescritura alineada; auto-sana archivos de esquema viejo. Nuevo `tests/test_settle_persist.py` (drift + idempotencia dedup). → KI-011 (Resuelto).
- **I-2 (operacional) `REFRESH_ML.bat`** — corría 4 scripts sin `if errorlevel 1` y salía 0 ante fallo (enmascaraba fallos del job semanal). Fix: check por paso + etiqueta `:error`.
- **M-1 `backtesting/roi_engine.py`** — docstring decía "exact staking logic" pero el backtest NO aplica calibración (a diferencia del run live con CALIBRATION_ENABLED). Aclarado que se excluye por circularidad (el historial alimenta a los calibradores). Sin cambio de lógica.
- **M-3 `scripts/run_all.py`** — un fallo transitorio de una liga dejaba `candidates_<liga>.csv` del día anterior, que el reporte mostraba como del día. Fix: en el `except`, `_finalize(lg, [], [], mode)` archiva y limpia (recuperable en archive/).
- **M-2 `models/distributions.py`** — eliminado `skellam_home_win` (código muerto, 0 referencias) + imports huérfanos `skellam`/`math` + línea de docstring.

**Validación:** pytest 165 → 167 passed (2 nuevos). Imports de distributions/run_all/_finalize verificados. Merge a master limpio, 167 passed post-merge.

**Estado al guardar:** master contiene las correcciones; rama de trabajo borrada (estaba mergeada). Sin remoto configurado (no hay push/PR). KI-006/H4 (factor pitcher) y la falta de validación de rentabilidad (sin odds históricas reales → sin ROI realizado) siguen siendo los pendientes de fondo, no tocados esta sesión.

## 2026-06-21 (cont.) — CI + penalización de EV (validada OOS, ACTIVADA) + ledger de bankroll (OFF)

Continuación de la misma sesión tras la auditoría. Tres entregas, cada una en su rama, mergeadas `--no-ff` a master y rama borrada (sin remoto).

**1) CI (commit `077daae`):** `.github/workflows/ci.yml` (push/PR, Python 3.11+3.12, pip cache, `ruff check` + `pytest -q`). `pyproject [tool.ruff]`: default+pyflakes, ignora E701/E702 (estilo compacto deliberado del proyecto). Corregidos los 2 únicos hallazgos reales de ruff (import `field` sin uso en features/builders.py; multi-import en logging_config.py). El config de ruff se había perdido en la re-importación.

**2) Penalización de EV portada del proyecto 2 (`_archive/2`), ACTIVADA (commits `60c633a`+`4f07a58`):**
- Diagnóstico previo: edges irreales por sobreconfianza. Calibración sobre 93 apuestas liquidadas: modelo crudo ECE 0.198 (media pred 0.607 vs obs 0.409); shrink 0.5 ECE 0.147; mercado no-vig ECE 0.076. Barrido de shrink → mejora monótona hasta s=1 (el modelo no aporta sobre el mercado en esa muestra sesgada).
- Mecánica del proyecto 2: blend con mercado dominante (ML 60%) + `adjusted_market_edge` que recorta el EV por el gap modelo-mercado (`UNCERTAINTY_PENALTY 0.35`, `+0.02` si gap>0.06, `+0.015` si <2 books) + techo EV 7.5% (flag a 13.5%).
- Porté solo la penalización: nuevo `src/sqp/markets/edge.py::adjusted_edge` (raw/penalty/adjusted/`p_eff`). El penalty se pliega en una **probabilidad efectiva** `p_eff = p - penalty/d` que alimenta edge+Kelly, así achica también el stake. `estimated_edge` sigue siendo el edge RAW (auditoría); nuevos campos `adjusted_edge`/`edge_penalty`/`books_count` en BetCandidate. Cableado en daily.py (+`_consensus_counts`) y roi_engine.py (espejo). 5 coeficientes nuevos en RiskConfig, default 0 = no-op.
- **Validación que decidió activar:** el retrospectivo de 93 apuestas comprimía el edge pero NO mejoraba ROI (muestra sesgada). El **walk-forward sobre odds capturadas (1654 apuestas, dominado por MLB)** sí: ROI agregado −0.74%→+0.37%, MLB −0.23%→+0.41%, WNBA −6.2%→−2.1%, **exposición ~a la mitad**. Por esa evidencia se ACTIVÓ en configs/default.yaml (valores del proyecto 2). Sigue ≈ break-even e in-sample en parámetros → no es claim de rentabilidad. `max_plausible_edge` se dejó en 0.15 (el techo 0.075 necesita su propia prueba).

**3) Ledger de bankroll real (commit `baa5f78`), OFF por defecto:**
- Problema: `Settings.bankroll` estático (1000); Kelly y el cap de exposición dimensionaban sobre capital nominal fijo.
- `src/sqp/risk/bankroll.py::BankrollLedger`: balance = inicial + PnL realizado (filas settled `data_label=="real"`) + ajustes manuales (`data/bets/bankroll_adjustments.csv`). Derivado de `settled_*.csv` (fuente única, sin store paralelo). `equity_curve`, `summary`, `max_drawdown`. CLI `scripts/bankroll_status.py`.
- Flag `bankroll_dynamic` (env/yaml, default OFF). Solo el entrypoint live (`run_all.py`) inyecta el balance corriente; demo y `run_league` directo usan el inicial → tests deterministas, comportamiento byte-idéntico apagado.
- Balance real verificado por el CLI: 1000 − 62.72 (93 apuestas) = **937.28**, ROI −20.81%, drawdown −90.78.

**Validación global:** pytest 167 → **179 passed** (test_edge.py ×6, test_bankroll.py ×6). ruff limpio. Todo en master.

**Recomendación al cerrar (prioridad):** (a) acumular odds capturadas + cargar resultados de tenis/NFL (dieron 0 apuestas) para muestra OOS con IC; (b) validar parámetros OOS (ratings.yaml sigue in-sample); (c) activar `bankroll_dynamic` tras verificar el balance con la liquidación real; (d) recién entonces probar techo 0.075 y señales por deporte. Diagnóstico de fondo: lo que falta no es código sino EVIDENCIA — el sistema está bien construido y honestamente medido, pero ≈ break-even, sin ventaja demostrada.

## 2026-06-22 — bankroll_dynamic ACTIVADO + OOS de tenis habilitado + interactividad del reporte

Continuación de la sesión. Tres entregas, cada una en su rama, mergeadas `--no-ff` a master y rama borrada (sin remoto).

**1) `bankroll_dynamic` ACTIVADO (commit `0af8106`):** verificado el balance del ledger por CLI (937.28 = 1000 − 62.72 sobre 93 apuestas, ROI −20.81%, drawdown −90.78, internamente consistente con la auditoría de liquidación). Activado en `configs/default.yaml` (`bankroll: { initial: 1000, dynamic: true }`). El run live ahora dimensiona Kelly + cap de exposición sobre la banca corriente; demo/tests usan el inicial → 181 passed sin cambios. Conciliación final contra el saldo real de la casa de apuestas queda al usuario (ajustes en `data/bets/bankroll_adjustments.csv`).

**2) OOS de tenis habilitado (commit `ea0bebc`):** el tenis daba 0 apuestas en el OOS por dos bloqueos. Diagnóstico con evidencia: NFL no es problema de datos sino de CALENDARIO (odds capturadas 2026-09/10, fuera de temporada; resultados ya cargados 7964) → nada útil que cargar hasta que se jueguen. Tenis sí era hueco de infraestructura: sin resultados en ResultsStore + el roi_engine emparejaba `(home,away)` ordenado mientras el tenis no tiene orientación. Fix en tres piezas: (a) `scripts/backfill_tennis_results.py` persiste resultados ESPN tour-wide bajo la clave de tour (results_atp.csv / results_wta.csv; home=winner, 1-0, neutral) — cargados **ATP 6205 / WTA 8503**; (b) `roi_engine` empareja order-insensible (frozenset) cuando family=="tennis" (la reorientación de marcadores existente maneja la orientación); deportes de equipo mantienen orden; (c) `validate_oos` carga resultados tour-wide para ligas de tenis y omite el freezing de parámetros (Elo neutral). Verificado: ATP Halle 26 matched/9 bets, Queen's 20/3, German Open 15/4; Wimbledon correctamente 0 (futuro). **ROI = ruido (3-9 apuestas/torneo)**: se entrega la capacidad, no señal. Anotado: WTA Bad Homburg 0 matched pese a 6 odds (posible mismatch de nombres → KI-014). Tests 181 passed (+2). Resultados CSV quedan fuera de git (.gitignore).

**3) Interactividad del reporte HTML (commit `f86157b`):** a pedido del usuario, replicando el estilo del proyecto 2 (`_archive/2/data/output/picks_report_all.html`).
- Picks: dropdown de deporte → **pills toggleables** por deporte (multi-select, todas activas, construidas client-side de `uniq(league)`; etiquetas bonitas incl. tenis "ATP Wimbledon"; color de mapa + paleta fallback).
- Auditoría (Por liga / Por mercado, incl. `hit_rate`) y Patrones (`hit_rate_%` + todas las situaciones): **orden por columna** client-side genérico (`makeSortable`/`initSortable`, numeric-aware, asc/desc).
- Historial: **filtros** por deporte (select etiquetado), mercado y rango de fecha (Desde/Hasta), con contador en vivo; tabla reconstruida con `data-fecha/league/market` por fila; también ordenable. `initSortable`/`initHistory` corren al inicio de `init()` (funcionan sin picks). Reporte sigue autónomo (sin assets externos). Tests 183 passed (+2).

**Validación global:** pytest 179 → **183 passed**. ruff limpio. Todo en master. `report_latest.html` regenerado con datos reales (21 picks, 4 ligas).

**Pendientes anotados:** KI-014 (mismatch WTA Bad Homburg en OOS de tenis); NFL OOS bloqueado por calendario; validación OOS de parámetros; señales por deporte. Sigue ≈ break-even — falta evidencia, no código.

## 2026-06-22 — Validación OOS de parámetros (VALIDATE_OOS): MLB generaliza, no overfit

Corrido `scripts/validate_oos.py` (congela tilt_scale/elo_home_adv/dc_rho solo en TRAIN, mide ROI realizado en el TEST posterior; compara frozen_train vs full_history vs family_default).

**MLB** (cutoff 2025-06-13, train 5896 / test 2547, 1154 odds; frozen tilt=0.4, home_adv=25):
- frozen_train: **ROI test +0.41%** (1148 graded, staked 4767, pnl +19.39). Por mercado: h2h +10.6%, spreads +2.4%, totals −4.9%.
- full_history (ratings.yaml): **IDÉNTICO** a frozen_train (los params OOS-congelados coinciden con ratings.yaml) → el tuning de MLB NO es optimista/overfit.
- family_default (sin tuning): **ROI test −3.28%** (apuesta MÁS: 1463 graded, staked 7077, pnl −231.95; más sobreconfianza → más/mayores edges → pierde).
- **Lectura: el tuning de MLB GENERALIZA OOS** (frozen +0.41% vs sin-tuning −3.28%, ~+3.7pp). Pero MLB sigue ≈ break-even, cargado por h2h; totals negativo (coherente con mlb/totals pausado).

**WNBA** (cutoff 2025-07-27, train 659 / test 288, 141 odds; frozen home_adv=70):
- frozen_train == full_history == family_default: **ROI test −2.13%** (170 bets, pnl −15.86). Por mercado: h2h −2.3%, spreads −11.3%, totals +8.2%.
- El home_adv congelado (70) coincide con el default de la familia basketball → no hay nada que distinga las 3 configs (nada que validar). Muestra chica (n=170) = ruido.

**Tenis** (Halle/Queen's/German Open; Bad Homburg/Wimbledon 0 por calendario): el tenis NO tiene parámetros que congelar (Elo neutral), así que es solo ROI realizado OOS, no validación de parámetros. Ruido (3-9 apuestas/torneo): Halle +41.9% (n=9), Queen's +104% (n=3), German Open −100% (n=4). Las ligas de 1 evento (nba/nhl) se omitieron (ruido + tuning lento e inútil).

**Conclusión:** los parámetros de MLB generalizan fuera de muestra (no overfit) y baten al baseline sin-tuning por ~3.7pp; WNBA no aporta señal (params = default, muestra chica). Sigue ≈ break-even sobre proxy de cierre de un snapshot, cobertura limitada, sin IC — no es rentabilidad demostrada. Cierra el item "(a) tuning in-sample" de KI-003.

## 2026-06-22 — max_plausible_edge 0.15 → 0.075 (techo del proyecto 2), probado OOS y activado

Probado OOS (realized ROI 0.15 vs 0.075 sobre odds capturadas, con la penalización de EV ya activa): **MLB** (n=1174→652) ROI +0.41%→**+2.42%**, profit +19→+51, exposición a la mitad; **agregado** +0.24%→+0.71%, exposición ~a la mitad. **WNBA** contradice (−2.1%→−14.5%) pero n=62 (ruido); tenis ruido. La evidencia (impulsada por MLB) favorece bajarlo: marca más edges sobreconfiados y reduce riesgo sin sacrificar ROI. Activado en `configs/default.yaml` (`max_plausible_edge: 0.075`); el default del dataclass queda en 0.15 (test pinned `test_risk_config_has_plausibility_cap_default`). 183 passed. Sigue ≈ break-even (proxy de cierre de un snapshot, sin IC) → control de riesgo, no rentabilidad. Cierra el pendiente del techo 0.075. Mitiga más KI-012.

## 2026-06-22 — Park factor MLB (PRIMERA señal por deporte que bate al baseline) + totals des-pausado

El usuario eligió "MLB park factors → totals" entre las señales por deporte (vs rest/B2B basketball y portero NHL). Restricción: solo MLB (1148 graded) y WNBA (170) tienen muestra OOS; el abridor MLB ya fue rechazado (KI-006). Hallazgo de infra: las features de equipo (NBA/NFL/NHL en `features/`, incl. rest_days) alimentan la ruta ML, NO los adapters de producción; una señal hay que enchufarla en el adapter (ajuste de lambda).

**Implementado (`src/sqp/models/park.py::ParkFactors`):** factor de parque = carreras totales en juegos de LOCAL del equipo / carreras en sus juegos de VISITA (el mismo equipo en ambos aísla el parque de su nivel ofensivo — park factor clásico). Regresado por muestra, acotado, leakage-safe (walk-forward). Enchufado en BaseballAdapter (update en observe; escala AMBAS lambdas en _rates → mueve Over/Under, no el moneyline). Gated por `park_bound` (default 0.0 = no-op).

**Validación OOS (config de producción: penalización EV + max_plausible_edge 0.075):**
- TOTALS ROI: off **−17.1%** → 0.10 **+2.8%** → 0.20 +1.0% (n≈187).
- MLB global ROI: off +2.4% → **+7.8%** (0.10), profit +51→+166.
- Held-out (mitad ≥ 2026-05-09, n≈89-111): off −15.9% → 0.10 +3.8% / 0.20 +7.0%. **Generaliza** en ambas mitades y ambos bounds → no es selección in-sample del bound. El park se estima walk-forward sobre toda la temporada; el split solo restringe qué se apuesta.

**Activado:** `ratings.yaml mlb.park_bound: 0.10` (elegido sobre 0.20 por menos sobre-corrección) + **mlb/totals DES-PAUSADO** en default.yaml (con totals pausado el factor no tenía efecto live, así que van juntos). Tests 187 passed (+4 test_park.py; test_default_config_*_mlb_totals actualizado al estado des-pausado + park activo).

**Lectura:** PRIMERA señal específica por deporte que bate al baseline de forma robusta (el abridor solo empataba). Pero una sola temporada de odds capturadas, proxy de cierre de un snapshot, sin IC → no es rentabilidad demostrada. Vigilar el ROI realizado de totals en la auditoría tras unos días y re-pausar si vuelve a negativo. Próximas señales: basketball rest/B2B (WNBA, muestra chica) o portero NHL (cuando haya cobertura OOS).

## 2026-06-22 — Segunda señal por deporte: rest/B2B basketball — RECHAZADA por OOS (OFF)

Siguiente señal tras el park factor. Apuntaba al mercado débil que quedaba: WNBA spreads (OOS −11.3%). `src/sqp/models/rest.py::RestModel`: ajusta el margen esperado del local por `points_per_day*(descanso_local − descanso_visita)` (acotado, leakage-safe, last-game-date por equipo); enchufado en NormalMarginAdapter (NBA/WNBA/NFL), gateado por `rest_points_per_day` (default 0.0 = no-op).

**Validación OOS (WNBA spreads, config de producción):** la ventana completa lucía fuerte (spreads −6%→+18% con rppd 0.5-2.0, n≈22-25) PERO **no generaliza** en el held-out (≥2026-05-29, n≈7-10): rppd=1.0 (el mejor en ALL) EMPEORA spreads −38%→−48%; relación no-monótona en el parámetro (1.5 peor que 1.0 y 2.0). Muestras minúsculas (mismo ruido de WNBA visto antes con el techo). **NO se activa** — disciplina OOS lo rechaza, igual que el abridor MLB. Código queda como infra dormida (no-op, testeada) para re-validar cuando NBA/WNBA acumulen odds. 192 passed (+5 test_rest.py). Commit `669edc2`, merge `6259cfb`.

**Lección reforzada:** WNBA es demasiado chica para validar señales; HOY solo MLB tiene muestra OOS confiable. Resumen de las 2 señales por deporte: park factor MLB→totals ACTIVADO (generaliza); rest/B2B basketball OFF (no generaliza). La disciplina "activar solo lo que bate al baseline OOS" funcionó en ambos sentidos.

## 2026-06-22 — Backfill histórico de odds: NBA/NHL OOS desbloqueado (con gasto autorizado)

Para romper el cuello de botella ("solo MLB tiene OOS confiable") se usó el backfill de pago `scripts/backfill_historical_odds.py` (presupuestado, idempotente, 1 snapshot/liga/día, costo 10×mercados×regiones).

**Test chico autorizado (NFL 14 días):** RESUELVE la duda de la memoria — **`/historical` SÍ funciona en el plan actual** (la memoria decía 401 en el gratuito). Costo real **30 créditos/llamada** (us, 3 mercados). PERO los 13 snapshots de NFL reciente capturaron juegos FUTUROS (commence 2026-09/10, aperturas que la API ya lista), cero solape con resultados (terminan 2026-02-08) → inútiles para OOS. Lección: `/historical` en una fecha devuelve lo que la API listaba ENTONCES; para deportes fuera de temporada eso son aperturas futuras. Esos 13 snapshots son inertes (el matching usa el último snapshot antes del commence = el de cierre forward, no la apertura de junio).

**Backfill autorizado NBA+NHL ~90 días (playoffs, EN temporada con resultados):** 177 snapshots, 57.240 líneas, **5.310 créditos** gastados. Cuota restante: **2.842** (el plan tenía ~8.500 efectivos, no 20k). Verificación OOS (config de producción):
- **NHL: 266 eventos / 260 matched / n=188 bets** — PRIMERA muestra OOS usable fuera de MLB. ROI −4.5%; mercado débil totals −10.0% (h2h −7.1%, spreads +4.6%).
- **NBA: 240 / 228 / n=67** (marginal, ventana solo-playoffs). ROI −25.6%; spreads −45.7% (n=38).
- El modelo actual PIERDE en ambas (régimen de playoffs, sin señal específica) → NO operar NBA/NHL; la cobertura es para VALIDAR señales.

**Estado:** cuota baja (2.842). NFL OOS sigue bloqueado: necesita la ventana 2025 (Sept 2025–Feb 2026, 130-290 días atrás) y el script captura "más reciente primero" → requiere mejora `--start/--end` (sin gasto, pospuesto). Próximo natural: probar una señal de NHL (totals −10% candidato a factor de entorno tipo park, o portero) contra los 188 bets.
