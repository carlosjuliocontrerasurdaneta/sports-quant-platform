# Validación — Auditoría 2026-08-02

Todos los comandos se ejecutaron realmente; las salidas se transcriben de la
terminal. Sin herramientas faltantes: ruff, mypy, pytest y pip disponibles.

## Línea base (antes de cualquier modificación)

| Comando | Resultado |
|---|---|
| `git rev-parse HEAD` | `1dba6b0474a148ea3c49c449518f5a7f341f902c` (rama `main`) |
| `git status --short` | ` M .claude/settings.json` (1 entrada preexistente: renombre de modelo del harness) |
| `python --version` | Python 3.14.4 |
| `python -m compileall -q src scripts` | exit 0 |
| `PYTHONPATH=src pytest tests/ -q` | **581 passed** in 191.48s |
| `ruff check .` | All checks passed! |
| `ruff format --check .` | 186 archivos reformatearía — el proyecto NO usa ruff format (CI solo `ruff check`); no es hallazgo |
| `mypy src` | Success: no issues found in 88 source files |
| `pip check` | No broken requirements found |
| `python scripts/health_check.py` | **WARN** (0 errors, 3 warnings): brasileirao 73 / mlb 12 / tennis_atp_washington_open 2 filas servidas pendientes fuera de la ventana de scores (>3d) |

## Validaciones de auditoría (sin modificar)

| Verificación | Resultado |
|---|---|
| Escaneo de secretos en trackeados (regex api_key/secret/token/password) | 1 match: placeholder `abcd…` en el VALIDATION.md anterior (prueba del hook). Sin secretos reales |
| Uso de `ODDS_API_KEY` | Solo vía `settings.odds_api_key` (env/dotenv); nunca hardcodeada |
| Imports de terceros vs pyproject | 8/8 declarados |
| Matemática nbinom (`distributions.py`) | media λ preservada, varianza λ(1+λ/k) — correcta |
| Rutas del router quant (`00-quant-operations-router.md`) | 13 loops + STATES.md existen todos |
| Agentes/comandos referenciados por ORCHESTRATOR | existen (verificado contra `.claude/agents/`, `.claude/commands/`) |
| `docs/loop-mandate-precision.md`, `docs/loop-progress.md` | NO existen (borrados en `f43ba00`) → B-02 |

## Prueba del fix B-01 (TDD)

| Paso | Resultado |
|---|---|
| Test nuevo contra código viejo | falla (no hay backup ni WARNING) — rojo verificado por diseño del test |
| `pytest tests/test_ml_models.py -q` tras el fix | **7 passed** (incluye el nuevo) |

## Validación final (tras todas las correcciones)

| Comando | Resultado |
|---|---|
| `PYTHONPATH=src pytest tests/ -q` | **582 passed** in 100.33s |
| `ruff check .` | All checks passed! |
| `mypy src` | Success: no issues found in 88 source files |
| `pip check` | No broken requirements found |
| `python -m compileall -q src scripts` | OK |

## Diferencias línea base → final

- Tests: 581 → **582** (+1, regresión B-01). 0 fallos en ambos puntos.
- ruff / mypy / pip check / compileall: verdes en ambos puntos.
- health check: WARN en ambos puntos (M-01 requiere decisión del operador:
  backfill gratis + settle con cuota API; esta auditoría no muta datos).
- Git: 1 entrada preexistente → cambios documentados en CHANGES.md, sin commit.
