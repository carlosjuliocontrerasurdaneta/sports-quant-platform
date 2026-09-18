# Verificación independiente — ronda `audit-2026-09-16`

Fecha: 2026-09-17. Ejecutada según `audits/prompts/verificar-remediacion.md`
(fase «Verificación independiente» de `.claude/automation/audit-workflow.md`).
Verificador: agente independiente, sin participación en el diagnóstico ni en
la remediación de esta ronda; los informes previos (`FINDINGS.md`,
`BACKLOG.md`, `CHANGES.md`, `VALIDATION.md`, `STATUS.md`, `claude/REPORT.md`)
se trataron como hipótesis a contrastar contra el código actual, no como
hechos.

## Alcance y base

- Base verificada: rama `main` en `1ee3571` (working tree limpio, confirmado
  con `git status -sb` → `## main...origin/main`, sin salida adicional).
  Divergencia con `origin/main`: `git fetch` + `git rev-list --left-right
  --count HEAD...origin/main` → `0  0`.
- CI remoto para `1ee3571`: run `35227142998`, **success**.
- `C:\dev\3\sports-quant-platform` (producción): `git rev-parse HEAD` →
  `1ee3571…` (idéntico a `main`), `git status -sb` limpio. El `git pull`
  pendiente que registraba `STATUS.md`/`CHANGES.md` ya se completó; no queda
  acción de producción abierta para esta ronda.
- Intérprete: Python 3.14 (win32), mismo entorno que el resto de la ronda.
- Exclusiones heredadas de la ronda (no re-verificadas: no forman parte de la
  remediación de esta ronda): `logs/`, `.env` (permiso denegado), suite
  `slow`, `pip-audit` local.
- No se editó código, tests, configuración ni datos. No se hizo commit ni
  push. Único cambio: este documento, la columna «Verificación» de
  `STATUS.md` y la actualización de `MANIFEST.json`, con histórico
  preservado en `audit/latest/history/verification-20260917T134633Z/`
  (copias verificadas byte-idénticas por hash antes de reemplazar).

## Metodología

Por cada ID: reconstrucción de causa/activación a partir del diagnóstico,
inspección del diff `44e48f2..1ee3571` y de los llamadores, reproducción
independiente (oráculos propios, no reutilización de los tests nuevos como
única evidencia) cuando fue seguro, ejecución de los tests relevantes y
comprobación explícita de cada criterio de aceptación del `BACKLOG.md`.
Búsqueda deliberada de bypasses, regresiones y consumidores no listados.

## Estado y evidencia por ID

### AUD-001 (HIGH, P1) — pricing de líneas de cuarto — **verificado-corregido**

Oráculo propio (no reutiliza `distributions.py` salvo la función bajo prueba):
recalculo del grid Poisson y de `_grade_linea`/`combine_adjacent_lines` de
forma independiente para 6 líneas de cuarto (spreads home −0,25/+0,75, away
+0,25/−0,75; totales 2,25/2,75) con λ distintos de 1,5/1,0
(λ ∈ {0,8–2,1}). Desviación máxima frente a `poisson_match_probs`:
`2,22e-16` (precisión de punto flotante). No-regresión confirmada del mismo
modo para spread entero (−1), spread medio (−0,5), total medio (2,5) y total
entero (3): desviación máxima `2,8e-17`. `spread_line=total_line=None`
devuelve únicamente `home_win`/`away_win`, sin claves de línea.

Búsqueda de bypass: `sports/adapters.py::PoissonAdapter.estimate` y
`estimate_f5` llaman ambos a `dist.poisson_match_probs` (la función
corregida); no hay ruta alternativa de pricing Poisson en el pipeline vivo.
`models/independent.py::FrozenScoreModel.price` (módulo offline, no importa
el pipeline vivo) ya usaba `split_asian_line`/`combine_adjacent_lines`
incondicionalmente antes de esta ronda — no estaba afectado y sigue
correcto para toda línea, cuarto o no.

