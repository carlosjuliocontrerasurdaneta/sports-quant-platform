# VERIFICATION — ronda `audit-2026-11-03`

- **Fecha:** 2026-11-04 (UTC 12:01 al empezar a escribir).
- **Verificador:** subagente independiente con Fable 5.1 (`claude-fable-5-1`), en solo lectura del proyecto. Lo despachó la sesión principal, que coordinó la remediación pero no la verifica. El verificador no implementó nada de esta remediación.
- **Procedimiento:** `audits/prompts/verificar-remediacion.md` (fuente: `.claude/automation/audit-workflow.md`, «Verificación independiente»).

## Veredicto: APTO CON PENDIENTES

Regla aplicada: la primera aplicable de las cuatro del contrato es la 3.

- **No hay NO APTO.** El único P1, AUD-002, está corregido: el BAT real espera al árbol limpio y aborta con centinela solo al agotar el plazo (4 escenarios ejecutados contra el BAT real copiado a un repo temporal). Ninguna regresión confirmada es P0/P1. No se encontró ninguna corrección importante con evidencia inválida.
- **No hay VERIFICACIÓN INCOMPLETA.** Cada ID tiene evidencia actual: tests acotados (398 + 429 passed, ver §4), `ruff` y `mypy` en rc 0, CI de `786daeb` verde en las 7 tareas de test, reproducciones independientes y lectura en vivo del Programador de tareas.
- **Quedan pendientes menores:** 2 regresiones LOW/P4 (REG-001, REG-002), un defecto preexistente con la misma causa raíz que AUD-006 y no extendido (NEW-001, P3), AUD-022 bloqueado por decisión del operador (P4), y riesgos residuales declarados en AUD-014, AUD-016, AUD-018 y AUD-019.
- Este dictamen califica solo la remediación evaluada. No afirma ventaja predictiva ni rentabilidad, y no garantiza ausencia absoluta de defectos.

## 1. Alcance, base, metodología y limitaciones

### Base

- `main` @ `786daeb26bdd6dfcd3e5994005ed8ef9fc46bac6`. Árbol limpio al empezar (`git status --porcelain` vacío).
- Remediación evaluada: `ead24b2`, `77110b4`, `df015bf`, `1e50400`, `914707c`, `1832272`, `4d10703`. `786daeb` solo toca documentación (`audit/latest/*`, memoria y bitácora), comprobado con `git diff --stat 4d10703..786daeb`.
- Línea base de diagnóstico: `FINDINGS.md` (sha256 `b47b29e9…`) y `BACKLOG.md` (`d07b1b29…`), sin modificar.
- Fuente de verdad: el código actual. `CHANGES.md` y `VALIDATION.md` son evidencia secundaria del implementador.

### Método por ID

1. Reconstruir la causa original (`FINDINGS.md`, `claude/REPORT.md`).
2. Leer el parche (`git show <commit>`) y sus llamadores (`grep` sobre `src/` y `scripts/`).
3. Reproducir cuando era seguro: scripts propios en el scratchpad de la sesión, directorios temporales, `SQP_LOG_DIR` apuntando fuera de `logs/`.
4. Ejecutar los tests relevantes y comprobar cada criterio de aceptación de `BACKLOG.md`.
5. Buscar regresiones, rutas alternativas, síntomas ocultados y fallos trasladados.

### Evidencia secundaria evaluada

Los 10 candidatos de una revisión de código previa (una sola pasada, sin verificar), recibidos por mensaje de la sesión principal. El fichero indicado (`…/tasks/ae2fea1f2f1cf3035.output`) tenía 0 bytes. Resultado de cada uno en §3.

### Exclusiones

- No se ejecutaron el BAT de producción, `validate_oos` completo ni `scripts/research/intraday_gate_analysis.py`.
- Sin llamadas a Odds API ni a servicios de pago; sin escrituras en GitHub; sin commits ni push.
- No se re-ejecutó localmente la suite completa (≈57 min). Se cita como secundaria la del implementador (3502 passed, 1 skipped sobre `4d10703`) y como evidencia independiente el CI de `786daeb` (`gh run view 41786550657`: success).

### Limitaciones

