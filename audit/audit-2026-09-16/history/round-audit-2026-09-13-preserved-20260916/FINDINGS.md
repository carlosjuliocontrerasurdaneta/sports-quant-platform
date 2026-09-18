# Hallazgos — Auditoría integral 2026-09-13

Skill: `full-audit` (fases 0–3, solo lectura) y, tras autorización expresa,
`audit-remediation` (fases 4–5; ver CHANGES.md y VALIDATION.md). Severidades, IDs y estados de
evidencia según `.claude/skills/full-audit/references/evidence-findings.md`.
`CONFIRMADO = REPRODUCIDO ∨ VERIFICADO_ESTÁTICAMENTE`. Durante las fases 0–3 nada se
modificó en el proyecto: la única escritura fue este informe (`audit/latest/`),
y la ronda anterior (2026-09-10) se copió íntegra a `audit/audit-20260910/`
antes de escribir. Las modificaciones posteriores son de la Fase 4.

**Base auditada.** Árbol `C:\dev\3\sports-quant-platform`, que es el directorio
de PRODUCCIÓN (las 5 tareas `SQP_*` del Programador apuntan aquí) y **no es un
repositorio Git**. Integridad de partida: coincide con
`audit/audit-20260910/POST-REMEDIATION-HASHES.json` (662 ficheros) salvo 4
ficheros con cambios posteriores legítimos (`.claude/memory/project-decisions.md`,
`.claude/memory/session-summaries.md`, `Obsidian/Bitácora/2026-09-11.md` y el
centinela `.claude/.tests-pending`); sólo `.mcp.json`, `.claude/settings.local.json`
y `Obsidian/Bitácora/2026-09-12.md` son posteriores. Es decir: se audita el
estado tal como quedó tras la remediación del 2026-09-10 más dos sesiones de
infraestructura.

**Suite de partida** (Python 3.14.4, producción): `pytest -m "not slow"` → 1741
passed (396,6 s); `pytest -m slow` → 224 passed, 1 skipped (725,1 s). `ruff check
src scripts tests` → limpio. `mypy src` → limpio (101 ficheros). Ningún fallo.

---

## Resumen de estado (actualizado tras la Fase 4, 2026-09-13)

| ID | Sev. | Confianza | Evidencia | Estado tras la remediación |
|---|---|---|---|---|
| AUD-HIGH-001 | HIGH | HIGH | REPRODUCIDO | **corregido**: repositorio reconstituido en producción, rama `prod/remediacion-20260913` (ver CHANGES.md / VALIDATION.md) |
| AUD-HIGH-002 | HIGH | HIGH | REPRODUCIDO | **parcial**: parte técnica corregida (`open_dashboard.ps1` + liveness al logon); el modo de inicio de sesión de las tareas **requiere decisión del operador** |
| AUD-MED-001 | MEDIUM | HIGH | REPRODUCIDO | **corregido** (scoping por run vigente; 3 tests) |
| AUD-MED-002 | MEDIUM | HIGH | REPRODUCIDO | **corregido hacia delante** (`half_win`/`half_loss`; revisión `fable`); el ledger histórico NO se regradúa |
| AUD-MED-003 | MEDIUM | HIGH | REPRODUCIDO | **corregido hacia delante** (picks `superseded`; revisión `fable`); los 132 del pasado NO se regradúan |
| AUD-MED-004 | MEDIUM | HIGH | REPRODUCIDO | **corregido** (guard M2 sobre toda fila real + fallback histórico de tenis) |
| AUD-MED-005 | MEDIUM | HIGH | VERIFICADO_ESTÁTICAMENTE | **corregido** (subrutina `:lista` en ambas rutas; simulación del BAT) |
| AUD-MED-006 | MEDIUM | HIGH | VERIFICADO_ESTÁTICAMENTE | **corregido** (documental: decisión vigente registrada) |
| AUD-MED-007 | MEDIUM | HIGH | REPRODUCIDO / INFERIDO | **corregido** (`_es_escritura` + guard sin Git; tras HIGH-001 la sub-parte inferida deja de aplicar) |
| AUD-LOW-001 | LOW | HIGH | VERIFICADO_ESTÁTICAMENTE | **corregido** (poda de huérfanos; efectiva en el próximo run) |
| AUD-LOW-002 | LOW | HIGH | REPRODUCIDO | **corregido** (retención de 4 familias más; efectiva en el próximo `BACKFILL_ALL`) |
| AUD-LOW-003 | LOW | HIGH | REPRODUCIDO | **corregido** (carga condicional; semántica intacta) |
| AUD-LOW-004 | LOW | HIGH | VERIFICADO_ESTÁTICAMENTE | **parcial**: docstrings, etiquetas y rama muerta corregidos; el `.joblib` colapsado y la contradicción del MCP **requieren al operador** |
| AUD-INF-001 | MEDIUM | MEDIUM | INFERIDO | superado por HIGH-001 + guard del hook |
| AUD-INF-002 | LOW | LOW | INFERIDO | sin cambio (no confirmado) |
| AUD-NV-001..004 | — | — | NO_VERIFICABLE | sin cambio; B-01 sigue pendiente del operador |
| AUD-FP-001..007 | — | — | DESCARTADO | sin cambio |

---

## 4. Hallazgos confirmados

### AUD-HIGH-001 — Producción ejecuta un árbol sin control de versiones que diverge del repositorio publicado; el CI verde valida otro código

