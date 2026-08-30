# Archivos modificados — Auditoría 2026-08-30

Sin commit (pendiente de autorización). Estado exacto: `git status --short`.

## Corregido

### A-1 · `.claude/loops/audit.md`

Cambio: se restauró bajo `## Common guardrails` el bloque canónico literal de 5
viñetas que comparten los otros 10 loops, se movieron las restricciones
específicas del diagnóstico a una sección propia (`## Restricciones propias del
diagnóstico`), y se añadió `8. Finish through /verification-gate.` como paso de
cierre.

La sección propia es necesaria porque el contrato exige identidad byte a byte
del bloque canónico, y ese bloque incluye "Prefer the smallest reversible
change", que en un loop de solo lectura podría leerse como permiso para cambiar
algo. La sección nueva lo desambigua explícitamente: durante el diagnóstico el
cambio correcto es ninguno.

Verificación: `pytest tests/test_claude_system_contract.py -q` → 15 passed
(código 0), y extracción programática → 1 bloque distinto sobre 11 loops, 0
archivos sin `/verification-gate`.

### M-1 (parte documental) · `.claude/skills/full-audit/references/taxonomy.md`

Cambio: se añadió la tabla de equivalencia entre el esquema histórico
`AUD-<NIVEL>-NNN` (usado por la auditoría del 2026-08-29, que no persistió
informe) y el esquema vigente `C/A/M/B`, más la regla de que un ID citado en un
commit debe poder resolverse contra un informe.

La otra mitad de M-1 —la ausencia de informe— se corrige por construcción: este
directorio `audit/latest/` es el artefacto que faltaba.

## Efecto del hook de formato

Ninguno. El hook `PostToolUse` ejecuta `ruff check --fix`, que sólo actúa sobre
Python; los dos archivos modificados son Markdown. El diff es exactamente el
parche, sin autofixes añadidos.

## Lo que se decidió NO tocar

| Qué | Por qué |
|---|---|
| `B-1` (revalidación del registro live con historial vacío) | `INFERIDO`, confianza BAJA, no observado. La instrucción era aplicar sólo mejoras sustentadas por evidencia de la auditoría; ésta se sostiene en lectura del flujo de control, no en un caso reproducido. |
| `I-1` / `.claude/settings.json`, `.claude/automation/MODEL_ROUTING.md`, el literal de `test_claude_model_routing.py` | El árbol contiene un cambio deliberado a medias: `settings.json` y `docs/MODEL-ROUTING.md` ya declaran Opus 5, el literal del test y `MODEL_ROUTING.md` siguen en Fable 5. Completarlo exige decidir cuál es la política real, que es una decisión del operador. El test es un candado de coste que existe para forzar esa decisión; cerrarlo yo lo anularía. |
| `README.md`, `docs/MODEL-ROUTING.md` | Modificaciones preexistentes en el árbol al abrir esta auditoría, ajenas a ella. Regla 2: preservar el estado existente. |
| `NOTAS.md`, `auditoria-integral-codex.md` | Untracked y ajenos al alcance. No se tocan ni se borran. |
| Parámetros de riesgo, `shadow_mode`, `pick_mode`, promoción de modelos | Exigen aprobación humana separada. Ningún hallazgo la requería. |

## Incidente y restauración (posterior a la corrección)

Al revisar el diff final se detectó que `.claude/skills/full-audit/` había
cambiado durante la sesión sin intervención de esta auditoría:

- **09:00:54** — `SKILL.md` reemplazado por una versión de 713 líneas (monolito
  con fases 0–5, sin mención de `audit-remediation` ni de `audit/latest/`, y con
  el frontmatter mal formado: la línea 5 cerraba con 633 guiones en vez de `---`).
- **09:36:41** — el directorio `references/` borrado. Era untracked, así que git
  no podía recuperarlo.

Esto dejaba el sistema incoherente: `model-routing.json` manda `full-audit` a
`audit.md`, que delega en `audit-remediation`, pero el `SKILL.md` instalado no
conocía ninguno de los dos.

Carlos decidió restaurar la versión reestructurada. Antes de sobrescribir, la
versión de 713 líneas —sin commitear, por tanto irrecuperable— se preservó en
`audit/full-audit-SKILL-reemplazado-2026-08-30.md`.

Restaurados desde el contenido de la sesión: `SKILL.md` (91 líneas) y los cuatro
archivos de `references/`. Verificado: frontmatter válido en ambas skills, todas
las referencias con ruta resuelven, y
`pytest tests/test_claude_system_contract.py tests/test_claude_model_routing.py -q`
→ 26 passed, 1 failed (sólo el preexistente I-1/KI-021).

### Mejoras incorporadas en la restauración

Tres, todas sustentadas por evidencia de esta misma auditoría y no por
preferencia:

1. `references/phases.md`, Fase 2: regla nueva de que una búsqueda que no
   encuentra algo no es evidencia de que no exista, con la instrucción de
   repetirla sin filtros —incluida la exclusión del módulo que define el
   símbolo— antes de reportar código muerto. Origen: el falso positivo `ALTO`
   sobre `revalidate_live_registry()` documentado en `FINDINGS.md`.
2. `references/deliverables.md`: prohibición explícita de escribir en
   `VALIDATION.md` o `MANIFEST.json` el resultado de un comando que aún corre.
   Origen: en esta auditoría escribí "1 failed, 1377 passed" mientras la suite
   seguía en ejecución y tuve que corregirlo a `NO_EJECUTADA`.
3. `references/project-anchors.md`: entrada para
   `tests/test_claude_system_contract.py` y `tests/test_claude_model_routing.py`
   como lectura obligada antes de tocar `.claude/`. Origen: `A-1`.
