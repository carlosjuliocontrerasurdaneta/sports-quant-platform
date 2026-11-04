# CHANGES — remediación de la ronda `audit-2026-11-03`

- **Autorización.** El operador, el 2026-11-03: «Lo autorizo. Te doy una autorización total y plenipotenciaria», sobre todo el BACKLOG.
- **Base.** `aa8db2f` (incluye la corrección KI-078 previa, `aa8db2f`).
- **Cómo se trabajó.**
  - Seis lotes, cada uno implementado por Sonnet en un worktree aislado.
  - Los lotes con rutas de escalado los diseñó y revisó Fable antes del commit: D, G1 y G2 (AUD-001, 003, 005, 009, 010, 011 y 021).
  - Integración en `main` en estos commits:

| Commit | Lote | IDs |
|---|---|---|
| `ead24b2` | O | AUD-002, 007, 014, 024, 025 |
| `77110b4` | Q | AUD-004, 012, 013 |
| `df015bf` | D | AUD-006, 008, 015, 016, 017, 018, 019, 020, 026 |
| `1e50400` | G2 | AUD-005, 010, 011 |
| `914707c` | G1 | AUD-001, 003, 009, 021 |

`FINDINGS.md` se conserva como línea base. El estado de cada ID está en `STATUS.md` y la evidencia, en `VALIDATION.md`.

---

## AUD-001 (MEDIUM, P2): la condición 2 del gate no podía cumplirse

- **Inicial:** confirmado (REPRODUCED).
- **Causa:** el EV plano promediaba las dos caras de cada mercado; con cuotas simétricas salía −vig fuera cual fuera el modelo.
- **Archivos:** `docs/research/2026-11-03-repreregistro-condicion2-gate.md` (re-pre-registro nuevo de Fable), `src/sqp/risk/prediction_gate.py`, `scripts/update_prediction_gate.py`, `scripts/gate_status.py`, `configs/default.yaml` (comentarios) y `.claude/skills/clv-shadow-exit/SKILL.md`.
- **Cambio:**
  - La condición 2 pasa a ser `ev_lado_modelo`: el EV realizado a stake plano de la cara de mayor edge positivo del modelo puro.
  - Se calcula por run, en la unidad (evento, mercado), al precio min(mediana, ejecución) y con los push dentro.
  - Deniega si `n_ev = 0`.
  - `ev_flat` se sigue publicando como métrica retirada.
  - La condición 1 y la cota de Bonferroni no cambian.
- **Prueba:** casos sintéticos T1–T5 del documento: el modelo bueno pasa, el que iguala al mercado no pasa y el vig se come el margen. También precio de ejecución, varios runs y push. Fable comprobó que 13 tests nuevos fallan sobre la base.
- **Aceptación:** sí. El criterio discrimina la calidad del modelo y queda commiteado antes de que ningún corte llegue a n ≥ 300 (máximo n = 224).
- **Residual:** la métrica no se ha calculado nunca sobre datos reales; está prohibido antes del commit (§1.2). Pasar el gate no promete rentabilidad.
- **Final:** corregido, pendiente de verificación.

## AUD-002 (MEDIUM, P1): el guard de árbol sucio perdía el día

- **Inicial:** confirmado (REPRODUCED, abortos del 02-11 y del 03-11).
- **Causa:** el guard abortaba al primer vistazo y no había reintento.
- **Archivos:** `DIARIO_COMPLETO.bat` (nueva sección [0a]), `scripts/wait_for_clean_tree.ps1` (nuevo) y `tests/test_diario_espera_arbol.py`.
- **Cambio:**
  - El BAT re-evalúa el guard cada 900 s durante 180 min (`SQP_TREE_WAIT_MAX_MIN`, `SQP_TREE_WAIT_INTERVAL_S`) y continúa si el árbol queda limpio.
  - Si agota el plazo, aborta como antes: centinela y `data/` intacto.
  - Escape: `SQP_SKIP_TREE_WAIT=1`.
  - No se eligió una tarea de reintento porque crearla exige un proceso elevado.
- **Prueba:** el BAT real, copiado a un repo temporal, se ejecutó con cuatro escenarios: plazo agotado, árbol limpiado durante la espera, escape y árbol limpio.
- **Aceptación:** sí.
- **Residual:**
  - Con el árbol sucio, el run puede empezar hasta 3 h tarde.
  - No se ejecutó el BAT de producción.
  - El aislamiento en worktree es una práctica, ya registrada en la memoria.
- **Final:** corregido, pendiente de verificación.

## AUD-003 (MEDIUM, P2): los overrides gastaban el test único