- **Categoría**: integridad de código / operaciones / CI-CD.
- **Severidad** HIGH · **Confianza** HIGH · **Evidencia** REPRODUCIDO.
- **Componente**: todo el árbol; `BUILD_INFO.json`; `DIARIO_COMPLETO.bat`
  (guard de árbol); `.claude/hooks/crossreview-on-stop.sh`;
  `.claude/hooks/_targets.py` (`--with-git`); `.github/workflows/ci.yml`.
- **Descripción**. El remoto existe y es alcanzable:
  `github.com/carlosjuliocontrerasurdaneta/sports-quant-platform` (público),
  `main` = `a401f06` (2026-09-09T20:53Z), CI verde (últimos 8 runs `success`,
  issues `ci-rojo` cerrados). Ese commit es exactamente `base_commit` de
  `BUILD_INFO.json`. El árbol de producción = `main@a401f06` + paquete de
  optimización (`OPTIMIZATION.diff`, 29 ficheros: pricing independiente,
  `settlement_math`, `setup_local`…) + remediación del 2026-09-10 (82 ficheros
  + 3 tests). **Nada de eso está en GitHub** y el árbol no tiene `.git`.
- **Evidencia** (dos métodos independientes):
  1. `BUILD_INFO.json` (654 hashes SHA-256 del paquete): **92 ficheros
     divergen** del paquete, 0 faltan, 15 nuevos.
  2. Comparación con el árbol Git de `a401f06` vía `gh api
     repos/…/git/trees/a401f06?recursive=1` (632 blobs) recomputando el SHA-1
     de blob de cada fichero local: **538 iguales, 94 difieren, 0 faltan en
     local, 41 ficheros locales no existen en `main`** (entre ellos
     `src/sqp/markets/independent.py`, `src/sqp/markets/settlement_math.py`,
     `src/sqp/models/independent.py`, `scripts/price_independent.py`,
     `scripts/setup_local.py`, `tests/test_league_id_validation.py`,
     `tests/test_temporal_cutoff.py`). Entre los que difieren: los 9 `.bat`,
     `configs/default.yaml`, `src/sqp/pipeline/daily.py`,
     `src/sqp/settlement/runner.py`, `src/sqp/config.py`, `scripts/run_all.py`,
     `scripts/validate_oos.py`, 35 ficheros de `.claude/`.
- **Condición de activación**: permanente. Se materializa en cualquier
  redespliegue, clonado, restauración o «sincronización» desde GitHub: el
  precedente es INC-20260910 (el paquete desplegado sobre producción se llevó
  `data/` y `.env`).
- **Resultado esperado**: producción = un commit identificable, publicado y
  validado por CI. **Observado**: la única copia de 5 HIGH + 19 MEDIUM + 24 LOW
  corregidos y de la feature de pricing independiente es este disco.
- **Causa raíz**: el paquete `local-optimization-20260910` se desplegó como
  árbol plano (`published_to_github: false`) y la remediación se hizo encima
  sin reconstituir el repositorio.
- **Impacto**. (a) Riesgo de pérdida total de las correcciones ante un fallo de
  disco o un despliegue. (b) El CI verde no dice nada de lo que corre: valida
  `a401f06`. (c) **Todos los controles que dependen de Git fallan abiertos en
  producción**: el guard de árbol limpio/atrasado de `DIARIO_COMPLETO.bat`
  («git no disponible: NO se pudo comprobar»), la revisión cruzada al cerrar el
  turno (`crossreview-on-stop.sh` resuelve `--commit HEAD`, ver AUD-MED-007) y
  la red de seguridad `git status` de `_targets.py --with-git`. (d) Sin Git,
  ninguna eliminación es reversible (ya lo señalaba B-06).
- **Alcance**: todo el proyecto.
- **Solución mínima propuesta** (requiere aprobación y, por la lista `deny` de
  `settings.json`, **al operador** para `git reset`): en el propio directorio,
  `git init` → `git remote add origin <url>` → `git fetch origin` →
  `git reset --mixed origin/main` (fija HEAD sin tocar el árbol de trabajo) →
  `git status` debe listar exactamente las 94+41 rutas anteriores → commit en
  rama `prod/remediacion-20260910` → push → PR a `main` para que el CI valide
  por fin el código de producción. Verificar antes que `.gitignore` sigue
  excluyendo `data/`, `logs/` y `.env` (verificado hoy: sí).
- **Alternativas**: clonar en otro directorio y copiar encima (rechazable:
  repite el mecanismo de INC-20260910).
- **Riesgo de regresión**: nulo sobre el código; el riesgo es operar mal Git
  sobre producción (por eso `--mixed` y nunca `checkout`/`reset --hard`).
- **Pruebas**: `git status` sin rutas de `data/`; suite completa en la rama;
  CI verde sobre el PR.
- **Limitaciones**: la autoría/fecha real de cada cambio no puede
  reconstruirse; el commit inicial será un «snapshot de producción».

### AUD-HIGH-002 — La generación diaria no se produjo 4 de los últimos 7 días y la ausencia es silenciosa por diseño

- **Categoría**: operaciones / monitorización (control inventariado ≠ control
  pasando).
