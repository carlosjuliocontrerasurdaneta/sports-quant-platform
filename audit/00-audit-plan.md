# 00 — Plan de auditoría integral

Fase 0 (planificación). **No se modificó código de aplicación.** Este documento
es un inventario y un plan; no contiene correcciones.

- Fecha: 2026-08-05 · Rama: `main` · Commit base: `7871bdb`
- Alcance leído: `README.md`, `CLAUDE.md`, `.claude/CLAUDE.md`, `.claude/rules/*`,
  `pyproject.toml`, `Makefile`, `configs/**`, `.github/workflows/ci.yml`, `*.bat`,
  el árbol completo de `src/` y `tests/` (a nivel de módulos y símbolos),
  `docs/`, `audit/latest/**`.
- **No escaneado** por regla permanente (`.claude/CLAUDE.md`): `data/`,
  `historical/`, `logs/`, `exports/`. `cat .env.example` fue **denegado por
  permisos** durante esta fase; la revisión de secretos se apoya en el barrido ya
  ejecutado por la auditoría previa y deberá repetirse con permiso explícito.

## Convención de evidencia

| Marca | Significado |
|---|---|
| **[C]** | **Confirmado en esta sesión** por ejecución de comando o lectura directa del archivo citado. |
| **[H]** | **Hipótesis**: derivada de lectura estática o de auditorías previas, pendiente de verificación ejecutable. Se indica qué la confirmaría o refutaría. |
| **[P]** | Heredado de `audit/latest/` (auditoría 2026-08-04), no re-verificado aquí. |

Toda afirmación cuantitativa lleva ruta y símbolo. Donde no hay medición, se dice.

## Relación con la auditoría anterior — leer antes de empezar

`audit/latest/` contiene una auditoría integral cerrada el **2026-08-05 03:55Z**
(`audit/latest/MANIFEST.json:3-4`), es decir de hace ~21 horas. **[C]** Repetirla
entera sería desperdicio. Lo que aquella pasada declaró explícitamente **fuera de
su alcance** define el valor de ésta:

> *"Esta auditoría **no ejecutó backtests, ni `validate_oos.py`, ni reentrenó
> nada**"* — `audit/latest/QUANT_REVIEW.md:8-9`
>
> *"**No puedo confirmar** la ausencia de leakage por inspección estática:
> requeriría re-ejecutar el backtest y los tests de leakage"* —
> `QUANT_REVIEW.md:88-89`

Puertas técnicas que aquella pasada dejó verdes **[P]** y que esta sesión
**re-verificó [C]**: `pytest` 637 passed, `ruff check` limpio, `mypy src` limpio
(89 archivos). No hay que volver a auditarlas; hay que auditar lo que ellas no
capturan.

**Consecuencia para el plan:** el peso se desplaza a las fases 3–7 (validez
cuantitativa, leakage, backtesting, calibración, riesgo), que son las únicas
donde la auditoría anterior admite no tener evidencia.

---

## 1. Arquitectura e inventario de componentes

**[C]** 72 módulos en `src/sqp/` (excluyendo `__init__.py`), 10.643 líneas.
81 archivos de test, 8.800 líneas.

