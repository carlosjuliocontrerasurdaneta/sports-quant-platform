# Sports Quant Platform (SQP) — Descripción técnica

> Generado: 2026-08-18. Solo lectura; no modificar manualmente.

---

## 1. Propósito general

SQP es una **plataforma cuantitativa de estimación de probabilidades pregame** para apuestas deportivas. Su objetivo único es **ganar dinero con las apuestas de los picks**, produciendo **probabilidades estimadas calibradas** para tres mercados —moneyline (1X2 en fútbol), spread/handicap y totals (over/under)— sobre un núcleo compartido y adaptadores por familia de deporte.

Cobertura: Basketball (NBA, WNBA, NCAAB, WNCAAB), American Football (NFL, NCAAF), Baseball (MLB), Hockey (NHL), Soccer (12 ligas preconfiguradas + extensible por YAML) y Tennis (ATP/WTA, solo ganador).

El sistema **nunca promete ganancia**: distingue estrictamente probabilidad estimada ≠ implícita sin vig ≠ edge ≠ ROI esperado ≠ ROI realizado. Estado actual auto-declarado: ≈ break-even sobre un proxy de cierre, operando en modo evidencia (stakes efectivamente 0 vía gates default-deny).

---

## 2. Arquitectura y estructura de directorios

510 archivos versionados. Árbol resumido:

```
sports-quant-platform/
├── src/sqp/                  # Paquete Python principal
│   ├── config.py             # Settings (env + configs/default.yaml), RiskConfig, validación fail-fast
│   ├── exceptions.py, logging_config.py
│   ├── domain/models.py      # Event, MarketLine, EventOdds, EstimatedProbabilities, BetCandidate
│   ├── providers/            # odds_api, mlb_statsapi, espn_results, espn_tennis, odds_cache, synthetic, base
│   ├── sports/               # base (SportAdapter ABC), adapters, registry, team_names
│   ├── models/               # elo, distributions, blend, fip, park, rest, starters, team_scoring, ml_train, ml_predict
│   ├── markets/              # odds (conversiones), vig (no-vig), edge (penalización)
│   ├── calibration/          # calibrator, data, metrics, pergame
│   ├── risk/                 # kelly, bankroll, clv_gate, prediction_gate, degradation
│   ├── backtesting/          # engine, roi_engine, tuning
│   ├── settlement/           # settle (grading), runner, backfill_teams
│   ├── storage/              # atomic, lock, odds_store, results_store, served_store, feature_store, starters, starter_fip
│   ├── audit/                # clv, clv_movement, segments, patterns, report, html_report, intraday_gate
│   ├── evaluation/           # compare, model_vs_market
│   ├── monitoring/           # health, run_status
│   ├── features/             # builders, common, mlb (subsistema ML experimental)
│   └── pipeline/             # daily (orquestador de liga), probabilities, budget, cleanup,
│                             #   closing_capture, intraday_scan, revalidation
├── scripts/                  # 43 scripts operativos (run_all, settle_all, backfill_*, train_*, tune_*, clv_*)
│   └── ai/                   # protocolo de cross-review Claude↔Codex (v2)
├── tests/                    # 77 archivos (~1073 tests)
├── configs/                  # default.yaml + leagues/ (soccer.yaml, ratings.yaml, team_aliases.yaml)
├── *.bat                     # entrypoints Windows (DIARIO_COMPLETO, SETTLE_ALL, RUN_DIARIO_ALL, etc.)
├── audit/                    # informes de auditorías previas (+ reproductions/)
├── docs/, Obsidian/          # documentación técnica + bitácora/vault de conocimiento
├── .claude/                  # agentes, skills, loops, hooks, reglas del harness
├── pyproject.toml, requirements.lock, Dockerfile, Makefile, .github/workflows/ci.yml
```

**Decisión estructural rectora**: núcleo único + patrón adapter. Agregar una liga de fútbol = una entrada YAML; agregar un deporte = implementar un `SportAdapter`; el pipeline nunca cambia.

---

## 3. Componentes y módulos principales

### Dominio (`src/sqp/domain/models.py`)
Dataclasses `Event`, `MarketLine`, `EventOdds`, `EstimatedProbabilities` (contrato de salida del modelo), `BetCandidate` (fila de pick con estimated/calibrated probability, edge crudo vs ajustado, kelly_stake_pct, stake, flags).

### Config (`src/sqp/config.py`)
`Settings.load()` fusiona env + `configs/default.yaml` con precedencia **env > yaml > default de código**. `_env_flag` es tri-estado (True/False/None) para no "fallar abierto". `Settings.validate()` hace fail-fast sobre parámetros de riesgo fuera de rango. Un `default.yaml` ausente lanza excepción.