- **Severidad** HIGH · **Confianza** HIGH · **Evidencia** REPRODUCIDO.
- **Componentes**: tareas `SQP_*` del Programador (LogonType `Interactive`,
  las 5); `scripts/open_dashboard.ps1`; `DIARIO_COMPLETO.bat` (`:salud`);
  `src/sqp/monitoring/health.py` (`pipeline_liveness`).
- **Evidencia**:
  - Días **sin una sola fila servida** en `data/calibration/served_*.csv`
    entre el 2026-08-25 y hoy: **2026-09-07, 09-08, 09-10, 09-11** (09-10 fue
    INC-20260910: run con exit 1 sobre `data/` vacío). Coincide con la ausencia
    de `report_20260907/08/11.*` y de `picks_ranked_20260907/08/11.md` en
    `data/predictions/`.
  - `Get-ScheduledTask`: las 5 tareas con `Logon: Interactive`;
    `SQP_Diario_Completo_Cdev` `LastRun 12-09-2026 12:00:02, LastResult 0`
    (no hay rastro de intentos los días perdidos).
  - `open_dashboard.ps1` (al iniciar sesión): `if (-not $isToday) { 'El reporte
    no es de hoy; se omite.'; exit 0 }` — **cuando el run no ha ocurrido, el
    tablero NO se abre**, que es exactamente el día en que debería avisar.
  - `health_check.py` sólo se ejecuta dentro de `DIARIO_COMPLETO.bat`
    (`:salud`): si el orquestador no arranca, `pipeline_liveness` nunca se
    evalúa. `data/output/pipeline_health.json` es del 12-09 y dice `OK`.
- **Condición de activación**: día sin sesión interactiva iniciada a las 12:00
  (o equipo apagado). B-07 del backlog anterior ya lo describía como riesgo;
  hoy está **medido**: 4/7.
- **Causa raíz**: (1) modo de inicio de sesión de las tareas (decisión del
  operador, no se toca sin orden); (2) la única señal de vida (dashboard al
  logon) se suprime precisamente cuando falta el run; (3) la comprobación de
  liveness vive dentro del proceso cuya ausencia debe detectar.
- **Impacto**: el producto principal del sistema (la lista diaria de picks, la
  REGLA FUNDAMENTAL) no existió el 57 % de los últimos 7 días y nadie recibió
  una alarma. Además cada día sin run deja picks sin refrescar y sin liquidar a
  tiempo (véase AUD-MED-004).
- **Solución mínima propuesta**: (a) `open_dashboard.ps1`: cuando el reporte no
  es de hoy, abrirlo IGUAL con un aviso visible (o abrir una página mínima
  «SIN RUN HOY») en vez de omitir; (b) que `open_dashboard.ps1` invoque
  `health_check.py` (liveness) al iniciar sesión, independientemente del
  orquestador; (c) **decisión del operador**: pasar las tareas a «ejecutar
  aunque el usuario no haya iniciado sesión» — fuera del alcance de una
  remediación de código.
- **Riesgo de regresión**: bajo (PowerShell de presentación).
- **Pruebas**: test del `.ps1` no existe hoy; añadir prueba de humo con
  `report_latest.html` de ayer → debe abrir/avisar.
- **Limitaciones**: `logs/` está denegado a esta sesión; no se ha podido
  consultar `diario_completo.log` ni el centinela `logs/run_status/`.

### AUD-MED-001 — La revalidación pre-partido es ciega para todo evento que empieza después de las 00:00Z del día de generación

- **Categoría**: corrección funcional / control de riesgo.
- **Severidad** MEDIUM · **Confianza** HIGH · **Evidencia** REPRODUCIDO.
- **Archivos**: `src/sqp/pipeline/revalidation.py:215` (`_filas_evaluables`) y
  `:425` (`revalidate_pitchers`); regla fijada por
  `tests/test_revalidation.py::test_skips_out_of_window_stale_price_and_old_rows`
  («ayer» → se salta).
- **Descripción**. Ambos pases filtran `generated_at[:10] != today` con
  `today = now.date()` en UTC. El run diario genera a las ~15:00Z; los partidos
  nocturnos de América (MLS, WNBA, MLB, NCAAF, Liga MX, sesiones nocturnas del
  US Open) empiezan a partir de las 00:00Z del día siguiente, así que cuando
  entran en la ventana de 120 min ya es «otro día» y ninguna pasada los evalúa.
- **Evidencia medida** (`data/bets/settled_*.csv`, picks con `generated_at ≥
  2026-08-16`, 484 filas): picks cuyo `game_date` = día de generación → **195
  de 369 revalidados (52,8 %)**; picks cuyo `game_date` = día siguiente → **2 de
  115 (1,7 %)**; +2/+3 días → 0 de 15. Las 115 son: ncaaf 21, mls 19, wnba 18,
  mlb 16, ligamx 9, US Open 12, brasileirao 4…
- **Causa raíz**: el «scoping por día» se pensó para no tocar un fichero
  rancio de ayer, y el test lo fija así, pero la clave elegida (día UTC de
  generación) no distingue «fichero de ayer» de «partido de esta noche».
- **Impacto**: el único control que puede retirar el stake de un pick cuyo
  precio o abridor cambió antes del partido no cubre la franja horaria donde
  más cambia la información (alineaciones nocturnas, abridores MLB). Hoy el
  efecto económico es nulo (stake 0 por el gate), pero el canal de medición
  `reval_action` queda sesgado a los partidos diurnos.