- `.env` no se leyó (denegado). Por eso `PICK_MODE` efectivo es NOT_VERIFIABLE. Indicio indirecto: los `candidates_*.csv` del run del 2026-11-03 (23:53 UTC) no llevan ningún flag `accuracy_mode`, y el yaml dice `picks.mode: edge`.
- No se leyeron árboles de `logs/` ni datasets completos. La única lectura de datos fue un agregado programático del stream servido graduado para simular la migración del gate en un directorio temporal (§2, AUD-001).
- La afirmación de Fable de que 13 tests nuevos de G1 fallan sobre la base no se re-ejecutó. La discriminación se comprobó con una reproducción propia (§2, AUD-001).

### Efectos laterales

- Ninguno sobre el proyecto. La simulación del gate escribió solo en un directorio temporal del sistema, que se borró. Los logs de los scripts fueron a `SQP_LOG_DIR` en el scratchpad.
- Los tests escribieron en `.codex-tmp/verif-a` y `.codex-tmp/verif-b`, como pide el contrato.

## 2. Estado por ID

| ID | Prio. | Estado de verificación | Evidencia | Riesgo residual |
|---|---|---|---|---|
| AUD-001 | P2 | **verificado-corregido** | `_ev_lado_del_modelo` (`prediction_gate.py`) implementa §2.1 del re-pre-registro: cara de mayor `e_m>0` por (evento, mercado, run), precio `min(mediana, ejecución)`, push dentro, `n_ev=0` deniega. Reproducción propia (2 vías a −110, ambas caras, 600 eventos): modelo informativo → `ev_flat=−0,0455` (lo que antes bloqueaba) pero `ev_lado_modelo=+0,217`, `allowed=True`; modelo = mercado → no pasa. Migración simulada sobre copia del registro vivo en dir temporal: 74 cortes, 0 cambios de `allowed/latched/reason/entry_test_at`, solo crecen `n` de chile/epl/laliga/seriea `spreads` (+3/+1/+4/+2, todos < 300), igual que declara CHANGES. n máximo de un corte no agotado: 224 (`nhl`). | La métrica no tiene umbral de `n_ev` ni test propio, por diseño pre-registrado (§2.1). Pasar el gate no promete rentabilidad. |
| AUD-002 | **P1** | **verificado-corregido** | `DIARIO_COMPLETO.bat` [0a] + `scripts/wait_for_clean_tree.ps1`: espera hasta 180 min (cada 900 s) y solo entonces `:error_arbol`. `tests/test_diario_espera_arbol.py` (BAT real en repo temporal: plazo agotado → rc 1, centinela, `data/` intacto; limpieza durante la espera → continúa; escape; árbol limpio) pasa. Tarea `SQP_Diario_Completo_Cdev`: `ExecutionTimeLimit=PT72H`, así que la espera no la mata. Árbol limpio hoy. | Arranque hasta 3 h tarde con árbol sucio. Mensaje de log engañoso tras la espera (REG-002). |
| AUD-003 | P2 | **verificado-corregido** | Reproducido: `write_prediction_gate(..., min_n=10)` → `ValueError`, directorio vacío. `update_prediction_gate.py --alpha 0.01` sin `--dry-run` → rc 2 antes de cargar datos (escritor sustituido por un centinela que no llegó a llamarse). Únicos llamadores de producción: `run_all.py:130` y el propio script, ambos con umbrales canónicos. `umbrales_de_prueba` no aparece en `src/` ni `scripts/` fuera de la definición. | — |
| AUD-004 | P2 | **verificado-corregido** | `_family_default` quita solo `TUNED_KEYS`; `_freeze_on_train` parte de la canónica sin ellas; ya no se fuerza `pitcher_bound=0`. `test_validate_oos_frozen_params` y `test_validate_oos_exit_code` pasan. | `main()` no ejecutado (prohibido en esta fase). |
| AUD-005 | P2 | **verificado-corregido** | `stake_price=min(mediana, ejecución)` en Kelly y elegibilidad (`daily.py`); guarda `_ev_ejecucion_no_positivo`; `settle_price=exec_price`; `settle._settle_px` cae a `price_decimal` si falta (filas antiguas idénticas). Revalidación no reescribe precios (solo lee `price_decimal`). `test_audit_g2_precio`, `test_settle_*` pasan. | Con `execution.books` vacío no hay cambio práctico. El ledger liquida a la cuota de ejecución y la condición 2 del gate mide a `min(·)`: distinto por diseño (ver candidato 1, §3). |
| AUD-006 | P2 | **verificado-corregido** | Reproducido: 100 filas buenas + 1 malformada → original movido a `.corrupt.<UTC>` con hash idéntico, `log.error`, log nuevo con solo la fila nueva. `EmptyDataError` sigue contando como vacío. | Mismo patrón en otros escritores, preexistente y fuera del alcance del hallazgo: NEW-001. |
| AUD-007 | P2 | **verificado-corregido** (código) | En esta máquina, `_scheduled_tasks_raw()` respondió en 6,4 s (con la suite de tests corriendo en paralelo) y `scheduled_tasks_status` leyó las 5 tareas `SQP_*`, con estado, último run y resultado. Timeout 120 s. Criterio de BACKLOG cumplido. | Historial del Programador **sigue deshabilitado** (`history_enabled: false`); el health lo avisa. Habilitarlo es del operador (consola elevada). |
| AUD-008 | P3 | **verificado-corregido** | `_set_best_method` hace el read-modify-write bajo `locked(path)` con `_read_registry_strict` (OSError tras reintentos, JSON roto, no UTF-8 o raíz no objeto → propaga, no reescribe). El lector de servicio sigue devolviendo `{}`. `test_calibration_registry_robustness` pasa. | Un registro corrupto ya no se «auto-cura» al reentrenar: error visible (declarado). |
| AUD-009 | P3 | **verificado-corregido** | `_persist_under_lock` recalcula con `bloquear_entradas=True` si `n_cortes>84` o la cota supera 5/82: `fuera_de_preregistro`, sin `entry_test_at`, sin pestillo. Tests de 85/84 cortes en `test_prediction_gate` pasan. Hoy: 74 cortes, `entradas_bloqueadas=False` en la simulación. | — |
| AUD-010 | P3 | **verificado-corregido** (modo edge) | `adjusted_edge` llega al stream servido; `classify` devuelve NO BET si `ev_riesgo<min_edge`; el sufijo «(pre-penalización)» solo con `ev_riesgo` NaN pasado explícitamente (el clasificador congelado del pre-registro tier A conserva su motivo; `tests/research/test_measure_tier_a_gap.py` pasa). | En `pick_mode=accuracy` el tier contradice al motor: REG-001. |
| AUD-011 | P3 | **verificado-corregido** (documentación) | Docstrings en `kelly.edge`, `tipster.expected_value`, `daily.py` y comentario de `min_edge` en `configs/default.yaml`. La fórmula no cambia, tal como pide el BACKLOG. | — |
| AUD-012 | P3 | **verificado-corregido** (documentación) | Limitación documentada en `walk_forward_backtest` (`engine.py`) y `realized_roi_backtest` (`roi_engine.py`). Comportamiento sin cambios, conforme al criterio. | El backtest sigue sobreestimando la información de abridor MLB; re-tunear `pitcher_bound` exige el log de probables. |
| AUD-013 | P3 | **verificado-corregido** | `_clv_frame` excluye cierres con `captured_for ≤ entrada` (ambos UTC: `_ts` con `utc=True`, `captured_out` de `load_closing_odds`) y colapsa a la media por evento antes del `binomtest`. El script de investigación pasa `captured_for`. `test_intraday_gate` pasa. | La media por evento fue elección del implementador. El script no se ejecutó (lee `data/`). |
| AUD-014 | P3 | **verificado-mitigado** | Diff de conjuntos de `.claude/settings.json` frente a `ead24b2^`: allow pierde solo `Bash(gh pr merge *)`, deny gana 12 patrones `.env*`, `ask` y el resto de claves sin cambios. Ninguna regla `gh` en allow ni en `settings.local.json`. | Los patrones son de prefijo: `grep … .env`, `python -c open('.env')`, `Get-Content -Path .env` o rutas absolutas no quedan cubiertos (residual declarado en CHANGES). |
| AUD-015 | P4 | **verificado-corregido** (parseo) | `parse_scoreboard(..., allow_draws=cfg["path"].startswith("soccer/"))`: 0-0 descartado con aviso fuera de fútbol. `test_espn_results` y `test_results_backfill` pasan. | Los 0-0 ya almacenados siguen ahí: la purga es del operador. |
| AUD-016 | P4 | **verificado-mitigado** | `drop_duplicates` dentro de la llamada y `_drop_already_stored` bajo el lock cuando el `captured_at` aparece en la cola de 256 KB. `test_odds_store` pasa. | Un backfill del mismo `captured_at` fuera de la cola no se detecta; comparación textual (`"3.0"` frente a `"3"`). Nunca pierde datos. |
| AUD-017 | P4 | **verificado-corregido** | Validación de raíz en `ml_train` (lista), `feature_store` (dict → caducado) y `feature_shadow` (dict con `predictions` lista y `protocol_sha256`). `test_json_root_validation_aud017` pasa. | — |
| AUD-018 | P4 | **verificado-mitigado** | Token `pid:uuid`; antes de romper un lock caducado se releen token y mtime; el `finally` solo borra el propio. `test_lock_ownership_aud018` pasa. | Ventana TOCTOU mínima entre la relectura y `unlink`. Si falla la escritura del token (`token=""`), el `finally` podría borrar un lock ajeno sin token. La caducidad sigue siendo solo por mtime (candidato 5, §3). |
| AUD-019 | P4 | **verificado-mitigado** | Eventos y cotizaciones malformados se omiten y cuentan (`last_parse_skipped`); `closing_capture` descuenta créditos en `finally`. `test_odds_parse_malformed_aud019` pasa. | Un `bookmaker` o `market` que no sea dict sigue lanzando `AttributeError` fuera del `try` (`odds_api.py`, `bm.get`/`mk.get`) y tumba la liga. Declarado como LOW opcional por Fable. |
| AUD-020 | P4 | **verificado-corregido** (diagnóstico) | `complementarity_gap` + aviso si > 0,01 en `calibrator_defect`; no cambia ninguna probabilidad servida. Medición de VALIDATION (wnba_spreads 0,0019) no re-ejecutada. | La tolerancia 0,01 es solo diagnóstica (no gobierna decisiones). |
| AUD-021 | P4 | **verificado-corregido** | `_graded_rows` + `_PESO_RESUELTO`: `half_*` con y del lado resuelto y peso ½; `d` de la unidad = Σw·d/Σw, exactamente §2.2 del re-pre-registro. Simulación: +3/+1/+4/+2 unidades en spreads de chile/epl/laliga/seriea. | Una unidad formada solo por medias cuenta como un ensayo completo, conforme al ejemplo pre-registrado (candidato 3, §3). |
| AUD-022 | P4 | **abierto, bloqueado** (exclusión; no es un cierre) | `git log --all -- data/backups` sigue mostrando `18826e2` y `f4537f5`; el repositorio es `PUBLIC` (`gh repo view`). Reescribir el historial exige un force-push, prohibido sin orden expresa. | Pendiente de la decisión del operador: aceptar el riesgo o reescribir el historial. |
| AUD-023 | P4 | **no aplicable** | `ci.yml:54,136` instala `pip install -e ".[dev]" -c requirements.lock`; el modo `--require-hashes` de pip no admite requisitos editables. El cambio era opcional en el BACKLOG. | Alternativa (lock de runtime con hashes) a decisión del operador. |
| AUD-024 | P4 | **verificado-corregido** | Los 8 `uses:` de `.github/workflows/ci.yml` van fijados por SHA. CI de `786daeb`: success (`secret-scan`, `dependency-audit`, `test` 3.11–3.14, `test-windows`, `cierre-ci-verde`). | Anotación de GitHub: Node 20 obsoleto en `checkout`/`setup-python` fijados (aviso, no fallo). |
| AUD-025 | P4 | **verificado-corregido** | `tools: Read, Glob, Grep` en los 9 agentes de solo lectura (cartographer, line-movement, odds-market, backtest, calibration, leakage, qa, security, sports-quant-auditor). `test_claude_system_contract` pasa. | `model: opus` fijo sigue en la frontmatter; el BACKLOG no pedía cambiarlo (lo mitiga `require-dispatch-model.sh`). `qa-engineer` ya no ejecuta tests. |
| AUD-026 | P4 | **verificado-corregido** | Reproducido: `american_to_decimal(-50)` y `(99)` → `ValueError`; `±100` → 2,0; `150` → 2,5. | — |

