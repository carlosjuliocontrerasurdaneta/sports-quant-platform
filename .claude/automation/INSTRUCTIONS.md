# Mantenimiento de instrucciones

## Fuentes y consumidores

| Responsabilidad | Fuente editable | Consumidores |
|---|---|---|
| Autoridad del repositorio | `AGENTS.md`, `CLAUDE.md` | Todos los flujos; prevalecen sobre los procedimientos |
| Auditoría, consolidación, remediación, verificación y formato de ronda | `audit-workflow.md` | Skills full-audit/code-audit/audit-remediation, loop audit y prompts generados |
| Investigación especializada | `../skills/full-audit/references/` | Solo el área que se esté revisando |
| Routing y especialistas | `model-routing.json` | `route_classifier.py`, tablas generadas de decision-engine/ORCHESTRATOR/router quant |
| Política de modelos | `MODEL_ROUTING.md` | Selección de modelos; no se redefine en tablas |
| Guardarraíles de loops | `loop-guardrails.md` | Bloques expandidos de los 25 loops ejecutables |
| Procedimiento de dominio | `../loops/` | Skills delgadas y router |
| Inspección operacional | `../skills/daily-operations/SKILL.md` | Operaciones generales y alias mlb-pipeline |

Los cinco archivos en `audits/prompts/` conservan sus nombres como entradas
compatibles. Son documentos autónomos generados (incluyen reglas comunes y su
fase); no mantenerlos manualmente. Su nombre histórico no cambia el modelo activo.

## Cambio y validación

1. Editar la fuente de la tabla, preservando alcance y autorizaciones.
2. Ejecutar `python scripts/sync_agent_instructions.py --write`.
3. Ejecutar `python scripts/sync_agent_instructions.py --check` y las pruebas
   `tests/test_agent_instruction_sync.py`, `tests/test_claude_system_contract.py`
   y `tests/test_claude_model_routing.py` con el basetemp de `AGENTS.md`.
4. Revisar el diff, incluyendo vistas generadas, y documentar cambios de contratos.

`--check` es de solo lectura y falla si hay deriva. El generador no mueve ni
actualiza informes, históricos, modelos, datos productivos o configuración de
riesgo. El catálogo JSON conserva las prioridades y modelos existentes; la
clasificación por keywords sigue siendo orientativa, no una autorización.

## Compatibilidad y retirada

- Las 15 skills delgadas conservan sus nombres: son accesos a loops, no copias
  del procedimiento. No hay objetivo artificial de reducir su número.
- `mlb-pipeline` conserva un alias; no mantiene un flujo paralelo.
- Las referencias antiguas evidence-findings/validation-remediation/reporting
  apuntan al contrato común. Así los consumidores previos no quedan rotos.
- Los ocho punteros de memoria persistente siguen siendo compatibilidad histórica.
  No hay evidencia suficiente de todos los consumidores externos para eliminarlos.
- Los informes `audits/*` anteriores se conservan sin alteraciones; el contrato
  documenta cómo continuar sus IDs desde una ronda nueva en `audit/latest/`.

Antes de retirar un alias/puntero, verificar invocaciones documentadas, referencias,
carga dinámica y consumidores externos conocidos, actualizar sus callers y probar
la nueva ruta. Si no puede establecerse compatibilidad, conservarlo o documentar
la limitación. Reducir reglas editadas por duplicado prima sobre borrar archivos.
