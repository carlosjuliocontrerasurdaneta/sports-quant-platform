---
tags: [meta, documentacion, sqp]
creada: 2026-07-08
actualizada: 2026-07-08
---

# Metodología de documentación

Cómo se mantiene esta bóveda actualizada y coherente. La regla que lo garantiza vive en `CLAUDE.md` (el asistente la aplica en cada sesión de trabajo).

## Regla de actualización (automática por flujo de trabajo)

Cada cambio relevante en el proyecto (feature, fix, decisión, hallazgo, cambio de configuración de producción, resultado de validación) debe reflejarse en la bóveda **en la misma sesión** en que ocurre:

1. **Bitácora**: crear/actualizar `Bitácora/AAAA-MM-DD.md` con qué cambió, por qué y los commits.
2. **Notas afectadas**: actualizar las notas temáticas tocadas (p. ej. una señal nueva → [[Conocimiento/Señales por deporte]]; una decisión → [[Decisiones/Registro de decisiones]]; un bug → [[Errores y lecciones/Errores detectados y soluciones]]).
3. **[[Estado del proyecto]]**: solo si cambia el estado operativo (modo, balance, gates, scheduler).
4. **[[Tareas]]**: marcar completadas / añadir nuevas.
5. Actualizar el campo `actualizada:` del frontmatter de cada nota tocada.

## Estructura

```
Obsidian/
├── 00 - Inicio.md               ← MOC / punto de entrada
├── Estado del proyecto.md       ← snapshot vivo (se sobreescribe)
├── Objetivos y requisitos.md
├── Tareas.md
├── Bitácora.md (índice) + Bitácora/AAAA-MM-DD.md
├── Arquitectura/                ← cómo está construido
├── Conocimiento/                ← dominio cuantitativo (calibración, CLV, señales, OOS)
├── Decisiones/                  ← qué se decidió y por qué
└── Errores y lecciones/         ← qué falló, cómo se arregló, qué se aprendió
```

## Convenciones

- **Idioma**: español. **Lenguaje de apuestas**: siempre "probabilidad estimada", nunca certezas ni profit garantizado.
- **Nota nueva vs actualizar**: actualizar la nota temática existente por defecto; nota nueva solo para un tema sustancial que no encaje en ninguna (y enlazarla desde [[00 - Inicio]]).
- **Enlaces**: liberales entre notas (`[[...]]`); commits como `código` corto; rutas del repo como `código`.
- **No duplicar fuentes canónicas**: la bóveda sintetiza y enlaza; el detalle exhaustivo vive en `.claude/memory/*` y en git. Nunca copiar datos de `data/` aquí.
- **Versionado**: la bóveda está dentro del repo → se committea junto con el trabajo que documenta (mensaje `docs(obsidian): ...` o incluida en el commit del feature).

## Reglas duras

- **NUNCA abrir la raíz del repo como bóveda de Obsidian** — solo `Obsidian/`. (La bóveda personal del usuario es `C:\Users\Richard\Obsidian-Personal`, separada.)
- La bóveda no contiene secretos, credenciales ni datos de `data/`.