| Capa | Ruta | LOC | Papel |
|---|---|---|---|
| Configuración | `src/sqp/config.py` | 356 | Precedencia env → YAML → defaults |
| Dominio | `src/sqp/domain/models.py` | 80 | `Event`, `MarketLine`, `EventOdds`, `EstimatedProbabilities`, `BetCandidate` |
| Proveedores | `src/sqp/providers/` | 573 | `OddsAPIClient`, `MLBStatsProvider`, `ESPNResultsProvider`, `ESPNTennisResultsProvider`, `SyntheticProvider`, `FileCache`, `NotConfiguredProvider` |
| Mercados | `src/sqp/markets/` | 122 | `odds.py` (conversión), `vig.py` (`remove_vig_proportional`, `remove_vig_power`), `edge.py` (`adjusted_edge`, `AdjustedEdge`) |
| Modelos | `src/sqp/models/` | 673 | `EloRatings`, `distributions.py`, `park.py`, `rest.py`, `fip.py`, `starters.py`, `team_scoring.py`, + ruta ML (`ml_train`, `ml_predict`, `blend`) |
| Simulación | `src/sqp/simulation/monte_carlo.py` | 58 | `simulate_normal_game`, `simulate_poisson_game` |
| Deportes | `src/sqp/sports/` | 440 | `SportAdapter` + 6 adaptadores + `registry.py` + `team_names.py` |
| Calibración | `src/sqp/calibration/` | 923 | `calibrator.py` (530), `data.py`, `metrics.py`, `pergame.py` |
| Riesgo | `src/sqp/risk/` | 461 | `kelly.py`, `bankroll.py`, `clv_gate.py`, `degradation.py` |
| Backtesting | `src/sqp/backtesting/` | 610 | `engine.py` (`walk_forward_backtest`), `roi_engine.py`, `tuning.py` |
| Pipeline | `src/sqp/pipeline/` | 1.929 | `daily.py` (740), `revalidation.py`, `cleanup.py`, `closing_capture.py`, `intraday_scan.py`, `probabilities.py`, `budget.py` |
| Liquidación | `src/sqp/settlement/` | 591 | `runner.py` (432), `settle.py`, `backfill_teams.py` |
| Auditoría | `src/sqp/audit/` | 1.869 | `html_report.py` (832), `report.py`, `segments.py`, `clv.py`, `clv_movement.py`, `patterns.py`, `intraday_gate.py` |
| Almacenamiento | `src/sqp/storage/` | 671 | `odds_store`, `served_store`, `results_store`, `feature_store`, `starters`, `starter_fip`, `lock`, `atomic` |
| Features | `src/sqp/features/` | 345 | `builders.py`, `common.py`, `mlb.py` |
| Evaluación | `src/sqp/evaluation/` | 211 | `model_vs_market.py`, `compare.py` |
| Monitorización | `src/sqp/monitoring/` | 248 | `health.py`, `run_status.py` |

**Observación estructural [C]:** los tres módulos más grandes —
`audit/html_report.py` (832), `pipeline/daily.py` (740), `calibration/calibrator.py`
(530)— concentran el 20% del código. `daily.py` expone 19 funciones, de las cuales
15 son privadas y una sola es pública (`run_league`, línea 476): es el punto de
mayor densidad de lógica del proyecto.

## 2. Puntos de entrada y flujos de ejecución

### Producción (Windows Task Scheduler → BAT)

**[C]** verificado en las cabeceras de los `.bat`:

```
DIARIO_COMPLETO.bat            (tarea SQP_Diario_Completo_Cdev, 11:00)
  ├─ SETTLE_ALL.bat            -> scripts/settle_all.py
  └─ RUN_DIARIO_ALL.bat        -> scripts/run_all.py --mode live
                                  -> sqp.pipeline.daily.run_league (por liga)
CAPTURE_CLOSE.bat  (horaria)   -> scripts/capture_closing_odds.py
                                  -> pipeline/closing_capture.capture_closing
                                  -> pipeline/revalidation.revalidate_candidates
                                  -> pipeline/intraday_scan.log_intraday_edges
BACKFILL_ALL.bat   (semanal)   -> scripts/backfill_results.py
REFRESH_ML.bat     (semanal)   -> build_features / train_models / compare_models
VALIDATE_OOS.bat   (mensual)   -> scripts/validate_oos.py
```

**Orden crítico [C]:** `RUN_DIARIO_ALL.bat` sobrescribe
`data/predictions/candidates_*.csv`, por eso la liquidación va primero
(`DIARIO_COMPLETO.bat`, comentario en cabecera; `RUN_DIARIO_ALL.bat` líneas 6-10).
Respaldo: `pipeline/daily.py:307` `_archive_existing`.

### Manual / demo

`scripts/run_daily.py` (herramienta ligera, **sin** guard de presupuesto ni
reporte consolidado — `README.md:93-95`), `scripts/run_backtest.py`,
`scripts/clv_analysis.py`, `scripts/health_check.py`, `scripts/bankroll_status.py`.
**[C]** 41 archivos en `scripts/`.

### Flujo de datos del run diario

