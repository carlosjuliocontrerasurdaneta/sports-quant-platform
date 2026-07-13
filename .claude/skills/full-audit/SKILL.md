---
name: full-audit
description: Realizar auditorías exhaustivas del proyecto, identificar errores, clasificarlos por severidad y proponer correcciones seguras antes de modificar código. Absorbe el antiguo comando /full-system-audit (auditoría orquestada con subagentes especialistas).
---

# Full Audit

Objetivo:
Analizar exhaustivamente el proyecto para detectar errores funcionales, riesgos de ejecución, deuda técnica, inconsistencias y posibles bugs.

## Fase 1 - Auditoría

Analizar:

- Arquitectura
- Scripts BAT
- Código Python
- Configuración
- Tests
- Dependencias
- Integraciones externas

Identificar:

- Bugs
- Errores lógicos
- Excepciones potenciales
- Dependencias rotas
- Código muerto
- Duplicación
- Problemas de rendimiento
- Riesgos de datos
- Riesgos operacionales

Para cada hallazgo entregar:

- Severidad
  - Crítico
  - Importante
  - Menor

- Archivo(s) afectados

- Evidencia

- Impacto

- Solución propuesta

- Nivel de confianza
  - Alto
  - Medio
  - Bajo

## Fase 2 - Validación

Revisar nuevamente todos los hallazgos.

Eliminar posibles falsos positivos.

Indicar cuáles están confirmados.

## Fase 3 - Plan de corrección

Generar un plan ordenado por prioridad.

Agrupar:

1. Bugs críticos
2. Bugs importantes
3. Deuda técnica
4. Mejoras opcionales

NO modificar archivos todavía.

Esperar aprobación.

## Fase 4 - Corrección

Corregir únicamente los elementos aprobados.

Antes de modificar:

- Mostrar archivos afectados
- Mostrar plan de cambios

Mantener:

- Lógica de negocio
- Comportamiento funcional
- Configuración existente

Salvo indicación explícita.

## Fase 5 - Validación final

Ejecutar:

- Tests afectados
- Validaciones necesarias

Entregar:

- Cambios realizados
- Resultado de pruebas
- Riesgos pendientes

## Modo orquestado (antiguo /full-system-audit)

Si la auditoría abarca todo el sistema (o el usuario pide "full system audit"),
ejecutar la Fase 1 vía `principal-orchestrator` delegando en los especialistas:

- repository-cartographer, backend-architect, data-engineer
- feature-engineer, leakage-detector, ml-engineer
- calibration-auditor, backtest-reviewer, odds-market-auditor
- risk-manager, qa-engineer, security-reviewer

Salida consolidada: Executive Summary, Critical Findings, High/Medium Risks,
Required Fixes, Validation Commands, Prioritized Roadmap. Las Fases 2–5
(validación, plan, corrección aprobada, validación final) aplican igual.

## Restricciones

No modificar archivos automáticamente durante la auditoría.

No realizar refactorizaciones masivas sin aprobación.

No cambiar modelos, estrategias o criterios de negocio sin autorización explícita.

Priorizar precisión sobre velocidad.

Documentar toda modificación relevante.