Recuento: 19 verificado-corregido, 4 verificado-mitigado (AUD-014, 016, 018, 019), 1 abierto-bloqueado (AUD-022), 1 no aplicable (AUD-023). Ninguno reabierto.

Nota sobre AUD-007: el STATUS de remediación decía «parcial» porque faltaba comprobarlo en la máquina real. Esa comprobación se hizo aquí. Habilitar el historial queda como acción del operador, no como defecto del código.

## 3. Regresiones y candidatos de la revisión de código previa

### Regresiones confirmadas

**REG-001 — El tipster marca NO BET «descartado por el motor de riesgo» picks que el motor sí apuesta en `pick_mode=accuracy`**

- **Relación:** introducida por AUD-010 (`1e50400`).
- **Severidad:** LOW. **Confianza:** HIGH. **Evidencia:** REPRODUCED (función) + STATICALLY_VERIFIED (motor). **Prioridad:** P4.
- **Archivo:** `src/sqp/evaluation/tipster.py:91` (`classify`); el motor en `src/sqp/pipeline/daily.py:1051-1070` (rama accuracy).
- **Activación:** solo con `PICK_MODE=accuracy`. Producción parece estar en modo edge (yaml `picks.mode: edge`; 0 flags `accuracy_mode` en los candidates del 2026-11-03). `.env` no se pudo leer: NOT_VERIFIABLE.
- **Observado:** `classify(ev=0.03, …, ev_riesgo=0.01, min_edge=0.02)` devuelve `('NO BET', 'descartado por el motor de riesgo (EV ajustado en ejecución < min_edge)')`. En modo accuracy el motor da stake plano sin filtro `min_edge`; solo la guarda de AUD-005 (EV ≤ 0 en ejecución) anula el stake.
- **Esperado:** un tier coherente con el motor (criterio de AUD-010) en los dos modos soportados.
- **Consecuencia:** un informe contradice al motor sobre picks con 0 < EV ajustado < `min_edge`. No mueve dinero, porque todo sigue en shadow o bajo el gate.
- **Corrección mínima:** aplicar el descarte por `min_edge` solo en modo edge, o en accuracy descartar solo `ev_riesgo ≤ 0`.
- **Prueba necesaria:** `tipster_table` con modo accuracy y una fila con EV ajustado de 0,01.

