# STATUS — ronda `audit-2026-11-03`

**Fase actual:** VERIFICACIÓN INDEPENDIENTE COMPLETADA (2026-11-04). **Veredicto: APTO CON PENDIENTES.** Detalle en `VERIFICATION.md`.

Autorización del operador (2026-11-03): total y plenipotenciaria sobre el BACKLOG. La línea base sigue en `FINDINGS.md`, el detalle por ID está en `CHANGES.md`, la evidencia del implementador en `VALIDATION.md` y la del verificador en `VERIFICATION.md`. La versión previa de este fichero (fase de remediación) está en `history/verificacion-20261104T120104Z/STATUS.md`.

Las columnas «Estado (remediación)» y «Commit» se conservan tal como las dejó la fase de remediación. Las columnas de verificación son nuevas.

| ID | Prio. | Estado (remediación) | Commit | Estado de verificación | Evidencia (resumen) | Próxima acción |
|---|---|---|---|---|---|---|
| AUD-001 | P2 | corregido, pendiente de verificación (re-pre-registro de Fable) | `914707c` | verificado-corregido | Reproducción 2 vías: `ev_flat` −0,0455 pero `ev_lado_modelo` +0,217 y `allowed`; migración simulada sin transiciones | Confirmar el registro del run de las 12:00 del 2026-11-04 |
| AUD-002 | P1 | corregido, pendiente de verificación | `ead24b2` | verificado-corregido | BAT real en repo temporal (4 escenarios); `ExecutionTimeLimit` PT72H | REG-002 |
| AUD-003 | P2 | corregido, pendiente de verificación | `914707c` | verificado-corregido | `ValueError` sin escritura; script rc 2 antes de cargar datos | — |
| AUD-004 | P2 | corregido, pendiente de verificación | `77110b4` | verificado-corregido | `_family_default`/`TUNED_KEYS`; tests pasan | — |
| AUD-005 | P2 | corregido, pendiente de verificación (diseño de Fable) | `1e50400` | verificado-corregido | `stake_price`, guarda de EV en ejecución, `settle_price` con fallback | — |
| AUD-006 | P2 | corregido, pendiente de verificación | `df015bf` | verificado-corregido | Reproducido: cuarentena `.corrupt.<UTC>` con hash idéntico | NEW-001 (otros escritores) |
| AUD-007 | P2 | **parcial**: falta comprobarlo en la máquina real y habilitar el historial del Programador (operador) | `ead24b2` | verificado-corregido (código) | Lectura real de las 5 tareas en 6,4 s; `history_enabled: false` | Operador: habilitar el historial (consola elevada) |
| AUD-008 | P3 | corregido, pendiente de verificación | `df015bf` | verificado-corregido | Lock + lectura estricta; tests pasan | — |
| AUD-009 | P3 | corregido, pendiente de verificación | `914707c` | verificado-corregido | `bloquear_entradas` con > 84 cortes o cota > 5/82; tests pasan | — |
| AUD-010 | P3 | corregido, pendiente de verificación | `1e50400` | verificado-corregido (modo edge) | NO BET si `ev_riesgo < min_edge`; tier A congelado intacto | REG-001 |
| AUD-011 | P3 | corregido (documentación), pendiente de verificación | `1e50400` | verificado-corregido (documentación) | Docstrings y comentario del yaml | — |
| AUD-012 | P3 | corregido (documentación), pendiente de verificación | `77110b4` | verificado-corregido (documentación) | Docstrings de los dos motores | — |
| AUD-013 | P3 | corregido, pendiente de verificación | `77110b4` | verificado-corregido | Cierre ≤ entrada excluido (UTC); una unidad por evento | — |
| AUD-014 | P3 | corregido, pendiente de verificación | `ead24b2` | verificado-mitigado | Diff de conjuntos: −`gh pr merge`, +12 deny | Residual: patrones de prefijo |
| AUD-015 | P4 | corregido (parseo; la purga de datos queda para el operador), pendiente de verificación | `df015bf` | verificado-corregido (parseo) | `allow_draws` solo en `soccer/` | Operador: purga opcional |
| AUD-016 | P4 | corregido, pendiente de verificación | `df015bf` | verificado-mitigado | Dedupe en llamada y en la cola de 256 KB | Residual: backfill fuera de la cola |
| AUD-017 | P4 | corregido, pendiente de verificación | `df015bf` | verificado-corregido | Validación de raíz en los tres lectores | — |
| AUD-018 | P4 | corregido, pendiente de verificación | `df015bf` | verificado-mitigado | Token `pid:uuid`; solo se borra el propio | Residual: TOCTOU mínimo, token vacío |
| AUD-019 | P4 | corregido, pendiente de verificación | `df015bf` | verificado-mitigado | Omite outcomes y eventos malformados; créditos en `finally` | Residual: `bookmaker`/`market` no dict |
| AUD-020 | P4 | corregido (diagnóstico), pendiente de verificación | `df015bf` | verificado-corregido (diagnóstico) | `complementarity_gap` y aviso > 0,01 | — |
| AUD-021 | P4 | corregido, pendiente de verificación | `914707c` | verificado-corregido | Peso ½ conforme a §2.2 del re-pre-registro | — |
| AUD-022 | P4 | **bloqueado**: requiere reescribir el historial y hacer force-push, prohibido por `CLAUDE.md`; decide el operador | — | abierto, bloqueado (exclusión, no cierre) | `git log --all -- data/backups` no vacío; repositorio PUBLIC | Operador: aceptar el riesgo o reescribir el historial |
| AUD-023 | P4 | **no aplicable** tal como está especificado: un lock de restricciones con instalación editable es incompatible con `--require-hashes` | — | no aplicable | `ci.yml:54,136` usa `pip install -e … -c requirements.lock` | Opcional: lock de runtime con hashes |
| AUD-024 | P4 | corregido, pendiente de verificación (falta comprobar el CI tras el push) | `ead24b2` | verificado-corregido | 8 `uses:` por SHA; CI de `786daeb` success | — |
| AUD-025 | P4 | corregido, pendiente de verificación | `ead24b2` | verificado-corregido | `tools: Read, Glob, Grep` en 9 agentes | — |
| AUD-026 | P4 | corregido, pendiente de verificación | `df015bf` | verificado-corregido | `ValueError` para \|x\| < 100 | — |

