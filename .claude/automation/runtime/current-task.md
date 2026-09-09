# Current Task

Status: closed
Result: VERIFICADO — pendiente de aprobación para commit
Primary loop: `bugfix.md`
Skills: `bugfix`
Iteration: 1 / 1
Owner: sesión principal (`claude-opus-5`), sin delegación
Date: 2026-09-09

## Routing

Sin escalón a `claude-fable-5-1`. La clase observable no lo pide: no es trabajo
irreversible, no toca parámetros de riesgo/modelo/estrategia/umbral/gate, no
produce cifras publicables, no contradice ninguna decisión registrada y no
cambia el contrato de ningún artefacto persistido. Es la resolución de un
binario en un lanzador, reversible y cubierta por pruebas.

## Objective

Eliminar la divergencia entre los dos binarios de Codex que usan las dos mitades
de la revisión cruzada: `codex_command()` fijaba `%APPDATA%\npm\codex.cmd`
mientras `crossreview-on-stop.sh` resuelve `codex` por PATH.

## Estado

| Paso del loop | Estado |
|---|---|
| 1. Reproducir el defecto | HECHO — 0.147.0 (lanzador) contra 0.153.4 (hook), mismo repo |
| 2. Causa raíz, no síntoma | HECHO — pin de `8907fcb` (2026-08-13) + `codex_command()` sin ninguna prueba |
| 3. Hipótesis e invariante | HECHO — invariante: las dos vías resuelven el MISMO binario |
| 4. Corrección mínima | HECHO — PATH primero, shim de npm como respaldo |
| 5. Rojo antes / verde después | HECHO — 6 de 7 en rojo por la razón correcta; 7/7 en verde |
| 6. Regresión adyacente | HECHO — 378 pasados / 1 saltado / exit 0 (13:13); ruff y mypy en verde |
| 7. ¿Afecta datos/liquidación/cuotas/probabilidades? | NO — solo qué binario se lanza para revisar |
| 8. `/verification-gate` | HECHO — 10/10; se detiene antes del commit, que requiere aprobación |

## Ficheros tocados

- `scripts/ai/codex_review.py` — `codex_command(windows: bool | None = None)`
- `tests/test_codex_review.py` — 7 pruebas nuevas, una fija la CLASE
- `docs/CLAUDE-CODEX-INTEGRATION.md` — el párrafo del binario ya no miente
- `.claude/memory/known-issues.md` — `KI-046`
- `Obsidian/Bitácora/2026-09-09.md` — bitácora de la sesión

## Nota

`scripts/ai/` NO está en el ámbito vigilado por `mark-crossreview-pending.sh`
(`configs/`, `src/sqp/risk/`, `src/sqp/calibration/`), así que este cambio —que
toca la infraestructura de la propia revisión cruzada— no dispara la revisión
cruzada. Queda señalado, no cambiado: ampliar el ámbito es gasto de cuota
recurrente y es decisión del operador.
