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
| Gates de riesgo (`prediction_gate`, `clv_gate`, `degradation`, `kelly`, `bankroll`) | `PARCIAL` | Inventario de rutas y parámetros; sin auditoría línea a línea | Presupuesto de contexto agotado antes de la revisión completa |
| Pipeline diario, settlement, features, providers, storage, deportes | `PARCIAL` | Trazado de las rutas tocadas por los hallazgos; hotspots identificados por `git log` | No se auditó línea a línea |
| Backtesting y walk-forward | `COBERTURA_NO_VERIFICABLE` | — | No ejecutado: requiere corridas largas y datos que no se cargaron |
| `data/`, `logs/`, `historical/`, `exports/` | `EXCLUIDA` | — | Prohibido por `CLAUDE.md` y por el `deny` de `settings.json` |

**Resultado de cobertura: `PARCIAL`.** Las áreas de dinero/probabilidad no se
revisaron con la lectura completa que exige `references/phases.md` para
declarar `REVISADA`. Se declara `PARCIAL` en vez de inflar la cobertura.

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
| `pip-audit` | Vulnerabilidades conocidas | no instalado en el entorno | — | `NO_EJECUTADA` |
| Validación de los `.bat` operacionales | Scripts no Python | no cubierta por ruff/mypy/pytest | — | `NO_EJECUTADA` |

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
