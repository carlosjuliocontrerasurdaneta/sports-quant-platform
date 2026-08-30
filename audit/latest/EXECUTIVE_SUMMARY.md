# Resumen ejecutivo — Auditoría integral 2026-08-30

Sustituye el contenido de `audit/latest/` de la auditoría del 2026-08-04, que
era el último informe persistido pese a que entre medias hubo al menos una
auditoría más (2026-08-29) que no dejó artefactos.

## Alcance y método

Repositorio completo: 588 archivos trackeados, 275 módulos Python, 44.072 líneas.
179 commits desde la última auditoría con informe. Fases 0–3 en solo lectura
según la skill `full-audit`; fase 4 sólo tras la autorización explícita del
operador para "los hallazgos confirmados".

**Resultado de cobertura: `PARCIAL`.** Se declara así, y no `COMPLETA`, porque
los gates de riesgo y el pipeline diario no recibieron la lectura línea a línea
que el procedimiento exige para marcar un área `REVISADA`. Inflar la cobertura
habría sido el fallo más caro de esta auditoría.

## Estado del proyecto

El repositorio está en buena forma estructural. `ruff` limpio sobre `src`,
`scripts` y `tests`; `mypy` sin incidencias en 98 archivos; `pip check` sin
dependencias rotas; ningún secreto versionado; ninguna petición HTTP sin
timeout; health check en `WARN` por una advertencia conocida y declarada no
accionable.

La defensa contra el fallo cuantitativo más grave que este proyecto ha sufrido
—un calibrador colapsado sirviendo en producción— está construida, unificada en
una sola definición y cableada en las tres puertas donde importa: promoción,
tablero y registro live. Se verificó la cadena completa hasta el run diario.

## Hallazgos

| ID | Severidad | Estado | Resultado |
|---|---|---|---|
| A-1 | ALTO | `REPRODUCIDO` | **Corregido y verificado** |
| M-1 | MEDIO | `VERIFICADO_ESTATICAMENTE` | **Corregido** (causa raíz + documentación) |
| B-1 | BAJO | `INFERIDO` | No corregido por decisión: sin evidencia observada |
| I-1 | INFORMATIVO | `VERIFICADO_ESTATICAMENTE` | Requiere decisión humana |
| I-2 | INFORMATIVO | `VERIFICADO_ESTATICAMENTE` | Sin acción: cambio deliberado |

El hallazgo con más consecuencia, **A-1, lo introduje yo el día anterior**. Al
reestructurar la skill `full-audit` creé `.claude/loops/audit.md` con
guardarraíles redactados a medida en lugar del bloque canónico, y no ejecuté la
suite completa después. Dos tests de contrato llevaban un día en rojo. La
lección no es sobre el archivo: es que la reestructuración se validó con los
tests que parecían relevantes (`test_claude_model_routing.py`) en vez de con la
suite, y el contrato que se rompió vivía en otro archivo.

**M-1** es el motivo por el que ese día en rojo pudo pasar inadvertido: la
auditoría del 2026-08-29 corrigió cinco hallazgos (`AUD-HIGH-001`,
`AUD-MED-002`, `AUD-LOW-001/002/003`) sin dejar informe. Existen los arreglos en
`git log`, no la evidencia ni la línea base. Este directorio es la corrección.

## Riesgos pendientes

1. **La política de modelo está aplicada a medias** y deja la suite con un fallo
   permanente. Es lo único que exige decisión del operador. Detalle en
   `BACKLOG.md` D-1 y en `known-issues.md` KI-021.
2. **Los gates de riesgo no se auditaron completos.** Con `shadow_mode: false`
   el sistema dimensiona stakes reales, así que son el código con más
   consecuencia directa sobre el capital. Primera prioridad de la próxima
   auditoría (`BACKLOG.md` P-1).
3. **`pip-audit` no se ejecutó** (no instalado; instalarlo es modificar
   dependencias, prohibido en diagnóstico). La última corrida limpia fue hace
   179 commits.

## Lo que esta auditoría NO establece

No se midió hit rate observado frente a prometido, ni ROI esperado frente a
realizado, ni CLV, ni calibración sobre datos nuevos. **No hay ventaja
predictiva demostrada.** Una suite verde y un calibrador defendido significan
que el sistema está sano como software, no que gane dinero.
