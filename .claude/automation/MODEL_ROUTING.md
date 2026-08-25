# SQP Claude Code Model Routing

El enrutamiento tiene dos capas independientes:

1. `.claude/settings.json` selecciona el modelo de la conversación principal.
2. `UserPromptSubmit` clasifica la solicitud e inyecta una recomendación de loop y
   subagente. Cada subagente usa el modelo declarado en su frontmatter.

## PRINCIPIO RECTOR

> **Priorizar siempre el modelo superior para las tareas que requieran el máximo
> nivel de razonamiento, y delegar las demás en función de su complejidad y de
> las áreas en las que cada modelo ofrezca mejor rendimiento.**

Orden de decisión del operador (2026-08-25). **Gobierna toda esta política**: si
alguna regla concreta de abajo entra en conflicto con él, manda el principio y la
regla se corrige, no al revés.

Consecuencias vinculantes:

- La pregunta correcta ante una tarea **no** es "¿cuál es el modelo más barato
  que probablemente baste?" sino **"¿cuánto razonamiento exige de verdad?"**. El
  coste es una restricción, no el criterio.
- Ante la duda entre dos escalones en una tarea de razonamiento alto, **se sube**.
  Infra-asignar el modelo en trabajo cuantitativo crítico —calibración, detección
  de fuga, diseño de experimentos, decisiones de riesgo— sale más caro que el
  modelo, porque el error entra en producción y contamina las cifras con las que
  se decide.
- Delegar hacia abajo es legítimo y esperado **cuando la tarea lo es**: lookups
  acotados, resúmenes, extracción mecánica y trabajo repetitivo bien definido.
- Jerarquía de capacidad vigente en este proyecto:
  `claude-fable-5` > `claude-opus-5` > `sonnet` > `haiku`.
- Un modelo inferior **no deshace ni renegocia** trabajo o decisiones producidas
  por uno superior. Si detecta un problema, lo **reporta**; no lo revierte por
  iniciativa propia.

## Política autorizada

- **Conversación principal:** `claude-fable-5`, por decisión humana explícita del
  2026-08-24. Supersede a `sonnet` (2026-08-18), que había superseduo a
  `claude-opus-5` (2026-08-04) y este a `claude-fable-5` ese mismo día. Afecta solo
  al modelo interactivo de `settings.json`; el escalón de las rutas sigue en
  `sonnet` para el trabajo normal (abajo). El hook no debe afirmar que cambia este
  modelo.
- **Escalón de las rutas** (`model-routing.json`), el lever de coste:
  - `opus` — **solo** `full-audit`, `incident` y `quant-incident`: auditorías
    exhaustivas e incidentes críticos.
  - `haiku` — **solo** `documentation`: consulta y resumen acotados.
  - `sonnet` — todo lo demás, incluida la ruta `default`. Es el trabajo normal:
    modelado, calibración, backtesting, arquitectura, providers, bugfix,
    seguridad y release.
- **Frontmatter de subagentes:** política **independiente y sin cambios**. Un
  subagente declara `opus` o `haiku`, nunca `sonnet`: cuando se delega
  explícitamente a un especialista es porque el trabajo lo justifica. La ruta
  puede pasar un modelo que tiene precedencia sobre el frontmatter (ver abajo).

Una variable `CLAUDE_CODE_SUBAGENT_MODEL` o un modelo indicado explícitamente al
invocar un subagente puede tener precedencia sobre su frontmatter. Esa excepción
debe registrarse en `current-task.md`.

Este archivo es la fuente única de la política de modelos. `ORCHESTRATOR.md` y
`decision-engine.md` enlazan aquí en lugar de repetirla. Cambiar el modelo
principal o la política de subagentes requiere aprobación humana explícita y una
actualización deliberada de las pruebas de routing.

La clasificación por palabras clave es una ayuda determinista. El decision
engine, la semántica real de la solicitud y las reglas permanentes conservan
precedencia.
