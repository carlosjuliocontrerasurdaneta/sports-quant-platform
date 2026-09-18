# Backlog priorizado — ronda `audit-2026-09-16`

Nada se ejecuta sin autorización explícita por ID, grupo inequívoco o «todos
los confirmados» (`audit-remediation`). Orden: prioridad → impacto →
dependencias → riesgo. Los cambios marcados **escalado** tocan parámetros de
modelo, artefactos persistidos o decisiones registradas y, según el principio
rector de `CLAUDE.md`, requieren el escalón de máximo razonamiento y decisión
del operador además de la autorización de remediación.

| # | ID | Prio | Cambio mínimo | Archivos | Pruebas | Criterio de aceptación | Dependencias / riesgo | Autorización pendiente |
|---|---|---|---|---|---|---|---|---|
| 1 | AUD-003 | P1 | Commit coherente con `.claude/automation/{audit-workflow,loop-guardrails,INSTRUCTIONS}.md`, prompts regenerados, `tests/test_tennis_params.py` y `test_claude_model_routing.py`; `git fetch`; rebase/merge resolviendo `Obsidian/Tareas.md` y `Bitácora.md`; push; CI verde | `.claude/**`, `audits/prompts/*`, `tests/*` | `sync_agent_instructions.py --check`; suite sobre checkout limpio; `gh run list` | CI verde para el commit que ejecuta producción; `git status` sin ficheros sin trackear que el código necesite | Conflictos en Obsidian; hacerlo antes de las 12:00 evita el aviso «6 commits por detrás» del guard | **commit + push** (operación Git) |
| 2 | AUD-001 | P1 | En `poisson_match_probs`/`PoissonAdapter.estimate`: para líneas de cuarto, descomponer con `split_asian_line`, acumular `win/half_win/push/half_loss/loss` y servir `SettlementProbabilities.decision_probability`; revisar `estimate_f5` | `src/sqp/models/distributions.py`, `src/sqp/sports/adapters.py`, `src/sqp/pipeline/probabilities.py` (si el EV con push cambia) | test paramétrico modelo vs `_grade` (±0,25, ±0,75, 2,25, 2,75) tol 1e-9; no-regresión byte-idéntica en líneas enteras/medias; `test_settlement_math` | desviación ≤ 1e-9 frente a la liquidación; líneas no-cuarto sin cambio; suite verde | Cambia probabilidades servidas de ~2 % de las líneas (fútbol); las etiquetas históricas de calibración de esas líneas siguen con semántica antigua — documentarlo | **escalado** (parámetro de modelo) |
| 3 | AUD-002 | P2 | Una función canónica de ROI realizado (medias en numerador y denominador, como el ledger de banca) reutilizada por `roi_engine._summarize`, `html_report` y `audit/report.py` | `src/sqp/settlement/runner.py`, `src/sqp/backtesting/roi_engine.py`, `src/sqp/audit/html_report.py`, `src/sqp/audit/report.py` | caso media sola y mezcla media+win en los tres consumidores; candado contra `pnl` global con `stake` filtrado | mismo ROI en los cuatro puntos para el mismo `settled` | Antes del `VALIDATE_OOS` del 2026-10-01; decidir si las medias cuentan (recomendado sí) | remediación ordinaria; **decisión** sobre la definición |
| 4 | AUD-004 | P2 | Eliminar `.codex-tmp/pytest/openai-20260916-retry` con privilegios (`takeown`/`icacls`) o desde el sandbox que lo creó; opcionalmente documentar sub-basetemp por auditor en `AGENTS.md` | fuera del árbol Git (`.codex-tmp/` ignorado) | `pytest -p no:cacheprovider --basetemp=.codex-tmp/pytest -m "not slow"` verde | comando canónico ejecutable | ninguno | **operador** (borrado con privilegios) |
| 5 | AUD-005 | P2 | Sin contradecir `9dfb4cc`: anotar en `configs/default.yaml` y `Settings.validate` que `execution.books` está sin cablear y avisar (`log.warning`) si se declara no vacío; o cablear `_execution_prices` en `daily.py` bajo decisión explícita | `configs/default.yaml`, `src/sqp/config.py` (o `pipeline/daily.py`) | test que fije el estado elegido | ningún ajuste de configuración queda silenciosamente inerte | Cablear cambia precios de ejecución → escalado; la variante «aviso» es ordinaria | decisión del operador entre las dos variantes |
| 6 | AUD-006 | P3 | Fuente 3 de `_targets.py`: sólo ficheros cuyo `git status` cambió durante el turno, o desactivarla cuando el comando no contiene operadores de escritura | `.claude/hooks/_targets.py`, `mark-tests-pending.sh`, tests de hooks | test: Bash de lectura con árbol sucio no arma el centinela; escritura sí | sesiones de solo lectura no pagan la suite en cada Stop | ninguno | ordinaria |
| 7 | AUD-007 | P3 | `fingerprint(ROOT)` en `train` y en la comprobación previa a escribir el protocolo (la huella es del código) | `src/sqp/evaluation/feature_shadow.py` | test con `root` ≠ `ROOT` que entrena y luego carga | `load_protocol` acepta experimentos entrenados con `--data-root` distinto | ninguno | ordinaria |

## Heredado (persistente de rondas anteriores)

- **B-02** Pin de acciones de CI a SHA (`ci.yml` usa `@v4/@v5`): abierto, P3.
- **CL-02** `data/models/wnba_totals_calibration_iso.joblib` inerte, pendiente
  de retirar a `retired/` con aprobación expresa (dato de modelo).

## Observaciones sin acción propuesta

OBS-1 (train/serve del ML de investigación), OBS-2 (gate: 48 cortes con K=41,
límite 50), OBS-3 (`eval` sobre Markdown en tests), OBS-4 (dashboard
interactivo rc 267014). Ver `claude/REPORT.md`.