Hallazgo adyacente confirmado y **recuantificado** (`normal_margin_probs`/
`normal_total_probs`, usadas por `NormalMarginAdapter` en basketball/football
en vivo): mismo patrón — para una línea de cuarto, el código toma la rama
`else` (sin descomposición en las dos líneas adyacentes ni combinación de
medias) porque el umbral nunca es entero. Barrido propio sobre los `sigma`
reales de `sports/registry.py` (margin: 13,0/13,5/14,0/16,0/18,0/20,0; total:
13,5/15,5/17,0/18,0/19,0/22,0), con `mu` explorado en rejilla fina
(±3,2·sigma) en vez de puntos sueltos: desviación máxima medida **0,32 pp**
(spread, sigma=13,0, mu≈12,14 respecto a la línea) y **0,30 pp** (total,
sigma=13,5). El `≤0,25 pp` registrado en `CHANGES.md`/`STATUS.md` es algo
optimista frente a esta medición más exhaustiva; sigue, no obstante, por
debajo de `min_edge` (0,02 = 2 pp) en un orden de magnitud, así que la
consecuencia operativa declarada (ningún pick cruza el gate por este efecto
hoy) se sostiene. Confirmado como real, no ticketeado en esta ronda por
decisión explícita del backlog; recomendado abrir ticket LOW la próxima
ronda con la magnitud corregida (0,3 pp, no 0,25 pp).

Tests: `pytest tests/test_distributions.py tests/test_settlement_math.py
tests/test_distribution_validation.py` → 106 passed. Suite ampliada
(adaptadores/pipeline/F5/pricing): 166 passed. `ruff`/`mypy` limpios sobre
los ficheros tocados.

### AUD-002 (MEDIUM, P2) — ROI realizado con tres definiciones — **verificado-corregido**

Reproducción propia (DataFrames construidos a mano, sin reutilizar el test
nuevo): caso A (una fila `half_win`, stake 10, pnl 2,5) → `realized_roi_parts`,
`runner.realized_roi`, `roi_engine._summarize` (`by_market`) y
`report._segment_audit` dan los cuatro **0,25**. Caso B (una `win` stake 10
pnl 10 + una `half_win` stake 10 pnl 2,5) → los cuatro dan **0,625**
(= 12,5/20, verificado a mano). Caso C (solo push/void) → pnl=0, stake=0,
sin ROI en ningún punto. `html_report._audit_section` llama directamente a
`realized_roi_parts`/`staked_mask`, por lo que hereda la misma consistencia
sin necesidad de un quinto cálculo independiente.

`_segment_audit`: `n` cuenta únicamente filas decididas (win/loss, vía la
nueva columna auxiliar `_decided`) — numéricamente idéntico al `n` anterior
(que ya era solo win/loss); `hit_rate` sigue sobre win/loss (dirección
conservadora, sin cambio de semántica); `staked`/`pnl`/`realized_roi` ahora
sobre el conjunto con medias incluidas. `by_market` en `roi_engine._summarize`
asigna `pnl` con `.where(graded_mask, 0.0)` además de `stake_graded`, así que
el ROI por mercado usa el mismo conjunto en ambos lados, no solo el global.

Búsqueda de otros consumidores con el patrón «pnl global + stake filtrado»
(`grep isin(["win","loss"]) + pnl`): `audit/patterns.py::hit_rate` y
`audit/clv.py::compute_clv` también filtran a `win/loss`, pero calculan
`staked`/`pnl` **sobre el mismo subconjunto filtrado** en ambos lados (o, en
`clv.py`, no calculan ROI en absoluto) — no reproducen el defecto de AUD-002
(conjuntos distintos en numerador y denominador). `patterns.hit_rate` es una
cuarta definición de "ROI" pero autoconsistente y declarada como tal en su
docstring ("GRADED bets only (win/loss); medias excluidas"); no está en el
alcance de los cuatro consumidores listados en `BACKLOG.md` y no se tocó en
esta remediación. Se registra como observación, no como defecto ni regresión.

Tests: `tests/test_realized_roi_consistency.py` → 3 passed;
`tests/test_roi_engine.py` → 18 passed; batch ampliado (settle/roi/report/
html/dashboard/backtest) incluido en la corrida de 237 tests, sin fallos.

### AUD-003 (MEDIUM, P1) — HEAD autoconsistente / divergencia — **verificado-corregido**

`python scripts/sync_agent_instructions.py --check` → `Agent instructions:
synchronized`, rc 0. `pytest tests/test_agent_instruction_sync.py
tests/test_tennis_params.py tests/test_claude_system_contract.py` → 37
passed. `git status -sb` → limpio, sin divergencia (`0 0` commits
adelante/atrás de `origin/main`). `gh run list --branch main --limit 3`:
tres runs, los dos relevantes a HEAD/remediación en `success`. Corrección al
diagnóstico confirmada de forma independiente: `C:\dev\3\sports-quant-platform`
(producción) está en `1ee3571`, igual que `origin/main`; el `git pull`
pendiente que registraba la ronda ya se ejecutó.

### AUD-004 (MEDIUM, P2) — residuo `.codex-tmp/pytest` — **verificado-corregido**

