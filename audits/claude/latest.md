# Auditoría técnica integral — Claude Code / Opus 5

- **Proyecto:** Sports Quant Platform (`sqp`)
- **Fecha de ejecución:** 2026-09-14 (08:15–09:40, hora local)
- **Commit auditado:** `8503b7a` (`main`, árbol limpio salvo `audits/` sin versionar)
- **Auditor:** Claude Opus 5 (agente principal) con cuatro subagentes de solo lectura (`fable`, `opus`, `opus`, `sonnet`); uno abortado por límite de cuota del API sin producir salida y cubierto por el agente principal
- **Protocolo:** `audits/prompts/auditoria-claude-code-opus-5.md`
- **Informe anterior:** ninguno (primera ejecución del ciclo)
- **Modificaciones al proyecto:** ninguna (solo este informe y el registro de enrutamiento en `.claude/automation/runtime/current-task.md`)

## 1. Resumen ejecutivo

El repositorio está en un **estado técnico maduro**: `ruff`, `mypy` y la suite completa (2.013 pruebas) pasan en el intérprete real de producción (Python 3.14.4); `pip-audit` sobre el lock no encuentra vulnerabilidades; el historial git no contiene secretos; la matemática de cuotas, no-vig, edge, Kelly y liquidación está acotada y probada en los bordes; los controles de riesgo son allow-lists default-deny en capas y hoy **ningún mercado lleva stake real** (gate de predicción: 47 cortes evaluados, 0 permitidos). No se encontró ningún defecto que altere hoy probabilidades, edge, stakes ni liquidación, ni fuga temporal.

Se registran **12 hallazgos** (0 críticos, 0 altos, **5 medios**, 7 bajos) y 10 observaciones no puntuadas. **P0: 0 · P1: 0.** Los medios:

| ID | Hallazgo | Punt. | Prio. |
|---|---|---|---|
| AUD-002 | `_merge_results` descarta el 2.º partido de una serie de días consecutivos del mismo par (reproducido): ratings desactualizados hasta el backfill semanal | 65,0 | P2 |
| AUD-001 | El backtest de ROI no recibe tres términos de `adjusted_edge` (movimiento de línea, velocidad, dispersión entre casas) que producción sí aplica; inerte hoy (coeficientes a 0), pero es el instrumento con el que se decidiría activarlos | 63,8 | P2 |
| AUD-004 | La revalidación carga ficheros mensuales de cuotas dentro del lock; el umbral de "huérfano" (300 s) no se refresca y podría romper un lock vivo | 52,5 | P3 |
| AUD-005 | Seis ficheros de test escriben en el árbol real (`data/predictions/demo`, `data/calibration/demo`); `conftest.py` no impone aislamiento | 52,5 | P3 |
| AUD-003 | `predictions_<liga>.csv` se escribe fuera del lock y `os.replace` lanza `PermissionError` en Windows si un lector lo tiene abierto (reproducido); tareas co-programadas a las 12:00 | 47,5 | P3 |

Los siete bajos son controles con cobertura parcial (sidecar de integridad ausente en 3 de 4 calibradores live; instalador de hooks desincronizado; 4 interpolaciones HTML sin escapar; filtro del detector de secretos) e higiene de infraestructura (ciclo de imports conocido; manifiesto `BUILD_INFO.json` y parche `OPTIMIZATION.diff` obsoletos versionados; CI sin Windows+3.14 y con acciones por tag mutable).

**Limitaciones materiales:** (L1) `pip-audit` con resolución completa no reproducible localmente (se usó `--no-deps`); (L2) `.env` y `logs/` inaccesibles por política del proyecto, por lo que la materialización histórica de AUD-003 no pudo comprobarse; (L3) no se ejecutó ningún `.bat` ni tarea programada. Detalle en §4.

## 2. Alcance

- **Repositorio:** `C:\dev\3\sports-quant-platform`, rama `main`, HEAD `8503b7a` (árbol limpio salvo `audits/` sin versionar).
- **Incluido:** `src/sqp` (101 módulos, 18.360 líneas), `scripts/` (61 scripts Python + 3 `.ps1` + 1 `.cmd`), 10 `.bat` de orquestación, `tests/` (127 ficheros, 27.123 líneas, 2.014 pruebas recolectadas), `configs/` (5 YAML), `.github/workflows/ci.yml`, `Dockerfile`, `Makefile`, `pyproject.toml`, `requirements.lock`, `.claude/hooks` y `.claude/settings.json` (controles de gobernanza), estado de los registros de gate (`data/bets/*.json`, ficheros pequeños), metadatos de `data/models/` y `data/odds/` (solo tamaños/nombres), Programador de tareas de Windows (solo lectura).
- **Excluido por regla del protocolo:** `audit/` (informes de otro auditor), `audits/openai/`, `audits/consolidated/` (no existen todavía; no se leyeron). No existe informe Claude previo en `audits/claude/`.
- **Excluido por regla del proyecto:** contenido de `.env`, `logs/` y datasets completos de `data/` (los hooks de permisos del proyecto lo bloquean; solo se usaron agregados programáticos y metadatos).
- **No incluido:** `Obsidian/` (base de conocimiento), `docs/research/` (14 pre-registros), `.claude/skills|loops|agents` (sistema de instrucciones) salvo lo necesario para entender la gobernanza; `graphify-out/`.

## 3. Metodología

1. Inventario: árbol, manifiestos, CI, orquestadores, tabla de configuración, puntos de entrada.
2. Línea base ejecutada en el intérprete de producción (Python 3.14.4, mismas versiones que `requirements.lock`): `ruff check`, `mypy src`, `pytest -q` completo, `pip-audit`.
3. Lectura directa del núcleo por el agente principal: `pipeline/daily.py` íntegro, `markets/{odds,vig,edge}.py`, `risk/kelly.py`, `storage/{atomic,lock}.py`, `scripts/{run_all,settle_all}.py`, `DIARIO_COMPLETO.bat`, `CAPTURE_CLOSE.bat`, `ci.yml`, `Dockerfile`, `configs/default.yaml`, `pipeline/{budget,cleanup,revalidation(parcial)}.py`, `risk/prediction_gate.py` (parcial), `calibration/calibrator.py` (carga de artefactos), `audit/{report,html_report}.py` (parcial).
4. Cuatro subagentes de solo lectura sobre áreas independientes (§4 del protocolo), con modelo asignado según la regla de despacho del proyecto: lógica cuantitativa (`fable`), datos/proveedores/robustez (`opus`), operaciones/infraestructura/seguridad (`opus`), calidad de la suite de pruebas (`sonnet`). Cada candidato reportado por un subagente fue **revalidado por el agente principal** contra el código actual antes de entrar en el informe; los que no superaron la revalidación se descartaron o se degradaron a observación.
5. Reproducciones locales no destructivas en el directorio temporal de la sesión (nunca bajo `data/`): `os.replace` sobre fichero abierto en Windows; verificación de hashes de `BUILD_INFO.json`; grafo AST de imports (ciclos, fan-in); medición de `read_csv` sobre el mayor fichero mensual de cuotas; comprobación `git apply --check --reverse` de `OPTIMIZATION.diff`.
6. Clasificación con la matriz del protocolo (§11), confianza (§12) y prioridad (§13) por separado; deduplicación por causa raíz.

## 4. Limitaciones

| # | Limitación | Efecto |
|---|---|---|
| L1 | `pip-audit -r requirements.lock` (resolución completa, el comando del CI) falló en el venv temporal local: `No matching distribution found for ruff==0.15.14` (el índice sí lista la versión; fallo del resolutor efímero bajo 3.14). Se ejecutó `pip-audit -r requirements.lock --no-deps` → **sin vulnerabilidades conocidas**. | La auditoría de dependencias transitivas queda cubierta solo por los pines explícitos del lock (que incluye las transitivas principales) y por el CI en ubuntu. |
| L2 | El contenido de `.env` y del árbol `logs/` está bloqueado por los hooks de permisos del proyecto (deny `Read(./.env)`, `Read(./logs/**)`). | No se pudo comprobar en los logs si la colisión de escritura descrita en AUD-003 se ha materializado alguna vez; se declara como riesgo con reproducción sintética, no como incidente observado. |
| L3 | No se ejecutaron los `.bat` ni ninguna tarea programada (prohibido por §3: operaciones sobre datos reales). Los contratos de aborto se verificaron por lectura del código y de la configuración real del Programador (`Get-ScheduledTask`, solo lectura). | Las conclusiones sobre orquestación son de evidencia directa sobre el código, indirecta sobre el comportamiento en ejecución. |
| L4 | La imagen Docker no se construyó (el propio `Dockerfile` declara que nadie la construye y que es solo demo). | Sin evidencia de que la imagen compile hoy. |
| L5 | No existe informe Claude anterior en `audits/claude/`; la comparación histórica (§30) es por tanto "primera ejecución". | Todos los hallazgos se clasifican como *Nuevo*. |
| L6 | Cobertura porcentual no medida: `--cov` aborta en 3.14 (documentado en `pyproject.toml`) y el protocolo pide no usar el porcentaje global. | La evaluación de pruebas es por inspección de flujos críticos. |

## 5. Inventario y cobertura

### 5.1 Componentes

