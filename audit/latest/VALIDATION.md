# Validación — Auditoría 2026-08-30

Códigos de salida reales. Ningún resultado se declara sin haberlo ejecutado.

## Matriz de cobertura

| Área | Estado | Método | Limitación |
|---|---|---|---|
| Contratos de `.claude` (loops, routing, skills) | `REVISADA` | Lectura completa + los 15 tests de `test_claude_system_contract.py` + extracción programática de los bloques de guardarraíles | — |
| Calibración (camino de servicio) | `REVISADA` | Lectura de `calibrator.py` (criterio estructural, `revalidate_live_registry`, `promote_calibrators`) + trazado de la cadena del run diario | Sin ejecución del pipeline real: no se consumió cuota de API |
| Cuotas y edge | `REVISADA` | Lectura de `markets/odds.py`, `markets/edge.py` y de todos los consumidores de `is_usable_price` | — |
| Seguridad (secretos, timeouts, `.env`) | `REVISADA` | Barrido sobre archivos trackeados + verificación de `requests.get/post` sin `timeout` | — |
| Dependencias | `REVISADA` | `pip check` | `pip-audit` `NO_EJECUTADA` (no instalado en este entorno) |
| Calidad estática de `src`, `scripts`, `tests` | `REVISADA` | `ruff check`, `mypy src` | — |
| Suite de pruebas | `REVISADA` | `pytest tests/ -q` completo, antes y después | 30:51 por ejecución |
| Configuración de riesgo | `PARCIAL` | Lectura de `configs/default.yaml` y de la detección de divergencia en `config.py` | `.env` no es legible por política de permisos: la divergencia efectiva `.env`↔YAML no se verificó, sólo la existencia del mecanismo que la vigila |
| Gates de riesgo (`prediction_gate`, `clv_gate`, `degradation`, `kelly`, `bankroll`) | `REVISADA` (2026-08-31) | Lectura completa de los 5 módulos (708 líneas) + los 11 consumidores + reproducción controlada de 3 comportamientos + corroboración sobre el registro vivo del gate | No se ejecutó el pipeline real (no se consumió cuota de API); los `.bat` siguen sin validación |
| Settlement — grading (`settlement/settle.py`) | `REVISADA` (2026-08-31) | Lectura completa + verificación empírica del guard de `away` (845 filas) y del cableado de `three_way` | — |
| Persistencia — atomicidad y locking (`storage/atomic.py`, `storage/lock.py`) | `REVISADA` (2026-08-31) | Lectura completa + inspección de las 6 secciones críticas que usan `locked()` | — |
| Pipeline diario (`daily.py`, `probabilities.py`, `budget.py`) | `REVISADA` (2026-08-31, it. 3) | Lectura línea a línea (1.122 líneas) + reproducciones en memoria + revalidación propia del hallazgo ALTO (N-A-4) contra `tests/test_daily_exposure.py:120-129` | No se ejecutó el pipeline real: no se consumió cuota de API |
| Settlement (`runner.py`, `backfill_teams.py`) y `revalidation.py` | `REVISADA` (2026-08-31, it. 3) | Lectura línea a línea (764 líneas) + reproducciones + agregados de solo lectura sobre `data/bets` y `data/historical` + revalidación propia de N-A-3 sobre `runner.py:389-406` | `logs/` no legible por política de permisos: no se pudo confirmar si N-A-3, N-M-10 o N-M-12 ya se manifestaron |
| Resto de `storage/` y captura (`closing_capture`, `intraday_scan`, `cleanup`) | `REVISADA` (2026-08-31, it. 3) | Lectura línea a línea (1.106 líneas) + 9 reproducciones en directorio temporal del sistema + revalidación propia de N-A-1 (vía `settle.py:86-95`), N-A-2 (`served_store.py:99-139`) y N-A-5 (medición sobre `data/calibration`) | Frecuencia real de N-M-19/20/21 y N-M-22 no cuantificada sobre `data/historical` |
| Scripts `.bat` operacionales (8) | `REVISADA` (2026-08-31, it. 3) | Lectura completa de los 8 | Revisión estática: no se ejecutó ninguno (dispararían el pipeline real y consumirían cuota) |
| Features, providers, adaptadores por deporte | `PARCIAL` | Leídos como contexto para verificar hallazgos del pipeline; sin lectura línea a línea propia | No auditados como alcance primario en ninguna iteración |
| Backtesting y walk-forward | `COBERTURA_NO_VERIFICABLE` | — | No ejecutado: requiere corridas largas y datos que no se cargaron |
| `data/`, `logs/`, `historical/`, `exports/` | `EXCLUIDA` | — | Prohibido por `CLAUDE.md` y por el `deny` de `settings.json` |