- **Inicial:** confirmado.
- **Archivos:** `scripts/update_prediction_gate.py` y `src/sqp/risk/prediction_gate.py`.
- **Cambio:**
  - El script devuelve rc 2 sin escribir si `--min-n` o `--alpha` no son canónicos y no hay `--dry-run`.
  - `write_prediction_gate` lanza `ValueError` antes del lock si `min_n`, `alpha` o `validation_start` no son canónicos.
  - La única salida es `umbrales_de_prueba=True`, que un test de contrato prohíbe en `src/` y `scripts/`.
- **Prueba:** rc 2 sin fichero, `ValueError` sin escritura, y el test de contrato.
- **Aceptación:** sí.
- **Final:** corregido, pendiente de verificación.

## AUD-004 (MEDIUM, P2): `validate_oos` descartaba parámetros de liga

- **Inicial:** confirmado.
- **Archivos:** `scripts/validate_oos.py` y `tests/test_validate_oos_frozen_params.py`.
- **Cambio:**
  - `TUNED_KEYS` y `_family_default` (la configuración canónica sin las claves tuneadas).
  - `frozen_train` sobrescribe solo las claves tuneadas.
  - Se quitó el forzado de `pitcher_bound` a 0,0 y se corrigió el docstring.
- **Prueba:** el `frozen` de mlb conserva `park_bound`/`pitcher_bound` y el de epl conserva `avg_total`.
- **Aceptación:** sí.
- **Residual:** `main()` no se ejecutó completo.
- **Final:** corregido, pendiente de verificación.

## AUD-005 (MEDIUM condicionado, P2): stake y liquidación a la mediana

- **Inicial:** confirmado (STATICALLY_VERIFIED).
- **Archivos:** `src/sqp/risk/kelly.py`, `src/sqp/pipeline/daily.py`, `src/sqp/domain/models.py`, `src/sqp/settlement/settle.py` y `src/sqp/config.py` (docstring).
- **Cambio:**
  - `stake_price = min(mediana, ejecución)`.
  - Una guarda pone el stake a 0 si el EV en la casa de ejecución es ≤ 0 (flag `ev_ejecucion_no_positivo`).
  - `BetCandidate.settle_price` toma el valor del precio de ejecución, y `settle` liquida con él solo cuando existe.
  - Las filas históricas liquidan exactamente igual.
- **Prueba:** stake 0 con 1,85 frente a 4,46 a la mediana; pnl 8,5 en win y 4,25 en half_win con `settle_price`; 9,5 sin él.
- **Aceptación:** sí. Ningún stake real puede tener EV ≤ 0 en la casa de ejecución.
- **Residual:** la deriva entre la cuota de Pinnacle en el pick y la realmente cobrada no se mide; el backtest sigue a la mediana.
- **Final:** corregido, pendiente de verificación.

## AUD-006 (MEDIUM, P2): un CSV corrupto borraba el log intradía

- **Inicial:** confirmado.
- **Archivo:** `src/sqp/pipeline/revalidation.py`.
- **Cambio:**
  - Solo `EmptyDataError` cuenta como log vacío.
  - Un `ParserError` mueve el fichero a `.corrupt.<UTC>` y registra `log.error`.
  - Si no puede moverlo, relanza la excepción.
- **Prueba:** 100 filas buenas más 1 malformada: el original se conserva intacto en cuarentena.
- **Aceptación:** sí.
- **Final:** corregido, pendiente de verificación.

## AUD-007 (MEDIUM, P2): el health no leía las tareas programadas

- **Inicial:** confirmado.
- **Causa:** una sola llamada a PowerShell con `Get-ScheduledTaskInfo` por tarea y un timeout de 30 s.
- **Archivo:** `src/sqp/monitoring/health.py`.
- **Cambio:** `SCHEDULED_TASKS_TIMEOUT_S = 120`. No se usó `schtasks /fo CSV` porque su salida depende del idioma de Windows.
- **Prueba:** subprocess simulado: plazo de 120 s, y un timeout devuelve `None` con aviso.
- **Aceptación:** parcial. Falta comprobarlo en la máquina real, y habilitar el historial del Programador es tarea del operador.
- **Final:** parcial, pendiente de verificación.

## AUD-008 (LOW, P3): registro de calibración sin lock

- **Archivo:** `src/sqp/calibration/calibrator.py`.
- **Cambio:**
  - La lectura-modificación-escritura va bajo `locked(path)` con `read_json_retrying`.
  - Si el registro existe y no se puede leer, se aborta sin reescribirlo.
  - El lector de servicio sigue devolviendo `{}`.
- **Prueba:** raíz que es una lista, bytes no UTF-8, JSON roto y `OSError`: el registro no se reduce.
- **Residual:** un registro corrupto ya no se «auto-cura» al reentrenar; ahora da un error visible.
- **Final:** corregido, pendiente de verificación.

## AUD-009 (LOW, P3): el techo solo avisaba