| Elemento | Detalle | Estado |
|---|---|---|
| Paquete principal | `src/sqp` — 16 subpaquetes: `pipeline`, `markets`, `models`, `risk`, `calibration`, `settlement`, `backtesting`, `providers`, `storage`, `sports`, `features`, `evaluation`, `audit`, `monitoring`, `simulation`, `domain` | Inspeccionado (núcleo íntegro; periferia por subagentes) |
| Puntos de entrada de producción | `DIARIO_COMPLETO.bat` → `SETTLE_ALL.bat` (`scripts/settle_all.py`) → `RUN_DIARIO_ALL.bat` (`scripts/run_all.py --mode live`); `CAPTURE_CLOSE.bat` (`scripts/capture_closing_odds.py`, cada 30 min); `BACKFILL_ALL.bat` (semanal); `VALIDATE_OOS.bat` (mensual) | Inspeccionados |
| Tareas programadas (Windows, S4U) | `SQP_Diario_Completo_Cdev` 12:00 diaria; `SQP_Capture_Close_Cdev` cada 30 min desde 12:30 (→ dispara a :00 y :30, incluido 12:00); `SQP_Backfill_Cdev` semanal 10:00; `SQP_Validate_OOS_Cdev` mensual (último resultado **1** el 2026-09-01); `SQP_Dashboard_Cdev` al logon (interactiva) | Inspeccionadas en solo lectura |
| CLI manual | `scripts/run_daily.py`, `run_backtest.py`, `list_sports.py`, `bankroll_status.py`, `gate_status.py`, `promote_calibration.py`, `train_calibration.py`, `price_independent.py` | Localizados; `run_daily`/`price_independent` no inspeccionados en profundidad |
| Integraciones externas | The Odds API (cuotas y scores, pago, clave por `.env`), MLB Stats API (abridores, pública), ESPN (resultados/tenis, no oficial), Open-Meteo (clima, **desactivado**) | Inspeccionadas (cliente Odds API íntegro) |
| Modelos/artefactos | `data/models/`: 4 calibradores live (`mlb_h2h_pergame`, `mlb_spreads`, `mlb_totals`, `wnba_spreads`) + 8 modelos ML experimentales (sin consumidor en producción) + `registry.json` | Metadatos inspeccionados; contenido no deserializado |
| Registros de estado | `data/bets/prediction_gate.json` (47 cortes evaluados, **0 permitidos**, K=41, α=0,00122, n_min=300), `clv_gate.json` (0 permitidos, gate desactivado), `degradation_pause.json` (11 mercados auto-pausados) | Leídos (JSON pequeños) |
| Esquemas/almacenes | CSV mensuales `data/odds/odds_<liga>_<AAAAMM>.csv` (mes en curso: 19 ficheros, 214 MB), `data/predictions/{predictions,candidates}_<liga>.csv`, `data/bets/settled_<liga>.csv`, `data/calibration/served_*`/`graded_*`, `data/historical/results_*` | Solo metadatos (tamaños, cabeceras) |
| Configuración | `configs/default.yaml`, `configs/leagues/{ratings,soccer,team_aliases}.yaml`, `configs/venues.yaml`; precedencia documentada en `docs/CONFIG-PRECEDENCE.md` y verificada en `config.py` (`_env_flag` para los booleanos) | Inspeccionada |
| CI/CD | `.github/workflows/ci.yml`: matriz 3.11–3.14 (ubuntu), `test-windows` en 3.12, ruff, mypy (3.12), pytest, cobertura informativa (3.12), `pip-audit` bloqueante, job `alerta-ci-rojo` | Inspeccionado |
| Contenedor | `Dockerfile` (demo, 3.11-slim, usuario sin privilegios) | Inspeccionado; no construido |
| Gobernanza del asistente | `.claude/settings.json` (deny sobre `.env`, `logs/`, `data/**`; hooks `PreToolUse(Agent)`, `PostToolUse(check-secrets, mark-tests-pending, ...)`, `Stop(run-tests-on-stop, crossreview-on-stop)`) | Inspeccionado |
| Pruebas | 127 ficheros, 1.679 funciones `def test` (2.014 casos con parametrización), marcador `slow` (25 usos, **no** excluido en CI), `conftest.py` de 44 líneas | Inspeccionadas por subagente + revalidación |
| Documentación | `README.md`, `IMPLEMENTACION.md`, `REPO_DESCRIPTION.md`, `AGENTS.md`, `docs/*.md`, `Obsidian/` | README/IMPLEMENTACION/CONFIG-PRECEDENCE leídos; resto localizado |
| Autenticación/autorización | No aplica: aplicación local sin servidor ni usuarios; la única credencial es la clave de The Odds API | — |
| Base de datos/migraciones/colas | No existen: persistencia en CSV/JSON/joblib con escritura atómica y lock de fichero | — |

### 5.2 Cobertura declarada

- **Inspeccionados en profundidad:** `pipeline/daily.py`, `pipeline/probabilities.py`, `markets/*`, `risk/*`, `settlement/settle.py`, `settlement/runner.py`, `calibration/*`, `backtesting/*`, `models/*`, `sports/*`, `evaluation/*`, `storage/*`, `providers/*`, `config.py`, `pipeline/{budget,cleanup,revalidation,closing_capture,intraday_scan}.py`, `monitoring/*`, `audit/{report,clv,segments,patterns}.py`, `scripts/{run_all,settle_all,settle_bets,capture_closing_odds,update_prediction_gate,health_check,run_status,setup_local,purge_artifacts}.py`, todos los `.bat`, `.ps1`, hooks, CI, Dockerfile, `tests/` (por patrones y ficheros críticos).
- **Localizados, no inspeccionados en profundidad:** `audit/html_report.py` (1.583 líneas; solo revisión de escape HTML: 33 usos de `html.escape`, sin interpolación sin escapar detectada por grep), `features/*` (capa de ajustes inerte: todos los coeficientes a 0), `models/ml_*` (sin consumidor), ~35 scripts de investigación/medición en `scripts/`, `scripts/ai/`.
- **Excluidos:** `audit/`, `Obsidian/`, `docs/research/`, `graphify-out/`, `.claude/skills|loops|agents`.

No se declara cobertura del 100 %.

## 6. Arquitectura

Flujo de producción (verificado en `daily.run_league` y `run_all.main`):

```
/sports (activas) → guard de presupuesto (cuota real / días restantes) → por liga:
  resultados (ResultsStore ∪ /scores recientes, dedup ±1 día) → adapter.fit_results (Elo + distribución por familia)
  → /odds (5 regiones, 3 mercados; caché TTL acotado por la política de frescura)
  → consenso (mediana) → no-vig (proporcional/power) → p_model → ajustes (inertes) → calibración (si hay calibrador live)
  → blend p_decision = (1-s)·cal(p_adj) + s·fair (s = 0,5) → edge crudo → adjusted_edge (penalización por desacuerdo)
  → Kelly fraccional (0,08) con topes → cadena de stake 0: cuota_vencida > paused > incomplete > suspect > shadow > prediction_gate > clv_gate
  → served stream (todas las caras) + candidates (solo los que llevarían stake) → cap de exposición por liga
→ cap global → informes md/HTML → auditoría de liquidación → CLV → prediction gate (reescrito para el PRÓXIMO run) → recalibración a STAGING.
```

Observaciones estructurales:

- **Separación de responsabilidades** clara por subpaquete; los helpers de probabilidad están compartidos entre producción y backtest (`build_model_map`, `adjust_model_probability`, `build_adjustment_context`) y esa paridad está fijada por identidad de objeto en `tests/test_backtest_parity.py`. La paridad **no** cubre los argumentos de `adjusted_edge` (ver AUD-001).
- **Dependencias:** 101 módulos, 221 aristas intra-paquete (grafo AST). **0 ciclos a nivel de módulo** (imports de cabecera). Existe **1 ciclo de 5 módulos** cerrado por un import diferido y documentado en el propio código (`daily → markets.line_movement → audit.clv_movement → audit.clv → backtesting.roi_engine → daily`); ver AUD-009.
- **Mayor fan-in:** `logging_config` (30), `config` (20), `storage.atomic` (19), `domain.models` (9), `pipeline.daily` (7), `storage.lock` (7).
- **Puntos únicos de fallo:** `pipeline/daily.py` (983 líneas) concentra la ruta del dinero; The Odds API es proveedor único de cuotas y scores (sin proveedor secundario configurado); la máquina Windows única con Task Scheduler es el único entorno de ejecución.
- **Estado por diseño:** persistencia en ficheros planos con `atomic_write_csv/json` + lock sidecar `O_EXCL`; no hay base de datos ni transacciones.
- **Inconsistencias de diseño detectadas:** `predictions_<liga>.csv` se escribe fuera del lock que protege `candidates_<liga>.csv` (AUD-003); el backtest de ROI no recibe tres términos del penalizador (AUD-001).

## 7. Estado técnico general

| Puerta | Comando | Resultado |
|---|---|---|
| Lint | `python -m ruff check src scripts tests` | **All checks passed** (exit 0) |
| Tipos | `python -m mypy src` | **Success: no issues found in 101 source files** (exit 0) |
| Pruebas | `python -m pytest -q -p no:cacheprovider` (Python 3.14.4, intérprete de producción) | **2013 passed, 1 skipped** en 26 min 11 s (exit 0). El skip es `tests/test_open_dashboard.py` (requiere entorno específico). |
| Dependencias | `python -m pip_audit -r requirements.lock --no-deps` | **No known vulnerabilities found** (exit 0); la variante con resolución falló (L1) |
| Git | `git status` | Limpio salvo `audits/` (sin versionar); 517 commits; ningún `.env` ni cadena tipo clave en el historial (`git log --all --name-only` + `git grep` hex32) |

Valoración: el proyecto está en un estado técnico **maduro y disciplinado** para su tamaño. Las tres puertas de calidad pasan en el intérprete real de producción, las fórmulas de mercado y de riesgo están acotadas y probadas, los controles default-deny (prediction gate, CLV gate, shadow) están implementados como allow-lists con registro ausente → deny, y el código documenta y protege con pruebas la mayoría de los incidentes previos. Los hallazgos de esta auditoría son de **severidad media y baja**: brechas de paridad latentes, una condición de carrera específica de Windows, coberturas parciales de controles y artefactos obsoletos versionados. No se encontró ningún defecto confirmado que altere hoy las probabilidades, el edge, los stakes (todos 0 por el gate) ni la liquidación.
## 8. Tabla maestra

Fórmula (§11): `Puntuación = (I×30 + A×20 + P×20 + E×15 + R×10 + C×5) / 4`. Severidad y confianza son independientes; prioridad es independiente de ambas.

