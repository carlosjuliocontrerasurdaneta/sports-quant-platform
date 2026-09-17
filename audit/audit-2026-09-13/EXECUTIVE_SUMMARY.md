# Resumen ejecutivo — Auditoría integral 2026-09-13

## 1. Propósito, arquitectura y estado general

**Propósito.** Estimar probabilidades pregame (h2h / spreads / totals) para
todos los deportes y ligas soportados, publicar diariamente la lista completa
de picks ordenada por probabilidad y, aparte, decidir por gate qué mercado
puede llevar stake real. Hoy ningún mercado lo lleva: el gate de predicción
(pre-registro 2026-08-16, Bonferroni 2026-09-04) niega los 47 cortes por
`muestra_insuficiente` (máximo n = 203 en `mlb|h2h/spreads`, umbral 300).

**Arquitectura.** Python 3.14 (`src/sqp`, 101 módulos, 18.078 líneas), 62
scripts operativos, 9 BAT + 2 PowerShell + 1 CMD, 5 tareas del Programador de
Windows, 258 ficheros de tests (1.965 pruebas), un sistema de Skills/agentes/
hooks para Claude Code (26 skills, 27 agentes, 17 comandos, 26 loops, 7 hooks) y
un vault Obsidian. Proveedores: The Odds API (cuotas, marcadores), ESPN
(resultados, tenis), MLB Stats API (abridores), Open-Meteo (clima, apagado).

**Estado general.** Código en buen estado: suite completa en verde (1.965
passed, 1 skipped), `ruff` y `mypy` limpios, remediación del 2026-09-10 intacta
(hashes verificados). Los problemas graves de esta ronda no son de código sino
de **custodia y operación**: el código que corre no está en ningún repositorio,
y la generación diaria dejó de ocurrir 4 de los últimos 7 días sin que nada lo
señalara.

## 2. Riesgos principales

1. **AUD-HIGH-001** — Producción es un árbol plano sin `.git`, con 94 ficheros
   modificados y 41 nuevos respecto a `main@a401f06` (GitHub, público, CI verde).
   El CI valida un código distinto del que opera; la única copia de las
   correcciones del 10 de septiembre es este disco; todos los guards basados en
   Git fallan abiertos.
2. **AUD-HIGH-002** — Sin run el 07, 08, 10 y 11 de septiembre. Las tareas son
   «Solo interactivo» (decisión del operador, B-07) y, además, el tablero al
   iniciar sesión se omite justo cuando el reporte no es de hoy, y el health
   check sólo corre dentro del orquestador ausente.
3. **AUD-MED-003 / AUD-MED-004** — El ledger `settled_*` gradúa sólo la última
   vista de candidatos: el 20,5 % de las unidades listadas entre el 16-08 y el
   08-09 nunca reciben veredicto (132 por refresco antes del partido, 18 por
   sobrescritura tras un fallo de liquidación que el guard M2 no ve porque sólo
   cuenta stake > 0). Con stake 0 es un sesgo en la métrica rectora; con stake
   real sería un ledger incorrecto.
4. **AUD-MED-001** — La revalidación pre-partido no evalúa ningún evento que
   empiece después de las 00:00Z del día de generación (2 de 115 frente a 195
   de 369).
5. **AUD-MED-002** — Líneas asiáticas de cuarto graduadas como enteras (1 caso
   ya mal graduado; 212 filas de evidencia del gate afectadas).
6. **AUD-MED-006** — La memoria persistente registra `PREDICTION_GATE_MIN_N =
   100` como decisión vigente; el código y el pre-registro dicen 300.
7. **AUD-MED-007** — Los hooks se arman con lecturas: esta auditoría, sin
   editar nada, disparará la suite y una llamada de pago a Codex al cerrar.

## 3. Conclusión

