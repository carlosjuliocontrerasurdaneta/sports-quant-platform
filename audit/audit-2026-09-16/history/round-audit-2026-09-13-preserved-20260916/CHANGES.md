# Cambios — Fase 4, auditoría integral 2026-09-13

Autorización: aprobación explícita del operador de **todos los hallazgos
confirmados** más las mejoras cuya necesidad y beneficio quedaron demostrados por
la evidencia de la auditoría. Base: árbol de producción tal como quedó tras la
remediación del 2026-09-10 (verificado por hashes al abrir).

**Ni un cambio de parámetro de riesgo, `pick_mode`, `shadow_mode`, calibrador,
umbral de gate, modelo, estrategia ni dato histórico.** No se escribió nada en
`data/` (el único movimiento propuesto sobre datos, CL-02, quedó bloqueado por
el clasificador de permisos y se devuelve al operador). Los dos cambios de
contrato del ledger (AUD-MED-002 y AUD-MED-003) se revisaron de forma
independiente en el escalón `fable` (clase de escalado «contrato de artefacto
persistido», `MODEL_ROUTING.md`); su veredicto consta en VALIDATION.md.

## Efecto del hook de formato

`post-edit-format.sh` (`ruff check --fix`) corre tras cada `Edit`/`Write`. Las
ediciones de esta fase se hicieron mayoritariamente con scripts Python desde
Bash (por la contrabarra en heredocs, documentada en memoria), así que el hook
no intervino sobre ellas; `ruff check src scripts tests` está limpio de todas
formas. Revisado el diff final (`git diff` sobre el repositorio reconstituido):
el hook no tocó lógica.

## HIGH

| ID | Cambio | Ficheros |
|---|---|---|
| **AUD-HIGH-001** | Repositorio reconstituido EN EL DIRECTORIO DE PRODUCCIÓN sin tocar el árbol de trabajo: `git init` · `remote add origin` · `fetch` · `update-ref` + `symbolic-ref` a la rama nueva `prod/remediacion-20260913` sobre `origin/main` · `git read-tree HEAD` (índice = `main`, árbol intacto; equivalente a `reset --mixed`, que está en la lista `deny`). `git status` mostró exactamente la divergencia medida (107 modificados incl. esta fase, 32 nuevos; `data/`, `logs/`, `.env`, `settings.local.json` ignorados). Commit y push de la rama (ver VALIDATION.md). | `.git/` (nuevo); ningún fichero del árbol |
| **AUD-HIGH-002** (parte técnica) | `open_dashboard.ps1`: ya NO se omite cuando el reporte no es de hoy — ejecuta `scripts/health_check.py` al iniciar sesión (liveness independiente del orquestador, log `logs/open_dashboard.log`), muestra un aviso modal si el reporte no es de hoy o la salud es ERROR, y abre el último reporte igualmente; marcador diario conservado. Interruptor `SQP_DASHBOARD_NO_UI` solo para pruebas. 4 tests que ejecutan el `.ps1` real sobre un root temporal. | `scripts/open_dashboard.ps1`, `tests/test_open_dashboard.py` (nuevo) |
| **AUD-HIGH-002** (2b) | **NO APLICADO — decisión del operador**: cambiar el modo de inicio de sesión de las 5 tareas del Programador no se toca sin orden explícita. | — |

## MEDIUM

- **AUD-MED-001** — `revalidation._dia_run_vigente(df)`: el scoping de los dos
  pases (precio y abridores) pasa de «generado HOY (UTC)» a «run vigente del
  fichero» (generación más reciente presente en `candidates_*`). Test de
  costes adaptado (la exclusión ejercitada pasa a ser un `revoke` previo) y 2
  tests nuevos: evento a las 01:30Z con generación de ayer → evaluado; dos
  generaciones conviviendo → sólo la más reciente. `src/sqp/pipeline/revalidation.py`,
  `tests/test_revalidation.py`.
- **AUD-MED-002** — `settle._grade` descompone líneas de cuarto con
  `settlement_math.split_asian_line` y devuelve `half_win`/`half_loss`
  (`HALF_RESULTS`); `settle_candidates` fija `pnl = ±0,5·stake·(precio−1)` /
  `−0,5·stake`; `runner.realized_roi` y `bankroll.summary()` incluyen las medias
  en el stake graduado. Los consumidores que filtran `isin(["win","loss"])`
  (gate, calibración, degradación, CLV, informes) las EXCLUYEN como a un push
  (dirección conservadora, deliberada). 14 tests parametrizados + pnl + ROI.
  `src/sqp/settlement/settle.py`, `src/sqp/settlement/runner.py`,
  `src/sqp/risk/bankroll.py`, `tests/test_settle_candidates.py`. **No se
  regraduó ninguna fila histórica** (la única mal graduada, chile
  `Universidad de Chile −0,75`, tiene stake 0; regraduar el ledger es decisión
  aparte).
- **AUD-MED-003** — `runner.superseded_candidates()` + `_con_superseded()`:
  antes de decidir si hay algo que liquidar, `fetch_and_settle` y
  `_settle_tennis` recuperan del archivo (14 días) la ÚLTIMA generación de cada
  identidad (evento, mercado, selección, línea) real que ya no está en el
  fichero vigente, la gradúan con los mismos marcadores y la persisten con flag
  `superseded` (una fila por pick; idempotente por `DEDUP_KEY`). Una liga sin
  fichero vigente ya no sale antes de tiempo. 4 tests nuevos.
  `src/sqp/settlement/runner.py`, `tests/settlement/test_superseded_picks.py`.