| ID | Título | Categoría | Área | I | A | P | E | R | C | Punt. | Severidad | Prioridad | Confianza | Validación |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AUD-001 | El backtest de ROI no recibe tres términos del penalizador de edge que sí usa producción | Riesgo potencial | Lógica/Backtesting | 3 | 3 | 2 | 2 | 2 | 3 | 63,8 | Media | P2 | Alta | Verificado por lectura + grep (sin test de paridad) |
| AUD-002 | `_merge_results` descarta el 2.º partido de una serie de días consecutivos del mismo par de equipos | Defecto confirmado | Lógica/Datos | 2 | 2 | 4 | 4 | 1 | 2 | 65,0 | Media | P2 | Alta | Reproducido localmente |
| AUD-003 | `predictions_<liga>.csv` se escribe fuera del lock y `os.replace` falla en Windows si el destino está abierto; tareas co-programadas a las 12:00 | Riesgo potencial | Robustez/Concurrencia | 2 | 2 | 2 | 2 | 1 | 2 | 47,5 | Media | P3 | Media | `PermissionError` reproducido sintéticamente; solape verificado en el Programador; logs no accesibles |
| AUD-004 | La sección crítica de revalidación carga ficheros mensuales de cuotas bajo el lock; el umbral de "lock huérfano" (300 s) no se refresca | Riesgo potencial | Robustez/Concurrencia | 3 | 2 | 1 | 2 | 2 | 2 | 52,5 | Media | P3 | Media | Medido: 6,3 MB/s; mes en curso 214 MB |
| AUD-005 | Seis ficheros de test ejecutan `run_league(..., mode="demo")` contra el árbol real y `conftest.py` no impone aislamiento | Deuda técnica | Pruebas | 1 | 1 | 4 | 4 | 1 | 2 | 52,5 | Media | P3 | Alta | mtimes observados durante la suite |
| AUD-006 | 3 de los 4 calibradores live (12 de 13 artefactos `.joblib`) carecen de sidecar `.sha256`: la verificación de integridad se omite | Riesgo potencial | Seguridad/Modelos | 2 | 1 | 1 | 1 | 2 | 3 | 37,5 | Baja | P3 | Alta | `ls data/models` + lectura de `_verify_hash` |
| AUD-007 | `instalar-candados.sh` reinstala versiones obsoletas de dos hooks y revertiría correcciones ya aplicadas | Deuda técnica | Infraestructura/Gobernanza | 1 | 1 | 2 | 3 | 1 | 1 | 37,5 | Baja | P3 | Alta | Diff heredoc vs hooks vivos |
| AUD-008 | Dashboard HTML: cuatro interpolaciones en JS cliente sin `esc` (`market`, `fecha`, `motivo`) | Riesgo potencial | Seguridad | 2 | 1 | 1 | 1 | 1 | 2 | 33,8 | Baja | P3 | Alta (código) / Baja (explotabilidad) | Lectura directa |
| AUD-009 | Ciclo de importación de 5 módulos sostenido por un import diferido | Deuda técnica | Arquitectura | 1 | 2 | 1 | 2 | 1 | 2 | 35,0 | Baja | P4 | Alta | Grafo AST (Tarjan) |
| AUD-010 | Artefactos de entrega obsoletos versionados: `BUILD_INFO.json` (106 hashes no cuadran, 45 ficheros ausentes) y `OPTIMIZATION.diff` (parche ya integrado) | Deuda técnica | Infraestructura/Repositorio | 1 | 1 | 2 | 2 | 1 | 4 | 37,5 | Baja | P4 | Alta | Recalculado SHA-256; `git apply --check --reverse` |
| AUD-011 | CI: acciones ancladas por tag mutable, `pip-audit` sin pin, sin ejercicio de `.bat`/Docker, pata Windows solo en 3.12 | Deuda técnica | Infraestructura/CI | 1 | 2 | 1 | 2 | 1 | 2 | 35,0 | Baja | P4 | Alta | Lectura de `ci.yml` |
| AUD-012 | `check-secrets.sh` descarta la línea entera cuando contiene una palabra de "ruido"; no hay segunda puerta en CI | Deuda técnica | Seguridad | 2 | 1 | 1 | 2 | 2 | 1 | 38,8 | Baja | P4 | Alta | Lectura del hook |

**Totales:** Crítica 0 · Alta 0 · Media 5 · Baja 7 · Informativa 0 (más 10 observaciones no puntuadas en §13). **P0: 0 · P1: 0** · P2: 2 · P3: 6 · P4: 4.

## 9. Hallazgos críticos

Ninguno.

## 10. Hallazgos altos

Ninguno.

## 11. Hallazgos medios

### AUD-001 — El backtest de ROI no recibe tres términos del penalizador de edge que sí usa producción

- **Categoría:** Riesgo potencial · **Área:** Lógica de negocio / Backtesting · **Severidad:** Media (63,8) · **Prioridad:** P2 · **Confianza:** Alta
- **Estado de validación:** Verificado por lectura directa de ambas llamadas y por grep negativo sobre `roi_engine.py` y la suite; no reproducido en ejecución porque hoy los tres coeficientes valen 0 (el término es inerte).
- **Ubicación:** `src/sqp/backtesting/roi_engine.py:355-360` (`adjusted_edge(...)`, 5 argumentos con nombre) vs `src/sqp/pipeline/daily.py:860-874` (`adjusted_edge(...)`, 14 argumentos con nombre). Parámetros afectados definidos en `src/sqp/markets/edge.py:140-153`.
- **Evidencia (directa):** producción pasa `line_movement_pp`, `line_movement_penalty`, `line_movement_flat_pp`, `line_velocity_pp_per_h`, `line_velocity_penalty`, `line_velocity_flat_pp_per_h`, `books_spread`, `books_spread_penalty`, `books_spread_threshold`; el backtest pasa solo `uncertainty_penalty`, `anomaly_edge_gap`, `anomaly_extra_penalty`, `low_book_penalty`, `min_books_for_consensus`. `grep -n "line_movement\|books_spread\|line_velocity" src/sqp/backtesting/roi_engine.py tests/test_backtest_parity.py tests/test_roi_engine.py` → sin coincidencias. `roi_engine.py` tampoco calcula `_consensus_spread` ni `event_line_movement`.
- **Descripción:** el proyecto ya corrigió dos veces esta misma clase de divergencia producción↔backtest (F-10 para el mapa de mercados; AUD-MED-006 para la capa de ajustes) fijando helpers compartidos y un test de paridad por identidad de objeto. Los tres términos más recientes del penalizador quedaron fuera de ese contrato.
- **Causa raíz:** `adjusted_edge` se invoca con argumentos con nombre en dos sitios sin un helper compartido ni un test que compare la firma efectiva; `configs/default.yaml:35-49` documenta los tres coeficientes como "activar solo tras evidencia OOS", y la evidencia OOS se obtendría precisamente con el backtest que no los aplica.
- **Impacto:** al activar cualquiera de los tres coeficientes, `VALIDATE_OOS.bat`/`scripts/backtest_roi.py` medirían una política distinta de la desplegada (menos penalización → stakes Kelly mayores → ROI más optimista). Hoy no altera ninguna cifra.
- **Escenario de materialización:** el operador pone `books_spread_penalty: 0.5` para validar la señal; el backtest devuelve un ROI que no incluye la penalización; la decisión de activar/desactivar se toma sobre una cifra que no describe producción.
- **Controles existentes:** `tests/test_backtest_parity.py` (paridad de `build_model_map`, `adjust_model_probability`, `build_adjustment_context`); comentario en `roi_engine.py:352-354` que afirma "Same EV penalty as the live pipeline" (hoy parcialmente falso); coeficientes a 0.
- **Matriz:** I=3 (decisión de parámetro de riesgo sobre una medición que no describe producción) · A=3 (flujo principal de validación) · P=2 (posible: los coeficientes están declarados para activarse) · E=2 (requiere activar un coeficiente) · R=2 (repetir la validación) · C=3 (el test de paridad no cubre esta firma).
- **Cálculo:** (3×30 + 3×20 + 2×20 + 2×15 + 2×10 + 3×5)/4 = (90+60+40+30+20+15)/4 = 255/4 = **63,8**.
- **Recomendación:** extraer la construcción de los kwargs de `adjusted_edge` a un helper único en `pipeline/probabilities.py` (o `markets/edge.py`) que reciba `settings.risk`, `_lm` y `cons_spread`, y consumirlo desde `daily.py` y `roi_engine.py`; en el backtest, calcular `_consensus_spread` y `event_line_movement` con los mismos helpers (o pasar `None` explícitamente y documentar que el backtest no puede reproducir movimiento de línea).
- **Criterio de aceptación:** con los tres coeficientes puestos a un valor distinto de 0 en un fixture, el backtest y `run_league` producen el mismo `adjusted_edge`/`stake` para un evento sintético idéntico; `grep` de los nueve nombres de argumento devuelve una única definición.
- **Prueba de regresión sugerida:** en `tests/test_backtest_parity.py`, comprobar por `inspect.signature`/identidad que ambos módulos invocan el mismo helper de kwargs, y un test funcional con `books_spread_penalty=0.5` que exija igualdad de `adjusted_edge` entre ambas rutas.

### AUD-002 — `_merge_results` descarta el segundo partido de una serie de días consecutivos del mismo par de equipos

- **Categoría:** Defecto confirmado · **Área:** Lógica de negocio / Datos · **Severidad:** Media (65,0) · **Prioridad:** P2 · **Confianza:** Alta
- **Estado de validación:** Reproducido localmente con entradas sintéticas (comando en §32, R-3).
- **Ubicación:** `src/sqp/pipeline/daily.py:92-121` (`_merge_results`), en particular `:107` (`history_days = {k[:3] for k in seen}`) y `:114-117` (`if any((d, nk(r["home"]), nk(r["away"])) in history_days for d in _adjacent_days(day)): continue`).
- **Evidencia (directa):** con `history=[(2026-09-10, A, B)]` y `recent=[(2026-09-11T23:05Z, A, B), (2026-09-12T23:05Z, A, B)]`, la salida es `[('2026-09-10','h1'), ('2026-09-12','r3')]`: el partido del 11 desaparece. La tolerancia ±1 día se introdujo para el caso "mismo partido, fecha UTC ≠ fecha local" (`tests/test_results_backfill.py:103-110`), pero no distingue ese caso de "dos partidos distintos del mismo par en días consecutivos", que es la estructura normal de una serie de MLB (3-4 partidos seguidos, mismo local) y frecuente en NHL/NBA.
- **Descripción:** la clave de deduplicación entre fuentes es (día ±1, local, visitante). Un resultado reciente legítimo se elimina si el histórico ya contiene un partido del mismo par el día anterior o el siguiente.
- **Causa raíz:** dedup por proximidad de fecha sin ningún atributo discriminante del partido (marcador, `game_id` cruzado, hora de inicio); el histórico se rellena semanalmente (`BACKFILL_ALL.bat`) mientras `recent` cubre 3 días, así que la ventana de solape existe todos los días.
- **Impacto:** el ajuste de Elo/ratings omite resultados recientes reales durante hasta una semana (hasta el siguiente backfill); las probabilidades servidas (stream de calibración, gate de predicción) y los candidatos de ese periodo se calculan con ratings ligeramente desactualizados. La dirección del error es "ratings más antiguos", no fuga de futuro. No altera dinero hoy (todos los stakes son 0 por el gate), pero sí la evidencia con la que el gate decide.
- **Escenario de materialización:** serie MLB Lun-Mié entre A y B; el backfill semanal cubrió hasta el lunes; el martes por la noche `/scores` devuelve el partido del martes → se descarta; el miércoles el modelo estima el tercer partido sin el resultado del martes.
- **Controles existentes:** backfill semanal (`SQP_Backfill_Cdev`) que acaba incorporando los partidos al histórico; `MIN_RESULTS_FOR_RATINGS` (aviso, no bloqueo). Tests: `test_merge_results_tolerates_utc_date_drift` y `test_merge_results_keeps_doubleheaders_history_wins_per_day` (no cubren series de días consecutivos).
- **Matriz:** I=2 (probabilidades servidas con ratings desactualizados; alimenta calibración y gate) · A=2 (todas las ligas con `has_scores` y series consecutivas) · P=4 (ocurre en cada serie) · E=4 (trivial, sin condición especial) · R=1 (se autocorrige con el backfill) · C=2 (backfill semanal parcial).
- **Cálculo:** (60+40+80+60+10+10)/4 = 260/4 = **65,0**.
- **Recomendación:** exigir, para descartar una fila reciente por día adyacente, una coincidencia adicional que identifique el mismo partido (marcador idéntico `home_score/away_score`, o la hora de inicio dentro de ±6 h del partido histórico si el histórico la tiene); mantener el descarte por día exacto tal como está. Alternativa: comparar fechas locales convirtiendo `commence_time` a la zona del local (venues) antes de deduplicar.
- **Criterio de aceptación:** el caso reproducido devuelve 3 filas (10, 11, 12) y el caso `test_merge_results_tolerates_utc_date_drift` sigue devolviendo 1.
- **Prueba de regresión sugerida:** `test_merge_results_keeps_consecutive_day_series` con histórico `(D, A, B, 3-2)` y recientes `(D+1, A, B, 1-5)`, `(D+2, A, B, 4-0)` → 3 resultados; y una variante con mismo marcador y ±1 día → 1 resultado.

