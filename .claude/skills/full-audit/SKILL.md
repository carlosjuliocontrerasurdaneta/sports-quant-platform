---
name: full-audit
description: >
  Auditar exhaustivamente repositorios y proyectos de software sin modificar archivos
  durante el diagnóstico. Usar cuando el usuario solicite una auditoría completa,
  revisión integral, full audit, full system audit, detección general de bugs, riesgos,
  vulnerabilidades, problemas de arquitectura, dependencias, configuración, pruebas,
  scripts, datos, modelos cuantitativos, integraciones externas o sistemas de Skills e
  instrucciones del proyecto. Inventariar primero
  el proyecto, documentar evidencia reproducible, validar de forma independiente cada
  candidato, clasificar los hallazgos por severidad, confianza y estado de evidencia,
  preparar un plan de corrección y esperar aprobación explícita antes de implementar
  cualquier cambio. La activación de esta skill autoriza únicamente diagnóstico,
  validación y planificación; nunca autoriza por sí sola la modificación de archivos.
---

# Full Audit

Entrada para diagnóstico integral. La activación autoriza diagnóstico, validación
y planificación; la implementación es una fase separada y necesita alcance
autorizado por el usuario. No editar código durante la auditoría.

## Procedimiento canónico

Leer [el contrato de auditoría](../../automation/audit-workflow.md): secciones
«Autoridad, alcance y evidencia», «Contrato de hallazgos», «Rondas, archivos y
compatibilidad» y «Diagnóstico independiente». Allí viven los IDs, evidencia,
severidad, resultados, autorización, entregables y compatibilidad legacy.
No redefinir esas reglas aquí ni en los prompts generados.

## Carga progresiva

Antes de cada fase, cargar la referencia correspondiente:

| Cuándo | Referencia |
|---|---|
| Siempre: inventario y cobertura | [discovery-coverage.md](references/discovery-coverage.md) |
| Inspección del stack detectado | [audit-areas.md](references/audit-areas.md) |
| Skills, prompts, routing o loops | [skills-instructions.md](references/skills-instructions.md) |
| Limpieza y compatibilidad | [repository-cleanup.md](references/repository-cleanup.md) |
| Modelos, calibración o backtesting | [quant-ml.md](references/quant-ml.md) |
| Especialistas autorizados y útiles | [orchestration.md](references/orchestration.md) |

Inventariar primero; cada área debe quedar revisada, parcial, no aplicable,
no verificable o excluida con motivo. No ejecutar comandos indiscriminadamente
para aparentar exhaustividad. No asumir que un agente existe por estar nombrado.

## Ejecución y entrega

1. Inspeccionar Git y preservar cambios preexistentes. Aplicar el loop
   `.claude/loops/audit.md` como entrada operacional al mismo contrato.
2. Revisar con independencia y buscar controles/contraejemplos antes de confirmar.
3. Guardar el informe individual en el subdirectorio del auditor de la ronda.
4. Si esta invocación debe producir el backlog final, ejecutar la fase
   «Consolidación independiente» del contrato una vez cerrado el diagnóstico.
   Con un solo auditor, declarar la ausencia de segunda opinión. Entregar
   `audit/latest/FINDINGS.md`, `BACKLOG.md` y `MANIFEST.json`.
5. Proponer correcciones por ID y terminar el diagnóstico. Si el usuario autoriza
   implementar, continuar con `audit-remediation` bajo ese alcance.

Conservar rondas anteriores antes de reemplazar entregables, según el contrato.
Durante diagnóstico no ejecutar bookkeeping que escriba fuera de sus destinos
autorizados; registrar la limitación. Auditoría completa no significa código
corregido, pruebas no ejecutadas aprobadas ni ventaja predictiva demostrada.
