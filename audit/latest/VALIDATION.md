# Validación — Auditoría 2026-07-29/30

Todos los comandos se ejecutaron realmente. Las salidas se transcriben literalmente.

## Línea base (antes de cualquier modificación)

| Comando | Resultado |
|---|---|
| `git rev-parse HEAD` | `4036fea598b97dbe397a47f9d4318619be33a08e` (rama `main`) |
| `git status --short` | 28 modificados + 15 sin seguimiento = **43 entradas preexistentes** |
| `python --version` | `Python 3.14.4` |
| `python -m compileall -q src scripts` | exit 0, sin salida |
| `PYTHONPATH=src pytest tests/ -q` | **439 passed in 76.07s** |
| `ruff check .` | **1 error**: `E401 Multiple imports on one line` en `scripts/validate_claude_model_routing.py:3` (archivo sin seguimiento) |
| `ruff format --check .` | `173 files would be reformatted, 17 already formatted` |
| `mypy src` | `Success: no issues found in 86 source files` |
| `pip check` | `No broken requirements found.` |

### Sobre `ruff format`

Reporta 173 archivos, pero **no es un hallazgo**: el proyecto no usa `ruff format`.
El `Makefile` define `lint: ruff check src scripts tests` y CI ejecuta `ruff check`,
no `ruff format`. Se dejó intacto: reformatear 173 archivos sería un refactor
cosmético masivo sin beneficio verificable y con alto riesgo de ocultar el diff real.

## Estado final (después de las correcciones)

| Comando | Resultado |
|---|---|
| `python -m compileall -q src scripts` | exit 0, sin salida |
| `PYTHONPATH=src pytest tests/ -q` | **466 passed in 55.27s** |
| `ruff check .` | **`All checks passed!`** |
| `mypy src` | `Success: no issues found in 86 source files` |
| `pip check` | `No broken requirements found.` |
| `python scripts/validate_claude_model_routing.py` | `Claude model routing configuration: OK` |

## Comparación línea base ↔ final

| Métrica | Base | Final | Δ |
|---|---|---|---|
| Pruebas que pasan | 439 | **466** | **+27** |
| Pruebas que fallan | 0 | 0 | 0 |
| Errores de ruff | 1 | **0** | −1 |
| Errores de mypy | 0 | 0 | 0 |
| Dependencias rotas | 0 | 0 | 0 |
| Archivos modificados (vs HEAD) | 28 | 58 | +30 |
| Archivos sin seguimiento | 15 | 8 | −7 (17 duplicados eliminados, 2 tests y STATES.md añadidos) |

Las 27 pruebas nuevas: 25 en `tests/test_audit_2026_07_29.py` (una o más por hallazgo
corregido) y 2 en `tests/test_claude_model_routing.py`.

## Smoke tests y verificaciones de dominio

### Pipeline end-to-end (modo demo)

```
PYTHONPATH=src python scripts/run_daily.py --sports mlb nba --mode demo
```
`EXIT=0`. Ambas ligas estimaron 3 eventos cada una y emitieron el disclaimer
obligatorio de probabilidades estimadas. Ejecutado **después** de modificar
`daily.py`, `probabilities.py`, `config.py`, `features/*.py` y `storage/starters.py`.

### Health check

```
PYTHONPATH=src python scripts/health_check.py
```
`HEALTH_EXIT=0`, veredicto `WARN` (0 errores, 2 warnings):
```
mlb  results=8889  features=8889  moneyline_model=True calibration=True
nba  results=34065 features=34065 moneyline_model=True calibration=False
nfl  results=7964  features=7964  moneyline_model=True calibration=False
nhl  results=32837 features=32837 moneyline_model=True calibration=False
[WARN] brasileirao: 35 served row(s) pending beyond the scores window (>3d)
[WARN] chile: 49 served row(s) pending beyond the scores window (>3d)
```
Los 2 warnings son **preexistentes** y ajenos a esta auditoría (filas servidas de
fútbol fuera de la ventana de scores). Nótese que confirma Q-01: `calibration=True`
solo en MLB, y ese calibrador es de `totals`, no de `h2h`.

### Verificación del detector de secretos (S-9)

Ejecutado contra 8 archivos de prueba. **Positivos (deben detectarse):**