```
OddsAPIClient           providers/odds_api.py:54
  -> OddsStore          storage/odds_store.py:30
  -> _consensus_lines   pipeline/probabilities.py:17
  -> _novig_probs       pipeline/probabilities.py:46  (markets/vig.py)
  -> SportAdapter       sports/adapters.py            (Elo + distribución)
  -> calibrate_probability  calibration/calibrator.py:523
  -> adjusted_edge      markets/edge.py:32
  -> kelly_fraction_stake  risk/kelly.py:14
  -> capas de riesgo:   _apply_daily_exposure_cap (daily.py:218)
                        apply_global_exposure_cap (daily.py:245)
                        _zero_stake_flag          (daily.py:373)
                        market_allowed            (risk/clv_gate.py:76)
  -> _finalize          daily.py:337  -> ServedStore + candidates_*.csv
```

## 3. Módulos críticos de negocio y cuantitativos

Ordenados por consecuencia de un fallo silencioso:

| # | Módulo / símbolo | Por qué es crítico |
|---|---|---|
| 1 | `pipeline/probabilities.py:17` `_consensus_lines` | Origen de toda probabilidad implícita. Alimenta el run vivo **y** la auditoría de CLV. |
| 2 | `markets/vig.py:21` `remove_vig_power` | La probabilidad justa del mercado; si falla, el edge entero es ficticio. |
| 3 | `markets/edge.py:32` `adjusted_edge` | Combina shrink de mercado, penalización de incertidumbre y anomalía. Determina qué se apuesta. |
| 4 | `risk/kelly.py:14` `kelly_fraction_stake` | 27 líneas que fijan el tamaño de cada apuesta. |
| 5 | `pipeline/daily.py:245` `apply_global_exposure_cap` | Único tope que impide que el cap por liga se multiplique por N ligas (`configs/default.yaml:7-10`). |
| 6 | `risk/clv_gate.py:76` `market_allowed` | Regla vinculante de salida del shadow mode. Default-deny. |
| 7 | `risk/degradation.py:81` `evaluate_pauses` | Auto-pausa por Brier/ROI con histéresis. |
| 8 | `calibration/calibrator.py:423` `auto_promote_calibrators` | Puede cambiar probabilidades servidas sin humano si se activa (`auto_promote: false` hoy, `configs/default.yaml:85`). |
| 9 | `backtesting/roi_engine.py:187` `realized_roi_backtest` | Produce la cifra OOS con la que se decide todo. |
| 10 | `settlement/runner.py:389` `fetch_and_settle` | Define el resultado observado; un fallo aquí corrompe todas las métricas aguas abajo. |

## 4. Integraciones externas y proveedores de datos

| Proveedor | Módulo | Naturaleza | Riesgo declarado |
|---|---|---|---|
| The Odds API | `providers/odds_api.py:54` `OddsAPIClient` | **De pago**, cuota mensual | Consumo de cuota; redacción de `apiKey` en errores verificada **[P]** en `odds_api.py:132-144` |
| MLB Stats API | `providers/mlb_statsapi.py:14` | Pública, oficial | — |
| ESPN (resultados) | `providers/espn_results.py:59` | **No oficial**, sin contrato | Ruptura silenciosa de esquema |
| ESPN (tenis) | `providers/espn_tennis.py:82` | **No oficial** | The Odds API no da scores de tenis (`README.md:178-179`) |
| Sintético | `providers/synthetic.py:25` | Demo, etiquetado `demo_synthetic` | Confusión demo/live |

Controles existentes: `providers/base.py:26` `NotConfiguredProvider` (falla
explícito), `providers/odds_cache.py:16` `FileCache`, guard de presupuesto en
`pipeline/budget.py:37` `leagues_within_budget` y tope diario de créditos en
`closing_capture.py:63-74` (`spent_today` / `add_spent`).

## 5. Estructura de tests y comandos de validación

**[C]** 81 archivos, 8.800 líneas, subdirectorios `tests/audit/`,
`tests/pipeline/`, `tests/settlement/`.

```powershell
$env:PYTHONPATH="src"; python -m pytest tests/ -q   # 637 passed (62 s)  [C]
ruff check src scripts tests                        # limpio             [C]
mypy src                                            # 89 archivos, limpio [C]
make check                                          # las tres puertas juntas
python scripts/health_check.py                      # OK / WARN / ERROR
python scripts/clv_analysis.py                      # escribe data/bets/clv_*.md
```