**REG-002 — `wait_for_clean_tree.ps1` registra «git no pudo comprobar el árbol» cuando el árbol se limpió durante la espera**

- **Relación:** introducida por AUD-002 (`ead24b2`).
- **Severidad:** LOW. **Confianza:** HIGH. **Evidencia:** REPRODUCED. **Prioridad:** P4.
- **Archivo:** `scripts/wait_for_clean_tree.ps1:26` (`return @(...)`) y `:37`.
- **Activación:** el árbol está sucio al empezar la espera y se limpia antes de agotar el plazo.
- **Observado:** en un repo temporal (fichero sucio revertido a los 3 s; `-IntervalSeconds 2`), la salida fue `arbol SUCIO (1 fichero(s))…` seguida de `git no pudo comprobar el arbol; se continua (falla abierto).`, con rc 0. PowerShell desenrolla el array vacío devuelto por la función a `$null`, y el llamador entra en la rama de fallo de git. La rama `Count -eq 0` y su mensaje «arbol limpio» son inalcanzables. Comprobado aparte: `function F { return @() }` da `$null`.
- **Consecuencia:** el código de salida es correcto (continúa), así que no se pierde ningún run. Pero un árbol limpio y un fallo real de git son indistinguibles en `logs\diario_completo.log`. El BAT añade su propio «[0a] Arbol limpio tras la espera», que contradice la línea anterior. El test `test_si_el_arbol_se_limpia_durante_la_espera_el_flujo_continua` no lo detecta porque comprueba la línea del BAT.
- **Corrección mínima:** `return ,@(...)`, o devolver un objeto con el estado de git separado.
- **Prueba necesaria:** aserción sobre la ausencia de «git no pudo comprobar» en ese escenario.