## Regresiones y hallazgos de la verificación

| ID | Sev. | Prio. | Relación | Estado | Próxima acción |
|---|---|---|---|---|---|
| REG-001 | LOW | P4 | Introducida por AUD-010 (`1e50400`): el tipster marca NO BET picks que el motor apuesta en `pick_mode=accuracy` | corregido en `f5b80e2`, pendiente de verificación (marca `accuracy_mode` por fila, también en el stream servido) | Condicionar el descarte por `min_edge` al modo (escalado: contrato del informe) |
| REG-002 | LOW | P4 | Introducida por AUD-002 (`ead24b2`): `wait_for_clean_tree.ps1` registra «git no pudo comprobar» cuando el árbol se limpió | corregido en `f5b80e2`, pendiente de verificación | `return ,@(...)` + aserción en el test |
| NEW-001 | MEDIUM | P3 | Preexistente (base `a5d1860`), misma causa raíz que AUD-006 no extendida: `_append_latch_log` y los escritores de `promotion_log.csv` reescriben perdiendo filas ante `ParserError` | corregido en `f5b80e2`, pendiente de verificación (helper `append_csv_log`) | Cuarentena como AUD-006 (rutas del candado Fable) |

Recuento de verificación: 19 verificado-corregido, 4 verificado-mitigado, 1 abierto-bloqueado, 1 no aplicable; 2 regresiones LOW/P4 y 1 hallazgo preexistente P3. Ningún P0/P1 abierto.

Además, KI-078 (cuenta del α consumido) se corrigió antes de esta remediación, en `aa8db2f`, y quedó fuera del alcance de esta verificación.

**Siguiente paso:** NEW-001, REG-001 y REG-002 se corrigieron el 2026-11-04 en `f5b80e2`, con revisión Fable previa al commit (APTO CON CAMBIOS, cambio aplicado) y autorización del operador («Házlo»). Falta la verificación independiente de ese commit. El operador decide AUD-022 y habilita el historial del Programador.