CI (`.github/workflows/ci.yml`) **[C]**: matriz 3.11/3.12/3.13;
`ruff check src scripts tests` en todas; `mypy src` **solo en 3.12**; `pytest`
en 3.11 y 3.13; cobertura **informativa sin umbral** en 3.12; `pip install -e
".[dev]" -c requirements.lock`.

**[C] Módulos de `src/` no importados por ningún test (6 de 72):**

| LOC | Módulo | Comentario |
|---|---|---|
| 58 | `sqp.storage.lock` | **El más relevante**: es el mecanismo de concurrencia |
| 54 | `sqp.sports.base` | Clase base abstracta; se ejerce vía adaptadores |
| 43 | `sqp.models.ml_predict` | Ruta ML, no en producción |
| 37 | `sqp.providers.base` | Interfaces |
| 22 | `sqp.storage.atomic` | `atomic_write_csv` |
| 19 | `sqp.logging_config` | — |

**[H]** "No importado por nombre" ≠ "no ejercitado": `locked()` y
`atomic_write_csv` pueden ejecutarse indirectamente desde `daily.py` o los
stores, que sí están cubiertos. **Lo confirma o refuta** una corrida de
`pytest --cov=sqp.storage.lock --cov=sqp.storage.atomic` mirando líneas
cubiertas, no imports. Es la primera medición de la Fase 14.

## 6. Áreas sensibles a seguridad

| Área | Ubicación | Estado |
|---|---|---|
| Clave del proveedor | `providers/odds_api.py`, `.env` | Solo por `.env`; redacción en errores **[P]** `odds_api.py:132-144` |
| Carga de configuración | `config.py` | Fail-fast tras C-2 **[P]** (`audit/latest/FINDINGS.md:9-26`) |
| Escritura de artefactos | `storage/atomic.py:16`, `settlement/runner.py:256` | Escrituras atómicas |
| Deserialización | `calibration/calibrator.py` (`joblib`) | Carga de `.joblib` desde `data/models/` |
| Ejecución programada | `*.bat` | Intérprete fijo con fallback (`SQP_PYTHON`) |
| Permisos del agente | `.claude/settings.local.json` | Saneado 2026-08-04 **[P]** |

**[H]** No verificado en esta fase: presencia de `timeout=` en **todas** las
llamadas HTTP (`.claude/rules/security-rules.md` lo exige). Se comprueba con un
grep sobre `requests.get|requests.post` en `src/sqp/providers/`.

## 7. Áreas sensibles al rendimiento

| Área | Símbolo | Naturaleza |
|---|---|---|
| Lectura de odds históricas | `backtesting/roi_engine.py:52` `load_closing_odds` | **[P]** Concatena todos los meses por llamada (`audit/latest/BACKLOG.md:97-100`, heredado de 07-12) |
| Monte Carlo | `simulation/monte_carlo.py` | `n_sims: 20000` (`configs/default.yaml:44`) por evento |
| Construcción de features | `storage/feature_store.py:131` `build_training_dataset` | Recorre histórico completo |
| Suite de tests | — | **[C]** 62 s para 637 tests |
| Dashboard HTML | `audit/html_report.py:422` `html_dashboard` | 832 líneas, render completo por run |

## 8. Áreas sensibles estadística y modelísticamente

Ésta es la zona de mayor valor de la auditoría, porque es donde la pasada
anterior admite no tener evidencia.