### Hallazgo nuevo preexistente (no es regresión)

**NEW-001 — Otros escritores de logs siguen tratando `ParserError` como fichero vacío y reescriben perdiendo el historial (misma causa raíz que AUD-006, no extendida)**

- **Severidad:** MEDIUM (misma clase de impacto que AUD-006: pérdida silenciosa de un rastro auditable, condicionada a un CSV corrupto). **Confianza:** HIGH. **Evidencia:** REPRODUCED (latch log) + STATICALLY_VERIFIED (resto). **Prioridad:** P3.
- **Archivos:** `src/sqp/risk/prediction_gate.py:686-689` (`_append_latch_log`); `src/sqp/calibration/calibrator.py` (los tres escritores de `promotion_log.csv`).
- **Preexistente:** el patrón ya estaba en la base del diagnóstico `a5d1860` (`prediction_gate.py:480` de entonces) y viene, al menos, de `7341150`. No lo introdujo la remediación; el hallazgo AUD-006 solo citaba `revalidation.py`.
- **Observado:** un `prediction_gate_latch_log.csv` con 50 filas y una línea malformada queda, tras `_append_latch_log`, con **1** fila. Sin cuarentena ni error.
- **Consecuencia:** se pierde el rastro de armados y liberaciones de pestillos (quién liberó, cuándo y con qué nota) y el historial de promociones de calibradores. El estado vigente del gate no se pierde, porque vive en `prediction_gate.json`.
- **Corrección mínima:** el mismo tratamiento de AUD-006 (cuarentena `.corrupt.<UTC>` o propagar).
- **No evaluado:** `daily.py:387` usa el mismo `except`, pero solo para saltarse un fichero en el cálculo del tope de exposición. Su impacto es distinto y no se verificó.

