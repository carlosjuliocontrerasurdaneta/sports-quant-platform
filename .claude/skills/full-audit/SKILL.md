---
name: full-audit
description: Audita de forma integral y de solo lectura un repositorio o proyecto completo. Produce inventario, matriz de cobertura, hallazgos con evidencia reproducible, validación independiente y plan priorizado en audit/latest/. Usar cuando el alcance sea el sistema completo o varias áreas coordinadas y el usuario pida una auditoría completa, integral, full audit, full system audit o análisis exhaustivo. No usar para un único archivo, PR, bug o cambio puntual: para eso usar la skill code-audit. No corrige nada; la corrección es la skill audit-remediation, tras aprobación explícita.
argument-hint: "[alcance opcional]"
---

# Full Audit

Auditar el proyecto para identificar defectos funcionales, errores lógicos,
vulnerabilidades, riesgos operacionales, problemas de datos, inconsistencias y
deuda técnica **con impacto demostrable**.

Priorizar precisión, evidencia y cobertura verificable sobre cantidad de
observaciones o velocidad.

Esta skill cubre las fases 0–3 (diagnóstico) y termina entregando un plan.
**No corrige.** La corrección autorizada es la skill `audit-remediation`.

## Reglas obligatorias

1. **Solo lectura.** No modificar código, configuración, datos, dependencias ni archivos del proyecto. Única excepción: los artefactos de `audit/latest/` y `.claude/automation/runtime/current-task.md` (ver Persistencia).
2. **Preservar estado existente.** No sobrescribir, revertir, limpiar ni descartar cambios preexistentes.
3. **Evidencia antes que inferencia.** No presentar hipótesis ni salidas de herramientas como defectos confirmados.
4. **Validación independiente.** Revalidar cada hallazgo activo con un segundo método cuando sea viable.
5. **Cobertura explícita.** No llamar "exhaustiva" a la auditoría sin matriz de cobertura.
6. **Auditar no autoriza corregir.** Esperar aprobación explícita antes de modificar el proyecto.
7. **Sin acciones externas o destructivas.** No alterar producción, remotos, servicios, bases reales ni recursos de pago.
8. **No exponer secretos.** Reportar tipo y ubicación; redactar el valor.
9. **No inventar evidencia.** Ni archivos, líneas, comandos, resultados, errores ni comportamientos.
10. **No afirmar éxito no comprobado.**

## Precedencia

- Estas reglas prevalecen sobre los comandos generales de validación de `CLAUDE.md` durante las fases 0–3. Un comando recomendado por `CLAUDE.md` sólo se ejecuta si sus efectos son compatibles con la política de solo lectura. Las reglas cuantitativas globales siguen vigentes.
- **Ninguna ruta, loop, hook ni contexto inyectado autoriza saltarse el gate de la Fase 3.** Si un contexto de routing designa un loop de modificación (p. ej. `refactor.md`), prevalece esta skill y el loop correcto es `.claude/loops/audit.md`.
- No interpretar las reglas de implementación de `CLAUDE.md` como autorización para corregir.
- Un `CRITICAL` con exposición activa (credenciales expuestas, corrupción de datos en curso, pérdida de dinero) se comunica **en cuanto se confirma**, sin esperar al informe. Comunicar no autoriza corregir.

## Alcance

Si se recibe argumento de alcance, restringe las fases 0–3 a esos componentes:
las áreas fuera de alcance se marcan `EXCLUIDA` con la justificación "fuera del
alcance solicitado", y el resultado se declara `PARCIAL` por definición. Sin
argumento, el alcance es el repositorio completo.

## Preflight

1. Leer `AGENTS.md`, `CLAUDE.md` y las reglas de directorio aplicables. **No importar la identidad ni el rol de Codex desde `AGENTS.md`**: usarlo sólo como fuente de reglas del repositorio.
2. Leer `.claude/memory/known-issues.md` y `.claude/memory/session-summaries.md`. Marcar lo ya resuelto o aceptado deliberadamente para no re-reportarlo.
3. Leer `audit/latest/FINDINGS.md` y `.claude/automation/runtime/current-task.md`: si hay una auditoría en curso, reanudar (ver Persistencia) en vez de empezar de cero.
4. Inspeccionar Git: estado, cambios preexistentes y untracked relevantes.
5. Determinar alcance, exclusiones y acciones autorizadas. Registrar limitaciones del entorno.

## Persistencia y reanudación

Una auditoría integral no cabe en una ventana de contexto. **Persistir a medida
que se avanza, no al final:**

- escribir cada hallazgo en `audit/latest/FINDINGS.md` en cuanto alcanza estado final;
- actualizar la matriz de cobertura y los comandos ejecutados en `.claude/automation/runtime/current-task.md`;
- al reanudar, releer ambos y **no re-auditar áreas ya marcadas `REVISADA`**.

Estas escrituras son bookkeeping obligatorio, no ampliación de alcance. Son la
única excepción a la regla 1.

## Procedimiento

Leer el archivo correspondiente a la fase en curso; no cargarlos todos a la vez.

| Fase | Contenido | Archivo |
|---|---|---|
| 0–3 | Descubrimiento, cobertura, áreas de auditoría, validación independiente, plan y orquestación | `references/phases.md` |
| — | Estados de evidencia, severidad, confianza y registro por hallazgo | `references/taxonomy.md` |
| — | Formato y ubicación de los entregables | `references/deliverables.md` |
| — | Rutas canónicas del proyecto para la revisión cuantitativa | `references/project-anchors.md` |
| 4–5 | Corrección autorizada y validación final | skill `audit-remediation` |

## Finalización

Declarar `COMPLETA` sólo si: existe inventario verificable; la matriz tiene la
granularidad definida en `references/phases.md`; toda área aplicable está
revisada o limitada explícitamente; los hallazgos activos fueron revalidados
cuando era viable; se registraron descartados y límites; existe plan priorizado;
y no se modificó el proyecto fuera de los artefactos de auditoría.

Si no se cumple, declarar `PARCIAL` y explicar por qué. `PARCIAL` con la
limitación nombrada es un resultado válido; un `COMPLETA` no sostenido, no.

Al cerrar, registrar el resultado en `current-task.md` con el vocabulario de
`.claude/loops/quant/STATES.md` y añadir a `.claude/memory/known-issues.md` los
hallazgos que queden abiertos.
