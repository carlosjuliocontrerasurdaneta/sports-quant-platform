# Archivos modificados — Auditoría 2026-08-30

Sin commit (pendiente de autorización). Estado exacto: `git status --short`.

## Corregido

### A-1 · `.claude/loops/audit.md`

Cambio: se restauró bajo `## Common guardrails` el bloque canónico literal de 5
viñetas que comparten los otros 10 loops, se movieron las restricciones
específicas del diagnóstico a una sección propia (`## Restricciones propias del
diagnóstico`), y se añadió `8. Finish through /verification-gate.` como paso de
cierre.

La sección propia es necesaria porque el contrato exige identidad byte a byte
del bloque canónico, y ese bloque incluye "Prefer the smallest reversible
change", que en un loop de solo lectura podría leerse como permiso para cambiar
algo. La sección nueva lo desambigua explícitamente: durante el diagnóstico el
cambio correcto es ninguno.

Verificación: `pytest tests/test_claude_system_contract.py -q` → 15 passed
(código 0), y extracción programática → 1 bloque distinto sobre 11 loops, 0
archivos sin `/verification-gate`.

### M-1 (parte documental) · `.claude/skills/full-audit/references/taxonomy.md`

Cambio: se añadió la tabla de equivalencia entre el esquema histórico
`AUD-<NIVEL>-NNN` (usado por la auditoría del 2026-08-29, que no persistió
informe) y el esquema vigente `C/A/M/B`, más la regla de que un ID citado en un
commit debe poder resolverse contra un informe.

La otra mitad de M-1 —la ausencia de informe— se corrige por construcción: este
directorio `audit/latest/` es el artefacto que faltaba.

## Efecto del hook de formato

Ninguno. El hook `PostToolUse` ejecuta `ruff check --fix`, que sólo actúa sobre
Python; los dos archivos modificados son Markdown. El diff es exactamente el
parche, sin autofixes añadidos.

## Lo que se decidió NO tocar

| Qué | Por qué |
|---|---|
| `B-1` (revalidación del registro live con historial vacío) | `INFERIDO`, confianza BAJA, no observado. La instrucción era aplicar sólo mejoras sustentadas por evidencia de la auditoría; ésta se sostiene en lectura del flujo de control, no en un caso reproducido. |
| `I-1` / `.claude/settings.json`, `.claude/automation/MODEL_ROUTING.md`, el literal de `test_claude_model_routing.py` | El árbol contiene un cambio deliberado a medias: `settings.json` y `docs/MODEL-ROUTING.md` ya declaran Opus 5, el literal del test y `MODEL_ROUTING.md` siguen en Fable 5. Completarlo exige decidir cuál es la política real, que es una decisión del operador. El test es un candado de coste que existe para forzar esa decisión; cerrarlo yo lo anularía. |
| `README.md`, `docs/MODEL-ROUTING.md` | Modificaciones preexistentes en el árbol al abrir esta auditoría, ajenas a ella. Regla 2: preservar el estado existente. |
| `NOTAS.md`, `auditoria-integral-codex.md` | Untracked y ajenos al alcance. No se tocan ni se borran. |
| Parámetros de riesgo, `shadow_mode`, `pick_mode`, promoción de modelos | Exigen aprobación humana separada. Ningún hallazgo la requería. |

## Incidente y restauración (posterior a la corrección)

Al revisar el diff final se detectó que `.claude/skills/full-audit/` había
cambiado durante la sesión sin intervención de esta auditoría:

- **09:00:54** — `SKILL.md` reemplazado por una versión de 713 líneas (monolito
  con fases 0–5, sin mención de `audit-remediation` ni de `audit/latest/`, y con
  el frontmatter mal formado: la línea 5 cerraba con 633 guiones en vez de `---`).
- **09:36:41** — el directorio `references/` borrado. Era untracked, así que git
  no podía recuperarlo.

Esto dejaba el sistema incoherente: `model-routing.json` manda `full-audit` a
`audit.md`, que delega en `audit-remediation`, pero el `SKILL.md` instalado no
conocía ninguno de los dos.

Carlos decidió restaurar la versión reestructurada. Antes de sobrescribir, la
versión de 713 líneas —sin commitear, por tanto irrecuperable— se preservó en
`audit/full-audit-SKILL-reemplazado-2026-08-30.md`.

Restaurados desde el contenido de la sesión: `SKILL.md` (91 líneas) y los cuatro
archivos de `references/`. Verificado: frontmatter válido en ambas skills, todas
las referencias con ruta resuelven, y
`pytest tests/test_claude_system_contract.py tests/test_claude_model_routing.py -q`
→ 26 passed, 1 failed (sólo el preexistente I-1/KI-021).