| Área | Símbolos | Riesgo |
|---|---|---|
| De-vig | `markets/vig.py:14,21` | Método power con `brentq`; fallback proporcional |
| Composición de penalizaciones | `markets/edge.py:32` `adjusted_edge` + `market_shrink` | **[P]** La penalización efectiva es 0.175, no el 0.35 nominal, por composición con el shrink (observación registrada 2026-08-04) |
| Validación temporal | `backtesting/engine.py:17` `walk_forward_backtest`, `tuning.py:75` `rolling_origin_improvement` | Splits temporales, warmup 60 |
| Gates de tuning | `tuning.py:36-38` `MIN_EVAL_HOME_ADV=200`, `MIN_DRAWS_DC_RHO=80`, `IMPROVEMENT_MARGIN=0.002` | Sobreajuste a la grilla |
| Calibración | `calibrator.py:57,69` `_is_monotone_increasing`, `_no_extreme_expansion` | Solo `mlb_h2h` en live **[P]** |
| Métricas | `calibration/metrics.py`, `evaluation/model_vs_market.py:48` `_cluster_bootstrap_ci` | El único IC del proyecto vive aquí |
| Umbrales de muestra | `clv_gate.py:23` `CLV_GATE_MIN_N=30`, `degradation.py:35`, `calibrator.py:420` `AUTO_PROMOTE_MIN_N_VAL=30` | n=30 es pequeño para decisiones de dinero |

**Hecho dominante que el plan no debe perder de vista [P]:** no hay ventaja
predictiva demostrada — gate de CLV vacío, ROI realizado −8.4% de banca sobre 431
apuestas, OOS −5.32% (`audit/latest/QUANT_REVIEW.md:18-25`). Una auditoría que
mejore el software sin tocar esto no cambia el hecho dominante, y debe decirlo.

### Familia de defectos abierta y confirmada: guards que no filtran `NaN`

**[C]** Demostrado con prueba ejecutable en esta sesión (ciclo M-7, commit
`7871bdb`): el guard `price_decimal is None or price_decimal <= 1.0` de
`pipeline/probabilities.py:17` `_consensus_lines` **no filtra `NaN`**, porque
`NaN <= 1.0` es `False`. Propagación medida: `median` → `NaN`, `implied` → `NaN`,
`remove_vig_power` tampoco cae por su guard de cuotas degeneradas y su fallback
divide `NaN` entre `NaN` → las probabilidades justas del **mercado completo**
salen `NaN` y el evento desaparece de los picks en silencio.

**[C]** Segundo miembro, medido hoy: `inf` **no** es ignorado por
`pandas.median`/`mean` (a diferencia de `NaN`), así que una fila con `inf` deja
`mean_clv_pct` de su `(liga, mercado)` en `inf` y desplaza la mediana — la que
gobierna `risk/clv_gate.py`. Ver `REVIEW.md` (I-2 del ciclo 2026-08-05).

Tercer miembro **[P]**: el guard de `price_decimal = 1.0` en ingestión, abierto
desde la auditoría 07-24 (`audit/latest/BACKLOG.md:72-78`).

Los tres están anotados en `Obsidian/Tareas.md`. **La Fase 4 debe tratarlos como
una sola clase de defecto, no como tres incidencias sueltas.**

## 9. Checklist de auditoría por fases

Cada fase declara: qué se revisa, con qué comando se verifica, y qué constituye
evidencia. Ninguna fase puede cerrarse con "revisado": necesita salida de comando
o cita de archivo.

### Fase 1 — Arquitectura y mantenibilidad
- [ ] Dirección de dependencias: ¿algún módulo de `domain/` o `markets/` importa de `pipeline/`? (`grep -rn "^from sqp" src/sqp/domain src/sqp/markets`)
- [ ] `pipeline/daily.py` (740 líneas, 19 funciones): ¿`run_league` tiene responsabilidades separables?
- [ ] `audit/html_report.py` (832): ¿presentación mezclada con cálculo?
- [ ] Duplicación real entre `audit/clv.py:124` `clv_segments` y `audit/clv_movement.py:131` `movement_segments` (ambos agregan `beat_close_rate`).
- **Evidencia:** grafo de imports + lista de funciones > 50 líneas.

### Fase 2 — Corrección y lógica de negocio
- [ ] `settlement/settle.py:21` `_grade`: empates, push, `three_way`.
- [ ] `settlement/runner.py:176` `_void_stale_served` y `settle.py:79` `void_stale_candidates`: política stale coherente entre ambos caminos.
- [ ] `pipeline/cleanup.py:103` `unsettled_completed_picks` como guard del abort diario (`scripts/settle_all.py`).
- [ ] `pipeline/daily.py:373` `_zero_stake_flag`: precedencia entre `shadow_mode`, `market_paused`, `clv_gate` y `stale_edge_revoked`.
- **Evidencia:** tabla de precedencia de flags contrastada con los tests que la fijan.

