# Validación — Auditoría 2026-09-06 y su remediación

Clasificación: `PASO` / `FALLO` / `FALLO_PREEXISTENTE` / `REGRESIÓN_INTRODUCIDA` /
`NO_EJECUTADA`. Se registra el **código de salida real**.

Línea base capturada **antes** de tocar nada: `1547 passed, 1 skipped` en
2515,40 s, exit 0.

---

## 1. Matriz de cobertura de la auditoría

| Área | Prio | Estado | Componentes | Método | Validación | Limitaciones |
|---|---|---|---|---|---|---|
| Arquitectura y límites | P0 | REVISADA | capas de `src/sqp` | lectura dirigida + llamadores | `mypy src` exit 0 | — |
| Riesgo y staking | P0 | REVISADA | kelly, bankroll, edge, caps de exposición | lectura + llamadores | tests dirigidos | **insuficiente**: no se ejerció la condición de disparo de `_exigir_pnl_legible` (ver §5) |
| Cuotas / no-vig | P0 | REVISADA | `markets/{odds,vig,edge}` | lectura + guards de finitud | suite completa | — |
| Calibración y promoción | P0 | REVISADA | `calibration/calibrator.py`, `pergame.py` | lectura + **reproducción controlada** | 74 tests dirigidos, exit 0 | — |
| Gates (CLV / prediction / degradación) | P0 | REVISADA | `risk/*_gate.py`, `daily._zero_stake_flag` | lectura + precedencia | suite | — |
| Liquidación | P0 | REVISADA | `settlement/{settle,runner}.py` | lectura del grading | suite | — |
| Persistencia y concurrencia | P0 | REVISADA | `storage/{atomic,lock,served_store}` | lectura + llamadores de `locked()` | suite | fsync de directorio (POSIX) no cubierto |
| Fuga temporal / features | P0 | REVISADA | `features/rest_form.py`, `roi_engine._prior_games` | contrato + inspección de ambos llamadores | 20 tests nuevos, exit 0 | — |
| Pipeline diario | P0 | REVISADA | `daily.py`, `probabilities.py`, `revalidation.py` | lectura + diff del último commit | suite | — |
| Integración proveedores | P1 | REVISADA | `providers/odds_api.py` + caché | lectura de retry/timeout/redacción | reproducción de caché | — |
| **CI/CD (fichero + estado)** | P1 | REVISADA | `ci.yml`, runs de `main` | lectura + `gh run list/view` | **ROJO** (run 33994699340) | — |
| **Tareas programadas (fichero + estado)** | P1 | REVISADA | 5 tareas `SQP_*` | `Get-ScheduledTaskInfo` | `SQP_Validate_OOS_Cdev` rc=0x1 | — |
| **Hooks (cableado + presupuesto)** | P1 | REVISADA_PARCIALMENTE | 7 hooks + `settings.json` | lectura + tests de contrato | 40 tests, exit 0 | el timeout real de `codex review` no se midió (llamada de pago) |
| Configuración | P1 | REVISADA | `configs/*.yaml`, `Settings.validate` | lectura + rangos | suite | `.env` EXCLUIDA |
| Dependencias | P1 | REVISADA | `pyproject`, `requirements.lock` | coherencia + `pip-audit` en CI | patas 3.11/3.13/3.14 verdes el 2026-09-05 | `pip-audit` no re-ejecutado localmente |
| Seguridad | P1 | REVISADA | secretos, redacción, hook, dashboard | grep + lectura de escapes | 0/297 `.md` con coincidencia | — |
| Pruebas | P1 | REVISADA | 1395 funciones, 4 skips | ejecución completa | ver §2 | 224 `slow` fuera del hook local (deliberado) |
| Sistema de Skills/instrucciones | P1 | REVISADA | `.claude/**` | inventario + integridad de referencias | validador de routing exit 0 | — |
| Docker | P2 | REVISADA | `Dockerfile`, `Makefile` | lectura | **CI no lo construye** | imagen no construida |
| Documentación | P2 | REVISADA | README, REPO_DESCRIPTION, docs/, Obsidian | contraste con el código | 7 desviaciones halladas | — |
| Limpieza / residuos | P2 | REVISADA | `graphify-out`, `.codex-tmp`, caches | `du`, `git check-ignore`, historial | — | ninguna eliminación autorizada |
| `logs/` | P1 | **EXCLUIDA** | — | — | — | denegado por `Read(./logs/**)` |
| `.env` | P0 | **EXCLUIDA** | — | — | — | denegado por `Read(./.env)` |
| Datos operativos (contenido) | P1 | REVISADA_PARCIALMENTE | `data/odds` | agregado programático (33 ligas) | 0 sin cierre utilizable | prohibido cargar datasets a contexto |