### Mejoras incorporadas en la restauración

Tres, todas sustentadas por evidencia de esta misma auditoría y no por
preferencia:

1. `references/phases.md`, Fase 2: regla nueva de que una búsqueda que no
   encuentra algo no es evidencia de que no exista, con la instrucción de
   repetirla sin filtros —incluida la exclusión del módulo que define el
   símbolo— antes de reportar código muerto. Origen: el falso positivo `ALTO`
   sobre `revalidate_live_registry()` documentado en `FINDINGS.md`.
2. `references/deliverables.md`: prohibición explícita de escribir en
   `VALIDATION.md` o `MANIFEST.json` el resultado de un comando que aún corre.
   Origen: en esta auditoría escribí "1 failed, 1377 passed" mientras la suite
   seguía en ejecución y tuve que corregirlo a `NO_EJECUTADA`.
3. `references/project-anchors.md`: entrada para
   `tests/test_claude_system_contract.py` y `tests/test_claude_model_routing.py`
   como lectura obligada antes de tocar `.claude/`. Origen: `A-1`.

---

## Iteración 3 — Fase 4: correcciones aprobadas (2026-08-31)

Grupo A aprobado explícitamente por el operador. **Cinco IDs, ningún otro.** Los
del Grupo B (`R-A-1`, `N-A-4`, `N-A-5`) NO se tocaron: alteran criterios
pre-registrados o contratos con test y siguen esperando decisión.

### N-A-1 · La poda borraba ficheros sin liquidar

`src/sqp/pipeline/cleanup.py`. `_all_actionable_settled` → `_all_settled`: ahora
compara contra **todas** las filas del candidato, que es el conjunto que
`settle_candidates` gradúa, en vez de contra `_actionable` (stake>0). Se eliminó
el atajo `if actionable.empty: return True`, que con el prediction gate negando
los 39 mercados convertía la comprobación en un `True` incondicional.

Se añadió `try/except` alrededor de la lectura del settled (antes podía
propagar) y **archivado previo a cada `unlink()`**, porque una liga fuera de
temporada nunca se sobrescribe y por tanto el archivado pre-sobrescritura del run
diario no se dispara nunca para ella.

`_actionable` se conserva —lo usa `tests/test_audit_2026_07_29.py` y describe la
semántica de flags del reporte de picks— pero su docstring ya no afirma que sean
las únicas filas que se liquidan, que era la premisa falsa de raíz.

### N-A-2 · CSV corrupto que inutilizaba una liga para siempre

`src/sqp/storage/served_store.py`. Nuevo `_quarantine()`: mueve el fichero a
`<nombre>.csv.corrupt.<ts>` y eleva a `log.error`. Nunca lanza — reparar no puede
tumbar la liquidación. El `_load` ya no se limita a devolver vacío en silencio.

### N-A-3 · Respuesta vacía leída como cancelación masiva

`src/sqp/settlement/runner.py`. Guard `scores_trusted = bool(scores)` en
`fetch_and_settle`. Con un payload sin ninguna entrada usable se saltan
`_void_stale_served` y `_with_stale_voids` y se registra `log.error`. La
graduación normal sigue intacta; sólo se posterga lo irreversible.

### R-B-1 · `max_drawdown` subestimaba

`src/sqp/risk/bankroll.py`. `peak` se siembra con
`self.initial + self.adjustments_total()` en vez de `-inf`.

### N-M-6 · `event_id` sin validar abortaba el día entero

`src/sqp/pipeline/cleanup.py`. `unsettled_completed_picks` valida ahora
`event_id` en ambos DataFrames antes del merge. Corre en `run_all` antes del
bucle de ligas y fuera de todo `try`, así que el `KeyError` impedía generar picks
de **todas** las ligas.

### Prueba existente corregida, no eliminada

`test_out_of_season_only_flagged_rows_is_pruned` afirmaba que un fichero sin
picks accionables era seguro de borrar. Esa premisa es exactamente la refutada
por N-A-1. Se reescribió como
`test_out_of_season_only_flagged_rows_is_kept_until_settled` con la razón en el
docstring, y se añadió `test_out_of_season_zero_stake_rows_are_pruned_once_settled`
como contrapartida: la corrección **retrasa** la poda hasta la liquidación, no la
desactiva.

### Pruebas añadidas

| Archivo | Pruebas | Cubre |
|---|---|---|
| `tests/test_cleanup.py` | 5 (2 reescritas/nuevas de poda, 1 de archivado, 2 de `event_id`) | N-A-1, N-M-6 |
| `tests/test_bankroll.py` | 3 (drawdown desde apertura, pico móvil, curva creciente) | R-B-1 |
| `tests/test_served_store.py` | 2 (cuarentena y recuperación, fallo de cuarentena no letal) | N-A-2 |
| `tests/settlement/test_empty_scores_no_void.py` (nuevo) | 3 (lista vacía, esquema roto, payload sano **sí** anula) | N-A-3 |

