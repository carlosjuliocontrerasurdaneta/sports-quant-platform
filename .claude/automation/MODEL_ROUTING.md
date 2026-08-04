# SQP Claude Code Model Routing

El enrutamiento tiene dos capas independientes:

1. `.claude/settings.json` selecciona el modelo de la conversación principal.
2. `UserPromptSubmit` clasifica la solicitud e inyecta una recomendación de loop y
   subagente. Cada subagente usa el modelo declarado en su frontmatter.

## Política autorizada

- **Conversación principal:** `claude-fable-5`, por decisión humana explícita del
  2026-08-04. El hook no debe afirmar que cambia este modelo.
- **Subagentes Opus:** auditorías, arquitectura, modelado, calibración, leakage,
  backtesting, riesgo, implementación, datos, providers, QA, seguridad, DevOps y
  especialistas deportivos.
- **Subagente Haiku:** documentación estrictamente limitada.

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