- **Solución mínima**: sustituir la comparación por «generado en el run más
  reciente del fichero» (p. ej. `generated_at[:10] == max(generated_at[:10])`
  del propio `candidates_*.csv`) o por antigüedad (`now - generated_at ≤ 36 h`),
  y actualizar el test para que «ayer» siga excluyéndose sólo cuando existe una
  generación más reciente.
- **Riesgo de regresión**: bajo; ampliar el conjunto evaluable nunca sube
  stakes (el pase sólo revoca).
- **Pruebas**: test nuevo con `generated_at` = ayer 15:00Z y evento a las
  01:00Z de hoy dentro de la ventana → debe evaluarse.

### AUD-MED-002 — `settle._grade` gradúa las líneas asiáticas de cuarto (±0,25/±0,75) como enteras: hay un caso ya mal graduado y 212 filas de evidencia del gate afectadas

- **Categoría**: corrección cuantitativa / liquidación.
- **Severidad** MEDIUM · **Confianza** HIGH · **Evidencia** REPRODUCIDO.
- **Archivos**: `src/sqp/settlement/settle.py:62-72` (`_grade`, rama
  `spreads`); `src/sqp/markets/settlement_math.py` (implementa la semántica
  correcta — `split_asian_line`, `combine_adjacent_lines` — pero declara «This
  research API does not change the legacy ledger/settlement contract»).
- **Descripción**. Para `spreads`, `_grade` calcula `adj = margin ± line` y
  devuelve win/push/loss; con `line = -0,75` y margen +1 el resultado real es
  «medio gana» (push en −1, win en −0,5), pero sale `win` completo; con −0,25 y
  empate sale `loss` completo en vez de «medio pierde».
- **Evidencia medida**: en `settled_*.csv` hay **22 filas** con línea de cuarto
  (brasileirao 5, chile 9, epl 1, laliga 3, ligamx 1, seriea 3). Recalculadas
  contra `data/historical/results_<liga>.csv` (16 con marcador disponible):
  **1 mal graduada** — chile, `Universidad de Chile −0,75`, margen +1, graduada
  `win` cuando es medio-win — y 15 correctas por casualidad del marcador. En el
  stream graduado (`graded_*.csv`) hay **536 filas** con línea de cuarto
  (todas `spreads`), **212 posteriores a `VALIDATION_START`**, es decir dentro
  de la muestra que decide el gate de predicción; a la tasa observada
  (1/16 ≈ 6 %) son ~13 etiquetas `y` incorrectas para `*|spreads` de fútbol.
- **Condición de activación**: la línea de consenso principal es de cuarto
  (`_pick_main_lines` la elige si es la más cotizada) y el margen cae en la
  zona de medio resultado.
- **Impacto**: hoy stake 0 → pnl 0 en las 22; con stake real el pnl de un
  medio-win/medio-loss quedaría duplicado o anulado. Para el gate: etiquetas
  binarias incorrectas en `spreads` de fútbol; efecto acotado.
- **Solución mínima**: en `_grade`, para `spreads`/`totals` con `line*4`
  entero y `line*2` no entero, descomponer con `split_asian_line` y devolver
  `half_win`/`half_loss` (nuevos valores de `result`), con `pnl` =
  ±0,5·stake·(precio−1) / −0,5·stake; consumidores (`realized_roi`,
  `_usable` del gate, `train_market_calibrators`, `degradation`) deben decidir
  el tratamiento de las medias (propuesta: `y = 0,5`, o excluir). Es un cambio
  de contrato del ledger → **clase de escalado (parámetro de liquidación)**:
  exige aprobación explícita y, según `MODEL_ROUTING.md`, el escalón `fable`.
- **Alternativas**: excluir las líneas de cuarto de las selecciones
  (`_pick_main_lines`) — evita el problema pero cambia qué se ofrece.
- **Pruebas**: casos −0,25/−0,75/+0,25/+0,75 con margen 0 y ±1.

### AUD-MED-003 — El ledger `settled_*` sólo gradúa la última vista de `candidates_*`: el 18 % de las unidades listadas nunca reciben veredicto (refresco antes del partido)

- **Categoría**: integridad de datos / métrica rectora.
- **Severidad** MEDIUM (HIGH en cuanto un mercado pase el gate) · **Confianza**
  HIGH · **Evidencia** REPRODUCIDO.
- **Archivos**: `src/sqp/pipeline/daily.py:434-445` (`_finalize` sobrescribe),
  `src/sqp/settlement/runner.py:448-503` (`fetch_and_settle` lee sólo
  `candidates_<liga>.csv`), `src/sqp/pipeline/cleanup.py:122-131`
  (`unsettled_completed_picks`: «Future-game picks are excluded — refreshing
  them is the normal daily behavior, not a loss»).
- **Evidencia medida** (archivo `data/predictions/archive/candidates_*_2026-08-16..09-08.csv`
  frente a `settled_*.csv` y `graded_*.csv`, unidad = (event_id, market)):
  **730 unidades listadas; 150 (20,5 %) nunca están en `settled_*` aunque el
  stream servido SÍ las graduó** (el resultado existía). De ellas, **132 dejaron
  de aparecer en `candidates_*` antes del día del partido** (el edge cayó bajo
  `min_edge` o cambió la línea) y 18 son AUD-MED-004. Ligas más afectadas:
  tennis_wta_us_open 22/73, seriea 17/41, mls 16/67, laliga 15/35, epl 12/30.