- **Archivo:** `src/sqp/risk/prediction_gate.py`.
- **Cambio:** con más de 84 cortes o una cota > 5/82, ningún test de entrada se consume (`fuera_de_preregistro`, `entradas_bloqueadas`).
- **Prueba:** con 85 cortes queda bloqueado sin consumir; con 84 se recupera. Un α previo de 0,06 también bloquea.
- **Final:** corregido, pendiente de verificación.

## AUD-010 (LOW, P3): tier del tipster frente al motor de riesgo

- **Archivos:** `src/sqp/evaluation/tipster.py`, `src/sqp/pipeline/daily.py`, `src/sqp/storage/served_store.py`, `scripts/tipster_report.py`, `src/sqp/audit/report.py` y `src/sqp/audit/html_report.py`.
- **Cambio:**
  - `adjusted_edge` se añade al stream servido.
  - `ev_riesgo` = EV ajustado al precio de stake.
  - El tier pasa a NO BET si `ev_riesgo < min_edge`, y las filas legadas se marcan «(pre-penalización)».
  - `served_store` reconcilia la cabecera vieja una sola vez.
- **Prueba:** el caso de la auditoría da NO BET; la cabecera vieja provoca una sola reescritura.
- **Final:** corregido, pendiente de verificación.

## AUD-011 (LOW, P3): el edge es EV condicionado a no-push

- **Cambio:** solo documentación en `kelly.edge`, `tipster.expected_value`, `daily.py` y el comentario de `min_edge` de `configs/default.yaml`. La fórmula no cambia.
- **Prueba:** `SettlementProbabilities(0,45, 0,10, 0,45)` cumple `expected_value = edge × 0,9`.
- **Final:** corregido, pendiente de verificación.

## AUD-012 (LOW, P3): backtest MLB con el abridor almacenado

- **Cambio:** limitación documentada en los docstrings de `walk_forward_backtest` y `realized_roi_backtest`. El comportamiento no cambia.
- **Final:** corregido (documentación), pendiente de verificación.

## AUD-013 (LOW, P3): gate intradía

- **Archivos:** `src/sqp/audit/intraday_gate.py` y `scripts/research/intraday_gate_analysis.py`.
- **Cambio:**
  - Se excluyen los cierres capturados en el instante de entrada o antes (`captured_for`).
  - Se colapsa a una unidad por evento (media del CLV) antes del binomtest.
- **Prueba:** un cierre anterior a la entrada queda excluido, y dos líneas del mismo evento cuentan como una unidad.
- **Residual:** usar la media por evento fue elección del implementador. El script de investigación no se ejecutó.
- **Final:** corregido, pendiente de verificación.

## AUD-014 (LOW, P3): permisos

- **Archivo:** `.claude/settings.json`.
- **Cambio:**
  - Se retiró `Bash(gh pr merge *)` de la lista de permitidos.
  - Se añadieron 12 deny para leer `.env*` por shell.
  - No se añadió ningún permiso nuevo; se comparó por diff de conjuntos.
- **Residual:** los patrones son de prefijo y no cubren todas las formas de leer un fichero.
- **Final:** corregido, pendiente de verificación.

## AUD-015 (LOW, P4): marcadores 0-0 de relleno

- **Archivo:** `src/sqp/providers/espn_results.py`.
- **Cambio:** el parseo descarta 0-0 solo fuera de las ligas `soccer/`. No se purgan datos ya almacenados; eso queda para el operador.
- **Final:** corregido (parseo), pendiente de verificación.

## AUD-016 (LOW, P4): snapshots duplicados

- **Archivo:** `src/sqp/storage/odds_store.py`.
- **Cambio:**
  - Deduplica dentro de cada llamada.
  - Antes de anexar, revisa la cola del fichero (256 KB) y, si encuentra el mismo `captured_at`, lee por bloques y descarta lo ya guardado.
  - Se ajustaron dos tests que aseguraban el contrato viejo; Fable lo juzgó legítimo.
- **Residual:** un backfill del mismo `captured_at` fuera de la cola no se detecta; si el texto de `point` difiere puede duplicar, pero nunca se pierden datos.
- **Final:** corregido, pendiente de verificación.

## AUD-017 (LOW, P4): raíz JSON

- **Archivos:** `ml_train.py`, `feature_store.py` y `feature_shadow.py`.
- **Cambio:** se valida la raíz y una raíz inválida falla de forma controlada.
- **Final:** corregido, pendiente de verificación.

## AUD-018 (LOW, P4): carrera del lock

- **Archivo:** `src/sqp/storage/lock.py`.
- **Cambio:**
  - El lock lleva un token `pid:uuid`.
  - Antes de romper un lock caducado se vuelven a comprobar el mtime y el token.
  - El `finally` solo borra el lock propio.