---

## 2. Comandos ejecutados

### Línea base (antes de corregir)

| Comando | Propósito | Salida | Clase |
|---|---|---|---|
| `python -m pytest -q -p no:cacheprovider` | línea base | `1547 passed, 1 skipped` en 2515,40 s, **exit 0** | `PASO` |
| `ruff check src scripts tests` | lint | `All checks passed!`, **exit 0** | `PASO` |
| `mypy src` | tipos | `no issues found in 98 source files`, **exit 0** | `PASO` |
| `gh run list --branch main --limit 5` | **estado** del CI | último run `failure` | `FALLO_PREEXISTENTE` |
| `gh run view 33994699340 --log-failed` | causa | `test_file_cache_roundtrip_and_ttl` → `1 failed, 1546 passed` | `FALLO_PREEXISTENTE` |
| `gh issue list --label ci-rojo` | ¿avisó la alarma? | issue #1 OPEN | `PASO` (el control funcionó) |
| `Get-ScheduledTaskInfo` ×5 | **estado** de las tareas | `SQP_Validate_OOS_Cdev` rc=0x1 | `FALLO_PREEXISTENTE` |
| `python scripts/validate_claude_model_routing.py` | política de routing | `OK`, **exit 0** | `PASO` |

### Reproducciones controladas (todas en directorios temporales)

| Reproducción | Antes | Después del parche |
|---|---|---|
| `FileCache` con `mtime` +0,5 s | edad −0,4996; `get(ttl=0)` → `{'v': 1}` | `get(ttl=0)` → `None` |
| `promote_calibrators`, meta `n_val_events=1` | `[]` (rechazado) | `[]` |
| `promote_calibrators`, **sin** meta | `['liga_h2h']` **promovido** | `[]` |
| `promote_calibrators`, meta corrupto | `['liga_h2h']` **promovido** | `[]` |
| Agregado sobre `data/odds` (33 ligas) | 0 ligas sin cierre utilizable | — |

**Efectos observados:** ninguno sobre el repositorio ni sobre `data/`. Ambas
reproducciones redirigieron `MODELS_DIR` / usaron `tempfile.mkdtemp()`.

### Validación de los parches

| Comando | Salida | Clase |
|---|---|---|
| `pytest tests/test_odds_cache.py` | `6 passed` en 2,19 s, **exit 0** | `PASO` |
| `pytest tests/test_calibrator.py test_calibration_live.py test_pergame_calibration.py test_auto_promote.py test_calibradores_pendientes.py` | `74 passed` en 12,05 s, **exit 0** | `PASO` |
| `pytest tests/test_run_status.py tests/test_health*.py` (1.ª pasada) | `1 failed, 37 passed` | `REGRESIÓN_INTRODUCIDA` (ver §3) |
| `pytest tests/test_run_status.py tests/test_health*.py` (tras corregir) | `40 passed` en 5,45 s, **exit 0** | `PASO` |
| `pytest tests/test_rest_form_cutoff.py` | `20 passed` en 0,16 s, **exit 0** | `PASO` |
| `pytest tests/test_rest_form_cutoff.py test_backtest_parity.py test_measure_features_harness.py` | `37 passed` en 7,73 s, **exit 0** | `PASO` |
| `ruff check src scripts tests` (final) | `All checks passed!`, **exit 0** | `PASO` |
| `mypy src` (final) | `no issues found in 98 source files`, **exit 0** | `PASO` |
| Hook de secretos sobre un `.md` con `sk-…` | **exit 2** (bloquea) | `PASO` |
| Hook de secretos sobre un `.md` legítimo | **exit 0** | `PASO` |
| Barrido del patrón sobre los 297 `.md` rastreados | **0 coincidencias** | `PASO` (sin falsos positivos) |
| Sincronía `STAGES` ↔ `_BAT_POR_ETAPA` (en proceso, sin efectos) | `True` | `PASO` |
| Validación estática de las 7 BAT (etiquetas, `goto`, etapas, `endlocal`) | todas OK | `PASO` |
| `python -m pytest -q -p no:cacheprovider` (final) | `1575 passed, 1 skipped` en 1067,85 s, **exit 0** | `PASO` |