- **Causa raíz**: `candidates_*.csv` es una «última vista» y la liquidación
  sólo gradúa esa vista; un pick publicado el día D para un partido D+k que no
  sobrevive al refresco de D+1 desaparece del ledger sin `revoke` ni `void`.
  Es una decisión documentada (cleanup.py), pero su consecuencia sobre el
  ledger no lo está.
- **Impacto**: sesgo de supervivencia en `settled_*` — hit rate por banda del
  tablero, ROI realizado, ledger de banca y monitor de degradación sólo ven los
  picks que aguantaron hasta el día del partido. Con stakes reales, un pick
  apostado el día D y desaparecido el D+1 no se liquidaría nunca: la banca
  dinámica quedaría desalineada con el dinero real.
- **Solución mínima** (decisión de política, requiere aprobación): o bien (a)
  la liquidación gradúa también los picks archivados no supervivientes
  (`archive/candidates_<liga>_<día>.csv`, clave `DEDUP_KEY` completa, flag
  `superseded`), o bien (b) los picks publicados se restringen al día del
  partido. (a) preserva la REGLA FUNDAMENTAL.
- **Pruebas**: escenario pick día D, ausente D+1, partido D+1 → aparece en
  `settled_` con flag.

### AUD-MED-004 — El guard M2 (`unsettled_completed_picks`) sólo cuenta picks con stake > 0: con el gate en default-deny, un fallo de liquidación en día de partido se sobrescribe al día siguiente

- **Categoría**: integridad de datos / liquidación.
- **Severidad** MEDIUM · **Confianza** HIGH · **Evidencia** REPRODUCIDO.
- **Archivos**: `src/sqp/pipeline/cleanup.py:151` (`staked = cands[cands["stake"] > 0]`),
  `scripts/settle_all.py:66-78`, `scripts/run_all.py:154-166`.
- **Descripción**. La misma premisa que N-A-1 corrigió en `prune_stale_candidates`
  («settleable ≠ stakeable») sigue viva en el guard de sobrescritura: con todos
  los stakes a 0 (gate), `at_risk` siempre está vacío, `settle_all` devuelve 0
  aunque una liga fallara, y el run siguiente sobrescribe picks comenzados sin
  liquidar.
- **Evidencia medida**: **18 unidades (event, market)** que seguían listadas en
  `candidates_*` **el día del partido**, con resultado graduado en el stream
  servido, y que nunca entraron en `settled_*` (ni como `void`):
  tennis_wta_monterrey_open 7, tennis_wta_us_open 4, tennis_atp_us_open 4,
  wnba 2, ligamx 1. La ruta de tenis además gradúa candidates sólo contra el
  payload vivo de ESPN (`_settle_tennis`), sin el fallback histórico que sí
  tiene el stream servido.
- **Solución mínima**: contar en `unsettled_completed_picks` todas las filas
  `data_label == real` (no sólo `stake > 0`), como ya hace `_all_settled`; y
  en `_settle_tennis`, aplicar a los candidates el mismo
  `history_scores_map` que usa `_grade_served_from_history`.
- **Riesgo de regresión**: el run diario puede OMITIR una liga más a menudo
  (por diseño, para no perder picks); `SQP_ALLOW_UNSETTLED_OVERWRITE=1` sigue
  disponible.
- **Pruebas**: `tests/test_cleanup*.py`: pick stake 0 comenzado y sin liquidar
  → `at_risk` > 0.

### AUD-MED-005 — Un fallo en UNA liga de `run_all` aborta la generación de la lista diaria de TODAS (`[3/3]` de `DIARIO_COMPLETO.bat`)

- **Categoría**: robustez / REGLA FUNDAMENTAL.
- **Severidad** MEDIUM · **Confianza** HIGH · **Evidencia** VERIFICADO_ESTÁTICAMENTE.
- **Archivos**: `scripts/run_all.py:196-203` y `:377` (`return 1 if failures`),
  `RUN_DIARIO_ALL.bat` (`if %ERRORLEVEL% neq 0 goto :error`),
  `DIARIO_COMPLETO.bat` (`call RUN_DIARIO_ALL.bat` → `if %ERRORLEVEL% neq 0
  goto :error_run` ANTES de `[3/3]`).
- **Descripción**. `run_league` de una liga cualquiera lanza excepción →
  `failures=1` → exit 1 → `RUN_DIARIO_ALL` sale con 1 → `DIARIO_COMPLETO` salta
  a `:error_run` y no ejecuta `daily_picks.py` (×3) ni `tipster_report.py`,
  aunque las otras 20+ ligas se hayan generado y el tablero HTML ya exista. Los
  cuatro pasos están marcados «no bloqueante», pero nunca llegan a ejecutarse.
- **Condición de activación**: cualquier excepción por liga (proveedor caído
  para un torneo de tenis, fichero corrupto, KeyError de configuración).
- **Impacto**: la lista que exige la REGLA FUNDAMENTAL («se produce SIEMPRE y
  COMPLETA») no se produce por un fallo parcial. No se ha observado en los
  ficheros de `data/predictions/` de agosto–septiembre (todos los días con
  reporte tienen `picks_ranked`), de ahí que sea estático y no reproducido.
- **Solución mínima**: en `DIARIO_COMPLETO.bat`, ejecutar `[3/3]` también en
  la rama `:error_run` (o mover los cuatro comandos antes del `goto`),
  conservando el código de salida 1 y el centinela.