### Candidatos de la revisión previa: resultado

| # | Candidato | Resultado | Motivo |
|---|---|---|---|
| 1 | Ledger liquida a `settle_price` y el stake/gate usan `min(mediana, ejecución)` | **Descartado** como defecto (DISMISSED); observación | Es la regla diseñada por Fable para AUD-005: dimensionar de forma conservadora y cobrar lo que paga la casa de ejecución, acotada por `max_uplift`. La condición 2 a `min(·)` es la dirección conservadora fijada en §2.1 del re-pre-registro. Con `execution.books` vacío, la ejecución repite la mediana. Residual ya declarado: no se mide la deriva entre la cuota de ejecución registrada y la cobrada de verdad. |
| 2 | Tipster NO BET contra el motor en modo accuracy | **Confirmado → REG-001** | Reproducido (ver arriba). |
| 3 | Unidad solo con `half_*` cuenta como ensayo completo | **Descartado** | Es exactamente §2.2 del re-pre-registro: `d = Σw·d/Σw`. El ejemplo §3 («un `half_win` y un `half_loss`: condición 1 n = 2, 1 victoria») lo fija. Cambiarlo sería re-pre-registrar, no corregir un bug. |
| 4 | `_append_latch_log` (y otros) siguen con `ParserError` → vacío | **Confirmado → NEW-001** (preexistente, no REG) | Reproducido (50 filas → 1). Estaba ya en la base `a5d1860`. |
| 5 | La caducidad del lock es solo por mtime; un titular vivo > 300 s lo pierde | **Descartado** como regresión; riesgo residual de AUD-018 | Diseño preexistente (`LOCK_STALE_S=300` frente a `LOCK_TIMEOUT_S=120`); las secciones críticas son read-modify-write de décimas de segundo. Los locks nuevos de la remediación (registro de calibración, dedupe de `odds_store`) mantienen secciones cortas; el dedupe solo lee el fichero entero si el mismo `captured_at` ya está en la cola. El token de AUD-018 evita además que el titular antiguo borre el lock nuevo. No se demostró ninguna sección > 300 s. |
| 6 | `Get-ArbolSucio` devuelve `$null` con árbol limpio | **Confirmado → REG-002** | Reproducido en repo temporal. |
| 7 | La elección de la cara se hace tras filtrar los `void` | **Descartado** | §2.1, paso 5, del re-pre-registro: «Las filas `void` o sin resultado no entran». El código implementa lo pre-registrado. En la práctica un `void` anula el evento entero (todas las caras), no una sola cara. |
| 8 | Regla `min(mediana, ejecución)` triplicada; `_usable` solo en tests | **Descartado** (calidad, sin consecuencia) | Las tres copias son equivalentes (el `np.where` anidado da `min(price, ej)` cuando `ej` es válido). Duplicación sin defecto demostrado. |
| 9 | Chequeo canónico duplicado en el script; no comprueba `validation_start` | **Descartado** | El script no tiene opción `--validation-start`, así que no hay nada que comprobar. El chequeo temprano evita cargar datos y es defensa en profundidad; `write_prediction_gate` comprueba los tres. |
| 10 | `_ev_ejecucion_no_positivo` nunca se dispara en modo edge | **Descartado** (cierto, pero no es defecto) | Con stake de Kelly a `min(price, exec)` y `min_edge = 0,02 > 0`, el EV en ejecución ya es > 0. La guarda es defensa en profundidad y sí actúa en accuracy (motivo de `1832272`). El comentario «Guarda universal» describe dónde se aplica, no que se dispare en ambos modos. |

## 4. Validación global

