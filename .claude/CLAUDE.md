# Claude Code project notes

- Use `graphify query`, `graphify path`, or `graphify explain` when `graphify-out/graph.json` exists; use raw source search when it is more direct. Run `graphify update .` after code changes when available.
- Load specialized loops, agents, playbooks, and memory only when the task requires them; do not preload the whole `.claude/` tree.
- Commands: `/route-task` for explicit routing, `/project-health` for health checks, `/autopilot` for bounded maintenance, and `/verification-gate` before completion when relevant.
- Para operaciones quant sin skill explícito, consultar primero `.claude/loops/quant/00-quant-operations-router.md` para seleccionar el loop correcto.
- Do not run `/memoria-cargar` or `/memoria-guardar` automatically in an ordinary session; use them only when persistent project memory is needed. EXCEPCIÓN, y no es una excepción menor: cuando la tarea entra por un **loop** (`.claude/loops/**`) o por `ORCHESTRATOR.md`, esos ficheros SÍ los ordenan en su arranque y cierre, y ahí mandan ellos. Los 14 loops quant comparten ese bloque y `tests/test_claude_system_contract.py::test_quant_loops_share_an_identical_common_rules_block` lo fija idéntico, así que la orden es deliberada, no una filtración. Esta línea decía sólo la primera mitad y contradecía de frente a `ORCHESTRATOR.md:11` (auditoría integral 2026-09-10, AUD-MED-014).
- Before unrelated work use `/clear`; during a long related task use `/compact` with the project compact instructions. Use `/context`, `/usage`, `/memory`, and `/mcp` to diagnose unexpected consumption.