### AUD-003 — `predictions_<liga>.csv` se escribe fuera del lock, `os.replace` falla en Windows sobre un destino abierto y hay tareas co-programadas a las 12:00

- **Categoría:** Riesgo potencial · **Área:** Robustez / Concurrencia / Operaciones · **Severidad:** Media (47,5) · **Prioridad:** P3 · **Confianza:** Media
- **Estado de validación:** `PermissionError [WinError 5]` reproducido sintéticamente con `atomic_write_csv` sobre un fichero abierto para lectura (§32, R-4); el solape de horarios verificado con `Get-ScheduledTask` (solo lectura). No fue posible comprobar en `logs/` si se ha materializado (limitación L2).
- **Ubicación:** `src/sqp/pipeline/daily.py:439` (`atomic_write_csv(df, pred_path)` fuera de `with locked(outdir / "candidates")` que empieza en `:443`); `src/sqp/storage/atomic.py:45` y `:92` (`os.replace(tmp, out)` sin reintento); lectores sin lock: `src/sqp/pipeline/closing_capture.py:47`, `src/sqp/pipeline/revalidation.py:121,397`, `src/sqp/audit/report.py` (informes), `scripts/run_status.py`/`health_check.py`. Programador: `SQP_Diario_Completo_Cdev` diaria 12:00; `SQP_Capture_Close_Cdev` cada 30 min (dispara también a las 12:00 y 12:30); `SQP_Validate_OOS_Cdev` día 1 a las 12:00.
- **Evidencia:** (directa) en Windows, `os.replace` sobre un destino que otro proceso tiene abierto sin `FILE_SHARE_DELETE` lanza `PermissionError`; reproducido: `EXC: PermissionError [WinError 5] Acceso denegado: ...race.csv.<pid>.<uuid>.tmp -> ...race.csv`; el contenido previo se conserva y el temporal se limpia (dirección segura). (Indirecta) la captura de cierre lee `predictions_*.csv` cada 30 min y el run diario los sobrescribe por liga; ambos procesos coinciden en el minuto 12:00 cada día y la captura de 12:30 puede coincidir con un run largo.
- **Descripción:** el lock sidecar serializa solo los escritores/lectores de `candidates_*`; `predictions_*` no está protegido, y en Windows un lector concurrente convierte la escritura atómica en una excepción.
- **Causa raíz:** la garantía "atómico y atómico-en-Windows" se asume idéntica a POSIX; la ventana de colisión existe por diseño de horarios y por lectores externos (operador con Excel, dashboard).
- **Impacto:** `run_league` lanza → `failures += 1` → `run_all` devuelve 1 → `RUN_DIARIO_ALL.bat` va a `:error` → el día se marca fallido en el centinela aunque el resto de ligas se generó; la liga afectada no publica lista ese día (contrario a la regla "generar la lista siempre") y conserva el fichero anterior. No hay corrupción.
- **Escenario de materialización:** 12:31, el run diario todavía escribe `predictions_mlb.csv` (`_finalize`) mientras `capture_closing_odds.py` está leyendo ese mismo fichero con `read_csv` para obtener `start_time` → `PermissionError`.
- **Controles existentes:** `atomic_write_csv` conserva el fichero previo; lock para `candidates`; `failures` visible en exit code y centinela; `_archive_existing`.
- **Matriz:** I=2 (una liga sin lista ese día, run marcado en rojo) · A=2 (cualquier liga + orquestación) · P=2 (posible: ventana de milisegundos pero solapes diarios y lectores externos) · E=2 (condiciones específicas) · R=1 (re-ejecutar la liga) · C=2 (lock parcial; fallo visible).
- **Cálculo:** (60+40+40+30+10+10)/4 = 190/4 = **47,5**.
- **Recomendación:** (a) mover `atomic_write_csv(df, pred_path)` dentro del bloque `locked(outdir / "candidates")` y hacer que los lectores de `predictions_*` en `closing_capture`/`revalidation` lean bajo el mismo lock (lecturas de milisegundos); (b) en `atomic.py`, reintentar `os.replace` ante `PermissionError` con espera corta acotada (p. ej. 5 intentos × 200 ms) y solo entonces propagar; (c) desplazar el inicio de `SQP_Capture_Close_Cdev` a :15/:45 para que no coincida con el arranque de 12:00.
- **Criterio de aceptación:** un test que mantenga `predictions_x.csv` abierto en un hilo durante 300 ms mientras `_finalize` escribe termina sin excepción y con el contenido nuevo; el Programador no tiene dos tareas SQP con el mismo minuto de disparo.
- **Prueba de regresión sugerida:** `test_atomic_write_retries_when_destination_is_open` (marcado `skipif(sys.platform != "win32")`) y `test_finalize_writes_predictions_under_candidates_lock` (comprobar que `.lock` existe durante la escritura de `pred_path` mediante `to_csv` parcheado).

### AUD-004 — La sección crítica de revalidación carga ficheros mensuales de cuotas bajo el lock; el umbral de "lock huérfano" no se refresca

- **Categoría:** Riesgo potencial · **Área:** Robustez / Concurrencia · **Severidad:** Media (52,5) · **Prioridad:** P3 · **Confianza:** Media
- **Estado de validación:** Medido el coste de lectura (`odds_ncaaf_202609.csv`: 40,5 MB, 250.736 filas, 6,5 s → 6,3 MB/s); tamaño del mes en curso 214 MB en 19 ficheros; no reproducida la ruptura del lock (requeriría >300 s de retención).
- **Ubicación:** `src/sqp/pipeline/revalidation.py:268-300` (bucle por liga bajo `with locked(predictions_dir / "candidates")` que llama a `_league_odds(...)` en `:292`); `src/sqp/pipeline/revalidation.py:151-170` (`_league_odds` lee los ficheros mensuales completos con `pd.read_csv`); `src/sqp/storage/lock.py:36-37` (`LOCK_TIMEOUT_S = 120`, `LOCK_STALE_S = 300`) y `:45-52` (un `.lock` con `mtime` > 300 s se borra sin comprobar si el titular vive; el `mtime` nunca se refresca mientras se retiene).
- **Evidencia:** (directa) el propio módulo documenta "`odds_mlb_202608.csv` son 107 MB y 32,5 s de `read_csv`" y pases de "5 min 37 s" antes del filtro por filas evaluables (`revalidation.py:157-165`); el filtro evita la lectura cuando no hay filas evaluables, pero en un día con eventos inminentes en varias ligas la lectura ocurre **dentro** del lock. (Directa) `tests/test_storage.py:131-139` justifica `LOCK_TIMEOUT_S ≥ 120` por "la sección crítica más lenta" = `fetch_probables` (≤60 s), sin contar esta carga.
- **Descripción:** retención legítima del lock proporcional al tamaño de los CSV mensuales (crecen ~30 MB/mes según `daily.py:781-785`), frente a un timeout de 120 s para el otro proceso y un umbral de 300 s tras el cual el otro proceso **rompe** el lock aunque el titular siga vivo.
- **Causa raíz:** lock sin latido (heartbeat) ni comprobación de vitalidad del titular (PID), y una sección crítica que incluye E/S proporcional al histórico.
- **Impacto:** (i) si la retención supera 120 s, el run diario (`_finalize`/`apply_global_exposure_cap`) o la captura lanzan `LockNoAdquiridoError` → liga fallida (visible); (ii) si supera 300 s, el segundo proceso borra el lock y entra: dos read-modify-write concurrentes sobre `candidates_*.csv` → pérdida silenciosa de una revocación o de candidatos recién generados, que es exactamente el defecto que el lock existe para impedir.
- **Escenario de materialización:** último fin de semana del mes, 12:30: NCAAF, NFL, MLB, EPL, La Liga y MLS con eventos en ventana → la revalidación lee ~150-250 MB bajo el lock (~40-70 s hoy, más al crecer); simultáneamente el run diario intenta `_finalize`. Hoy queda por debajo de 120 s; el margen se estrecha cada mes.
- **Controles existentes:** filtro `_filas_evaluables` antes de leer cuotas; `_odds_files(since)` limita a los meses relevantes; `LockNoAdquiridoError` en vez de degradación silenciosa; el test de la relación 120 < 300.
- **Matriz:** I=3 (pérdida silenciosa de una escritura de `candidates`) · A=2 (candidates y revocaciones de varias ligas) · P=1 (poco probable hoy: ~35-70 s medidos frente a 300 s) · E=2 (día con muchas ligas en ventana y fin de mes) · R=2 (recuperar desde `archive/` y `revalidation_log.csv`) · C=2 (parciales).
- **Cálculo:** (90+40+20+30+20+10)/4 = 210/4 = **52,5**.
- **Recomendación:** sacar la carga de cuotas fuera del lock (leer `_league_odds` y calcular `_fresh_snapshot` primero; entrar al lock solo para releer `candidates`, decidir y escribir), o refrescar el `mtime` del `.lock` periódicamente / escribir el PID en el lock y comprobar vitalidad antes de romperlo; alinear el test de `LOCK_TIMEOUT_S` con la sección crítica realmente más lenta.
- **Criterio de aceptación:** ninguna sección `with locked(...)` contiene lecturas de `data/odds/`; un test con lock retenido 2×`stale_s` por un proceso vivo no permite la entrada del segundo.
- **Prueba de regresión sugerida:** test que parchee `_league_odds` para registrar si se invoca con el `.lock` presente (debe ser falso); test de `locked` con titular vivo que refresca el `mtime` (o escribe PID) y un segundo aspirante que agota `timeout_s` sin romper el lock.

### AUD-005 — Seis ficheros de test ejecutan `run_league(..., mode="demo")` contra el árbol real y `conftest.py` no impone aislamiento

