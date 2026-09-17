# Remediación — ronda `audit-2026-09-16`

Fecha: 2026-09-17. Autorización del operador en sesión: «Sí, hazlo» sobre la
propuesta «todos los confirmados (AUD-001…007), incluido commit+push». Base
inicial de la remediación: `44e48f2` + working tree sucio (57 entradas
preexistentes, no pisadas: se commitearon íntegras y coherentes en `f93bdc1`
como parte de AUD-003). Validación inicial: suite rápida 1936 passed, ruff 0,
mypy 0 (diagnóstico). Implementador: `claude-opus-5`; revisión escalada de
AUD-001 en `fable` (clase «parámetro de modelo», REGLA DE DESPACHO).

| ID | Estado inicial | Causa | Archivos | Cambio | Prueba | Aceptación | Riesgo residual | Estado final |
|---|---|---|---|---|---|---|---|---|
| AUD-001 | confirmado (REPRODUCED) | `poisson_match_probs` trataba las líneas de cuarto como enteras (push 0) mientras `settle._grade` liquida a medias | `src/sqp/models/distributions.py`, `src/sqp/markets/settlement_math.py` (`is_quarter_line`), `src/sqp/settlement/settle.py` (usa el predicado compartido), `tests/test_distributions.py` | Para líneas ±x,25/±x,75 se acumulan las masas de las dos líneas adyacentes (`split_asian_line`), se combinan con `combine_adjacent_lines` y se sirve la probabilidad de decisión `win_units/(win_units+loss_units)`; líneas enteras/medias ejecutan exactamente las mismas operaciones que antes | `test_quarter_line_pricing_matches_settlement_contract` (10 casos, oráculo independiente vía `_grade`): **10 failed antes → 18 passed después**; `test_non_quarter_lines_unchanged_by_asian_split` (4 casos) | desviación ≤ 1e-9 frente a la liquidación; no-cuarto sin cambio; 106 tests de distribuciones/settlement_math + 166 de adaptadores/pipeline verdes | Cambia la probabilidad servida de ~2 % de las líneas (fútbol, spreads); las etiquetas de calibración de esas líneas anteriores al 09-13 siguen con la semántica antigua (documentado, no regraduado). Revisión `fable`: 0 defectos, barrido de 18.432 combinaciones sin excepción; hallazgo adyacente **no ticketeado**: `normal_margin_probs`/`normal_total_probs` (NBA/NFL) tienen el mismo patrón con Δ ≤ 0,25 pp (por debajo de `min_edge`); queda para la siguiente ronda | pendiente de verificación |
| AUD-002 | confirmado (REPRODUCED) | remediación AUD-MED-002 actualizó `realized_roi` y dejó `roi_engine._summarize`, `html_report` y `report.py` con conjuntos distintos en numerador/denominador | `src/sqp/settlement/settle.py` (`STAKED_RESULTS`, `staked_mask`, `realized_roi_parts`), `src/sqp/settlement/runner.py`, `src/sqp/backtesting/roi_engine.py`, `src/sqp/audit/html_report.py`, `src/sqp/audit/report.py`, `tests/test_realized_roi_consistency.py` | Una definición canónica (medias en numerador y denominador; push/void fuera) reutilizada por los cuatro consumidores. `_segment_audit`: `hit_rate` sigue sobre win/loss (dirección conservadora de AUD-MED-002); `staked/pnl/realized_roi` sobre todo el stake arriesgado | 3 tests nuevos (media sola: 0,5 en los cuatro puntos; mezcla: 0,75 y no 1,5; sólo push/void: sin ROI). «Fallo antes» = reproducción del diagnóstico (0,0 / 1,50), no se pudo re-ejecutar sin parche (stash denegado) | mismo ROI en los cuatro puntos; 351 tests de liquidación/informes/dashboard verdes | Cambia la cifra publicada sólo cuando hay medias con stake; `n` por segmento pasa a contar sólo win/loss (idéntico cuando no hay medias) | pendiente de verificación |
| AUD-003 | confirmado (REPRODUCED) | commit parcial forzado por el guard de árbol; fuentes del contrato sin trackear; divergencia local/remoto | `f93bdc1` (contrato, prompts, tests, docs, Obsidian, preservación de ronda) + commit de remediación + merge con `origin/main` | Ver sección «Git» | `sync_agent_instructions.py --check` rc 0; suite sobre el árbol resultante; CI tras el push | HEAD autoconsistente y publicado; CI verde | conflictos resueltos a mano en Obsidian (si los hay) | ver «Git» |
| AUD-004 | confirmado (ENVIRONMENTAL) | directorio con ACL ilegible creado por el sandbox del auditor OpenAI | fuera del árbol Git: `.codex-tmp/pytest` → `.codex-tmp/pytest.bloqueado-20260916` | `takeown`/`icacls`/`Remove-Item`/`Rename-Item` sobre el residuo: **acceso denegado** (sin elevación). Se renombró el directorio PADRE, liberando la ruta canónica | `pytest --basetemp=.codex-tmp/pytest tests/audit/test_history_loader.py` → 4 passed | comando canónico ejecutable | el residuo sigue en disco dentro de `pytest.bloqueado-20260916/`; borrarlo requiere privilegios del operador | **mitigado** (parcial) |
| AUD-005 | confirmado (STATICALLY_VERIFIED) | decisión `9dfb4cc` (no cablear line shopping) no reflejada en yaml/`Settings` | `src/sqp/config.py`, `configs/default.yaml`, `tests/test_line_shopping.py` | Variante «aviso» (no contradice la decisión): docstring de `ExecutionConfig` y comentario del yaml declaran SIN CABLEAR; `Settings.load` emite `warning` si `books` no está vacío; candado `test_execution_prices_sigue_sin_llamadores_en_el_pipeline` que obliga a retirar el aviso si algún día se cablea | `test_books_declarados_sin_cablear_avisan` + candado; 21 tests de line shopping/config verdes | ninguna clave declarada queda silenciosamente inerte | cablearlo sigue siendo decisión del operador (cambia precios de ejecución) | pendiente de verificación |
| AUD-006 | confirmado (REPRODUCED) | fuente 3 de `_targets.py` (`--with-git`) devolvía el árbol sucio ante cualquier Bash | `.claude/hooks/_targets.py`, `tests/test_hook_targets.py` | La red de seguridad de git sólo se consulta si el comando contiene operadores de escritura (`_es_escritura`) | 2 tests nuevos (lectura con árbol sucio → nada; escritura → sí); reproducción: `cat README.md` con `--with-git` → 0 rutas (antes: árbol entero); 45 tests de hooks verdes | sesiones de solo lectura no arman el centinela | un comando que escribe en ruta calculada sin operador reconocible sigue sin cubrirse (igual que antes) | pendiente de verificación |
| AUD-007 | confirmado (STATICALLY_VERIFIED) | `train` huellaba `root` (`--data-root`) y `load_protocol` `ROOT` | `src/sqp/evaluation/feature_shadow.py`, `tests/test_feature_shadow.py` | `fingerprint(ROOT)` en `train` (huella del código) | candado por inspección de fuente; tests de shadow verdes | experimentos con `--data-root` ≠ `ROOT` cargan | ninguno | pendiente de verificación |