- **Residual:** queda una ventana TOCTOU mínima. Si falla la escritura del token, el `finally` podría borrar un lock ajeno recién creado (LOW de Fable, opcional).
- **Final:** corregido, pendiente de verificación.

## AUD-019 (LOW, P4): `_parse_events` y créditos

- **Archivos:** `src/sqp/providers/odds_api.py` y `src/sqp/pipeline/closing_capture.py`.
- **Cambio:** los elementos malformados se omiten y se cuentan (`last_parse_skipped`), y los créditos se descuentan en `finally`.
- **Residual:** un bookmaker o un market que no sea dict sigue tumbando la liga (LOW de Fable, opcional).
- **Final:** corregido, pendiente de verificación.

## AUD-020 (LOW, P4): complementariedad del calibrador

- **Archivo:** `src/sqp/calibration/calibrator.py`.
- **Cambio:**
  - `complementarity_gap` y un `log.warning` cuando el gap supera 0,01. Es solo diagnóstico: no cambia ninguna probabilidad servida ni ningún veredicto.
  - La tolerancia 0,01 la eligió el implementador y Fable la confirmó. Gap máximo de los calibradores vivos: 0,0019 (`wnba_spreads`).
- **Final:** corregido (diagnóstico), pendiente de verificación.

## AUD-021 (LOW, P4): el gate excluía `half_*`

- **Archivo:** `src/sqp/risk/prediction_gate.py`.
- **Cambio:** `half_win`/`half_loss` entran con la y del lado resuelto y peso ½.
- **Recuentos:** 0 líneas de cuarto en los seis cortes agotados y en `nhl|*`. Con las medias, solo ganan unidades los spreads de chile, epl, laliga y seriea (+1 a +4, todos con n < 300).
- **Prueba:** un test discriminante con una unidad que solo tiene `half_win`.
- **Final:** corregido, pendiente de verificación.

## AUD-022 (LOW, P4): copias de `data/backups` en el historial público

- **Estado:** **BLOQUEADO, requiere al operador.**
- **Motivo:** retirarlas exige reescribir el historial (`git filter-repo`) y hacer un force-push. Las reglas del proyecto lo prohíben («Nunca utilices `git push --force`», `CLAUDE.md`), y la autorización general no las anula.
- **Acción del operador si decide hacerlo:** desde una terminal propia, hacer una copia del repositorio, ejecutar `git filter-repo --path data/backups --invert-paths`, hacer un force-push coordinado a `main` y verificar que `git log --all -- data/backups` sale vacío.
- **Si no lo hace:** el riesgo queda aceptado, porque el contenido ya es público desde `18826e2`.

## AUD-023 (LOW, P4): `requirements.lock` sin hashes

- **Estado:** **NO APLICABLE tal como está especificado.**
- **Motivo:**
  - `requirements.lock` es un fichero de restricciones de pip (`-c`), y el CI instala el proyecto en modo editable (`pip install -e ".[dev]" -c requirements.lock`).
  - El modo de hashes de pip (`--require-hashes`) exige hash para todo lo que se instala, incluido el proyecto editable, que no puede tenerlo.
  - Además, generarlo requiere instalar pip-tools, una dependencia nueva.
- **Alternativa, si se quiere:** un lock completo de solo-runtime con hashes para producción (`pip-compile --generate-hashes`) separado del de CI. Es decisión del operador.

## AUD-024 (LOW, P4): acciones de GitHub fijadas por tag

- **Archivo:** `.github/workflows/ci.yml`.
- **Cambio:** 8 `uses:` fijados por SHA de commit, con el tag en comentario. Los SHA se obtuvieron con `git ls-remote`.
- **Residual:** el CI real se comprueba después del push.
- **Final:** corregido, pendiente de verificación.

## AUD-025 (LOW, P4): agentes sin `tools:`

- **Cambio:** `tools: Read, Glob, Grep` en 9 agentes de solo lectura. Quedan fuera `independent-code-reviewer` y `review-adjudicator`, que necesitan escribir o ejecutar.
- **Residual:** `qa-engineer` ya no puede ejecutar tests.
- **Final:** corregido, pendiente de verificación.

## AUD-026 (LOW, P4): `american_to_decimal`

- **Archivo:** `src/sqp/markets/odds.py`.
- **Cambio:** `ValueError` si `abs(x) < 100`. Sin llamadores en producción.
- **Final:** corregido, pendiente de verificación.

---

## Observaciones opcionales registradas, sin corregir

Son LOW de las revisiones de Fable:

- `odds_api.py` ~297: un bookmaker o market que no sea dict tumba la liga.
- `odds_store._drop_already_stored` compara texto (por ejemplo, "3.0" frente a "3").
- `lock.py` ~74: token vacío si falla su escritura.