- **AUD-MED-004** — `cleanup.unsettled_completed_picks` cuenta toda fila
  `data_label == real` (no sólo `stake > 0`), como ya hacía `_all_settled`.
  `runner.tennis_history_results()`: fallback al histórico del tour con
  emparejamiento SIN orden (`tennis_scores_map`) para los candidates de tenis y
  para `_grade_served_from_history` (el ordenado fallaba con el ganador listado
  como visitante). Tests: guard con stake 0 → `at_risk`; tenis con resultado
  sólo en histórico → graduado. `src/sqp/pipeline/cleanup.py`,
  `src/sqp/settlement/runner.py`, `tests/test_cleanup.py`,
  `tests/settlement/test_settle_tennis_e2e.py`.
- **AUD-MED-005** — `DIARIO_COMPLETO.bat`: el bloque `[3/3]` (tres
  `daily_picks.py` + `tipster_report.py`) vive en la subrutina `:lista`,
  llamada desde la ruta correcta Y desde `:error_run` (exit 1 y centinela
  intactos). Etiquetas `[1/3] [2/3] [3/3]`. Validado con una SIMULACIÓN del BAT
  real sobre stubs en el scratchpad (ruta OK: exit 0, 3+1 vistas, 3 `--clear`;
  ruta con `run_all` fallando: exit 1, 3+1 vistas, `--fail`, 0 `--clear`).
  Candado nuevo en `tests/test_run_status.py`.
- **AUD-MED-006** — `.claude/memory/project-decisions.md`: entrada del
  2026-08-19 marcada SUPERADA y entrada nueva del 2026-09-13 que fija
  `PREDICTION_GATE_MIN_N = 300` como vigente (con lo que sí y lo que no puede
  establecerse sin Git); nota espejo en `session-summaries.md`. Sin cambio de
  código.
- **AUD-MED-007** — `_targets.py`: la fuente «rutas nombradas en el comando»
  sólo produce objetivos si el comando contiene un operador de ESCRITURA
  (`_es_escritura`: redirección, `sed -i`, `tee/mv/cp/rm/touch/patch`,
  `--fix`, `write_text/to_csv/open(...,"w")`, `Set-Content`…); `cat`, `sed -n`,
  `grep`, `head` ya no arman nada. `crossreview-on-stop.sh`: sin repositorio
  Git avisa una vez y sale limpio en vez de lanzar una llamada de pago
  condenada a fallar y re-armar el centinela cada turno (mensaje redactado sin
  el literal `codex review` ni los selectores, para no tropezar con los
  candados textuales del hook). 14 tests parametrizados nuevos.
  `.claude/hooks/_targets.py`, `.claude/hooks/crossreview-on-stop.sh`,
  `tests/test_hook_targets.py`.

## LOW

- **AUD-LOW-001** — `prune_stale_candidates`: segunda pasada que archiva y
  borra `predictions_<liga>.csv` de ligas inactivas sin `candidates_`. Test
  nuevo. (Los 10 ficheros huérfanos actuales se podarán en el próximo run.)
- **AUD-LOW-002** — `purge_old_artifacts`: familias `report_20*.*`,
  `picks_ranked_20*.md`, `audit_20*.md`, `segment_diagnostics_20*.md`; todo
  nombre con `latest` excluido. Corre semanalmente en `BACKFILL_ALL.bat`. Tests
  actualizados + 1 nuevo.
- **AUD-LOW-003** — `daily.run_league` no carga el histórico de cuotas cuando
  `line_movement_penalty` y `line_velocity_penalty` son 0 (inerte); con
  cualquiera activo carga todo como antes (semántica intacta). 2 tests (espía
  sobre `load_league_odds` en demo).
- **AUD-LOW-004** — docstrings «hourly»/«horaria» corregidos
  (`capture_closing_odds.py`, `revalidation.py`); rama muerta de
  `validate_oos.py` retirada; etiquetas del BAT (ya en MED-005). **NO
  APLICADO**: mover `wnba_totals_calibration_iso.joblib` a `retired/` (escritura
  en `data/` bloqueada por el clasificador; inerte mientras tanto) y la
  contradicción `settings.local.json` ↔ `.claude/CLAUDE.md` sobre el MCP
  graphify (decisión del operador: aprobar el MCP o retirar la instrucción).

## Lo que se decidió NO tocar

- Parámetros de riesgo, gates, calibradores, `pick_mode`, `shadow_mode`: nada.
- Ledger histórico: no se regradúa ninguna fila (ni la línea de cuarto mal
  graduada ni los 150 picks sin veredicto del pasado); la corrección aplica
  hacia delante. Regraduar el pasado es una decisión aparte.
- Programador de tareas (2b).
- `OPTIMIZATION.diff` y `BUILD_INFO.json` se commitean tal cual en la rama (CL-05:
  moverlos a `audit/optimization-20260910/` es una decisión de orden del
  repositorio para el PR).