`.codex-tmp/pytest.bloqueado-20260916` y `.codex-tmp/pytest/openai-20260916-retry`
ya no existen (comprobado con `test -e`). `pytest -p no:cacheprovider
--basetemp=.codex-tmp/pytest tests/audit/test_history_loader.py` → 4 passed,
sin `PermissionError`. Comando canónico operativo.

### AUD-005 (MEDIUM, P2) — `execution.books` sin cablear — **verificado-mitigado**

`ExecutionConfig` y el comentario de `configs/default.yaml` declaran
explícitamente "SIN CABLEAR"; `Settings.load` emite `log.warning` cuando
`s.execution.books` es no vacío, verificado que se activa tanto si el yaml
declara `books` como si lo hace `EXECUTION_BOOKS` (ambos alimentan el mismo
atributo antes de la comprobación). `grep _execution_prices src tests`
confirma que sigue sin llamadores fuera de `pipeline/probabilities.py` (su
definición) y `tests/test_line_shopping.py`; el candado
`test_execution_prices_sigue_sin_llamadores_en_el_pipeline` está presente y
pasa. No contradice la decisión `9dfb4cc`. Riesgo residual explícito y
aceptado por el propio backlog: cablearlo sigue pendiente de decisión del
operador (clase «escalado»), fuera del alcance autorizado de esta
remediación.

Tests: `tests/test_line_shopping.py` incluido en el batch de 237 (passed).

### AUD-006 (LOW, P3) — centinela de tests con árbol sucio — **verificado-corregido**

Reproducción propia en un repositorio Git temporal aislado bajo
`.codex-tmp/verify-aud006/repo` (sin ensuciar este repositorio): árbol con un
fichero trackeado modificado y uno sin trackear, ejecutando
`.claude/hooks/_targets.py --with-git` vía `CLAUDE_PROJECT_DIR` apuntando al
repo temporal. Comando de **lectura** (`cat tracked.py`) → 0 rutas devueltas.
Comando de **escritura** (`echo hi > tracked.py`) → devuelve las 2 rutas del
`git status` (el fichero modificado y el sin trackear), como se espera del
candado. Confirma `_es_escritura` como predicado único y compartido entre la
fuente 2 (`_del_comando`) y la fuente 3 (`_de_git`), sin discrepancia.

Tests: `tests/test_hook_targets.py tests/test_audit_hooks.py` incluidos en
el batch de 237 (passed).

### AUD-007 (LOW, P3) — huella `ROOT` vs `--data-root` — **verificado-corregido**

Inspección de código: `feature_shadow.py` líneas 103, 140 y 171 usan
`fingerprint(ROOT)` en los tres puntos (dos en `train`, uno en
`load_protocol`); antes del parche `train` usaba el parámetro `root` (que
`--data-root` puede hacer distinto de `ROOT`) en las líneas 103/140. La
huella es ahora simétrica por construcción: cualquier valor de `root`
producirá el mismo `code_hash` en `train` y en `load_protocol`, porque ambos
dependen únicamente de `ROOT`.

Tests: `tests/test_feature_shadow.py` incluido en el batch de 237 (passed).

## Regresiones

Ninguna detectada (`REG-###`: no aplica). Revisión específica de
`_segment_audit` (semántica de `n`/`hit_rate`/`n_staked`) y de `by_market`
en `_summarize`: ambas preservan el comportamiento previo cuando no hay
medias, y corrigen el conjunto cuando las hay, tal como reclama `CHANGES.md`.
No se detectó ningún efecto de AUD-001 sobre `markets/edge.py` o
`risk/kelly.py`: ninguno de los dos ficheros cambió en el diff
`44e48f2..1ee3571`, ninguno referencia `poisson_match_probs`/
`decision_probability`/`home_cover`/`over` directamente; consumen las
probabilidades servidas por los adaptadores como entrada opaca, así que el
efecto de AUD-001 es exclusivamente un cambio en el VALOR de esa entrada
(intencionado), no en la fórmula de edge/Kelly.

## Herencia (rondas anteriores)

- **B-02** (acciones CI sin pin a SHA): confirmado aún abierto —
  `.github/workflows/ci.yml` usa `actions/checkout@v4` y
  `actions/setup-python@v5`. Consistente con `STATUS.md`.