### Fase 3 — Validez cuantitativa y estadística
- [ ] `markets/vig.py:21` `remove_vig_power`: comportamiento cuando `brentq` no converge; ¿el fallback avisa?
- [ ] `markets/edge.py:32`: verificar la composición shrink × penalización y si el 0.175 efectivo **[P]** es intencional o un artefacto.
- [ ] `models/distributions.py:46` `_dixon_coles_tau` y `:133` `elo_diff_to_margin`: rangos de validez.
- [ ] Ausencia de intervalos de confianza en todo el reporte salvo `_cluster_bootstrap_ci`.
- **Evidencia:** cross-check analítico vs `simulation/monte_carlo.py` con semilla fija (`seed: 42`).

### Fase 4 — Leakage y look-ahead ⚠️ prioridad máxima
- [ ] **La familia `NaN`/`inf`** (§8) como una sola clase.
- [ ] `features/common.py:41` `get_team_features` y `features/mlb.py:88` `build_mlb_dataset`: ventanas móviles solo sobre partidos pasados.
- [ ] `pipeline/daily.py:119` `_already_started` y `:110` `_within_horizon`.
- [ ] `backtesting/roi_engine.py:52` `load_closing_odds` y `:111` `_match_index`: ¿el emparejamiento puede tomar un snapshot posterior al comienzo? **Precedente confirmado: KI-019** (commit `dad8433`) — `commence_time` obsoleto admitía precios EN VIVO como cierre.
- [ ] `calibration/data.py:110` `load_settled_training_history`: la distribución de entrenamiento es la de servicio.
- **Evidencia:** un test que falle si se introduce un snapshot post-comienzo.

### Fase 5 — Validez del backtesting
- [ ] `backtesting/engine.py:17` `walk_forward_backtest`: warmup, ausencia de splits aleatorios.
- [ ] `roi_engine.py:173` `_apply_backtest_daily_cap` vs el cap del run vivo (`daily.py:218`): ¿misma regla?
- [ ] `roi_engine.py:119` `_match_result` y `:149` `_day_diff`: tolerancia de fechas y riesgo de doble conteo.
- [ ] Sesgo de supervivencia: **[P]** 54 filas servidas sin liquidar (`audit/latest/FINDINGS.md:78-88`).
- [ ] Disponibilidad de la apuesta: ¿el precio del backtest era obtenible en el momento del pick?
- **Evidencia:** ejecutar `scripts/validate_oos.py` (no ejecutado en la pasada anterior) y comparar con el −5.32% registrado.

### Fase 6 — Calibración
- [ ] `calibrator.py:170` `train_calibration` y `:381` `promote_calibrators`: separación train/promote.
- [ ] `:69` `_no_extreme_expansion` (gate anti-inflación, añadido tras el caso `wnba_h2h` **[P]**).
- [ ] `:492` `apply_calibration` y `:523` `calibrate_probability`: no-op silencioso cuando no hay calibrador — ¿avisa? (`daily.py:415` `_warn_if_uncalibrated_accuracy` solo cubre el modo accuracy).
- [ ] `AUTO_PROMOTE_MIN_N_VAL = 30` (`:420`): ¿suficiente para promover?
- **Evidencia:** tabla de fiabilidad por (liga, mercado) con n y ECE.

### Fase 7 — Riesgo y banca
- [ ] `risk/kelly.py:14`: comportamiento con edge negativo, probabilidad 0/1, cuota ≤ 1.
- [ ] `daily.py:245` `apply_global_exposure_cap`: orden de aplicación respecto al cap por liga; ¿se puede sobrepasar en un día multi-liga?
- [ ] `risk/bankroll.py:29` `BankrollLedger`: banca dinámica y ajustes manuales.
- [ ] `clv_gate.py:76` `market_allowed`: default-deny ante registro ausente o corrupto.
- [ ] `degradation.py:81` `evaluate_pauses`: histéresis; ¿puede oscilar?
- **Evidencia:** prueba de propiedad — ninguna combinación de entradas produce stake > `max_stake_pct` × banca.