| Comando | rc | Resultado |
|---|---|---|
| `python -m pytest -q -p no:cacheprovider --basetemp=.codex-tmp/verif-a` sobre los 16 ficheros de test tocados por la remediación + `test_tipster`, `tests/research/test_measure_tier_a_gap`, `test_gate_status_cli`, `test_validate_oos_exit_code` | 0 | **398 passed** en 270,7 s |
| `python -m pytest -q -p no:cacheprovider --basetemp=.codex-tmp/verif-b` sobre llamadores: `settlement/`, `test_bat_files_integrity`, `test_calibrator`, `test_claude_system_contract`, `test_closing_capture_markets`, `test_config_yaml_keys`, `test_espn_results`, `test_feature_shadow`, `test_feature_store`, `test_gate_block_visibility`, `test_health`, `test_html_report`, `test_intraday_scan`, `test_kelly`, `test_reports`, `test_requirements_lock`, `test_served_market_shrink`, `test_settle_candidates`, `test_settle_persist`, `test_settlement_math`, `test_storage` | 0 | **429 passed** en 683,4 s |
| `ruff check src scripts tests` | 0 | All checks passed |
| `mypy src` | 0 | Success: no issues found in 116 source files |
| `gh run view 41786550657` (CI de `786daeb`) | 0 | success en las 9 tareas (alerta-ci-rojo omitida, como corresponde) |
| `_scheduled_tasks_raw()` + `scheduled_tasks_status()` (solo lectura) | — | 5 tareas leídas en 6,4 s; `history_enabled: false` |
| `Get-ScheduledTask SQP_Diario_Completo_Cdev` (solo lectura) | 0 | `ExecutionTimeLimit=PT72H`, disparo 12:00, `MultipleInstances=IgnoreNew` |
| Reproducciones propias (`repro.py`, `repro2.py`, `gate_migr.py` en el scratchpad; repo temporal para el `.ps1`) | 0 | Resultados en §2 y §3 |

Suite completa: no re-ejecutada aquí. Como evidencia secundaria, la del implementador sobre `4d10703` dio 3502 passed y 1 skipped. Como evidencia independiente, el CI de `786daeb` ejecutó la suite en Linux (3.11–3.14) y Windows, y salió verde. `786daeb` no cambia código respecto de `4d10703`.

Clasificación: sin `NEW_REGRESSION` en tests, sin `PRE_EXISTING_FAILURE`, sin `ENVIRONMENTAL_FAILURE` en esta fase. REG-001 y REG-002 son regresiones funcionales que los tests actuales no cubren.

## 5. P0/P1 abiertos

Ninguno. AUD-002 (P1) está verificado-corregido. Ninguna regresión ni hallazgo nuevo es P0/P1.

## 6. Pendientes y próxima acción

1. **NEW-001 (P3):** extender la cuarentena de AUD-006 a `_append_latch_log` y a los escritores de `promotion_log.csv`. Toca rutas del candado `fable_gate` (`src/sqp/risk/**`, `src/sqp/calibration/**`), así que necesita revisión Fable antes del commit.
2. **REG-002 (P4):** `return ,@(...)` en `wait_for_clean_tree.ps1` y una aserción sobre el mensaje en el test.
3. **REG-001 (P4):** hacer que el descarte por `min_edge` del tipster dependa de `pick_mode`. Cambia el contrato del stream servido o del informe, así que es de clase de escalado.
4. **AUD-022 (P4):** decisión del operador. Aceptar el riesgo (el repositorio es público desde `18826e2`) o reescribir el historial desde su terminal.
5. **AUD-007 (operador):** habilitar el historial del Programador de tareas desde una consola elevada.
6. **AUD-015 (operador):** purgar los 0-0 de relleno ya almacenados, si se quiere.
7. Residuales opcionales de AUD-014, AUD-016, AUD-018 y AUD-019 (§2).
8. **Primera ejecución real del gate nuevo:** el run de las 12:00 del 2026-11-04 será la primera escritura del registro con `criterio_condicion2` (el vivo es del 2026-11-03 23:52 UTC, anterior a `914707c`). Conviene confirmar después que aparecen `criterio_condicion2` y `entradas_bloqueadas: false` y que no hay transiciones.

## 7. Addendum: verificación independiente de `f5b80e2` (2026-11-07)

**Alcance:** REG-001, REG-002 y NEW-001, corregidos en `f5b80e2` con revisión Fable previa al commit. **Verificador:** subagente nuevo Fable 5.1 (`claude-fable-5-1`), solo lectura, que no implementó nada. **Base:** `0c6fb9f` (HEAD; posterior a `f5b80e2`, solo docs y graphify). **Árbol:** solo los dos `??` preexistentes (`.claude/settings.json.graphify-bak`, `.github/copilot-instructions.md`).

