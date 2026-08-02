# Revisión de Claude Code y Quant Loops — Auditoría 2026-08-02

La revisión estructural completa se hizo el 2026-07-29/30 (historial git de
este archivo) y su remediación sigue vigente. Esta pasada verifica el estado
actual pieza por pieza.

## Arquitectura de `.claude` — estado verificado

| Pieza | Estado 2026-08-02 |
|---|---|
| `CLAUDE.md` (raíz + `.claude/`) | Coherentes entre sí y con la realidad del repo |
| `ORCHESTRATOR.md` | Tabla de ruteo apunta a loops que existen; agentes referenciados existen en `.claude/agents/` |
| `automation/decision-engine.md` | 23 reglas ordenadas, sin contradicciones con el orquestador |
| `automation/autonomy-policy.md` | Consistente con los límites del operador (commit/push/promoción/riesgo = aprobación humana; shadow explícito desde K-009) |
| `automation/runtime/current-task.md` | **Corregido (M-02):** decía "in-progress" para la auditoría 07-29 cerrada el 07-31 — tarea zombi. Ahora refleja el estado real |
| Loops genéricos (10) | Versionados, referenciados por el router |
| Quant Loops (13 + STATES.md) | Versionados; `STATES.md` es fuente única de PASS/DEGRADED/BLOCKED/DONE con condiciones observables y umbrales de muestra anclados al código (fix K-003 de la auditoría anterior, verificado vigente) |
| Router quant (`00-…router.md`) | Las 13 rutas existen; reglas comunes centralizadas (sin duplicación) |
| Comandos (16) | Existen; `/memoria-cargar` y `/full-audit` ejecutados esta sesión |
| Hooks (`settings.json`) | PostToolUse/Stop/UserPromptSubmit activos; check-secrets verificado por su prueba documentada |
| Permisos | deny protege `data/`, `.env`, `git reset --hard`; `git push` fuera de deny por decisión 2026-07-31 |
| Memoria (`.claude/memory/`) | `roadmap.md` **corregido (B-02)**: enlaces muertos a docs borrados en `f43ba00` retirados. known-issues y project-decisions al día (decisión 2026-08-02 añadida) |
| Skills | 20+ del proyecto + plugins; sin colisiones nuevas detectadas |

## Contradicciones encontradas y resueltas

1. **Documentación vs configuración (A-01):** README/Obsidian/memoria decían
   `accuracy` activo; `configs/default.yaml` dice `edge`. Resuelto a favor de
   la realidad (config + commit `f6c2130`).
2. **current-task vs realidad (M-02):** tarea in-progress ya cerrada. Resuelto.
3. **roadmap.md vs docs/ (B-02):** índice apuntando a archivos borrados.
   Resuelto.

## Clasificador automático (UserPromptSubmit)

El hook clasificó esta solicitud como `modeling → model.md → ml-engineer`; la
semántica real era auditoría integral (→ `/full-audit`). La propia instrucción
del hook prevé la discrepancia ("confirma la semántica"), y así se operó. No es
defecto; queda anotado como limitación conocida del clasificador determinista.

## Evaluación de autonomía

Los límites siguen correctos tras la directiva del objetivo sacrosanto: el
policy exige aprobación humana para desactivar shadow, mover stakes, promover
modelos o publicar — todos controles que PROTEGEN el capital, no que
contravienen el fin de ganar dinero. No se modificó ninguno.

## Mejoras pendientes (backlog)

- M-7 (07-24): recortar permisos amplios de `settings.local.json` (archivo
  local del usuario; decisión manual).
- Considerar un check automático (health o hook) que compare
  `configs/default.yaml:picks.mode` contra lo que afirman README/Estado del
  proyecto, para que una brecha tipo A-01 no vuelva a pasar desapercibida.
