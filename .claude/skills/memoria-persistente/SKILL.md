---
name: memoria-persistente-pro
description: >
  Sistema de memoria persistente del proyecto. Carga contexto al inicio y mantiene
  decisiones, issues, roadmap, arquitectura y resúmenes de sesión. El almacén
  canónico es .claude/memory/.
---

# MEMORIA PERSISTENTE PRO

## Almacén canónico

**Todos los archivos de memoria viven en `.claude/memory/`.**

Hasta la auditoría 2026-07-29 esta skill listaba nombres sin ruta, y existían
copias homónimas VACÍAS dentro de la propia carpeta de la skill (15–99 bytes,
frente a 19–51 KB en `.claude/memory/`). Un agente que siguiera el protocolo
literalmente cargaba los stubs vacíos y concluía "sin contexto previo" en
silencio, porque la regla "nunca inventar memoria" convierte ese fallo en
ausencia de reporte en lugar de un error visible (hallazgo K-005). Los stubs
quedan como punteros al archivo real; no escribir en ellos.

Existe además una memoria del harness, fuera del repositorio, que se inyecta al
contexto automáticamente al iniciar sesión. Es complementaria: no sustituye a
`.claude/memory/`.

## Protocolo de inicio

Equivalente al comando `/memoria-cargar`. Leer en este orden:

1. `.claude/memory/session-summaries.md` — última entrada.
2. `.claude/memory/known-issues.md` — issues activos.
3. `.claude/memory/project-decisions.md` — decisiones recientes.
4. `.claude/memory/roadmap.md` — prioridades vigentes.
5. `.claude/memory/architecture-log.md` — cuando la tarea sea estructural.
6. `.claude/memory/lessons-learned.md` y `agent-topology.md` — según aplique.
7. `.claude/automation/runtime/current-task.md` — estado de la tarea en curso.

Reportar: última sesión, objetivo actual, bloqueadores, issues abiertos y próximo
hito. Si un archivo está vacío o ausente, decirlo explícitamente en lugar de
asumir que no hay contexto.

## Protocolo de cierre

Equivalente al comando `/memoria-guardar`. Actualizar en `.claude/memory/`:
`session-summaries.md`, `project-decisions.md`, `known-issues.md`,
`architecture-log.md`, `roadmap.md`.

La bóveda `Obsidian/` es la fuente central de conocimiento del proyecto y tiene
su propio protocolo obligatorio (ver `.claude/CLAUDE.md`); `.claude/memory/` es la
memoria operativa del agente. No duplicar contenido entre ambas: enlazar.

## Reglas

- Nunca inventar memoria. Solo información aportada por el usuario o almacenada.
- Convertir fechas relativas en absolutas al escribir.
- Una autorización del operador se registra **con su fecha**; una autorización sin
  caducidad no se trata como permanente (hallazgo K-006).