- **CL-02** (`wnba_totals_calibration_iso.joblib`): **discrepancia de
  bookkeeping, no de código.** El fichero ya reside en
  `data/models/retired/wnba_totals_calibration_iso.joblib` (no en la ruta
  activa) y no aparece referenciado en ninguna configuración de calibración
  del repositorio (`grep` sin resultados). `STATUS.md`/`BACKLOG.md` siguen
  describiéndolo como "abierto, pendiente de retirar con aprobación expresa",
  como si el traslado no se hubiera hecho. `data/` no está bajo control de
  Git en este repositorio, así que no hay forma de fechar el movimiento ni de
  confirmar si medió la aprobación expresa que exige el backlog: se declara
  **NOT_VERIFIABLE** si el movimiento ya ejecutado contó con esa aprobación.
  No es un hallazgo de código y no bloquea el veredicto, pero conviene que la
  próxima ronda actualice `STATUS.md`/`BACKLOG.md` para que reflejen el
  estado real del fichero.

## Validación global

| Comando | Resultado |
|---|---|
| `ruff check src scripts tests` | All checks passed |
| `mypy src` | Success: no issues found in 105 source files |
| `pytest -q -p no:cacheprovider --basetemp=.codex-tmp/pytest-verify-20260917 <lote AUD-001/002/005/006/007 + settlement_math/settle_candidates/html_report/distribution_validation>` | 237 passed |
| `pytest tests/test_roi_engine.py` | 18 passed |
| `pytest tests/test_analytical_skill_examples.py tests/test_pricing_prompt_formulas.py tests/test_claude_model_routing.py` | 95 passed |
| `pytest tests/test_agent_instruction_sync.py tests/test_tennis_params.py tests/test_claude_system_contract.py` | 37 passed |
| `pytest -q -p no:cacheprovider --basetemp=.codex-tmp/pytest tests/audit/test_history_loader.py` (comando canónico AUD-004) | 4 passed |
| `pytest -q -p no:cacheprovider --basetemp=.codex-tmp/pytest-verify-20260917-full -m "not slow"` (suite completa) | **1958 passed, 225 deselected**, exit 0 (375,93 s) — coincide exactamente con `tests_final` de `MANIFEST.json` |

No ejecutado (exclusión declarada, heredada del diagnóstico, no de esta
verificación): suite `slow`, `pip-audit` local, `logs/`, `.env`.

## P0/P1 abiertos

Ninguno. Los dos P1 de la ronda (AUD-001, AUD-003) están verificados como
corregidos con evidencia reproducida de forma independiente.

## Limitaciones

- Un solo verificador (sin segunda opinión), igual que el diagnóstico y la
  remediación de esta ronda.
- `logs/`, `.env`, suite `slow`, `pip-audit` local: no verificables por las
  mismas razones que en el diagnóstico (permiso/tiempo), sin cambio de
  estado en esta fase.
- CL-02: ver «Herencia» arriba — discrepancia de bookkeeping declarada como
  NOT_VERIFIABLE, no como hallazgo de código.
- La cuantificación del hallazgo adyacente Normal (0,32 pp) usa una rejilla
  fina pero finita (±3,2·sigma, 20001 puntos); no es una prueba analítica
  del máximo global, aunque es más exhaustiva que la medición original.

## Próxima acción

- Bookkeeping de la ronda (Obsidian, `.claude/memory/`,
  `.claude/automation/runtime/current-task.md`) según lo declarado pendiente
  en `STATUS.md`: fuera del alcance de esta fase de verificación.
- Abrir ticket LOW en la siguiente ronda para
  `normal_margin_probs`/`normal_total_probs` con líneas de cuarto (magnitud
  medida: 0,32 pp, no 0,25 pp), reutilizando la plantilla de
  `models/independent.py::FrozenScoreModel._single_line` como ya propone
  `STATUS.md`.
- Corregir en la próxima ronda la descripción de CL-02 en `STATUS.md`/
  `BACKLOG.md` para que refleje que el fichero ya está en `retired/`.
- Decisión del operador, sin cambios de este informe: cablear o no
  `execution.books` (AUD-005) y aprobación formal de CL-02.

## Veredicto

**APTO CON PENDIENTES** (regla 3 de `audits/prompts/verificar-remediacion.md`):
evidencia suficiente y reproducida de forma independiente para los 7 IDs,
validaciones global y por lote satisfactorias (ruff, mypy, 387 tests
dirigidos + 1958 de la suite completa, todo verde), sin ningún P0/P1 abierto
ni bloqueo confirmado de rondas anteriores — pero con hallazgos menores y
riesgos declarados por seguir: el hallazgo adyacente Normal (recuantificado
a 0,32 pp, sin ticket, para la próxima ronda), la decisión pendiente del
operador sobre `execution.books` (AUD-005), B-02 (pin de acciones CI) y la
discrepancia de bookkeeping de CL-02.

Este veredicto califica la remediación evaluada en esta ronda; no certifica
ausencia absoluta de defectos en el repositorio ni rentabilidad o ventaja
predictiva del sistema.
