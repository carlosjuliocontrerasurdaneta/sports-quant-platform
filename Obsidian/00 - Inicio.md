---
tags: [moc, sqp]
creada: 2026-07-08
actualizada: 2026-07-08
---

# 🧠 Sports Quant Platform — Segundo cerebro

Bóveda central de conocimiento del proyecto. **Toda modificación relevante del sistema debe reflejarse aquí** (regla en `CLAUDE.md`): una entrada en la [[Bitácora]] del día + actualización de las notas afectadas.

> Lenguaje obligatorio: siempre **probabilidad estimada**, nunca certezas ni profit garantizado. Separar probabilidad estimada / implícita / edge / ROI esperado estimado / ROI realizado.

## Mapa de la bóveda

### Estado y operación
- [[Estado del proyecto]] — snapshot vivo: modo operativo, balance, gates activos
- [[Objetivos y requisitos]] — qué persigue el sistema y bajo qué restricciones
- [[Tareas]] — pendientes activos y su prioridad
- [[Arquitectura/Automatización y operación]] — BATs, Task Scheduler, orden settle→run

### Conocimiento técnico
- [[Arquitectura/Arquitectura del sistema]] — módulos, flujo de datos, entrypoints
- [[Conocimiento/Calibración]] — staging/promoción, gates, mismatch train/serve
- [[Conocimiento/CLV y selección adversa]] — la métrica de gating y el gate por mercado
- [[Conocimiento/Señales por deporte]] — qué señales existen, cuáles están ON/OFF y por qué
- [[Conocimiento/Validación OOS]] — metodología y resultados por liga

### Historia y aprendizaje
- [[Decisiones/Registro de decisiones]] — decisiones técnicas con razón, alternativas y consecuencias
- [[Errores y lecciones/Errores detectados y soluciones]] — bugs encontrados y sus fixes
- [[Errores y lecciones/Lecciones aprendidas]] — principios destilados de la experiencia
- [[Bitácora]] — diario cronológico de cambios (una nota por día con trabajo relevante)

## Fuentes canónicas en el repo

La bóveda sintetiza y enlaza; los datos crudos viven en el repo:

| Contenido | Fuente canónica |
|---|---|
| Resúmenes de sesión completos | `.claude/memory/session-summaries.md` |
| Issues conocidos (KI-*) | `.claude/memory/known-issues.md` |
| Decisiones (formato completo) | `.claude/memory/project-decisions.md` |
| Configuración de producción | `configs/default.yaml`, `configs/leagues/ratings.yaml` |
| Historia de código | `git log` |

## Cómo mantener esta bóveda

Ver [[Metodología de documentación]] — estructura, convenciones de nombres, cuándo crear nota nueva vs actualizar existente.