La tercera prueba de N-A-3 es deliberada: sin ella el arreglo podría haber
desactivado la anulación por expiración sin que nada lo señalara.

---

## Iteración 4 — Fase 4, lote 1: los cuatro verificados por mí

Autorización del operador: "corrige los hallazgos confirmados y aplica
únicamente las mejoras sustentadas por evidencia obtenida durante la auditoría".
Se excluyen deliberadamente los parámetros de modelo y los criterios
pre-registrados, que siguen requiriendo decisión humana.

### N4-A-1 · Probabilidad de decisión en las vistas del operador

`evaluation/labels.py`, `audit/segments.py`, `audit/html_report.py`,
`evaluation/tipster.py`.

El predicado "calibrada con fallback por fila a la estimada" existía como
`segments._decision_prob`, privado. La lista diaria de picks y el tipster
median sobre `estimated_probability`, que es la mezcla CRUDA. Se **promueve a
`evaluation/labels.decision_prob`** y lo consumen los tres.

Se eligió `labels` y no `audit/segments` a propósito: `evaluation/tipster` no
debe depender de `audit/`. `labels` ya era la capa compartida de derivaciones
(`game_date_local`, `match_label`, `picks_vigentes`) y ya la importaban ambos.

`tipster_table(prob_col=...)` pasa de `str` a `str | None`; `None` (nuevo
default) usa el predicado compartido, y un nombre explícito sigue disponible
para diagnóstico.

### N4-A-2 · Centinela de run indexado por etapa

`monitoring/run_status.py`.

`record_run_failure` fusiona en `{"stages": {etapa: {...}}}` en vez de
sobrescribir el fichero. `clear_run_status(stage)` borra sólo su entrada y
conserva la otra; sin `stage` borra todo. `read_run_status` devuelve una forma
**plana** (`failed`/`stage`/`exit_code`/`failed_at`) porque `health.py` y el
banner del tablero leen esas claves, más un campo `stages` con la lista de
etapas rotas. Con las dos rotas manda la de **liquidación**, porque es la que
aborta el run del día siguiente.

`_read_stages` absorbe el formato plano anterior: un centinela escrito por la
versión previa sigue avisando tras actualizar, en vez de estrenar una ventana
ciega.

### N4-A-3 · El arnés de features vuelve a avanzar

`scripts/measure_features.py`.

Se reinserta el partido evaluado en `team_hist[hn]` y `team_hist[an]` al
**final** del cuerpo del bucle, después de calcular todas las señales. El orden
importa: adelantarlo sería lookahead, y hay un test que lo comprueba.

### N4-A-7 · El ECE ya no se puede deflactar

`calibration/metrics.py`. `reliability_table` descarta los pares no finitos
antes de binear. `brier_score` y `log_loss` se dejan como están: con NaN
devuelven NaN, que es fallar ruidosamente y por tanto correcto.

### Pruebas

| Archivo | Pruebas | Cubre |
|---|---|---|
| `tests/test_decision_probability_views.py` (nuevo) | 9 | N4-A-1 |
| `tests/test_run_status.py` | 4 nuevas, 2 actualizadas | N4-A-2 |
| `tests/test_measure_features_harness.py` (nuevo) | 5 | N4-A-3 |
| `tests/test_calibration_metrics.py` | 4 nuevas | N4-A-7 |

Dos pruebas existentes de `test_run_status.py` fijaban el formato plano en
disco que este cambio sustituye: `test_sentinel_is_valid_json` y
`test_dashboard_banner_escapes_its_content`. Se **actualizaron al formato
nuevo**, no se eliminaron, y la razón queda en el docstring de la primera.

Tres de las pruebas nuevas merecen mención porque cubren el riesgo del propio
arreglo, no sólo el defecto:

- `test_history_never_includes_the_game_being_evaluated`: el arreglo de N4-A-3
  consiste en añadir datos al historial, así que la pregunta obvia es si
  introduce lookahead. No lo hace, y ahora está fijado.
- `test_a02_legacy_flat_sentinel_is_still_honoured`: un cambio de formato de
  fichero de estado puede estrenar una ventana ciega en la primera ejecución
  tras actualizar.
- `test_segments_reuses_the_shared_predicate`: A-01 se produjo porque el
  predicado estaba duplicado. El test comprueba identidad de objeto, así que
  cualquier redefinición futura falla.