- **Pruebas**: `tests/test_run_status.py` ya inspecciona los BAT: añadir el
  candado «`daily_picks.py` aparece en `:error_run`».

### AUD-MED-006 — El registro de decisiones y la memoria de sesión afirman `PREDICTION_GATE_MIN_N = 100` (2026-08-19, «commit a5cb6ce»); el código, el pre-registro y el registro vivo dicen 300, y no hay decisión de reversión

- **Categoría**: sistema de instrucciones / memoria persistente / parámetro de gate.
- **Severidad** MEDIUM · **Confianza** HIGH · **Evidencia** VERIFICADO_ESTÁTICAMENTE.
- **Archivos**: `.claude/memory/project-decisions.md:253-258`,
  `.claude/memory/session-summaries.md:366-395`;
  `src/sqp/risk/prediction_gate.py:114` (`PREDICTION_GATE_MIN_N = 300`);
  `docs/research/2026-08-16-preregistro-regla-de-salida.md:43,147` (n ≥ 300, y
  la enmienda del 2026-09-04 dice «no se tocó ningún umbral»);
  `data/bets/prediction_gate.json` (`"min_n": 300`, 47 cortes, todos
  `muestra_insuficiente`).
- **Descripción**. Dos artefactos de memoria que `/memoria-cargar` inyecta al
  inicio de sesión registran como decisión vigente un umbral (100) que no está
  en vigor. No existe entrada posterior que la revierta, y sin Git en el árbol
  no puede comprobarse si `a5cb6ce` existió en `main` (no aparece en los 5
  últimos commits) ni cuándo volvió a 300.
- **Impacto**: una sesión futura que cargue la memoria puede «restaurar» 100
  creyendo aplicar la decisión registrada, sobre el parámetro que decide cuándo
  un mercado lleva stake real — justo la clase de cambio que el disparador de
  escalado reserva a revisión humana.
- **Solución mínima**: registrar en `project-decisions.md` la decisión vigente
  (300, con la fecha y motivo de la reversión si el operador la recuerda; si
  no, «reversión sin fecha registrada, vigente desde ≤ 2026-09-04 por el
  pre-registro de multiplicidad») y anotar en la entrada del 2026-08-19 que
  quedó superada. No tocar el código.
- **Pruebas**: `tests/test_claude_system_contract.py` podría fijar que el
  literal de `min_n` en `project-decisions.md` coincide con el del módulo.

### AUD-MED-007 — Los hooks se arman con comandos Bash de SOLO LECTURA: una auditoría dispara la suite completa y una llamada de pago a Codex al cerrar el turno

- **Categoría**: sistema de Skills/hooks.
- **Severidad** MEDIUM · **Confianza** HIGH · **Evidencia** REPRODUCIDO (armado);
  la sub-parte «Codex no puede ejecutarse sin Git» es INFERIDA.
- **Archivos**: `.claude/hooks/_targets.py:62-75` (fuente 2: «rutas nombradas
  en el comando que existan en disco», sin distinguir lectura de escritura);
  `.claude/hooks/mark-crossreview-pending.sh`, `mark-tests-pending.sh`,
  `check-secrets.sh`; `.claude/settings.json` (`PostToolUse` matcher
  `Edit|Write|Bash`).
- **Evidencia**: durante esta auditoría —sin una sola edición— los centinelas
  `.claude/.tests-pending` y `.claude/.crossreview-pending` aparecieron a las
  08:12, tras comandos `sed -n …/src/sqp/risk/prediction_gate.py` y `cat
  configs/default.yaml`. Consecuencia al cerrar el turno: `run-tests-on-stop.sh`
  (≈400 s medidos hoy para `-m "not slow"`, timeout 600 s) y
  `crossreview-on-stop.sh` → `codex review`. El diseño acepta sobre-disparar
  los hooks baratos, pero `_targets.py` documenta que el de revisión cruzada
  «no usa `--with-git` porque cada disparo es una llamada de pago» y aun así
  lo arma la fuente 2 con cualquier `cat`.
- **Sub-parte INFERIDA**: en este árbol `git rev-parse` falla, así que el hook
  resuelve `alcance="--commit HEAD"` y `codex review --commit HEAD` no tiene
  repositorio; el hook detecta rc≠0, restaura el centinela y lo reintenta en
  cada turno. No se ha ejecutado para no consumir cuota; `.crossreview-pending`
  existía ya al abrir la sesión (09-12 18:17), coherente con el reintento.
- **Solución mínima**: en `_targets.py`, para la fuente 2, sólo considerar
  «objetivo» una ruta cuando el comando contiene un operador de escritura
  (`>`, `>>`, `sed -i`, `tee`, `mv`, `cp`, `python -c … open(…,'w')`, heredoc
  `cat >`), y tratar `cat`/`sed -n`/`grep`/`head`/`tail` como lectura; en
  `crossreview-on-stop.sh`, salir con aviso si no hay repositorio Git en vez de
  reintentar cada turno.
- **Riesgo**: reducir falsos positivos puede perder algún verdadero (una
  escritura no reconocida); mantener `--with-git` como red en los hooks baratos.
- **Pruebas**: `tests/test_claude_system_contract.py` / tests de hooks
  existentes: caso `cat src/sqp/risk/x.py` → sin objetivo; `sed -i` → objetivo.