| ID | Estado de verificación | Evidencia |
|---|---|---|
| REG-001 | verificado-corregido | `tipster.py:112-120` (`_marca_accuracy`, celda a celda) y `:193-197` (`min_edge=None` solo en filas marcadas); `daily.py:1044-1048` escribe `served_stream;accuracy_mode` con la misma condición que `:1055`. Reproducido: las filas marcadas van a tier C; las no marcadas y `accuracy_mode_x` siguen en NO BET. Modo edge: 0 diferencias frente a `f5b80e2^` en 3.000 filas × 4 `min_edge` × 2 `prob_col` (`assert_frame_equal`). Tier A congelado intacto (`measure_tier_a_gap.py` carga el blob del tag). Ningún consumidor de `flags` compara por igualdad exacta. Discrepancia menor: `prediction_gate.py` no cambió para REG-001, solo para NEW-001. |
| REG-002 | verificado-corregido | `wait_for_clean_tree.ps1:28` `return ,@(...)`. Reproducido en PowerShell 5.1: vacío → `Count=0` (antes `$null`); una línea → `Object[]`; si git falla sigue devolviendo `$null` (falla abierto como antes). El test exige «arbol limpio; se continua.». |
| NEW-001 | verificado-corregido | `atomic.py:166-212` `append_csv_log`: cuarentena `.corrupt.<UTC µs>`, error sin escribir si no puede apartar, detección de columnas desplazadas, unión de columnas. Callers: `calibrator.py:1001,1012,1111`; `prediction_gate.py:687` (bajo `locked()`); `revalidation.py:76`. Reproducido: 50 filas + 1 malformada → `.corrupt` con sha256 idéntico y log nuevo de 1 fila; 0 bytes sin cuarentena. Otros escritores del patrón (`team_totals_capture.py:178`, `odds_store.py:68`, `goalies.py:223`, `pitchers_capture.py:87`, `starters.py:66`) propagan `ParserError` (fallan en alto, sin pérdida). Sin traslado. |

**Regresiones nuevas:** ninguna (no se asigna REG-003).

**Observaciones no bloqueantes:**
1. Punto ciego del detector de desplazamiento: si todas las filas traen un campo de más y la primera columna son enteros 0..n-1, se pierde una columna sin aviso (reproducido en temporal). No alcanzable en los logs cubiertos (primera columna `timestamp`); el comentario del código lo reconoce.
2. Los escritores de `promotion_log.csv` siguen sin lock entre procesos (preexistente; el docstring lo delega en el llamador). Residual de concurrencia, no regresión.
3. Filas del stream servido generadas en modo accuracy antes de `f5b80e2` no llevan la marca. Producción usa `picks.mode: edge` (`configs/default.yaml:200`): impacto esperado nulo; NOT_VERIFIABLE sin escanear `data/`.

**Validación (comando → rc):**

| Comando | Resultado | rc |
|---|---|---|
| pytest `test_audit_verif_regresiones`, `test_accuracy_mode`, `test_audit_log_concurrency`, `test_diario_espera_arbol` | 25 passed | 0 |
| pytest `test_tipster`, `test_prediction_gate`, `test_revalidation`, `test_auto_promote`, `test_calibrator`, `test_calibration_registry_robustness`, `test_audit_atomic_readers`, `research/test_measure_tier_a_gap` | 305 passed | 0 |
| `pytest -q -p no:cacheprovider -x -m "not slow and not heavy"` | 2738 passed, 778 deselected (36 min) | 0 |
| `ruff check src scripts tests` | All checks passed | 0 |
| `mypy src` | sin errores (116 ficheros) | 0 |

No ejecutado: la parte slow/heavy de la suite (queda para el CI). Sin `NEW_REGRESSION`, `PRE_EXISTING_FAILURE` ni `ENVIRONMENTAL_FAILURE`.

**Dictamen de la ronda:** **APTO CON PENDIENTES** (regla 3). No hay P0/P1 abierto ni regresión, y la evidencia de los tres IDs es suficiente. Siguen abiertos AUD-022 (P4, decisión del operador), el historial del Programador (AUD-007, operador), los residuales de AUD-014/016/018/019 y las observaciones 1-3. Este dictamen solo califica la remediación evaluada; no garantiza ausencia de defectos ni rentabilidad.