### Fase 8 — Calidad de datos y fiabilidad de proveedores
- [ ] `providers/espn_results.py:117` `parse_scoreboard` y `espn_tennis.py:43`: comportamiento ante cambio de esquema (proveedores **no oficiales**).
- [ ] `storage/odds_store.py:30` y `served_store.py:71`: deduplicación y esquema.
- [ ] `sports/team_names.py:57` `TeamNormalizer`: colisiones ESPN ↔ Odds API (**[P]** KI-002 abierto).
- [ ] Timeouts y reintentos en `odds_api.py`.
- **Evidencia:** tests con payloads malformados por proveedor.

### Fase 9 — Seguridad y secretos
- [ ] Re-ejecutar el barrido de secretos **con permiso explícito** (denegado en fase 0).
- [ ] `grep` de `timeout=` sobre todas las llamadas HTTP.
- [ ] Deserialización `joblib` desde `data/models/`.
- [ ] `.gitignore` cubre `.env`, `*.patch`, `settings.local.json` **[P]**.
- **Evidencia:** salida del barrido + lista de llamadas HTTP con su timeout.

### Fase 10 — Concurrencia y consistencia de estado
- [ ] `storage/lock.py:26` `locked`: **[C]** ningún test lo importa. ¿Reentrante? ¿Se libera ante excepción? ¿Bloqueo obsoleto?
- [ ] `storage/atomic.py:16` `atomic_write_csv`: **[C]** tampoco importado por ningún test.
- [ ] Carrera real: `CAPTURE_CLOSE.bat` es **horaria** y `DIARIO_COMPLETO.bat` corre a las 11:00 — **[H]** pueden solaparse escribiendo `candidates_*.csv` y el ServedStore. Confirmarlo requiere leer los guards de ambos caminos.
- **Evidencia:** test de escritura concurrente sobre el mismo archivo.

### Fase 11 — Manejo de errores y observabilidad
- [ ] **[P]** 0 `except:` desnudos, 1 `except: pass` benigno (`odds_api.py:159`) — re-verificar sobre el árbol actual.
- [ ] `monitoring/health.py:100` `generate_health_report`: cobertura de los WARN.
- [ ] `monitoring/run_status.py:34` `record_run_failure` y el banner del dashboard (`html_report.py:399`).
- [ ] Mensajes de log que describan mal el efecto. **Precedente [C] de hoy:** el aviso de CLV no finito afirmaba que la fila "no cuenta para la mediana" siendo falso por omisión; corregido, y su corrección resultó a su vez incompleta para `inf`.
- **Evidencia:** inventario de `log.warning`/`log.error` con su condición de disparo.

### Fase 12 — Rendimiento y escalabilidad
- [ ] `roi_engine.py:52` `load_closing_odds` (**[P]** B-8).
- [ ] Perfilado de `run_league` sobre una liga.
- [ ] Crecimiento de `data/odds/` y su efecto en el backtest.
- **Evidencia:** `cProfile` con las 10 funciones más costosas.

### Fase 13 — Dependencias y configuración
- [ ] `pyproject.toml` vs `requirements.lock` vs CI.
- [ ] **[C]** `pyproject.toml:53` ignora `E701`/`E702` deliberadamente; `ruff format` declarado NO adoptado (`:41-46`).
- [ ] Precedencia de configuración (`docs/CONFIG-PRECEDENCE.md`) contrastada con `config.py`.
- [ ] **[C] Deriva de runtime:** `MANIFEST.json:8` registra Python **3.14.4** en desarrollo; CI cubre 3.11–3.13. Nadie prueba la versión con la que se opera.
- **Evidencia:** `pip-audit`, `pip check`, y matriz versión-declarada vs versión-usada.

### Fase 14 — Calidad de tests y cobertura ausente
- [ ] Cobertura real de los 6 módulos sin import directo (§5) — **[H]** a confirmar por líneas, no por imports.
- [ ] Tests que puedan pasar en vacío (sin premisa). **Precedente [P]:** ya ocurrió en `test_clv.py` y se corrigió añadiendo `assert len(df) == 1`.
- [ ] CI: cobertura **sin umbral** — no es una puerta.
- [ ] Tests de propiedad ausentes en `markets/` y `risk/`, que son funciones puras y los candidatos naturales.
- **Evidencia:** informe de cobertura por módulo + lista de tests sin aserción sobre la premisa.

