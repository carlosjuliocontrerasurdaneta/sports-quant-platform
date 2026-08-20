# Queda prohibido borrar o editar este archivo sin autorización expresa.


# Integración Claude ↔ Codex en este proyecto

---

## ¿Qué es la integración?

Claude y Codex son dos instancias de modelos distintos que actúan como **revisores independientes** del mismo cambio de código. El sistema garantiza que ninguno puede aprobar un cambio sin que el otro lo haya revisado sobre exactamente el mismo árbol de trabajo.

La integración NO es Claude llamando a Codex para que implemente código (eso es el flujo Opus→Codex manual). La integración formal es el **Cross Review Protocol V2** (`scripts/ai/`): dos revisores, dos veredictos, un consenso.

---

## Forma 1: Flujo manual de implementación (Opus → Codex)

```
Opus: PLAN.md  →  Codex implementa  →  Sonnet revisa  →  commit
```

**Quién hace qué:**

| Actor | Rol | Herramienta |
|---|---|---|
| Claude (Opus) | Decide qué cambiar, escribe el plan | Escribe `PLAN.md` |
| Codex | Ejecuta los cambios en los archivos | `mcp__codex__codex` |
| Claude (Sonnet) | Lee el diff y verifica | Lee `REVIEW.md` |

**Notas:**
- `PLAN.md` y `REVIEW.md` son artefactos **temporales y sin versionar** — se sobrescriben cada ciclo. Cerrar el ciclo anterior antes de escribir uno nuevo.
- Codex opera en el mismo worktree local; no tiene acceso a secretos ni a servicios de pago.
- Claude (Sonnet) nunca aprueba un cambio sin leer el diff real.

---

## Forma 2: Cross Review Protocol V2 (revisión formal)

```
Claude revisa el diff  +  Codex revisa el mismo diff  →  consenso JSON
```

**Flujo:**
1. El launcher congela el árbol de revisión (`review_tree`) en un snapshot inmutable.
2. Claude y Codex reciben exactamente el mismo snapshot — ninguno ve el árbol en vivo.
3. Cada revisor emite un veredicto JSON: `APPROVE`, `REQUEST_CHANGES`, o `BLOCK`.
4. El launcher corre `pytest`/`ruff`/`mypy` y estampa los resultados reales en el JSON — un revisor no puede declarar tests pasados si no pasaron.
5. El consenso requiere que ambos aprueben; uno solo no es suficiente.

**Cuándo usarlo:** cambios de riesgo medio-alto — nuevos modelos, cambios de calibración, modificaciones al pipeline de predicción.

**Cómo invocarlo:** `/cross-review` o el skill `cross-review`.

---

## Configuración que puedes cambiar

| Qué | Dónde | Cómo |
|---|---|---|
| Modelo activo del proyecto | `.claude/settings.json` → `"model"` | Edit directo o `/model opus` en sesión |
| Modelo global por defecto | `~/.claude/settings.json` | Edit directo |
| Permisos de comandos | `.claude/settings.json` → `permissions.allow/deny` | Edit directo o skill `update-config` |
| Skills del proyecto | `.claude/skills/<nombre>/SKILL.md` | Crear/editar archivos markdown |
| Hooks automáticos | `.claude/settings.json` → `hooks` | Edit directo o skill `update-config` |
| Loops operacionales | `.claude/loops/` y `.claude/loops/quant/` | Editar los `.md` correspondientes |
| Backlog autónomo | `.claude/automation/backlog.md` | Añadir filas con status `ready` |
| Política de autonomía | `.claude/automation/autonomy-policy.md` | Editar con cuidado — rige lo que Claude puede hacer sin aprobación |

---

## Cuándo usar cada forma

| Situación | Forma recomendada |
|---|---|
| Implementar un feature planificado | Forma 1 (Opus→Codex) |
| Corregir un bug menor | Claude solo (Sonnet) |
| Cambio en calibración o modelo | Forma 2 (Cross Review) |
| Auditoría completa del sistema | `/full-audit` con subagentes especializados |
| Incidente en producción | Skill `quant-incident` → aprobación humana |

---

## Flujo Opus → Codex paso a paso

1. Abre una sesión con Claude (Opus recomendado para el plan).
2. Claude escribe `PLAN.md` con las tareas numeradas.
3. Dile a Codex: *"implementa el plan en PLAN.md"*.
4. Codex modifica los archivos; escribe `REVIEW.md` con el resumen.
5. Claude (Sonnet) lee `REVIEW.md` y el diff real (`git diff`).
6. Si está conforme, Claude hace el commit (requiere aprobación explícita).
7. Borra `PLAN.md` y `REVIEW.md` al cerrar el ciclo.