No hay defecto que hoy produzca un pick incorrecto o un stake indebido: la
cadena odds → modelo → no-vig → edge → Kelly → gates → ledger es coherente y
está bien protegida. Lo que la auditoría encuentra es que el sistema **no está
custodiado** (sin VCS) ni **vigilado** (sin señal de ausencia de run), y que
tres controles de segunda línea —revalidación, liquidación de picks
refrescados, guard de sobrescritura— tienen puntos ciegos medibles que sólo
son inocuos porque el gate mantiene todos los stakes a cero.

## 4. Limitaciones de esta ronda

- `logs/` y `.env` están vetados a la sesión (regla `deny`); el estado de los
  centinelas y la causa de los 8 minutos de AUD-INF-002 no se han visto.
- No se ha ejecutado `codex review` ni `pip-audit` ni `VALIDATE_OOS.bat`
  (consumo de cuota / escritura en producción).
- No se ha medido ninguna métrica cuantitativa viva (Brier, ECE, CLV); las
  cifras del ledger son históricas.
- Modo no orquestado: sin subagentes. La validación independiente de cada
  candidato se hizo con un segundo método en la misma sesión (código +
  medición sobre datos, o dos fuentes de hashes) y consta en cada hallazgo.

---

## Inventario

| Componente | Detalle |
|---|---|
| Paquete | `src/sqp` — 101 módulos: audit, backtesting, calibration, domain, evaluation, features, markets, models, monitoring, pipeline, providers, risk, settlement, simulation, sports, storage |
| Puntos de entrada | `DIARIO_COMPLETO.bat` → `SETTLE_ALL.bat` → `RUN_DIARIO_ALL.bat` (`scripts/run_all.py --mode live`) → `daily_picks.py`×3 → `tipster_report.py` → `health_check.py`; `CAPTURE_CLOSE.bat` (`capture_closing_odds.py` + revalidación + guard de abridores + observatorio intradía); `BACKFILL_ALL.bat`; `VALIDATE_OOS.bat`; `REFRESH_ML.bat`; `REVIEW_CALIBRATION_MLB_H2H.bat`; `open_dashboard.ps1` |
| Tareas programadas | `SQP_Diario_Completo_Cdev` (diaria 12:00, último 12-09 rc 0), `SQP_Capture_Close_Cdev` (PT30M, en ejecución, 08:00 rechazada 0x800710E0), `SQP_Backfill_Cdev` (semanal, 07-09 rc 0), `SQP_Validate_OOS_Cdev` (mensual, 01-09 **rc 1**, próxima 01-10), `SQP_Dashboard_Cdev` (al logon). Las 5 con `LogonType Interactive`, `ExecutionTimeLimit PT72H`, `IgnoreNew` |
| Configuración | `configs/default.yaml` (riesgo, gates, calibración, revalidación), `configs/leagues/*.yaml`, `configs/venues.yaml`, `.env` (presente; claves no leídas), `.env.example`; precedencia env > yaml para riesgo con aviso de divergencia |
| Configuración efectiva (no secreta) | kelly 0,08 · min_edge 0,02 · max_stake 2 % · max_plausible_edge 0,075 · market_shrink 0,5 · shadow_mode false · pick_mode edge · calibration auto (registro live: mlb_h2h_pergame/beta, mlb_spreads/beta, mlb_totals/iso, wnba_spreads/beta) · prediction_gate ON (0/47 permitidos) · clv_gate OFF · degradation ON (10 auto-pausados) · revalidation 120/90 min · TTL cuotas 1.200 s |
| Dependencias | `pyproject.toml` (numpy, pandas, scipy, scikit-learn, joblib, requests, pyyaml, python-dotenv; dev: pytest, pytest-cov, ruff, mypy), `requirements.lock` (constraints, Python 3.14.4 de producción) |
| Datos | `data/` 1.039 MB: odds 899 MB (76 CSV mensuales), calibration 13 MB (served/graded, 25 ligas, 24.324 graduadas), bets (1.360 liquidadas, ledger −84,25), historical 12,7 MB, models (12 joblib + staging), predictions (12 candidates, 30 predictions, 81 reportes HTML), cache 24 MB |
| Modelos | Elo/Poisson–Dixon-Coles/Bradley-Terry por adaptador de deporte; modelos ML `*_moneyline/totals_model.joblib` (mlb, nba, nfl, nhl; features 19 días de antigüedad, informativo); calibradores isotónico/beta por (liga, mercado) con staging → promoción humana |
| Tests | 258 ficheros, 1.965 pruebas (225 `slow`); `conftest.py` fija identidad git; demo aislado bajo `data/*/demo/` |
| CI/CD | `.github/workflows/ci.yml`: matriz 3.11–3.14 + Windows 3.12, ruff, mypy, pytest, pip-audit bloqueante, issue automático `ci-rojo` |
| Contenedores | `Dockerfile` (demo, 3.11; nadie lo construye — documentado) |
| Integraciones | The Odds API (retries, backoff, presupuesto de cuota, cache TTL, redacción de clave), ESPN (60 s), MLB Stats (timeout default), Open-Meteo (apagado) |
| Skills/instrucciones | `CLAUDE.md` ×2, `AGENTS.md`, `AGENTS Tipster.md`, 26 skills, 27 agentes (26 `model: opus`), 17 comandos, 26 loops, 7 hooks (+`_targets.py`), `.claude/automation/*`, `.claude/memory/*`, `.mcp.json` (graphify, deshabilitado en `settings.local.json`) |
| Documentación | `README.md`, `IMPLEMENTACION.md`, `REPO_DESCRIPTION.md`, `docs/` (36), `Obsidian/` (61), `audit/` (rondas 2026-09-08/10 preservadas) |
| Artefactos de auditoría previa | `BUILD_INFO.json`, `OPTIMIZATION.diff` (aplicado; 29 ficheros), `audit/latest/POST-REMEDIATION-HASHES.json` |