**Resultado de cobertura tras la iteración 3: `PARCIAL`**, pero por un motivo
distinto y mucho más acotado. Las ~2.700 líneas del camino del dinero que la
iteración 2 dejó pendientes están ahora `REVISADA`, igual que los `.bat`. Lo que
queda fuera es: **features, providers y adaptadores por deporte** (nunca fueron
alcance primario) y **backtesting/walk-forward** (no ejecutable sin corridas
largas). Se declara `PARCIAL` en vez de inflar la cobertura.

## Comandos ejecutados

| Comando | Propósito | Resultado | Código | Clasificación |
|---|---|---|---|---|
| `pytest tests/ -q` (línea base) | Estado antes de corregir | 3 failed, 1375 passed, 1 skipped (1851 s) | 1 | `FALLO` |
| `ruff check src scripts tests` | Lint | All checks passed! | 0 | `PASO` |
| `mypy src` | Tipos | no issues found in 98 source files | 0 | `PASO` |
| `pip check` | Coherencia de dependencias | No broken requirements found. | 0 | `PASO` |
| `scripts/health_check.py` | Salud operativa | WARN (0 errors, 1 warning) | 0 | `PASO` |
| `git show HEAD:.claude/settings.json` | Atribuir el fallo del modelo | `claude-fable-5` en HEAD | 0 | `PASO` |
| Extracción de bloques `## Common guardrails` (línea base) | Confirmar A-1 por segundo método | 2 bloques distintos; `audit.md` sin `/verification-gate` | 0 | `FALLO` |
| `pytest tests/test_claude_system_contract.py -q` (tras el fix) | Prueba específica de A-1 | 15 passed | 0 | `PASO` |
| Extracción de bloques (tras el fix) | Revalidación independiente de A-1 | 1 bloque sobre 11 loops; ninguno sin gate | 0 | `PASO` |
| `ruff check src scripts tests` (tras el fix) | Regresión estática | All checks passed! | 0 | `PASO` |
| `mypy src` (tras el fix) | Regresión de tipos | no issues found in 98 source files | 0 | `PASO` |
| `pytest tests/ -q` (final) | Regresión completa | 1 failed, 1377 passed, 1 skipped (1381 s) | 1 | `FALLO_PREEXISTENTE` |
| `pytest tests/ -q` (tras cerrar KI-021) | Confirmar verde total | **1378 passed, 1 skipped** (910 s) | 0 | `PASO` |
| `python -m pip_audit -s osv -r requirements.lock` | Vulnerabilidades conocidas | No known vulnerabilities found | 0 | `PASO` (2026-08-31) |
| Validación de los `.bat` operacionales | Scripts no Python | Revisión estática de los 8: errorlevel, orden SETTLE→RUN, intérprete fijo, `setlocal`, quoting. Sin defecto | — | `PASO` (2026-08-31, it. 3) |

## Iteración 3 (2026-08-31) — comandos ejecutados

| Comando | Propósito | Resultado | Código | Clasificación |
|---|---|---|---|---|
| `ruff check src scripts tests` | Deriva estática antes de auditar | All checks passed! | 0 | `PASO` |
| `mypy src` | Tipos | no issues found in 98 source files | 0 | `PASO` |
| `pytest tests/test_cleanup.py tests/test_daily_exposure.py tests/test_budget.py tests/test_feature_store.py tests/test_feature_manifest.py -q` | Línea base de los módulos auditados | 51 passed en 9,40 s | 0 | `PASO` |
| Agregado sobre `data/calibration/graded_*.csv` | Medir la duplicación (N-A-5) | 21 ficheros, 16.702 filas, 7.243 unidades, **ratio 2,306** | 0 | `PASO` |
| Diagnóstico de claves sobre `graded_mls.csv` | Refutar el 3,84x del especialista | 3.103 filas; 587 / 483 / 3.103 unidades según la clave; ninguna da 380 | 0 | `PASO` |
| `grep` de consumidores de `build_training_dataset` | Acotar la severidad de N-M-1 | Sólo `train_models.py`, `build_features.py`, `evaluation/compare.py` — rama ML, sin llamador en producción | 0 | `PASO` |
| `git status --short` antes y después de los especialistas | Verificar que la fase de solo lectura no escribió nada | Idéntico: los mismos 8 archivos preexistentes | 0 | `PASO` |
| `pytest tests/ -q` (fase 1-3) | — | no re-ejecutada | — | `NO_EJECUTADA` en la fase de auditoría: no se había modificado ningún archivo de código, así que el resultado conocido (1378 passed) seguía vigente |

## Iteración 3 — Fase 5: validación de las correcciones aprobadas

Grupo A: `N-A-1`, `N-A-2`, `N-A-3`, `R-B-1`, `N-M-6`. Grupo B no tocado.

