# Estado por hallazgo — ronda `audit-2026-09-16`

Actualizado: 2026-09-17 (fase verificación independiente,
`audits/prompts/verificar-remediacion.md`; ver `VERIFICATION.md` para el
detalle). La línea base es `FINDINGS.md`; esta tabla no la reescribe. Las
columnas «Remediación» y «Evidencia» generadas en la fase de remediación se
preservan sin cambios; solo se añade la columna «Verificación».

| ID | Sev | Prio | Remediación | Verificación | Evidencia | Próxima acción |
|---|---|---|---|---|---|---|
| AUD-001 | HIGH | P1 | corregido, pendiente de verificación (`4f06b4f`) | verificado-corregido | `tests/test_distributions.py` 10 failed → 18 passed; revisión `fable` 0 defectos, barrido 18.432 sin excepción | reproducción independiente propia (oráculo Poisson/`_grade` sin reutilizar `distributions.py`): desviación máxima 2,2e-16 en 6 líneas de cuarto y 4 no-cuarto; sin bypass en `adapters.py`; hallazgo adyacente Normal recuantificado a 0,32 pp (ver `VERIFICATION.md`) |
| AUD-002 | MEDIUM | P2 | corregido, pendiente de verificación (`4f06b4f`) | verificado-corregido | `tests/test_realized_roi_consistency.py` 3 passed; 351 tests de liquidación/informes | reproducción independiente propia (media sola y mixta) confirma el mismo ROI en los 4 consumidores nombrados; sin otros consumidores con conjuntos mezclados (`patterns.py`/`clv.py` revisados, autoconsistentes, fuera de alcance) |
| AUD-003 | MEDIUM | P1 | corregido, pendiente de verificación (`f93bdc1`, `31cfdb0`, push `a2ee66c..31cfdb0`) | verificado-corregido | checkout limpio de HEAD verde (`--check` rc 0, 107 tests de contratos); CI run 35224249563 **success** (test 3.11–3.14 y test-windows) | `git pull` en `C:\dev\3` ya ejecutado (HEAD idéntico a `main`, confirmado en esta fase); sin acción de producción pendiente |
| AUD-004 | MEDIUM | P2 | corregido (13:40 UTC: residuo eliminado con elevación UAC por orden del operador — `takeown` + `icacls` + `Remove-Item: OK`; padre vacío retirado) | verificado-corregido | `pytest --basetemp=.codex-tmp/pytest …` 4 passed; `existe despues: False` | ninguna; residuo confirmado ausente en esta fase |
| AUD-005 | MEDIUM | P2 | corregido (variante «aviso»), pendiente de verificación (`4f06b4f`) | verificado-mitigado → **cerrado por decisión** (operador, 2026-09-17: no se cablea; se mantiene `9dfb4cc`) | 21 tests de line shopping/config; candado `test_execution_prices_sigue_sin_llamadores_en_el_pipeline` | ninguna; decisión registrada en `.claude/memory/project-decisions.md` |
| AUD-006 | LOW | P3 | corregido, pendiente de verificación (`4f06b4f`) | verificado-corregido | reproducción: `cat README.md` con `--with-git` → 0 rutas; 45 tests de hooks | reproducción independiente propia en repo Git temporal aislado (`.codex-tmp/verify-aud006`): lectura con árbol sucio → 0 rutas; escritura → rutas del `git status` |
| AUD-007 | LOW | P3 | corregido, pendiente de verificación (`4f06b4f`) | verificado-corregido | candado en `tests/test_feature_shadow.py`; 77 tests | inspección de código: `train`/`load_protocol` usan `fingerprint(ROOT)` en los tres puntos (líneas 103, 140, 171); simetría confirmada por construcción |

## Nuevo, sin ID en esta ronda

- **Pricing Normal con líneas de cuarto** (revisión `fable` de AUD-001):
  `normal_margin_probs`/`normal_total_probs` (NBA/NFL/NCAA) tienen el mismo
  patrón que AUD-001; con `margin_sigma` 13 y `total_sigma` 22 la desviación
  medida es ≤ 0,25 pp (por debajo de `min_edge` 0,02). Plantilla disponible en
  `models/independent.py::FrozenScoreModel._single_line`. Propuesto para la
  siguiente ronda (LOW). **Verificación independiente (2026-09-17):**
  confirmado real; recuantificado con barrido propio sobre los `sigma`
  reales de `sports/registry.py` (rejilla fina, no puntos sueltos):
  desviación máxima medida **0,32 pp** (spread) / **0,30 pp** (total), algo
  por encima del `0,25 pp` original pero del mismo orden de magnitud y
  todavía por debajo de `min_edge` en un orden de magnitud. Ver
  `VERIFICATION.md`.

## Heredado

- B-02 (acciones CI sin pin a SHA): abierto. Verificación independiente
  (2026-09-17): confirmado aún abierto (`ci.yml` sigue en `@v4`/`@v5`).
- CL-02 (`wnba_totals_calibration_iso.joblib`): abierto, requiere aprobación.
  Verificación independiente (2026-09-17): el fichero ya está en
  `data/models/retired/` y sin referencias en el repositorio, pero
  `STATUS.md`/`BACKLOG.md` seguían describiéndolo como no trasladado; se
  declara NOT_VERIFIABLE si el traslado ya ejecutado contó con la aprobación
  expresa que exige el backlog (`data/` no está bajo Git). No es un defecto
  de código. Ver `VERIFICATION.md`. **Resolución del NOT_VERIFIABLE
  (sesión principal, 2026-09-17):** `Obsidian/Tareas.md:46` registra el
  traslado como hecho el 2026-09-13 dentro de la remediación aprobada de esa
  ronda; el diagnóstico de esta ronda lo marcó «persistente» por error de
  lectura (`ls data/models/retired/` sí lo listaba). CL-02: **cerrado**.

## Bookkeeping

- `.claude/automation/runtime/current-task.md`: escritura denegada durante el
  diagnóstico; actualizado en la fase de remediación (commit `7f24491`).
- Obsidian (`Bitácora/2026-09-17.md`, `Tareas.md`) y `.claude/memory`
  (`/memoria-guardar`): hechos en `7f24491`; tareas de pull y AUD-004
  cerradas en `09bcef5` y `1ee3571`.