## Sugerencia menor aplicada (revisión `fable`)

Predicado de línea de cuarto duplicado en `settle.py:83` y `distributions.py`:
extraído a `settlement_math.is_quarter_line` y usado por ambos, para que no
puedan divergir en silencio.

## Fuera de alcance / no autorizado

- Cablear el line shopping (AUD-005 variante «cablear»): decisión del operador.
- Regraduar etiquetas históricas de calibración de líneas de cuarto.
- `normal_margin_probs`/`normal_total_probs` (hallazgo adyacente de la revisión
  `fable`, Δ ≤ 0,25 pp): sin ID en esta ronda; propuesto para la siguiente.
- Borrado con privilegios del residuo de AUD-004.

## Efectos de hooks observados

- `check-secrets.sh` (PostToolUse Bash) avisó dos veces sobre literales de
  `tests/test_audit_hooks.py:29-31,49`: fixtures sintéticas preexistentes
  (`2787d4f`), no tocadas en esta remediación; no es un secreto.
- `mark-tests-pending.sh` armó `.claude/.tests-pending` (antes del parche
  AUD-006); el hook Stop ejecutará la suite al cerrar el turno.
- `post-edit-format.sh` no intervino (todas las ediciones fueron por Bash).

## Git

Ver `VALIDATION.md` para commits, merge y CI.