### Fase 15 — Documentación y preparación operativa
- [ ] `README.md` vs configuración real (**[P]** hubo deriva del `pick_mode` no documentada, 07-31 → detectada 08-02).
- [ ] Bóveda Obsidian sincronizada (obligatorio por `.claude/CLAUDE.md`).
- [ ] **[P]** Las 6 tareas del Task Scheduler no son verificables desde el repositorio.
- [ ] Runbook de fallos: qué hacer si el run diario falla.
- **Evidencia:** diff documentación ↔ configuración, campo por campo.

## 10. Archivos y módulos que exigen la revisión más profunda

Prioridad por (consecuencia del fallo × densidad de lógica × evidencia ausente):

| # | Archivo | Símbolos | Razón |
|---|---|---|---|
| 1 | `src/sqp/pipeline/probabilities.py` | `_consensus_lines:17`, `_novig_probs:46`, `_decision_probability:101` | **[C]** Hueco de `NaN` confirmado y vivo en producción. 124 líneas que condicionan todo lo demás. |
| 2 | `src/sqp/pipeline/daily.py` | `run_league:476`, `apply_global_exposure_cap:245`, `_zero_stake_flag:373` | 740 líneas, 19 funciones. Orquesta todas las capas de riesgo. |
| 3 | `src/sqp/backtesting/roi_engine.py` | `load_closing_odds:52`, `_match_index:111`, `realized_roi_backtest:187` | Produce la cifra OOS que decide todo; precedente confirmado de leakage (KI-019). |
| 4 | `src/sqp/calibration/calibrator.py` | `train_calibration:170`, `auto_promote_calibrators:423`, `calibrate_probability:523` | 530 líneas; puede alterar probabilidades servidas sin humano. |
| 5 | `src/sqp/settlement/runner.py` | `fetch_and_settle:389`, `_void_stale_served:176`, `history_scores_map:114` | 432 líneas; define el resultado observado. |
| 6 | `src/sqp/risk/degradation.py` | `evaluate_pauses:81`, `degradation_metrics:54` | Automatismo que pausa mercados solo. |
| 7 | `src/sqp/markets/edge.py` + `vig.py` | `adjusted_edge:32`, `remove_vig_power:21` | 100 líneas de las que cuelga el concepto de edge. |
| 8 | `src/sqp/storage/lock.py` | `locked:26` | **[C]** Sin test propio; único mecanismo de concurrencia. |
| 9 | `src/sqp/backtesting/tuning.py` | `rolling_origin_improvement:75`, `_gate:114` | Ajusta parámetros; **[P]** algunos en frontera de grilla (`README.md:176`). |
| 10 | `src/sqp/audit/html_report.py` | `html_dashboard:422` | 832 líneas — el mayor del proyecto; riesgo de mantenibilidad, no de corrección. |

## Restricciones de la auditoría

Heredadas de `.claude/CLAUDE.md` y `.claude/automation/autonomy-policy.md`:

1. **No escanear** `data/`, `historical/`, `logs/`, `exports/`.
2. **No consumir cuota** de The Odds API sin autorización explícita.
3. **No cambiar** `shadow_mode`, parámetros de riesgo ni promover calibradores.
4. **No declarar `PASS` sin evidencia observable** (`STATES.md`; **[P]** A-1 de la
   auditoría anterior documenta tres violaciones en tres días).
5. Lenguaje obligatorio: probabilidad estimada; nunca certeza ni ganancia
   garantizada; hit rate siempre contra su punto de equilibrio.

## Qué NO puede establecer esta auditoría

Dicho por delante para que ningún entregable lo sugiera:

- **Si el sistema gana dinero.** Ninguna fase mide eso. **[P]** El hecho dominante
  sigue siendo la ausencia de ventaja predictiva demostrada.
- **Ausencia de leakage.** Se pueden encontrar leaks; no se puede demostrar que no
  quedan.
- **El contenido de `data/`.** Bloqueado por regla permanente.
- **El estado del Task Scheduler.** Fuera del repositorio.