---

## 3. Regresión introducida y corregida

`test_health_report_is_error_when_last_run_failed` falló tras cambiar el mensaje
del health check. El test fijaba la **subcadena** `"run diario"`, que dejó de ser
cierta al cubrir el centinela etapas de fuera de la cadena diaria — y llamarle
«run diario» a un fallo de la validación OOS mensual manda a mirar el sitio
equivocado.

Se **corrigió el contrato del test**, no se revirtió el mensaje: localizador
estable (`"FALLIDA"`), más dos tests nuevos que comprueban lo que sí importa
—que el aviso nombre la etapa **y el BAT a re-ejecutar**— y que `STAGES` y
`_BAT_POR_ETAPA`, que viven en módulos distintos, no puedan derivar.

Es el mismo patrón de *assert por subcadena* que este repositorio ya se había
encontrado antes: fijaba la prosa sin comprobar nada útil.

---

## 4. Suite completa tras la remediación

```
python -m pytest -q -p no:cacheprovider
1575 passed, 1 skipped in 1067.85s (0:17:47)      exit 0
```

**Comparación con la línea base:**

| | Antes | Después | Δ |
|---|---:|---:|---:|
| passed | 1547 | **1575** | **+28** |
| failed | 0 | **0** | 0 |
| skipped | 1 | 1 | 0 |
| exit | 0 | **0** | — |

El delta cuadra exactamente con los tests añadidos, comprobado uno a uno:
**+1** `test_odds_cache` (edad negativa) · **+5** `test_calibrator` (3 de
promoción con metadato ausente/corrupto/`force` + 2 de integridad del digest) ·
**+2** `test_run_status` (el BAT a re-ejecutar por etapa + la sincronía
`STAGES`↔`_BAT_POR_ETAPA`) · **+20** `test_rest_form_cutoff` (4 casos directos +
16 parametrizaciones sobre 8 features × 2 propiedades). 1+5+2+20 = 28.

**Cero fallos, cero regresiones atribuibles.** La única regresión de la sesión
(§3) se detectó y corrigió antes de esta ejecución.

**Nota:** 1067 s frente a los 2515 s de la línea base. La diferencia es de
entorno, no de contenido: la medición inicial corrió con dos suites completas
compitiendo por CPU en la misma máquina. Ambas ejecutaron el mismo conjunto.

---

## 5. Limitaciones declaradas

1. **`logs/` y `.env` quedaron EXCLUIDAS** por la política de permisos del
   proyecto. Consecuencia directa: la causa raíz del fallo de `VALIDATE_OOS` del
   2026-09-01 es `NO_VERIFICABLE` (KI-034).
2. **Los `.bat` no los cubre ninguna puerta automática.** Se validaron
   estáticamente (etiquetas, `goto`, etapas válidas, `endlocal` en la rama de
   error). **No se ejecutaron**: dispararían el pipeline de producción y
   consumirían cuota de la API. Clase: `NO_EJECUTADA` para su ejecución real.
3. **El `Dockerfile` no se construyó.** Clase: `NO_EJECUTADA`. Por eso no se
   alineó su base a 3.14.
4. **`pip-audit` no se re-ejecutó localmente.** La evidencia es que las cuatro
   patas del job `test` pasaron en verde el 2026-09-05, y ese job incluye el
   paso bloqueante de `pip-audit`.
5. **El timeout de `crossreview-on-stop.sh` (600 s) no se midió** contra la
   duración real de `codex review`: consume una llamada de pago (KI-033/B-8).
6. **La revisión de `bankroll.py` fue insuficiente.** Se leyó el módulo y se dio
   por suficiente el guard de `_exigir_pnl_legible` sin ejercer su condición de
   disparo; sólo actúa cuando **no queda ningún** `pnl` numérico. La auditoría
   independiente de Codex del mismo día lo reprodujo como HIGH (KI-032). El área
   figura `REVISADA` en la matriz, pero esta limitación la califica.
7. **No se afirma ventaja predictiva ni rentabilidad.** Una corrección validada
   arregla un defecto; no acredita nada sobre el rendimiento del sistema.
