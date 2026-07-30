# Current Task

Status: in-progress
Loop: full-audit (Fase 4-5) → ver `.claude/loops/quant/STATES.md`
Iteration: 1 / 8
Owner: principal-orchestrator

## Objective

Auditoría integral del repositorio (código, datos, cuantitativo, seguridad,
Claude Code y Quant Loops) con corrección autónoma acotada y entregables en
`audit/latest/`. Solicitada por el operador el 2026-07-29.

## Acceptance criteria

- [x] Línea base medida antes de modificar (tests, ruff, mypy, pip check).
- [x] Hallazgos con evidencia `file:line` y severidad.
- [x] Correcciones seguras aplicadas con prueba de regresión cada una.
- [x] Suite completa verde tras las correcciones.
- [ ] Entregables escritos en `audit/latest/`.
- [ ] Bitácora Obsidian del día actualizada.

## Evidence log

- Línea base (2026-07-29): pytest 439 passed; ruff check limpio salvo 1×E401 en
  un script no versionado; mypy 86 archivos sin issues; pip check OK.
- Correcciones con prueba: B-01, B-05, B-06, B-08, B-13, D-01, D-04, D-05, D-06,
  D-08, D-09, Q-01, K-004, K-015.
- `ruff format --check` reporta 173 archivos, pero el proyecto NO usa
  `ruff format` (el Makefile solo hace `ruff check`): NO es un hallazgo.

## Risks and approvals

- **Sin autorización vigente para commit ni push.** La autorización "total" del
  2026-07-14 PM que este archivo arrastraba estaba caducada de facto y fue
  retirada en la auditoría 2026-07-29 (K-006): una autorización sin fecha de
  caducidad no puede tratarse como permanente.
- `shadow_mode: true` intacto. Ningún parámetro productivo de riesgo, umbral ni
  bankroll fue modificado.
- Pendiente de decisión humana: ver `audit/latest/BACKLOG.md`.

## Next decision

Revisar `audit/latest/EXECUTIVE_SUMMARY.md` y decidir sobre los ítems que
requieren autorización (commit, política del umbral de precisión frente a
`market_shrink`, destino de `superpowers-main`, alerta del run diario fallido).