### Sports (`src/sqp/sports/`)
`SportAdapter` (ABC en `base.py`) define `observe`/`fit_results`/`estimate`/`reliability_warning`. Dos familias de modelado en `adapters.py`:
- `NormalMarginAdapter` (basketball, football): margen ~ Normal(μ,σ), μ desde Elo; total desde tasas de anotación por equipo.
- `PoissonAdapter` (hockey, soccer, baseball): Poisson por equipo, split desde Elo; soccer añade Dixon-Coles (`dc_rho`), baseball sobredispersión (`dispersion_k`) y ajustes de pitcher/parque.
- `TennisAdapter`: Elo jugador-vs-jugador, solo ganador (NO modela superficie — limitación documentada).

`registry.py` mapea liga→(adapter, params) con precedencia `FAMILY_PARAMS → LEAGUE_OVERRIDES → league_params(yaml)`.

### Markets (`src/sqp/markets/`)
`odds.py`: conversiones american↔decimal, `is_usable_price` como única fuente de verdad (rechaza None/NaN/inf/≤1.0). `vig.py`: remoción proporcional y power. `edge.py`: edge + penalización por desacuerdo modelo-mercado y mercados finos.

### Risk (`src/sqp/risk/`)
`kelly.py` (Kelly fraccional con caps y min_edge), `bankroll.py` (ledger, banca dinámica), y tres gates default-deny: `prediction_gate.py` (regla RECTORA desde 2026-08-16), `clv_gate.py` (ahora solo evidencia), `degradation.py` (auto-pausa con histéresis).

### Calibration / Backtesting / Settlement / Audit
Calibración por (liga, mercado) con Brier/log-loss/ECE; backtesting walk-forward temporal; settlement append-only con grading contra ESPN; auditoría con reportes timestamped y dashboard HTML.

---

## 4. Flujo general de ejecución

### Producción diaria (`scripts/run_all.py --mode live`)

1. `Settings.load()` + banca dinámica desde ledger.
2. `_select_live`: auto-detecta ligas en temporada, aplica guard de presupuesto de cuota + tenis dinámico.
3. Guard M2: omite ligas con picks comenzados sin liquidar.
4. Monitor de degradación → fusiona auto-pausas.
5. Por cada liga, `pipeline/daily.run_league`:
   - Carga resultados + ajusta Elo/scoring + adjunta abridores MLB.
   - Obtiene cuotas → filtra horizonte → persiste snapshot forward.
   - Por evento: `adapter.estimate` → consenso mediano → no-vig → `_decision_probability` (blend con `market_shrink`) → `edge` → `adjusted_edge` → `kelly_fraction_stake`.
   - Served stream: registra toda cara priceada para calibrador insesgado.
   - Cadena de stake-0: paused → incomplete_market → suspect → shadow → prediction_gate → clv_gate.
   - Cap de exposición diaria por liga.
6. Post-loop: prune stale, cap de exposición global, reporte consolidado (md + HTML), auditoría CLV, reescritura del prediction_gate, recalibración a STAGING.

### Orden de operación
**SETTLE_ALL.bat → RUN_DIARIO_ALL.bat** (el run sobrescribe candidates; settlement debe ir primero).

### Modo demo
`SyntheticProvider`, etiqueta `demo_synthetic`, aislado en `predictions/demo`, nunca toca artefactos reales.

---

## 5. Tecnologías y dependencias

- **Python ≥ 3.11** (producción: 3.14). `pyproject.toml` con setuptools; layout `src/`.
- Dependencias core: **numpy, pandas, scipy, scikit-learn, joblib, requests, pyyaml, python-dotenv**.
- Dev: pytest, pytest-cov, ruff, mypy. `requirements.lock` (versiones pineadas reproducibles).
- Persistencia: **CSV/JSON/Parquet en `data/`** — sin base de datos; escrituras atómicas + locks inter-proceso.
- **Dockerfile** y **Makefile** presentes.
- **CI** (`.github/workflows/ci.yml`): matriz Linux 3.11–3.14 + leg Windows; ruff, mypy (3.12), pytest, pip-audit bloqueante, cobertura informativa.

---

## 6. Puntos de entrada principales

### BAT (Windows Task Scheduler, producción)
| Archivo | Propósito |
|---|---|
| `DIARIO_COMPLETO.bat` | Orquestador maestro (tarea diaria 11:00): SETTLE → RUN → abre dashboard |
| `SETTLE_ALL.bat` | `scripts/settle_all.py --days-from 2` |
| `RUN_DIARIO_ALL.bat` | `scripts/run_all.py --mode live` |
| `CAPTURE_CLOSE.bat` | Captura cierre horaria + revalidación + intraday scan |
| `BACKFILL_ALL.bat` | Semanal — rellena histórico |
| `REFRESH_ML.bat` | Semanal — subsistema ML experimental |
| `VALIDATE_OOS.bat` | Mensual — validación out-of-sample |