## Matriz de cobertura

| Área | Prioridad | Estado | Componentes | Método | Validación | Limitaciones |
|---|---|---|---|---|---|---|
| Pipeline diario (odds→modelo→edge→Kelly→gates→ficheros) | P0 | REVISADA | `pipeline/daily.py`, `probabilities.py`, `risk/kelly.py`, `markets/vig.py`, `markets/odds.py`, `run_all.py` | lectura completa + trazas de flujo | suite verde; medición de outputs 12-09 | — |
| Liquidación y ledger | P0 | REVISADA | `settlement/runner.py`, `settle.py`, `storage/served_store.py`, `risk/bankroll.py`, `settle_all.py` | lectura + recomputación sobre `settled_*`, `graded_*`, `archive/` | AUD-MED-002/003/004 medidos | scores históricos faltan en 6 filas |
| Gates (predicción, CLV, degradación) | P0 | REVISADA | `risk/prediction_gate.py`, `clv_gate.py`, `degradation.py`, `data/bets/*.json` | lectura + inspección del registro vivo | 0/47 permitidos; 10 pausados | — |
| Calibración | P0 | REVISADA | `calibration/calibrator.py`, `data.py`, `data/models/*` | lectura + `structural_defect` sobre los 6 joblib live | 1 colapsado inerte | métricas OOS no recomputadas |
| Revalidación / captura de cierre / intradía | P1 | REVISADA | `pipeline/revalidation.py`, `closing_capture.py`, `intraday_scan.py`, `capture_closing_odds.py` | lectura + medición en `settled_*` | AUD-MED-001 | log denegado |
| Limpieza / retención | P1 | REVISADA | `pipeline/cleanup.py`, `purge_artifacts.py` | lectura + tamaños medidos | AUD-LOW-001/002 | — |
| Proveedores externos | P1 | REVISADA | `providers/odds_api.py`, `odds_cache.py`, `espn_*`, `mlb_statsapi.py`, `features/weather.py` | lectura (timeouts, retries, cache, redacción) | sin llamadas externas | comportamiento real ante caída no reproducido |
| Configuración efectiva | P1 | REVISADA | `config.py`, `default.yaml`, `.env` (vía `Settings.load()`, sin imprimir secretos) | carga programática | valores listados arriba | `.env` no leído |
| Scripts BAT / PS1 / CMD | P1 | REVISADA | 9 `.bat`, `rotate_log.cmd`, `open_dashboard.ps1`, `register_dashboard_task.ps1` | lectura línea a línea | AUD-HIGH-002, AUD-MED-005 | — |
| Tareas programadas (inventario **y estado**) | P0 | REVISADA | 5 `SQP_*` | `Get-ScheduledTask`/`Info`, `Win32_Process` | estados y últimos rc consignados | log de eventos del Programador vacío/no habilitado |
| CI/CD (inventario **y estado**) | P1 | REVISADA | `ci.yml`, remoto GitHub | lectura + `gh run list`, `gh issue list`, `gh api` | verde para `a401f06`; **no cubre el árbol de producción** | — |
| Dependencias / lock | P1 | REVISADA_PARCIALMENTE | `pyproject.toml`, `requirements.lock`, `Makefile`, `Dockerfile` | lectura + coherencia | `pip-audit` no ejecutado (red) | vulnerabilidades no evaluadas localmente |
| Tests (calidad, aislamiento, skips) | P1 | REVISADA | 258 ficheros; `conftest.py`; marcadores `slow` | ejecución completa aislada (`--basetemp`, `-p no:cacheprovider`) + mtimes de `data/` | 1.965 passed; escritura sólo en `demo/` | 1 skip (node ausente) |
| Seguridad | P1 | REVISADA | secretos, `settings.json` allow/deny, hooks `check-secrets`, cache de cuotas, `shell=True`, deserialización joblib | grep dirigido + lectura | sin claves literales; sidecar sha256 (bypass si falta sidecar, aceptado) | — |
| Datos y persistencia | P0 | REVISADA | `storage/atomic.py`, `lock.py`, `odds_store`, CSV append-only | lectura + escaneo de duplicados/NaN | 0 duplicados en `DEDUP_KEY`, 0 pnl NaN | — |
| Rendimiento | P2 | REVISADA_PARCIALMENTE | carga de cuotas en `daily`, revalidación | medición dirigida (mlb 9,1 s / 342 MB) | AUD-LOW-003 | sin perfilado del run completo |
| Modelos / features / leakage | P0 | REVISADA_PARCIALMENTE | `features/*`, `models/*`, `backtesting/*`, `calibration/data.py` | lectura de cortes temporales (`ref_date`, `group_col`, `time_col`) | sin hallazgo nuevo; cortes vigentes desde AUD-LOW-005 (09-06) | no se re-ejecutó ningún backtest ni OOS |
| Sistema de Skills / hooks / memoria | P1 | REVISADA | 26 skills, 27 agentes, hooks, `settings.json`, `.claude/memory/*`, `.mcp.json` | frontmatter programático + lectura de hooks + verificación de rutas referenciadas + observación de centinelas | AUD-MED-006/007, AUD-LOW-004 | `codex review` no ejecutado |
| Documentación | P2 | REVISADA_PARCIALMENTE | docstrings, BAT, `README`, memoria | contraste puntual con disparadores y código | AUD-LOW-004 | README no contrastado línea a línea |
| Limpieza y racionalización | P2 | REVISADA | residuos en `data/predictions`, `data/models`, artefactos sin retención, referencias muertas | inventario + búsqueda de consumidores | tabla en BACKLOG.md | ninguna eliminación propuesta sobre datos sin aprobación |
| Contenedores | P3 | REVISADA | `Dockerfile` | lectura | documentado como demo no construida | no construido |
| Logs | P1 | NO_VERIFICABLE | `logs/**` | — | — | regla `deny` de `settings.json` |
| Obsidian (contenido) | P3 | EXCLUIDA | `Obsidian/` | — | — | fuera del alcance de código; sólo se leyó la bitácora 09-12 para contexto |