- **Categoría:** Deuda técnica · **Área:** Pruebas / Datos · **Severidad:** Media (52,5) · **Prioridad:** P3 · **Confianza:** Alta
- **Estado de validación:** Verificado por grep y por observación de `mtime` en `data/predictions/demo/` (08:39-08:40, coincidentes con la suite en ejecución).
- **Ubicación:** `tests/test_pipeline_demo.py:15,24,73,115`, `tests/test_accuracy_mode.py:88,111`, `tests/test_calibration_live.py:134`, `tests/test_team_scoring.py:163,193`, `tests/test_line_movement.py:184`, `tests/test_revalidation.py:205` (llamadas a `run_league` sin `monkeypatch.setattr(daily, "ROOT", tmp_path)`); `tests/conftest.py:1-44` (único fixture autouse: identidad git); destino real: `src/sqp/pipeline/daily.py:425-431` (`_finalize` → `ROOT/data/predictions/demo`) y `src/sqp/storage/served_store.py:64-66` (`ROOT/data/calibration/demo`).
- **Evidencia (directa):** `ls -la data/predictions/demo` durante la suite mostró `candidates_nba/nfl/nhl.csv` y `predictions_mlb.csv` con hora de la propia ejecución. El proyecto ya sufrió esta clase de fallo sobre datos **reales** (`daily.py:213-227`: filas sintéticas de la suite en `pitcher_confirmation_log_mlb.csv`, corregido el 2026-09-10 haciendo inyectable `root`), pero la corrección fue por instancia, no por clase.
- **Descripción:** el aislamiento depende de que cada autor recuerde parchear `ROOT`; cinco ficheros lo hacen, seis no.
- **Causa raíz:** `ROOT` es un global de módulo importado en muchos sitios y no hay fixture autouse que lo redirija ni una aserción post-sesión que detecte escrituras bajo `data/`.
- **Impacto:** los artefactos demo (`predictions/demo`, `calibration/demo`, `predictions/demo/archive`) reflejan datos de test, no del último `run_all --mode demo`; dos suites concurrentes o una suite coincidiendo con una tarea programada compiten por los mismos ficheros; y la puerta que evitaría una futura contaminación de datos **live** no existe.
- **Escenario de materialización:** un test nuevo llama `run_league(..., mode="live")` con un cliente falso y sin parchear `ROOT` → escribe `predictions_<liga>.csv` reales; nada lo detecta hasta la siguiente auditoría (ya ocurrió con el log de abridores).
- **Controles existentes:** separación `demo/` en `_finalize` y `ServedStore`; `data/` ignorado por git; `_archive_existing`.
- **Matriz:** I=1 (hoy solo artefactos demo) · A=1 (aislado) · P=4 (en cada ejecución de la suite) · E=4 (trivial) · R=1 (regenerar demo) · C=2 (separación demo/live parcial).
- **Cálculo:** (30+20+80+60+10+10)/4 = 210/4 = **52,5**.
- **Recomendación:** fixture `autouse` a nivel de sesión/función en `conftest.py` que redirija `sqp.config.ROOT` y los alias importados (`daily.ROOT`, `served_store`, `run_all.ROOT`, ...) a `tmp_path`, o que falle la sesión si `data/` cambió (comparar `mtime`/hash de un manifiesto antes y después); corregir los seis ficheros.
- **Criterio de aceptación:** ejecutar la suite completa no modifica ningún `mtime` bajo `data/` ni `logs/`.
- **Prueba de regresión sugerida:** `tests/test_suite_does_not_touch_repo_data.py` (fixture de sesión que fotografía `data/` al inicio y compara al final).

## 12. Hallazgos bajos

### AUD-006 — 3 de los 4 calibradores live carecen de sidecar `.sha256`: la verificación de integridad se omite

- **Categoría:** Riesgo potencial · **Área:** Seguridad / Modelos · **Severidad:** Baja (37,5) · **Prioridad:** P3 · **Confianza:** Alta
- **Validación:** `ls data/models` → 13 `.joblib`, 1 `.sha256` (`wnba_spreads_calibration_beta.joblib.sha256`); registro live `calibration_methods.json` = {`mlb_h2h_pergame`: beta, `mlb_spreads`: beta, `mlb_totals`: isotonic, `wnba_spreads`: beta}.
- **Ubicación:** `src/sqp/calibration/calibrator.py:257-263` (`_verify_hash`: `if not sidecar.exists(): return True`), `:80` (`joblib.load`); `src/sqp/models/ml_predict.py:56`.
- **Evidencia (directa):** el docstring lo declara ("Sin sidecar sigue cargando"); los artefactos live datan del 21-22 de agosto, anteriores al sidecar (28 de agosto).
- **Causa raíz:** compatibilidad hacia atrás elegida para no apagar calibradores sanos; no hubo paso de "sellado" de los artefactos existentes.
- **Impacto:** un artefacto alterado (y su sidecar borrado, si lo hubiera) se deserializa con pickle → ejecución de código. La frontera de confianza es la misma que la del árbol de trabajo que ya ejecuta producción, por lo que el riesgo incremental es bajo, pero el control descrito como "bloqueo" (AUD-LOW-001 previa) solo bloquea 1 de 13 artefactos.
- **Controles existentes:** hash verificado cuando existe; `revalidate_live_registry` (estructura del mapa); permisos deny del asistente sobre `data/**`.
- **Matriz:** I=2 · A=1 · P=1 · E=1 · R=2 · C=3 → (60+20+20+15+20+15)/4 = **37,5**.
- **Recomendación:** script único de sellado que escriba el sidecar de los 13 artefactos actuales tras verificarlos manualmente, y pasar `_verify_hash` a "sin sidecar → no cargar" con una fecha de corte.
- **Criterio de aceptación:** `ls data/models/*.joblib | wc -l == ls data/models/*.sha256 | wc -l`; `_verify_hash` devuelve `False` sin sidecar.
- **Prueba de regresión:** test que crea un `.joblib` sin sidecar y comprueba que `_load_model` devuelve `None` y registra el error.

### AUD-007 — `instalar-candados.sh` reinstala versiones obsoletas de dos hooks

- **Categoría:** Deuda técnica · **Área:** Infraestructura / Gobernanza del asistente · **Severidad:** Baja (37,5) · **Prioridad:** P3 · **Confianza:** Alta
- **Ubicación:** `instalar-candados.sh:2` ("EJECUTALO TU"), `:90-105` (heredoc HOOK2 → `mark-crossreview-pending.sh` derivando el fichero solo de `tool_input.file_path`, `:97`), `:107-140` (heredoc HOOK3 → `crossreview-on-stop.sh` con `codex review --uncommitted` fijo, `:126`); hooks vivos: `.claude/hooks/mark-crossreview-pending.sh:19` (usa `_targets.py`, cubre `Bash`), `.claude/hooks/crossreview-on-stop.sh:20-50` (elige `--uncommitted`/`--base`/`--commit HEAD` y exige repo git).
- **Evidencia (directa):** los heredocs no contienen `_targets.py` ni `--base`/`--commit`; los hooks vivos sí. El script hace respaldo `*.backup-<ts>` antes de sobrescribir (`:16-21`).
- **Causa raíz:** el instalador congela una versión de los hooks; las correcciones posteriores (AUD-MED-002 y la de 2026-09-13) se aplicaron a los ficheros vivos y no al instalador.
- **Impacto:** ejecutar el instalador (como su cabecera invita) revertiría dos correcciones auditadas; `tests/test_claude_system_contract.py` comprueba el cableado, no el contenido.
- **Matriz:** I=1 · A=1 · P=2 · E=3 · R=1 · C=1 → (30+20+40+45+10+5)/4 = **37,5**.
- **Recomendación:** o eliminar los heredocs y copiar desde `.claude/hooks/` (fuente única), o añadir un test que compare cada heredoc con el hook vivo.
- **Criterio de aceptación:** `diff <(extraer HOOKn) .claude/hooks/<hook>.sh` vacío para los tres hooks.
- **Prueba de regresión:** `test_instalador_de_candados_coincide_con_hooks_vivos`.

### AUD-008 — Dashboard HTML: cuatro interpolaciones en JS cliente sin escapar

- **Categoría:** Riesgo potencial · **Área:** Seguridad · **Severidad:** Baja (33,8) · **Prioridad:** P3 · **Confianza:** Alta (código) / Baja (explotabilidad)
- **Ubicación:** `src/sqp/audit/html_report.py:1244-1247` (`fillSelect`: `<option value="${v}">${v}</option>`), `:1200-1202` (`data-date="${d}" onclick="toggleDate('${d}')"`), `:1495-1496` (`<option>${m}</option>`), `:1550` (`title="${r.motivo}"`); `esc` definido en `:1227`.
- **Evidencia (directa):** los cuatro puntos no pasan por `esc`; el resto de celdas y nombres de equipo sí (`:1157`, `:548`, 33 usos de `html.escape` en servidor; `_json_para_script` `:886-908` impide cerrar el `<script>`).
- **Condición desencadenante:** `market` (procede de `markets[].key` del proveedor y de los CSV `served_*/candidates_*`), `fecha` (derivada internamente) o `motivo` (texto interno de `tipster.py`) con metacaracteres HTML. Requiere proveedor comprometido o edición local de los CSV.
- **Impacto:** XSS en contexto `file://` en el navegador del operador (lectura del propio informe; sin credenciales en la página).
- **Matriz:** I=2 · A=1 · P=1 · E=1 · R=1 · C=2 → (60+20+20+15+10+10)/4 = **33,8**.
- **Recomendación:** pasar `v`, `m`, `d`, `r.motivo` por `esc` (y `encodeURIComponent`/`JSON.stringify` en el argumento de `toggleDate`); opcionalmente validar `market ∈ {h2h, spreads, totals}` al construir el payload.
- **Criterio de aceptación:** un `market` con `"><img src=x onerror=1>` en el payload se renderiza como texto.
- **Prueba de regresión:** en `tests/test_html_report.py`, generar el dashboard con un `market` hostil y comprobar que el HTML resultante no contiene la cadena sin escapar dentro de `<option>`/`title=`.

### AUD-009 — Ciclo de importación de 5 módulos sostenido por un import diferido

- **Categoría:** Deuda técnica · **Área:** Arquitectura · **Severidad:** Baja (35,0) · **Prioridad:** P4 · **Confianza:** Alta
- **Ubicación:** `src/sqp/pipeline/daily.py:772` (`from sqp.markets.line_movement import ...` dentro de `run_league`); ciclo `daily → markets.line_movement → audit.clv_movement → audit.clv → backtesting.roi_engine → daily`.
- **Evidencia (directa):** grafo AST propio (101 módulos, 221 aristas): 0 ciclos con imports de cabecera; 1 componente fuertemente conexa de 5 módulos al incluir imports diferidos. El código lo documenta (`daily.py:757-770`, AUD-MED-015) y explica el `ImportError` si se sube el import.
- **Causa raíz:** `roi_engine` importa helpers desde `pipeline.daily` (re-exportados por compatibilidad) en vez de desde `pipeline.probabilities`.
- **Impacto:** fragilidad ante refactors; sin efecto funcional hoy.
- **Matriz:** I=1 · A=2 · P=1 · E=2 · R=1 · C=2 → (30+40+20+30+10+10)/4 = **35,0**.
- **Recomendación:** que `roi_engine`, `clv` y `clv_movement` importen desde `pipeline.probabilities`/módulos hoja; añadir un test de "0 ciclos" sobre el grafo AST.
- **Criterio de aceptación:** el import de `line_movement` puede subir a la cabecera de `daily.py` sin `ImportError`; el test de ciclos pasa.
- **Prueba de regresión:** `test_no_import_cycles` (AST + Tarjan, incluyendo imports diferidos).

