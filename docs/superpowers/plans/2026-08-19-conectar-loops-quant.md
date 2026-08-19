# Conectar Loops Quant al Flujo Activo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hacer que los 13 loops quant sean invocables automáticamente desde el sistema de skills de Claude Code.

**Architecture:** Modificar 2 skills existentes añadiendo una sección "Loop de referencia", crear 9 skills nuevos (uno por loop sin cobertura), y actualizar `.claude/CLAUDE.md` con referencia al router. Los nuevos skills son thin wrappers — el contenido vive en los loops.

**Tech Stack:** Markdown, Claude Code skills system.

## Global Constraints

- Cada SKILL.md nuevo debe tener frontmatter con `name:` y `description:` en español
- La `description:` debe incluir frases de trigger que el usuario usaría naturalmente
- El cuerpo de cada skill nuevo es una sola instrucción: leer y seguir el loop
- No duplicar contenido que ya vive en los loops
- No modificar los archivos de loop

---

### Task 1: Modificar `daily-operations` y `review-calibration`

**Files:**
- Modify: `.claude/skills/daily-operations/SKILL.md`
- Modify: `.claude/skills/review-calibration/SKILL.md`

- [ ] Añadir sección `## Loop de referencia` al final de `daily-operations/SKILL.md` que apunte a loops 01 y 03
- [ ] Añadir sección `## Loop de referencia` al final de `review-calibration/SKILL.md` que apunte a loops 06 y 10
- [ ] Verificar que los archivos son válidos markdown

### Task 2: Actualizar `.claude/CLAUDE.md`

**Files:**
- Modify: `.claude/CLAUDE.md`

- [ ] Añadir línea que referencia el router quant `00-quant-operations-router.md`

### Task 3: Crear 9 skills nuevos

**Files a crear:**
- `.claude/skills/daily-audit/SKILL.md`
- `.claude/skills/pregame-refresh/SKILL.md`
- `.claude/skills/loss-diagnosis/SKILL.md`
- `.claude/skills/drift-monitor/SKILL.md`
- `.claude/skills/data-quality-recovery/SKILL.md`
- `.claude/skills/champion-challenger/SKILL.md`
- `.claude/skills/season-transition/SKILL.md`
- `.claude/skills/quant-incident/SKILL.md`
- `.claude/skills/weekly-improvement/SKILL.md`

- [ ] Crear cada SKILL.md con frontmatter apropiado y referencia al loop
- [ ] Confirmar que los 9 directorios fueron creados

### Task 4: Commit

- [ ] `git add .claude/`
- [ ] `git commit -m "feat(loops): conectar loops quant al sistema de skills"`