| Comando | Propósito | Resultado | Código | Clasificación |
|---|---|---|---|---|
| `pytest tests/test_cleanup.py tests/test_bankroll.py tests/test_served_store.py tests/settlement/ -q` (1er intento) | Pruebas específicas de los 5 defectos | 1 failed, 105 passed | 1 | `FALLO` — **de la prueba, no del código**: `test_pruned_files_are_archived_before_deletion` fijaba el nombre del archivo de predictions, pero el fixture no escribe `generated_at`, así que `_archive_existing` cae al mtime (es N-B-5, no una regresión). Aserción corregida |
| `pytest tests/test_cleanup.py tests/test_bankroll.py tests/test_served_store.py tests/settlement/ -q` (2º) | Idem, tras corregir la aserción | **106 passed** en 12,83 s | 0 | `PASO` |
| `ruff check src scripts tests` | Regresión estática tras las correcciones | All checks passed! | 0 | `PASO` |
| `mypy src` | Regresión de tipos tras las correcciones | no issues found in 98 source files | 0 | `PASO` |
| `git diff` de los 4 módulos tocados | Revisión del parche | 68/39/28/7 líneas; sin cambios colaterales | 0 | `PASO` |
| `pytest tests/ -q` (suite completa, final) | Regresión total | **1390 passed, 1 skipped** en 1.145,81 s (19:05) | 0 | `PASO` |

### Separación de fallos — iteración 3

- **Regresiones introducidas: ninguna.** 1378 → **1390** aprobados, 0 fallos
  antes y después. El delta de +12 cuadra exactamente con las pruebas añadidas
  (4 en `test_cleanup.py`, 3 en `test_bankroll.py`, 2 en `test_served_store.py`,
  3 en `tests/settlement/test_empty_scores_no_void.py`); la prueba reescrita de
  la poda no altera el conteo.
- **Fallos preexistentes: ninguno.** KI-021 se cerró el 2026-08-30.
- **Único fallo de la sesión:** una aserción mía sobre-especificada, corregida
  antes de la validación final. No era del código.
- **`s` (1 skipped):** el mismo skip de siempre, sin relación con estas
  correcciones.

## Efectos secundarios — iteración 3

`pytest` escribe `__pycache__/` y `.pytest_cache/`, ignorados por git. Los tres
especialistas de fase 1 no escribieron nada en el repositorio (`git status`
idéntico antes y después). En fase 4 se tocaron **exactamente** 4 módulos de
`src/` y 4 archivos de `tests/`, más los artefactos de `audit/latest/` y
`current-task.md`. Ningún cambio en `configs/`, `.env`, `data/`, `scripts/` ni
en los `.bat`. Ningún parámetro de riesgo, stake, bankroll, `pick_mode` o
`shadow_mode` modificado. `NOTAS.md` intacto.
| Ejecución real de los 8 `.bat` | Validación dinámica | — | — | `NO_EJECUTADA` — dispararían el pipeline real y consumirían cuota de API |

## Nota de proceso sobre la delegación

Tres especialistas de solo lectura corrieron en paralelo (fase 1). Dos
dispararon un aviso de seguridad del harness por acciones que el clasificador no
pudo evaluar. **Comprobado:** `git status --short` es byte-idéntico antes y
después — los mismos 8 archivos preexistentes, ningún archivo nuevo ni
modificado. Las reproducciones corrieron en `%TEMP%\sqp_audit_repro`, fuera del
repositorio. Ningún hallazgo de especialista se aceptó sin comprobación propia;
dos afirmaciones se corrigieron a la baja (ver la tabla de correcciones en
`FINDINGS.md`).

## Separación de fallos

- **Regresión introducida y corregida:** los 2 fallos de
  `test_claude_system_contract.py` (A-1). Introducidos el 2026-08-29, detectados
  y corregidos en esta auditoría. Verificado por la prueba específica (15 passed,
  código 0), por la revalidación independiente y por la suite completa:
  1375 → 1377 aprobados, 3 → 1 fallos. Ninguna regresión nueva.
- **Fallo preexistente, ya cerrado:**
  `test_main_model_matches_the_authorized_policy` (I-1 / KI-021). No era
  atribuible a esta auditoría. El operador decidió Opus 5 en las cuatro puntas el
  2026-08-30 y la suite quedó completamente verde: **1378 passed, 0 fallos**.

## Efectos secundarios

`pytest` escribe `__pycache__/` y `.pytest_cache/`, ambos ignorados por git.
`git status` antes y después no muestra ningún archivo inesperado.

El hook `post-edit-format.sh` (`ruff check --fix`) no actuó en la corrección de
A-1 y M-1, cuyos dos archivos son Markdown. Sí se disparó al cerrar KI-021, que
tocó `tests/test_claude_model_routing.py`. Revisado el diff de ese archivo: 18
inserciones y 6 eliminaciones, de las cuales **sólo dos son lógica** —los dos
`assert` del modelo— y el resto comentarios. El hook no alteró el parche.