### AUD-010 — Artefactos de entrega obsoletos versionados: `BUILD_INFO.json` y `OPTIMIZATION.diff`

- **Categoría:** Deuda técnica · **Área:** Infraestructura / Repositorio · **Severidad:** Baja (37,5) · **Prioridad:** P4 · **Confianza:** Alta
- **Ubicación:** `BUILD_INFO.json` (71 KB, 654 hashes), `OPTIMIZATION.diff` (91 KB, 29 ficheros), ambos añadidos en `c578f52` (2026-09-13); referenciados por `IMPLEMENTACION.md:7`.
- **Evidencia (directa):** recalculado SHA-256 de los 654 ficheros listados: **503 coinciden, 106 no, 45 no existen**; `git apply --check --reverse OPTIMIZATION.diff` falla (`patch does not apply`) porque el parche ya está integrado y los ficheros han evolucionado.
- **Causa raíz:** artefactos de un paquete puntual (2026-09-10) commiteados como parte del "snapshot del árbol de producción" sin regla de regeneración ni de caducidad.
- **Impacto:** `IMPLEMENTACION.md` afirma que `BUILD_INFO.json` "identifica y verifica los archivos incluidos": cualquier verificación con él fallará y confundirá; el parche no es aplicable; ruido de 160 KB en cada diff/revisión.
- **Matriz:** I=1 · A=1 · P=2 · E=2 · R=1 · C=4 → (30+20+40+30+10+20)/4 = **37,5**.
- **Recomendación:** mover ambos a `audit/optimization-20260910/` (donde ya viven `CHANGES.md`/`VALIDATION.md`) o eliminarlos del índice con una nota en `IMPLEMENTACION.md`; si se conserva el manifiesto, regenerarlo en cada release.
- **Criterio de aceptación:** `IMPLEMENTACION.md` no promete verificación con un manifiesto que no cuadra; `git ls-files` no contiene parches ya aplicados en la raíz.
- **Prueba de regresión:** test (opcional) que verifique `BUILD_INFO.json` contra el árbol si se decide mantenerlo.

### AUD-011 — CI: acciones ancladas por tag mutable, `pip-audit` sin pin, sin ejercicio de `.bat`/Docker, pata Windows solo en 3.12

- **Categoría:** Deuda técnica · **Área:** Infraestructura / CI · **Severidad:** Baja (35,0) · **Prioridad:** P4 · **Confianza:** Alta
- **Ubicación:** `.github/workflows/ci.yml:34,37,91,92` (`actions/checkout@v4`, `actions/setup-python@v5`), `:82` (`pip install pip-audit`), `:94` (`python-version: "3.12"` en `test-windows`); `Dockerfile:9-12` (reconoce que nadie construye la imagen).
- **Evidencia (directa):** producción es Windows + Python 3.14 (`SQP_PYTHON` en los `.bat`); la matriz cubre 3.14 en ubuntu y Windows en 3.12: ninguna pata ejecuta la combinación real. Ningún paso ejecuta un `.bat`/`.cmd`/`.ps1` ni `docker build`.
- **Causa raíz:** decisiones documentadas de coste (minutos Windows ×2) y de alcance (Docker = demo).
- **Impacto:** una regresión específica de Windows+3.14 (rutas, `os.replace`, locale) pasaría CI; una regresión en los `.bat` solo la detectan aserciones textuales (`tests/test_run_status.py:156-230`); riesgo de cadena de suministro bajo por tags mutables y `pip-audit` flotante.
- **Matriz:** I=1 · A=2 · P=1 · E=2 · R=1 · C=2 → (30+40+20+30+10+10)/4 = **35,0**.
- **Recomendación:** cambiar la pata Windows a 3.14 (mismo coste) o añadir `include: {os: windows-latest, python: "3.14"}`; anclar acciones por SHA; pinear `pip-audit`; un job `docker build` mensual o bajo `workflow_dispatch`; un smoke `cmd /c RUN_DIARIO_ALL.bat` con `SQP_MODE=demo` en la pata Windows si el BAT lo admite.
- **Criterio de aceptación:** la matriz contiene Windows+3.14; `uses:` con SHA de 40 caracteres; `pip install pip-audit==X`.
- **Prueba de regresión:** el propio CI.

### AUD-012 — `check-secrets.sh` descarta la línea entera cuando contiene una palabra de "ruido"; no hay segunda puerta en CI

- **Categoría:** Deuda técnica · **Área:** Seguridad · **Severidad:** Baja (38,8) · **Prioridad:** P4 · **Confianza:** Alta
- **Ubicación:** `.claude/hooks/check-secrets.sh:36` (`_ruido='os\.environ|getenv|dotenv|...|\bexample\b|placeholder|changeme|dummy|your_|xxx|...'`) y `:64` (`grep -niE "$_patron" "$file" | grep -vE "$_ruido"`).
- **Evidencia (directa):** el filtro es por línea completa; una línea `ODDS_API_KEY=<clave real>  # replaces the example key` se descarta. El CI no ejecuta ningún detector de secretos.
- **Causa raíz:** filtro de falsos positivos aplicado a la línea en vez de al valor capturado.
- **Impacto:** falso negativo del único detector local; mitigado porque `.env`/`*.env` están ignorados por git y el historial está limpio.
- **Matriz:** I=2 · A=1 · P=1 · E=2 · R=2 · C=1 → (60+20+20+30+20+5)/4 = **38,8**.
- **Recomendación:** aplicar el filtro de ruido solo al **valor** capturado (grupo de la regex) y/o exigir longitud/entropía mínima del valor; añadir `gitleaks`/`trufflehog` en CI sobre el diff.
- **Criterio de aceptación:** una línea con clave real y la palabra "example" en el comentario es detectada.
- **Prueba de regresión:** caso en el test del hook (si existe) con esa línea.

## 13. Observaciones informativas

Sin puntuación: no cumplen el umbral de consecuencia técnica demostrable de §8 o son decisiones registradas del proyecto. Se listan para trazabilidad.

| # | Observación | Ubicación | Nota |
|---|---|---|---|
| O-1 | El guard "selección que no casa con ningún equipo → void" depende de que `row["away"]` exista y no esté vacío; sin esa columna la fila se gradúa como visitante. | `src/sqp/settlement/settle.py:44-47` | El propio código declara la ruta "hoy no alcanzable" (mismo proveedor de cuotas y marcadores). Inferencia; confirmar con un test de fila sin `away`. |
| O-2 | `AdjustedEdge.effective_probability` puede salir ≤ 0 sin clamp; el único consumidor (`kelly_fraction_stake`) lo absorbe devolviendo stake 0. | `src/sqp/markets/edge.py:193-194`, `src/sqp/risk/kelly.py:226` | Sin impacto actual; un consumidor futuro debería re-validar el rango. |
| O-3 | Con 47 cortes evaluados y K=41 fijado por pre-registro, la tasa de error familiar efectiva es 47×0,00122 ≈ 0,057 > 0,05. | `data/bets/prediction_gate.json` (`k_bonferroni: 41`, `n_cortes_evaluados: 47`), `src/sqp/risk/prediction_gate.py:101-112` | Decisión registrada (tolerancia hasta 50 cortes con aviso de re-pre-registro). No se contradice; se deja constancia de la magnitud. |
| O-4 | `SQP_Validate_OOS_Cdev` terminó con `LastTaskResult = 1` el 2026-09-01 y coincide en minuto con el run diario el día 1 de cada mes. | Programador de tareas | Ya registrado en `.claude/automation/runtime/current-task.md` (B-01). Causa no verificable sin `logs/` (L2). |
| O-5 | El aviso de fallback de intérprete (`[AVISO] SQP_PYTHON no existe`) va a consola (`echo`) y no al log; bajo S4U nadie lo ve. Además el centinela y `health_check` usan el mismo intérprete, así que su ausencia deja el día sin alarma escrita salvo el log del BAT y el `LastTaskResult`. | `DIARIO_COMPLETO.bat:17-19` y equivalentes en los demás `.bat` | Inferencia; mitigado por el banner de liveness del dashboard (`open_dashboard.ps1`) al iniciar sesión. |
| O-6 | La configuración S4U del run diario (aplicada el 2026-09-13 18:04) aún no se había ejercitado al cierre de esta auditoría; la captura de 08:30 de hoy sí corrió bajo S4U con rc 0. | Programador de tareas | Se confirma/refuta con el run de hoy 12:00. |
| O-7 | `SQP_SKIP_TREE_GUARD` desactiva el guard de árbol limpio sin caducidad si se fija como variable persistente. | `DIARIO_COMPLETO.bat` (bloque `tree_ok`) | Diseño explícito; bajo S4U las variables de usuario no se cargan. |
| O-8 | `scripts/run_all.py` y `scripts/settle_all.py` nunca se ejecutan como proceso en la suite (solo `importlib` + `main()`); un fallo a nivel de módulo/entorno solo lo detectaría el `.bat` en producción. | `tests/test_orchestrator_safety.py:60-104`, `tests/test_run_all_select.py:38-75` | La lógica de `main()` sí está cubierta. |
| O-9 | Meta-tests que fijan frases literales de prosa en `.claude/**` (`test_claude_system_contract.py:49-64,98,108,155`); `test_market_shrink_blends_model_toward_market` reconstruye la fórmula de producción (`tests/test_team_scoring.py:178-200`); una aserción compara con `datetime.now()` sin congelar (`tests/test_html_report.py:118`). | `tests/` | La fragilidad de los meta-tests está declarada como deliberada en `.claude/CLAUDE.md`. |
| O-10 | `FileCache.put` escribe el JSON de caché con `write_text` directo (no atómico); un lector concurrente que lea un fichero a medias obtiene `None` y vuelve a la red (coste de créditos, no de corrección). | `src/sqp/providers/odds_cache.py` (`put`) | Dirección segura; se anota por coherencia con `atomic_write_json`. |
## 14. Seguridad

- **Secretos:** la única credencial (clave de The Odds API) se lee de `.env`/entorno (`config.py`), nunca hardcodeada; se añade a la query **después** de calcular la clave de caché (`odds_api.py:143,155`), y los errores HTTP/conexión se relanzan con la query redactada (`odds_api.py:197-207`). `.env`/`*.env` ignorados; ningún `.env` ni cadena tipo clave en los 517 commits del historial. `.mcp.json` sin credenciales.
- **Deserialización:** `joblib.load` (pickle) protegido por sidecar SHA-256 solo cuando el sidecar existe → AUD-006. Sin `yaml.load` inseguro (solo `safe_load`), sin `shell=True`, sin `eval`.
- **Inyección/traversal:** ids de liga/torneo validados con `[a-z0-9_]+` antes de componer rutas (`daily.py:60`, `run_all.py:49-60`); nombres de etapa del centinela validados (`run_status.py`). HTML: 33 `html.escape` en servidor + `_json_para_script`; 4 interpolaciones cliente sin escapar → AUD-008.
- **Red:** todas las llamadas `requests` con `timeout` (30 s Odds API; 60-120 s MLB Stats; ESPN con reintentos lineales sobre 5xx/429). Sin SSRF posible (URLs fijas).
- **CI:** `permissions: contents: read`; `pip-audit` bloqueante; acciones por tag mutable → AUD-011; sin detector de secretos → AUD-012.
- **Gobernanza del asistente:** deny sobre `.env*`, `logs/**`, `data/**` verificado empíricamente en esta sesión (tres comandos bloqueados).
- **Dependencias:** `pip-audit --no-deps` sobre el lock: 0 vulnerabilidades conocidas (L1).

