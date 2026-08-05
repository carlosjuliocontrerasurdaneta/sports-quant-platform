# Archivos modificados — Auditoría 2026-08-04

Sin commit (pendiente de autorización). Estado exacto: `git status --short`.
14 archivos modificados, 296 inserciones, 91 supresiones.

## Código de producción

| Archivo | Cambio | Por qué |
|---|---|---|
| `src/sqp/config.py` | `load()` lanza `FileNotFoundError` si falta `configs/default.yaml`; el bloque de carga queda desanidado | C-2: el `if cfg_path.exists():` silencioso desarmaba `shadow_mode`, el gate de CLV, las pausas y duplicaba `max_plausible_edge`. El diff es grande pero mecánico: 3 líneas de lógica, el resto es dedent |
| `scripts/settle_all.py` | Importa `unsettled_completed_picks`; aborta solo con picks en riesgo; `settlement_audit_report()` pasa a best-effort | M-1: un 5xx o cuota agotada en una liga sin nada en riesgo costaba un día completo de evidencia. `run_all.py` ya aplica el guard M2 por liga |
| `src/sqp/monitoring/health.py` | `_rows` registra un WARNING cuando el CSV existe pero no se puede leer | B-1: "nunca ingerido" e "ingerido y ahora corrupto" eran indistinguibles en el reporte |

## Pruebas

| Archivo | Cambio |
|---|---|
| `tests/test_config.py` | +1 test: config ausente debe fallar rápido en vez de desarmar el riesgo |
| `tests/test_orchestrator_safety.py` | +3 tests: abort con picks en riesgo, no-abort transitorio, reporte best-effort |
| `tests/test_health.py` | +1 test: un CSV ilegible se registra, no se confunde con uno ausente |
| `tests/test_claude_model_routing.py` | Literal del modelo principal → `claude-opus-5`; test renombrado a `test_main_model_matches_the_authorized_policy`; retirada la aserción obsoleta `"Fable no se usa" not in policy` |

Nota: los tests de `test_config.py` y `test_orchestrator_safety.py` ya existían
en el árbol de trabajo al iniciar la sesión, escritos en rojo por una
remediación anterior que nunca implementó el código de producción. Esta
auditoría escribió el código que los pone en verde.

## Configuración y política

| Archivo | Cambio |
|---|---|
| `.claude/settings.json` | `model` → `claude-opus-5` (preexistente al iniciar la sesión; ratificado por el operador) |
| `.claude/automation/MODEL_ROUTING.md` | Modelo principal autorizado → `claude-opus-5`, con la razón y la referencia al riesgo declarado de Fable 5 |
| `.claude/memory/project-decisions.md` | Entrada de la decisión que supersede; la entrada anterior queda marcada como SUPERSEDIDA (no se reescribe el historial) |
| `.gitignore` | `*.patch` ignorado (B-2) |

## Documentación

| Archivo | Cambio |
|---|---|
| `Obsidian/Bitácora/2026-08-04.md` | Sección nueva con las salidas reales medidas; se conserva el texto original erróneo para que la corrección sea auditable |
| `Obsidian/Decisiones/Registro de decisiones.md` | Modelo principal actualizado con la revisión del mismo día |
| `Obsidian/Tareas.md` | Tarea nueva por las 54 filas servidas pendientes |
| `audit/latest/*` | Los 7 entregables regenerados (el contenido del 08-02 queda en el historial git) |

## No modificado deliberadamente

- **192 archivos que `ruff format` reformatearía** (I-1): el CI no ejecuta
  `ruff format`; sería un refactor cosmético masivo sin beneficio verificable.
- **`claude-loops-remediation-20260804.patch`**: no borrado. Es untracked, por
  tanto irrecuperable, y no fue creado en esta sesión.
- **Los 14 loops con "Reglas comunes" duplicado** (I-2/I-3): remediados hace
  horas; reescribirlos hoy es churn de alto riesgo. Ver `BACKLOG.md`.
- **Nada de riesgo:** `shadow_mode`, `pick_mode`, bankroll, stakes, límites de
  exposición, calibradores y modelos quedan exactamente como estaban.
