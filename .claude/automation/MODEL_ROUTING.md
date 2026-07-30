# SQP Claude Code Model Routing

El enrutamiento tiene dos capas:

1. `UserPromptSubmit` clasifica la solicitud e inyecta una recomendación de loop y subagente.
2. Cada subagente declara su modelo en el frontmatter (`opus` o `haiku`).

El hook no cambia el modelo de la conversación principal. Claude Code delega la tarea al subagente y este usa su modelo declarado. Una variable `CLAUDE_CODE_SUBAGENT_MODEL` o un modelo indicado en la invocación puede tener precedencia sobre el frontmatter.

## Política

Este archivo es la **fuente única** de la política de modelos. `ORCHESTRATOR.md`
y `decision-engine.md` enlazan aquí en lugar de repetirla (auditoría 2026-07-29,
K-014: estaba escrita tres veces y ya divergía).

- **Opus:** auditorías integrales, arquitectura, modelado, calibración, leakage,
  backtesting, riesgo, implementación, datos, providers, QA, seguridad, DevOps y
  especialistas deportivos.
- **Haiku:** documentación estrictamente limitada.

**Fable no se usa: la cuenta no tiene créditos de Fable 5.** Estaba asignado a 5
rutas y 10 agentes —precisamente los más críticos: auditoría, modelado,
calibración, backtesting y riesgo— y esos subagentes fallaban al arrancar sin
fallback (auditoría 2026-07-29, K-004). `tests/test_claude_model_routing.py`
impide que vuelva a entrar. Para reactivarlo hacen falta créditos y revertir esa
prueba de forma deliberada.

La clasificación por palabras clave es una ayuda determinista; el decision engine y las reglas permanentes conservan precedencia.