## 15. Arquitectura

Ver §6. Hallazgos: AUD-001 (paridad producción↔backtest incompleta), AUD-009 (ciclo de 5 módulos). Fortalezas: helpers de probabilidad compartidos y fijados por test; precedencia de configuración documentada y coherente con `config.py` (`_env_flag` para booleanos; comprobado para `CALIBRATION_ENABLED`, `SHADOW_MODE`, `CLV_GATE_ENABLED`, `PREDICTION_GATE_ENABLED`, `DEGRADATION_ENABLED`); `tests/test_config_yaml_keys.py` impide claves YAML sin consumidor.

## 16. Lógica y exactitud

Verificado por lectura y por el subagente cuantitativo (revalidado):

- **Conversión de cuotas y no-vig:** `is_usable_price` como predicado único (rechaza None/NaN/±inf/≤1); `remove_vig_power` con `brentq` y fallback proporcional **con aviso**; `_require_finite` como defensa en profundidad. Correcto.
- **Edge y Kelly:** `edge = p·d − 1`; `adjusted_edge` deflacta por desacuerdo con el mercado y re-expresa como `p_eff`; `kelly_fraction_stake` rechaza banca/probabilidad/precio no finitos y devuelve 0 bajo `min_edge`. Correcto; O-2 anotado.
- **Probabilidad de decisión:** `p_decision = (1−s)·cal(p_adj) + s·fair` con calibración pre-blend (pre-registro 2026-07-02); `p_used` almacenada sin calibrar (evita calibrar sobre calibrado). Coherente entre `daily.py` y `roi_engine.py`.
- **Liquidación:** push en 2-way con margen 0; empate 1X2 solo gana `Draw`; líneas asiáticas de cuarto con medias; línea no finita → void; selección que no casa → void (con la salvedad O-1). Correcto.
- **Gate de predicción:** unidad de inferencia por (evento, mercado); test de signo pareado unilateral; α = 0,05/41 con candado de re-pre-registro en 50 cortes; pestillo unidireccional con liberación humana. Correcto; O-3 anotado.
- **Fechas/zonas horarias:** `_parse_iso_utc` fuerza aware UTC; `_already_started` y `_within_horizon` conservadores ante fechas no parseables; la tolerancia ±1 día de `_merge_results` produce un falso positivo de deduplicación en series de días consecutivos → **AUD-002**.
- **Fuga temporal:** la calibración entrena sobre `adjusted_probability` servida y se aplica al día siguiente (los picks de hoy usan los modelos live previos); el gate solo cuenta filas con `game_date` > 2026-08-16; el backtest es walk-forward. No se detectó fuga de futuro. La divergencia AUD-001 es de **política**, no de información.

## 17. Datos

- Persistencia en CSV/JSON/joblib con `atomic_write_csv/json` (temporal único por PID+UUID, `fsync`, `os.replace`) y lock sidecar `O_CREAT|O_EXCL` con abort (no degradación). `settled_*`: dedup por `(event_id, market, selection, line, generated_at)` bajo lock, reconciliación de esquema por unión de columnas. `served_*`: dedup por (evento, mercado, selección, línea, día de run) bajo lock.
- Riesgos: AUD-003 (semántica de `os.replace` en Windows y `predictions_*` fuera del lock), AUD-004 (E/S grande dentro del lock), AUD-005 (tests sobre el árbol real), AUD-002 (dedup entre fuentes). Crecimiento: `data/odds/` ~30 MB/mes por liga grande; la carga completa del histórico ya se evita cuando el término de movimiento de línea está inerte (`daily.py:775-788`).
- Caché de cuotas: TTL acotado por la política de frescura (`_cache_ttl_acotado`), edad de la respuesta expuesta y usada para `cuota_vencida`. Correcto; O-10 anotado.

## 18. APIs e integraciones

- **The Odds API:** cliente único; `timeout=30`; reintentos con espera creciente sobre `_RETRY_STATUS` y errores de red; cuota leída de cabeceras y usada por el guard de presupuesto (`(mercados × regiones) + 1` por liga, racionado sobre los días restantes del mes con margen de seguridad; fallback conservador de 5 ligas si la cuota no se puede leer). `is_sport_active` best-effort: fallo transitorio → se asume activa (no se pierde la liga).
- **MLB Stats API / ESPN:** timeouts explícitos; ESPN con reintentos lineales; fallos degradan a aviso (`_attach_probable_pitchers`, `_tennis_results`) sin tumbar el run.
- **Idempotencia:** re-ejecutar el mismo día no duplica served/settled (claves con día/generated_at). Sin versionado de contrato externo (no aplica: consumidor único).
- Sin hallazgos puntuados en esta área.

## 19. Rendimiento y concurrencia

- Coste dominante conocido y ya mitigado: carga del histórico de cuotas (inerte cuando los coeficientes de movimiento son 0). Medición propia: `read_csv` a 6,3 MB/s sobre el mayor fichero mensual (40,5 MB, 250.736 filas, 6,5 s).
- Concurrencia entre las tareas `SQP_Diario_Completo_Cdev` (12:00) y `SQP_Capture_Close_Cdev` (:00/:30): serializada solo para `candidates_*` y `settled_*`; → AUD-003, AUD-004.
- Sin bloqueos indefinidos: locks con timeout 120 s y rotura de huérfanos a 300 s; sin hilos.

## 20. Robustez

- Cadena de orquestación: `DIARIO_COMPLETO.bat` aborta si `SETTLE_ALL.bat` devuelve ≠ 0, y `settle_all.py` devuelve 1 **solo** si una liga fallida retiene picks comenzados sin liquidar (contrato documentado en README y verificado en `settle_all.py:60-88`); `run_all.py` omite ligas con picks comenzados sin liquidar (guard M2). Todo lo best-effort (auditoría de liquidación, segmentos, CLV, gate, recalibración) está aislado con `try/except` y **no** toca el exit code.
- Degradación: caché de cuotas en modo offline con `cuota_vencida` (stake 0, lista conservada); `_finalize` con lista vacía borra `candidates_*` para no dejar picks obsoletos; `_archive_existing` antes de sobrescribir.
- Debilidades: AUD-003 (una excepción de fichero abierto tumba la liga), O-5 (fallback de intérprete sin alarma escrita).

## 21. Pruebas

- 2.013 casos pasan en el intérprete de producción (26 min); 0 `xfail`; 5 `skipif` solo por entorno; `slow` no excluye nada en CI. Cobertura por inspección de flujos críticos **buena**: odds/vig (valores conocidos, NaN/Inf, fallback de `brentq`), Kelly (todos los bordes), gates (default-deny explícito, latch, Bonferroni), liquidación (push, asiáticas, 3-way, void), atómico+lock (fsync, temporal único, huérfano), presupuesto y caps de exposición, proveedores con sesiones falsas.
- Debilidades: AUD-005 (aislamiento del árbol real), ausencia de test de paridad para `adjusted_edge` (AUD-001), ausencia de test para series consecutivas (AUD-002), ausencia de test de la sección crítica real más lenta (AUD-004), O-8/O-9.

## 22. Dependencias

- 12 dependencias directas pineadas en `requirements.lock` (numpy 2.4.4, pandas 3.0.2, scipy 1.17.1, scikit-learn 1.9.0, joblib 1.5.3, requests 2.33.1, PyYAML 6.0.3, python-dotenv 1.2.2 + dev), instaladas con `-c` en Makefile, CI, Docker y `setup_local.py`. `pip-audit --no-deps`: sin vulnerabilidades conocidas. Entorno local = lock (verificado: numpy 2.4.4, pandas 3.0.2, sklearn 1.9.0).
- Limitación L1: la resolución completa de `pip-audit -r` falló localmente en el venv efímero (no reproduce el fallo del CI). Deuda: `pip-audit` sin pin en CI (AUD-011).

## 23. Infraestructura

- Producción: Windows 11, Python 3.14.4 fijo por `SQP_PYTHON`, 5 tareas del Programador (4 en S4U desde 2026-09-13, `SQP_Dashboard_Cdev` interactiva). Guard de árbol limpio y de árbol atrasado (`git fetch` con plazo) en `DIARIO_COMPLETO.bat`; rotación de logs por `rotate_log.cmd`; centinela por etapa.
- CI: 4 patas ubuntu + 1 Windows; alerta por issue único ante CI rojo en `main`. Deudas: AUD-011, AUD-007 (instalador de hooks), AUD-010 (artefactos obsoletos). Docker solo demo, no construido (L4).

## 24. Observabilidad

- Logging por módulo (`logging_config`), un log por BAT con rotación, centinela `run_status` por etapa (atómico), `health_check` y `pipeline_health.json`, banner de liveness en el dashboard y modal al iniciar sesión si el informe no es de hoy. Sin métricas/tracing (no aplica a un pipeline batch local).
- Filtrado de sensible: la clave nunca se registra (query redactada); no se encontraron `log.*(api_key|apiKey|token)`.
- Puntos ciegos: O-5 (aviso de intérprete a consola), L2 impidió auditar el contenido real de los logs.

## 25. Deuda técnica

AUD-005, AUD-007, AUD-009, AUD-010, AUD-011, AUD-012 y las observaciones O-8/O-9. Común denominador: controles que existen pero dependen de disciplina manual (aislamiento de tests, sincronía instalador↔hooks, sellado de artefactos) en vez de una puerta automática.

## 26. Fortalezas

1. Cultura de auditoría interna excepcional: cada incidente previo está documentado en el código con su reproducción y protegido por test; en todos los casos verificados (`is_usable_price`, mediana de consenso, hash de artefactos "rechaza y no carga", `atomic_write_json`, filtro de evaluables antes de leer cuotas, `unsettled_completed_picks` contando stake 0) la corrección está realmente presente.
2. Controles de riesgo default-deny en capas (cuota vencida → pausa → mercado incompleto → edge implausible → shadow → prediction gate → CLV gate), con registros ausentes/corruptos tratados como deny.
3. Separación estricta y consistente de métricas en salidas e informes: probabilidad estimada, implícita sin vig, edge, hit rate observado vs punto de equilibrio, ROI esperado vs realizado (`report.py`, `DISCLAIMER`).
4. Persistencia atómica y duradera con locks que abortan en vez de degradar; ids externos validados antes de componer rutas.
5. Paridad producción↔backtest fijada por identidad de objeto para los helpers de probabilidad; calibración pre-blend pre-registrada; gate de predicción con corrección de multiplicidad pre-registrada y pestillo auditado.
6. Las tres puertas de calidad (ruff, mypy, pytest) verdes en el intérprete real de producción; `pip-audit` limpio; historial git sin secretos.
7. Gobernanza del asistente con hooks efectivos (deny sobre datos/logs/.env verificado; modelo obligatorio al delegar).

