# Estado por hallazgo — ronda `audit-2026-09-16`

Actualizado: 2026-09-17 (fase remediación). La línea base es `FINDINGS.md`;
esta tabla no la reescribe. La columna «Verificación» la rellena la fase
«Verificación independiente» (`audits/prompts/verificar-remediacion.md`).

| ID | Sev | Prio | Remediación | Verificación | Evidencia | Próxima acción |
|---|---|---|---|---|---|---|
| AUD-001 | HIGH | P1 | corregido, pendiente de verificación (`4f06b4f`) | — | `tests/test_distributions.py` 10 failed → 18 passed; revisión `fable` 0 defectos, barrido 18.432 sin excepción | verificación independiente; `git pull` en `C:\dev\3`; medir en la siguiente auditoría diaria las líneas de cuarto servidas |
| AUD-002 | MEDIUM | P2 | corregido, pendiente de verificación (`4f06b4f`) | — | `tests/test_realized_roi_consistency.py` 3 passed; 351 tests de liquidación/informes | verificación independiente |
| AUD-003 | MEDIUM | P1 | corregido, pendiente de verificación (`f93bdc1`, `31cfdb0`, push `a2ee66c..31cfdb0`) | — | checkout limpio de HEAD verde (`--check` rc 0, 107 tests de contratos); CI run 35224249563 **success** (test 3.11–3.14 y test-windows) | `git pull` en `C:\dev\3` |
| AUD-004 | MEDIUM | P2 | corregido (13:40 UTC: residuo eliminado con elevación UAC por orden del operador — `takeown` + `icacls` + `Remove-Item: OK`; padre vacío retirado) | — | `pytest --basetemp=.codex-tmp/pytest …` 4 passed; `existe despues: False` | verificación independiente |
| AUD-005 | MEDIUM | P2 | corregido (variante «aviso»), pendiente de verificación (`4f06b4f`) | — | 21 tests de line shopping/config; candado `test_execution_prices_sigue_sin_llamadores_en_el_pipeline` | decisión del operador sobre cablear el line shopping (clase de escalado) |
| AUD-006 | LOW | P3 | corregido, pendiente de verificación (`4f06b4f`) | — | reproducción: `cat README.md` con `--with-git` → 0 rutas; 45 tests de hooks | verificación independiente |
| AUD-007 | LOW | P3 | corregido, pendiente de verificación (`4f06b4f`) | — | candado en `tests/test_feature_shadow.py`; 77 tests | verificación independiente |

## Nuevo, sin ID en esta ronda

- **Pricing Normal con líneas de cuarto** (revisión `fable` de AUD-001):
  `normal_margin_probs`/`normal_total_probs` (NBA/NFL/NCAA) tienen el mismo
  patrón que AUD-001; con `margin_sigma` 13 y `total_sigma` 22 la desviación
  medida es ≤ 0,25 pp (por debajo de `min_edge` 0,02). Plantilla disponible en
  `models/independent.py::FrozenScoreModel._single_line`. Propuesto para la
  siguiente ronda (LOW).

## Heredado

- B-02 (acciones CI sin pin a SHA): abierto.
- CL-02 (`wnba_totals_calibration_iso.joblib`): abierto, requiere aprobación.

## Bookkeeping

- `.claude/automation/runtime/current-task.md`: escritura denegada por el
  clasificador durante el diagnóstico; pendiente en el cierre de sesión.
- Obsidian: pendiente de bitácora 2026-09-17 (implementación) y
  `/memoria-guardar` (obligatorio al cierre según `.claude/CLAUDE.md` tras el
  merge).
