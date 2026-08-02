# Archivos modificados — Auditoría 2026-08-02

Sin commit (pendiente de autorización). Estado exacto: `git status --short`.

## Código de producción

- `src/sqp/models/ml_train.py` — `_register`: registry corrupto se respalda
  (`registry.json.corrupt-<ts>`) y se loggea WARNING en vez de descartarse en
  silencio (hallazgo B-01).

## Tests

- `tests/test_ml_models.py` — test nuevo
  `test_register_corrupt_registry_backed_up_not_silently_discarded` (TDD para
  B-01). Suite: 581 → 582.

## Documentación

- `README.md` — modo precisión: "disponible, NO activo (revertido 2026-07-31)"
  con la razón económica (breakeven 93.5% a cuota 1.07) y las columnas
  `breakeven_hit_rate`/`hit_rate_margin` (hallazgo A-01).
- `Obsidian/Estado del proyecto.md` — snapshot 2026-08-02: objetivo sacrosanto
  (ganar dinero, directiva del operador) + modo EDGE activo (A-01).
- `Obsidian/Tareas.md` — tareas del modo precisión cerradas como obsoletas;
  revert en completadas; tarea nueva M-01 (filas sin liquidar) (A-01).
- `Obsidian/Bitácora/2026-08-02.md` — NUEVA: bitácora de la auditoría y de la
  directiva del operador.

## Claude Code / memoria

- `.claude/memory/project-decisions.md` — decisión 2026-08-02: objetivo
  sacrosanto = ganar dinero (supersede el pivot a hit rate del 07-27).
- `.claude/memory/roadmap.md` — enlaces muertos retirados (B-02).
- `.claude/automation/runtime/current-task.md` — tarea zombi cerrada; auditoría
  2026-08-02 registrada y cerrada en PASS (M-02).
- `.claude/settings.json` — PREEXISTENTE (renombre de modelo del harness), no
  tocado por esta auditoría.

## CI

- `.github/workflows/ci.yml` — comentario ">=3.10" → ">=3.11" (B-03).

## Entregables

- `audit/latest/*.md` + `MANIFEST.json` — regenerados para esta auditoría (los
  anteriores quedan en el historial git, commit `4fdf671`+).

## Memoria del asistente (fuera del repo)

- `~/.claude/projects/.../memory/objetivo-hit-rate-modo-precision.md` y
  `MEMORY.md` — actualizados a la directiva sacrosanta y al estado real
  (`pick_mode: edge`).