## 27. Riesgos principales

1. **Divergencia latente producción↔backtest** (AUD-001): la próxima activación de un coeficiente de movimiento de línea o dispersión se validaría con una medición que no describe la política desplegada.
2. **Dedup entre fuentes que descarta resultados reales** (AUD-002): ratings desactualizados en series consecutivas; contamina la evidencia del gate y de la calibración, aunque no el dinero (stakes 0).
3. **Concurrencia en Windows** (AUD-003/004): colisión de escritura o rotura de lock bajo condiciones de carga crecientes con el histórico.
4. **Controles con cobertura parcial** (AUD-005/006/007/012): la barrera existe pero no cubre todos los casos; la clase de fallo ya se materializó una vez (log de abridores).
5. **Punto único externo:** The Odds API como única fuente de cuotas y scores; sin proveedor secundario configurado (riesgo aceptado y documentado por el proyecto; no puntuado).

## 28. Plan de remediación

Lotes pequeños, cada uno con test de regresión y validación (`pytest -q` dirigido → `ruff` → `mypy` → suite completa):

| Lote | Hallazgos | Cambio | Esfuerzo | Riesgo del cambio |
|---|---|---|---|---|
| R1 (P2) | AUD-001 | Helper único de kwargs de `adjusted_edge` compartido por `daily`/`roi_engine`; test de paridad funcional con coeficientes ≠ 0 | 2-3 h | Bajo (no cambia producción con coeficientes a 0) |
| R2 (P2) | AUD-002 | Dedup adyacente solo con marcador idéntico (o hora ±6 h); dos tests nuevos | 1-2 h | Bajo; cambia el fit de ratings (más datos recientes): re-medir Brier antes/después sobre el stream servido |
| R3 (P3) | AUD-003, AUD-004 | `predictions_*` bajo el lock; reintento acotado de `os.replace` ante `PermissionError`; sacar `_league_odds` del lock; PID/latido en el lock; desplazar la captura a :15/:45 (**tocar el Programador solo con orden explícita del operador**) | 3-4 h | Medio (concurrencia); tests con hilos |
| R4 (P3) | AUD-005 | Fixture autouse de aislamiento de `ROOT` + test de "data/ intacto"; corregir 6 ficheros | 2 h | Bajo |
| R5 (P3) | AUD-006, AUD-007, AUD-008 | Sellado de los 13 artefactos + "sin sidecar → no cargar"; instalador copia desde hooks vivos; `esc` en 4 interpolaciones | 2 h | Bajo |
| R6 (P4) | AUD-009, AUD-010, AUD-011, AUD-012 | Imports desde `probabilities`; mover artefactos a `audit/optimization-20260910/`; Windows+3.14 y SHA en CI; filtro de secretos sobre el valor | 2-3 h | Bajo |

Ningún lote toca parámetros de riesgo, modelo, umbral ni gate. R2 modifica datos de entrada al modelo (más resultados recientes) y debe medirse antes/después. R3 incluye una acción sobre el Programador que requiere orden explícita del operador.

## 29. Criterios de aceptación

Consolidados de §11-12: (1) igualdad de `adjusted_edge` entre backtest y producción con coeficientes ≠ 0; (2) `_merge_results` conserva series consecutivas y sigue deduplicando el drift UTC; (3) escritura de `predictions_*` bajo lock y sin excepción con lector concurrente; ninguna E/S de `data/odds/` dentro de `locked`; (4) la suite completa no modifica `data/`; (5) 13/13 artefactos con sidecar y carga denegada sin él; (6) heredocs del instalador idénticos a los hooks vivos; (7) payload hostil renderizado como texto; (8) 0 ciclos en el grafo AST; (9) `IMPLEMENTACION.md` sin promesa de verificación con un manifiesto que no cuadra; (10) CI con Windows+3.14, acciones por SHA y `pip-audit` pineado; (11) clave real con "example" en el comentario detectada por el hook.

## 30. Comparación histórica

No existe informe Claude anterior en `audits/claude/` (primera ejecución del ciclo `audits/`). Los 12 hallazgos se clasifican como **Nuevo**. No se han copiado hallazgos de otros auditores ni de `audit/` (no leído, por independencia). Las referencias a correcciones previas (AUD-*, F-*, M-*, KI-*) citadas en el informe proceden exclusivamente de los comentarios del propio código, y cada una fue verificada contra la implementación actual antes de citarla como control existente.

## 31. Conclusiones

El repositorio está en un estado técnico sólido: puertas verdes en el intérprete de producción, controles de riesgo default-deny correctamente implementados, matemática de mercado y de liquidación probada en los bordes, y un historial de correcciones convertido en pruebas. No se encontró ningún defecto que altere hoy probabilidades, edge, stakes ni liquidación, ni ninguna fuga temporal. Los cinco hallazgos de severidad media son (a) una divergencia latente entre producción y backtest que se activaría al encender coeficientes hoy a cero, (b) una deduplicación entre fuentes que descarta partidos reales de series consecutivas, y (c) tres condiciones de concurrencia/aislamiento específicas de Windows y de la suite. Los siete bajos son deuda de controles con cobertura parcial y de higiene de infraestructura. No hay P0 ni P1. Limitaciones materiales: `pip-audit` con resolución completa no reproducible localmente y logs/`.env` inaccesibles por política (ambas registradas).

## 32. Anexo de comandos

Todos ejecutados desde la raíz del repositorio, Python 3.14.4 (`C:\Users\Richard\AppData\Local\Programs\Python\Python314\python.exe`), el 2026-09-14 entre las 08:15 y las 09:35 (hora local).

| # | Comando | Propósito | Resultado | Limitación |
|---|---|---|---|---|
| V-1 | `python -m ruff check src scripts tests` | Lint | `All checks passed!` exit 0 | — |
| V-2 | `python -m mypy src` | Tipos | `Success: no issues found in 101 source files` exit 0 | — |
| V-3 | `python -m pytest -q -p no:cacheprovider` | Suite completa | `2013 passed, 1 skipped in 1571.05s` exit 0 | Ejecutada en paralelo con la lectura de código; contaminó `data/predictions/demo` (AUD-005) |
| V-4 | `python -m pip_audit -r requirements.lock --progress-spinner off` | Vulnerabilidades (comando del CI) | exit 1: `No matching distribution found for ruff==0.15.14` en el venv efímero | L1 |
| V-5 | `python -m pip_audit -r requirements.lock --no-deps --progress-spinner off` | Vulnerabilidades sobre los pines | `No known vulnerabilities found` exit 0 | Sin resolución transitiva |
| V-6 | `python -m pip index versions ruff` | Comprobar que la versión existe en el índice | 0.15.14 listada e instalada | — |
| V-7 | `git status --short`, `git log --oneline`, `git ls-files`, `git log --all --diff-filter=A --name-only`, `git grep -nE "\b[a-f0-9]{32}\b" ...` | Higiene del repositorio y secretos en historial | Árbol limpio salvo `audits/`; 517 commits; 683 ficheros; solo `.env.example`; 0 cadenas tipo clave | — |
| V-8 | `git apply --check --reverse OPTIMIZATION.diff` | ¿El parche está integrado? | `patch does not apply` (ya integrado y evolucionado) | — |
| R-1 | Script Python: SHA-256 de los 654 ficheros de `BUILD_INFO.json` | Vigencia del manifiesto | 503 coinciden, 106 no, 45 ausentes | — |
| R-2 | Script Python: grafo AST de imports de `src/sqp` + Tarjan | Ciclos y fan-in | 101 módulos, 221 aristas; 0 ciclos de cabecera; 1 ciclo de 5 módulos con imports diferidos | — |
| R-3 | `PYTHONPATH=src python -c "from sqp.pipeline.daily import _merge_results; ..."` con histórico (D, A, B) y recientes (D+1, A, B), (D+2, A, B) | Reproducir AUD-002 | `[('2026-09-10','h1'), ('2026-09-12','r3')]` — el D+1 desaparece | — |
| R-4 | Script Python en scratchpad: `atomic_write_csv` sobre un CSV mantenido abierto para lectura | Reproducir AUD-003 en Windows | `PermissionError [WinError 5] Acceso denegado`; contenido previo conservado; temporal limpiado | Sintético |
| R-5 | Script Python: `pd.read_csv('data/odds/odds_ncaaf_202609.csv')` cronometrado | Coste de E/S dentro del lock (AUD-004) | 40,5 MB, 250.736 filas, 6,5 s (6,3 MB/s); mes en curso 19 ficheros, 213,8 MB | Solo agregados |
| R-6 | `Get-ScheduledTask | Where TaskName -like '*SQP*'` + `Get-ScheduledTaskInfo` (PowerShell, solo lectura) | Horarios, modo S4U, últimos resultados | 5 tareas; diaria 12:00; captura cada 30 min desde 12:30; Validate_OOS `LastTaskResult=1` (2026-09-01) | — |
| R-7 | Lectura de `data/bets/{prediction_gate,clv_gate,degradation_pause}.json` con `json.load` | Estado de gates | 47 cortes / 0 permitidos / K=41 / α=0,00122; CLV 0 permitidos; 11 mercados auto-pausados | — |
| R-8 | `ls -la data/models/`, `json.load('data/models/calibration_methods.json')` | Artefactos y sidecars | 13 `.joblib`, 1 `.sha256`; 4 calibradores live | — |
| R-9 | `sed`, `grep -n` sobre los ficheros citados en cada hallazgo | Anclas de línea | Ver ubicaciones en §11-12 | — |
| B-1 | `ls logs`, `grep ... logs/*.log` | Buscar `PermissionError` en logs | **Denegado** por permisos del proyecto | L2 |
| B-2 | `sed ... .env`, `cat .env.example` | Nombres de variables | **Denegado** por permisos del proyecto | L2 |
| S-1..S-4 | Cuatro subagentes de solo lectura (`fable`: lógica cuantitativa; `opus`: datos/robustez — **abortado por límite de cuota del API (HTTP 429) sin producir salida**; `opus`: operaciones/seguridad; `sonnet`: pruebas) | Cobertura por áreas | Candidatos recibidos: 3 + 0 + 9 + 6; tras revalidación por el agente principal: 1 + 0 + 5 + 1 puntuados, resto a observaciones o descartados | El área datos/robustez la cubrió el agente principal con lecturas dirigidas (`odds_cache`, `served_store`, `settlement/runner._persist_settled`, `config.validate`, timeouts de proveedores) |