### Scripts Python
`run_all.py`, `run_daily.py`, `run_backtest.py`, `settle_all.py`, `list_sports.py`, `train_calibration.py`, `promote_calibration.py`, `tune_ratings.py`, `tune_mlb_pitcher.py`, `backfill_*.py`, `clv_analysis.py`, `bankroll_status.py`, `health_check.py`, `update_prediction_gate.py`.

---

## 7. Configuración, persistencia, APIs externas y pruebas

### Configuración
`configs/default.yaml` (risk, bankroll, odds, picks, calibration, gates, degradation, revalidation, intraday). Precedencia documentada en `docs/CONFIG-PRECEDENCE.md`. Secretos solo por `.env` (`.env.example` como plantilla; `odds_api_key` con `repr=False`).

### Persistencia
Sistema de archivos bajo `data/` — CSV/Parquet/JSON, append-only en settlement, escrituras atómicas + locks. Registros clave: `data/bets/prediction_gate.json`, `clv_gate.json`, `degradation_pause.json`, `bankroll_adjustments.csv`, served stream, `segment_diagnostics_latest.csv`.

### APIs externas
- **The Odds API**: proveedor principal de cuotas (plan de pago 20k créditos/mes, cuota vía headers).
- **MLB Stats API**: pública, abridores probables.
- **ESPN**: resultados no oficiales, único settlement de tenis.
- Proveedores no configurados lanzan `ProviderNotConfiguredError` explícito.

### Pruebas
77 archivos de test (~1073 tests), cubriendo: odds/vig/edge, distribuciones, Elo, Kelly, calibración, backtest parity, settlement/grading, gates, pipeline demo, precios no-finitos, budget/selección, revalidación, contratos del harness. Suite en CI (Linux + Windows).

**Riesgo conocido**: rama live de `pipeline/daily.py` tiene cobertura inferior a la rama demo — un `NameError` en live pasó los 1073 tests y solo lo detectó ruff.

---

## 8. Patrones de diseño y decisiones arquitectónicas

| Patrón | Dónde |
|---|---|
| **Adapter + Registry** | `sports/adapters.py` + `sports/registry.py` — núcleo invariante, extensión por familia/liga |
| **Strategy** | `pick_mode` (`edge` activo / `accuracy` documentado como perdedor a cuotas bajas) |
| **Fail-fast, never fail-open** | `config.validate()`, `_env_flag` tri-estado, `is_usable_price` central, proveedores explícitos |
| **Default-deny gates en capas** | shadow_mode → prediction_gate (rector) → clv_gate; separación shadow global vs gates por mercado |
| **Corrección temporal estricta** | Elo/scoring secuenciales, backtesting walk-forward, served stream para calibración insesgada, snapshots forward OOS |
| **Seguridad operativa de datos** | Escrituras atómicas + locks, archivado antes de sobrescribir, append-only en settlement, aislamiento demo/real |
| **Idempotencia y orden garantizado** | SETTLE antes de RUN; dedupe por (día, home, away, game_id) con tolerancia ±1 día |
| **Autonomía controlada** | Monitor de degradación con histéresis, banca dinámica desde ledger, recalibración a staging con promoción humana |

---

## Archivos de referencia clave

| Archivo | Rol |
|---|---|
| `src/sqp/pipeline/daily.py` | Orquestador de liga (núcleo crítico, mayor concentración lógica) |
| `scripts/run_all.py` | Orquestador diario |
| `src/sqp/config.py` + `configs/default.yaml` | Config/riesgo |
| `src/sqp/sports/adapters.py`, `registry.py`, `base.py` | Adaptadores y registro |
| `src/sqp/domain/models.py` | Dominio |
| `src/sqp/settlement/settle.py` | Settlement/grading |
| `DIARIO_COMPLETO.bat` | Entrada de producción |

---

## Hotspots y riesgos inferidos

1. `pipeline/daily.py` concentra la lógica crítica con muchos parches de auditoría; rama live infra-testeada.
2. Dependencia de proveedores no oficiales (ESPN) para settlement de tenis y headers de The Odds API para el budget.
3. Persistencia en archivos planos con concurrencia por locks — sensible a corrupción parcial (mitigado con escrituras atómicas).
4. Parámetros σ por liga en frontera de grilla, algunos tuneados in-sample.
5. Subsistema ML sin integrar en producción (decisión abierta).