| Caso | Antes | Después |
|---|---|---|
| `ODDS_API_KEY = "abcdef1234567890abcdef"` (.py) | exit 2 ✓ | exit 2 ✓ |
| `set ODDS_API_KEY=abcdef1234567890abcdef` (.bat) | **exit 0 ✗** | exit 2 ✓ |
| `api_key: abcdef1234567890abcdef` (.yaml) | **exit 0 ✗** | exit 2 ✓ |
| `"Bearer abcdefghij1234567890abcdef"` | **exit 0 ✗** | exit 2 ✓ |
| `"sk-abcdefghij1234567890abcdefgh"` | **exit 0 ✗** | exit 2 ✓ |

**Negativos (no deben dar falso positivo):** `os.environ[...]` → exit 0 ✓;
`your_api_key_here` → exit 0 ✓; `os.getenv(...)` → exit 0 ✓.
Además contra archivos reales del repo: `.env.example` exit 0, `configs/default.yaml`
exit 0, `src/sqp/config.py` exit 0. Sin falsos positivos.

### Verificación de duplicados de Obsidian (K-007)

Script auditable que compara sha256 y estado de seguimiento en git:
- 48 archivos en disco, 26 versionados, 22 sin seguimiento.
- **18 grupos de duplicados exactos**; en 17 de ellos existía una pareja versionada
  con nombre UTF-8 correcto.
- 5 archivos sin pareja (`Obsidian/.obsidian/*.json`, config local del editor):
  **conservados**.
- Eliminados los 17 duplicados + 1 directorio vacío. Cero pérdida de información.

### Verificación de secretos en el historial

```
git log --all --diff-filter=A --name-only -- '*.env' '*.pem' '*.key' '*secret*' '*credential*' '*token*' '*.log'
```
174 commits revisados: el único archivo de esa forma jamás añadido es `.env.example`.
`git check-ignore -v .env` → `.gitignore:4 *.env`. Ningún archivo versionado con
`[0-9a-f]{32,}`. `git ls-files '*.pyc'` → 0. `data/` versionado solo con `.gitkeep`.

### Verificación de la configuración de Claude Code

- **67/67 rutas** en backticks (`.md`/`.py`/`.bat`/`.json`/`.yaml`/`.sh`/`.toml`)
  extraídas de `ORCHESTRATOR.md`, `CLAUDE.md`, `automation/`, 22 loops, 16 comandos,
  6 workflows, 7 playbooks y 6 checklists: **todas existen en disco**. 0 referencias rotas.
- Los 5 hooks de `settings.json` existen, todos con finales de línea LF.
- Los 24 agentes referenciados existen y están registrados en el harness.
- `route-model.py` ejecutado: exit 0, clasificación correcta.

## Herramientas y verificaciones no disponibles

| Elemento | Motivo |
|---|---|
| `pip-audit` sobre el lock actual | No se ejecutó (CI lo declara bloqueante). **No puedo confirmar** que el lock siga limpio; el último saneamiento documentado es del 2026-07-02. |
| Cobertura de pruebas por módulo | No se midió: CI la genera informativamente solo en la pata 3.12. |
| Contenido de `logs/` | Prohibido por las reglas del repositorio. **No puedo confirmar** si alguna rotación anterior al fix de redacción del 2026-07-24 conserva una URL con `apiKey=`. Si existen rotaciones previas a esa fecha, tratar la clave como potencialmente expuesta en disco. |
| Hit rate realizado del modo precisión | **No puedo confirmar esto.** No existe backtest de la regla vigente (B-02) y la muestra en producción es de 2 días. |
| Magnitud del sesgo de la no-vig sintética (Q-19) | **No puedo confirmar esto.** Requiere analizar snapshots. |
| Intención de la restauración de `superpowers-main` (K-023) | **No puedo confirmar esto.** |
| Existencia de un fallback de modelo del lado del harness (K-004) | **No puedo confirmar esto.** Lo observado es que 2 subagentes fallaron sin degradar. |
| Auditoría de calidad de código / arquitectura completa | El subagente asignado agotó su límite de sesión sin devolver informe. La dimensión queda cubierta parcialmente por la línea base (ruff, mypy, 466 pruebas) y por los hallazgos de los otros cuatro informes, pero **no hubo revisión sistemática de acoplamiento, código muerto ni cobertura por módulo**. Pendiente en `BACKLOG.md`. |

## Acciones que requerían autorización y NO se realizaron

`git commit`, `git push`, PR, merge, deploy, llamadas a APIs de pago, rotación de
credenciales, borrado de datos históricos, migraciones destructivas, habilitar
apuestas reales, cambiar bankroll o stakes, desactivar `shadow_mode`, promover
modelos o calibradores.

Verificado: `shadow_mode: true` sigue en `configs/default.yaml` y ningún parámetro
de `risk:` fue modificado.