### AUD-LOW-001 — `prune_stale_candidates` nunca poda un `predictions_<liga>.csv` huérfano: 9 ficheros de torneos de julio–agosto siguen en `data/predictions/`

- **Severidad** LOW · **Confianza** HIGH · **Evidencia** VERIFICADO_ESTÁTICAMENTE
  (+ observado).
- **Archivos**: `src/sqp/pipeline/cleanup.py:97-124` (itera sólo
  `candidates_*.csv`; `_finalize` borra `candidates_` cuando no hay candidatos,
  así que la liga sale del bucle y `predictions_` queda para siempre).
- **Evidencia**: `predictions_tennis_atp_halle_open.csv`,
  `…queens_club_champ`, `…wta_bad_homburg_open`, `…wta_german_open`,
  `…wta_wimbledon` (07-29), `…wta_washington_open` (08-03),
  `…atp_cincinnati_open`, `…wta_cincinnati_open` (08-22/23), `uwcl` (09-02),
  `frauen_bundesliga` (09-06).
- **Impacto**: residuo; los consumidores de `predictions_*` los leen por liga
  concreta, así que no contaminan nada. Es el mismo patrón de «poda
  incompleta» que N-A-1.
- **Solución mínima**: segunda pasada en `prune_stale_candidates` sobre
  `predictions_*.csv` de ligas inactivas sin `candidates_` (archivar y borrar).

### AUD-LOW-002 — Familias de artefactos sin retención fuera del allowlist de `purge_old_artifacts`

- **Severidad** LOW · **Confianza** HIGH · **Evidencia** REPRODUCIDO (medido).
- **Evidencia**: `data/predictions/report_*.html` **81 ficheros, 36,0 MB
  (+1,2 MB/día)**; `report_*.md` 80; `picks_ranked_*.md` 14; `data/bets/audit_*.md`
  87; `segment_diagnostics_*.md` 57 (2,1 MB); `data/cache/odds/*.json` 267
  (24 MB, nunca se purga: el TTL sólo gobierna la lectura). `purge_old_artifacts`
  (`cleanup.py:194-249`) sólo cubre `archive/*.csv`, `clv_*.md` y
  `.closing_credits_*`.
- **Solución mínima**: añadir las familias regenerables (`report_*.html/.md`,
  `audit_*.md`, `segment_diagnostics_*.md`, `picks_ranked_*.md`, cache de
  cuotas) al allowlist con la misma retención de 90 días, conservando
  `report_latest.html` y `*_latest.csv`.

### AUD-LOW-003 — `run_league` carga el histórico COMPLETO de cuotas de cada liga en cada run para un término inerte

- **Severidad** LOW · **Confianza** HIGH · **Evidencia** REPRODUCIDO (medido).
- **Archivos**: `src/sqp/pipeline/daily.py:775-776`
  (`load_league_odds(league, ROOT/"data"/"odds")`),
  `src/sqp/markets/line_movement.py:31-41` (concatena TODOS los meses).
- **Evidencia**: `data/odds/` = 898,9 MB (76 ficheros). `mlb`: 8 ficheros,
  241,5 MB → `pd.concat` de **1.587.980 filas, 9,1 s, 342 MB de RAM**, cada run,
  para `event_line_movement`, cuyos coeficientes `line_movement_penalty` y
  `line_velocity_penalty` son **0,0** en `configs/default.yaml` (efecto nulo
  sobre `adjusted_edge`). Crece ~30 MB/mes sólo en MLB. La ronda 2026-09-08
  corrigió exactamente esto en los consumidores de 30 min (`revalidation.
  _league_odds(since=…)`) y dejó el diario.
- **Solución mínima**: reutilizar `_odds_files(root, league, since=now−7d)` (el
  horizonte de eventos) en `load_league_odds`, o saltar la carga cuando ambos
  coeficientes son 0.

### AUD-LOW-004 — Residuos documentales y artefactos inertes (agrupados por causa: deriva entre artefactos)

- **Severidad** LOW · **Confianza** HIGH · **Evidencia** VERIFICADO_ESTÁTICAMENTE.
- Inventario exacto:
  1. `scripts/capture_closing_odds.py:5` «Runs hourly» y
     `src/sqp/pipeline/revalidation.py:6` «captura de cierre horaria» frente al
     disparador real `PT30M` (AUD-LOW-003 del 09-06 corrigió sólo el BAT).
  2. `DIARIO_COMPLETO.bat`: etiquetas `[1/2]`, `[2/2]`, `[3/3]`.
  3. `data/models/wnba_totals_calibration_iso.joblib`: calibrador **colapsado**
     (constante 0,490 en todo el dominio; `structural_defect` = «colapsado (sin
     resolucion)») que sigue en el directorio live sin entrada en
     `calibration_methods.json`. Inerte —`apply_calibration` lo rechazaría—
     pero es el artefacto del incidente del 2026-08-28 sin retirar
     (`_set_best_method(None)` no borra el fichero).
  4. `.claude/settings.local.json` declara `"disabledMcpjsonServers":
     ["graphify"]` mientras `.claude/CLAUDE.md` ordena usar `graphify query`
     cuando existe `graphify-out/graph.json` (existe, 42 MB).
  5. `scripts/validate_oos.py:246-249`: rama `if not results:` inalcanzable
     (ya devolvió `False` en `:225-237`).
  6. `.claude/memory/*` referencia 12 rutas ya inexistentes (p. ej.
     `.claude/hooks/route-model.py`, `docs/loop-progress.md`,
     `.claude/skills/superpowers-main`); son históricas y no rompen nada.
