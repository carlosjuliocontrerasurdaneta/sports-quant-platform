# Validación — Auditoría 2026-08-04

Todos los comandos se ejecutaron realmente; las salidas se transcriben de la
terminal. Esta sección existe porque el hallazgo A-1 de esta misma auditoría es
que el estado se declaraba sin medirlo.

Entorno: Windows 11, Python 3.14.4, rama `fix/claude-audit-20260804`, commit
base `2a293cb`.

## Línea base

La sesión encontró el árbol de trabajo ya modificado por una remediación previa
inconclusa. Se registran las dos lecturas para no ocultar el punto de partida.

### Al abrir la sesión (antes de cualquier cambio propio)

```
$ PYTHONPATH=src pytest tests/ -q
5 failed, 612 passed in 220.46s (0:03:40)

FAILED tests/test_claude_model_routing.py::test_fable_5_is_authorized_as_the_main_model_only
FAILED tests/test_config.py::test_missing_config_file_fails_fast_instead_of_disarming_risk
FAILED tests/test_orchestrator_safety.py::test_settlement_failure_with_picks_at_risk_aborts_the_day
FAILED tests/test_orchestrator_safety.py::test_transient_settlement_failure_does_not_abort_the_day
FAILED tests/test_orchestrator_safety.py::test_audit_report_failure_is_best_effort
```

Contradice directamente `Obsidian/Bitácora/2026-08-04.md`, que afirmaba "Suite
completa verde".

```
$ python -m ruff --version
ruff 0.15.14
$ python -m mypy --version
mypy 2.1.0 (compiled: yes)
```

Contradice directamente la afirmación "Ruff y Mypy: no ejecutados porque no
están instalados en el entorno". **Ninguna herramienta faltó**: no hubo que
instalar nada.

### Tras corregir los 5 fallos, antes de las correcciones de esta auditoría

```
$ python --version
Python 3.14.4
$ python -m compileall -q src scripts
OK
$ python -m pip check
No broken requirements found.
$ python -m ruff format --check .
192 files would be reformatted, 17 files already formatted
$ PYTHONPATH=src pytest tests/ -q
617 passed in 103.51s
$ python -m ruff check .
All checks passed!
$ python -m mypy src
Success: no issues found in 89 source files
$ PYTHONPATH=src python scripts/health_check.py
Pipeline health: WARN (0 errors, 2 warnings)
```

## Estado final

```
$ python -m compileall -q src scripts
OK

$ PYTHONPATH=src pytest tests/ -q
618 passed in 85.14s (0:01:25)

$ python -m ruff check .
All checks passed!

$ python -m mypy src
Success: no issues found in 89 source files

$ python -m pip check
No broken requirements found.

$ PYTHONPATH=src python scripts/health_check.py
Health report: WARN (0 errors, 2 warnings)
Pipeline health: WARN
  mlb  results=8971 features=8971 moneyline_model=True calibration=True
  nba  results=34065 features=34065 moneyline_model=True calibration=False
  nfl  results=7964 features=7964 moneyline_model=True calibration=False
  nhl  results=32837 features=32837 moneyline_model=True calibration=False
  [WARN] chile: 42 served row(s) pending beyond the scores window
  [WARN] tennis_atp_canadian_open: 12 served row(s) pending beyond the scores window
```

## Comparación línea base → final

| Verificación | Al abrir | Final | Δ |
|---|---|---|---|
| pytest | 5 failed / 612 passed | **618 passed / 0 failed** | +6 tests, 5 fallos resueltos |
| ruff check | no ejecutado (declarado imposible) | **All checks passed!** | verificado |
| mypy | no ejecutado (declarado imposible) | **89 archivos, sin issues** | verificado |
| compileall | no registrado | OK | verificado |
| pip check | no registrado | No broken requirements | verificado |
| health check | no registrado | WARN (0 errors, 2 warnings) | ver M-2 |
| ruff format --check | no registrado | 192 reformatearía | I-1, no es estándar del proyecto |

## Verificaciones específicas de auditoría

```
$ git ls-files | wc -l
443
$ git ls-files | grep -iE '\.(pyc|pkl|joblib|log|csv|parquet|zip|env|db)$|^data/|^logs/'
data/bets/.gitkeep
data/processed/.gitkeep
$ du -sh .git
5.8M
```

Barrido de secretos sobre los 443 archivos trackeados (patrones
api_key/secret/token/password con valores ≥16 caracteres, y cadenas base64/hex
≥32): sin coincidencias reales. El único match es
`audit/latest/MANIFEST.json:6`, que es un hash de commit git.

```
$ python (integridad referencial de .claude/automation/model-routing.json)
rutas totales: 24
loops inexistentes: ninguno
agentes referenciados inexistentes: ninguno
```

## Herramientas no disponibles

Ninguna. `pytest`, `ruff`, `mypy`, `pip` y `python` estaban todos instalados y
se ejecutaron. `pip-audit` (que el CI ejecuta contra `requirements.lock`) **no se
ejecutó localmente**: requiere instalación y descarga del índice de advisories.
No puedo confirmar el estado de vulnerabilidades de dependencias en esta pasada;
el CI lo cubre de forma bloqueante en cada push.

## No verificado

- Tareas del Task Scheduler de Windows: fuera del alcance del repositorio.
- Contenido de `data/`, `historical/`, `logs/`, `exports/`: regla permanente del
  proyecto.
- Ejecución real del pipeline diario (consume cuota del API de odds).