- **Solución mínima**: corrección documental; (3) mover el `.joblib` a
  `data/models/retired/` (eliminación de dato → requiere aprobación expresa).

---

## 5. Hallazgos inferidos (no confirmados)

### AUD-INF-001 — La revisión cruzada de Codex no puede ejecutarse en este árbol (sub-parte de AUD-MED-007)
Severidad MEDIUM · Confianza MEDIUM · INFERIDO. Ver AUD-MED-007. Falta:
ejecutar `codex review --commit HEAD` aquí (no se hizo para no consumir cuota)
o leer el rastro del hook en el turno anterior.

### AUD-INF-002 — `SQP_Capture_Close_Cdev` tarda más que su intervalo tras el arranque
Severidad LOW · Confianza LOW · INFERIDO. Observado hoy: instancia del
`CAPTURE_CLOSE.bat` creada a las 07:51:44 (arranque diferido de la 07:30),
`python capture_closing_odds.py` creado a las **07:59:44** (8 min después, sin
explicación visible: entre medias sólo hay `cd`, `rotate_log.cmd` y `echo`) y
aún en ejecución a las 08:06; la instancia de las 08:00 fue rechazada
(`LastResult 0x800710E0`, política `IgnoreNew`). Sin acceso a
`logs/capture_close.log` no puede establecerse la causa. Se auto-recupera en
la pasada siguiente, así que no se eleva.

---

## 6. No verificables en este entorno

- **AUD-NV-001** Estado del centinela `logs/run_status/*.json` y contenido de
  todos los logs: regla `deny` `Read(./logs/**)` de `settings.json`.
- **AUD-NV-002** Cierre del ciclo de `VALIDATE_OOS` (B-01): la tarea sigue con
  `LastResult 1` del 2026-09-01 y próxima ejecución 2026-10-01; el código
  corregido (`validate_oos.py:225-237`) es correcto por lectura, pero ejecutar
  la puerta escribe informes y logs en producción y no se ha hecho.
- **AUD-NV-003** `pip-audit -r requirements.lock`: requiere red; no ejecutado.
  `pip-audit` es puerta bloqueante del CI, que está verde para `a401f06`, cuyo
  `requirements.lock` **difiere** del local (ver AUD-HIGH-001).
- **AUD-NV-004** Métricas cuantitativas vivas (Brier, ECE, CLV, ROI esperado):
  no se ha medido ninguna en esta ronda y ninguna se afirma. Lo único
  reportado son cifras del ledger: 1.360 filas liquidadas, 150 con stake
  (todas junio–julio), pnl realizado −84,25 sobre 552,14 apostados (ROI
  realizado −15,3 %), balance 915,75 — cifras históricas de shadow/real
  anteriores al gate, no una afirmación sobre el rendimiento actual.

## 7. Detecciones por herramientas pendientes

Ninguna: `ruff` y `mypy` no reportan nada, y la suite está en verde. No hay
alertas de herramientas sin validar.

## 8. Falsos positivos descartados

| ID | Sospecha inicial | Evidencia revisada | Motivo del descarte |
|---|---|---|---|
| AUD-FP-001 | `mlb_statsapi._get` llama a `session.get(url, **kwargs)` sin `timeout` | `:31` `kwargs.setdefault("timeout", _DEFAULT_TIMEOUT_S)` | el timeout existe por defecto |
| AUD-FP-002 | `.claude/skills/full-audit/SKILL.md` empieza con BOM UTF-8 antes de `---` | la skill aparece listada con su descripción y se invocó en esta sesión | sin efecto demostrable sobre la activación |
| AUD-FP-003 | `_apply_latch` consume el «test único de entrada» sin lock: dos evaluaciones simultáneas | sólo `run_all` y `update_prediction_gate.py` lo escriben; el diario corre bajo `IgnoreNew` | condición no alcanzable en el flujo programado; queda como nota |
| AUD-FP-004 | `.env` fija `CACHE_TTL_SECONDS=86400` como fallback de `ODDS_CACHE_TTL_SECONDS=1200` | `daily._cache_ttl_acotado` acota a 90 min; `closing_capture` usa `force_refresh=True`; `fetch_scores` no cachea | sin impacto mientras exista la variable específica; variable legada no documentada |
| AUD-FP-005 | La suite escribe en el árbol de producción durante los tests | comprobado con mtimes: sólo `data/predictions/demo/` y `data/calibration/demo/` (16 ficheros); los 3 ficheros no-demo tocados a las 08:06 son de la captura de cierre real | aislamiento por subdirectorio `demo/`, por diseño |
| AUD-FP-006 | `prediction_gate.json` evalúa 47 cortes con `K=41` (Bonferroni corto) | `PREDICTION_GATE_K_REPREGISTRO = 50` y el pre-registro del 2026-09-04 acepta hasta +22 % | dentro del margen pre-registrado; se avisa sólo al superar 50 |
| AUD-FP-007 | `_usable` compara `game_date > validation_start` como texto: `'nan' > '2026…'` sería True | `graded_*.csv`: 0 filas con `game_date` NaN o no-ISO en 24.324 | no alcanzable con los datos existentes; candado barato si se desea |
