# Claude Code project notes

- Use `graphify query`, `graphify path`, or `graphify explain` when `graphify-out/graph.json` exists; use raw source search when it is more direct. Run `graphify update .` after code changes when available.
- Graphify skill oficial vendorizada en `.claude/skills/graphify/` (version en `.graphify_version`). Requiere el CLI: `pip install graphifyy` (paquete oficial; el binario se llama `graphify`). Para actualizar la skill: `pip install -U graphifyy && graphify install --platform claude` y copiar `~/.claude/skills/graphify/` sobre `.claude/skills/graphify/`. `graphify claude install` ya esta aplicado: seccion `## graphify` en `CLAUDE.md` y hooks `PreToolUse` (`hook-guard search` en `Bash|Grep`, `hook-guard read` en `Read|Glob`) en `.claude/settings.json`. Esos hooks se reescribieron a mano para no depender de una ruta absoluta: se saltan solos (`exit 0`) si el CLI no esta en el `PATH` o si no existe `graphify-out/graph.json`.
- Load specialized loops, agents, playbooks, and memory only when the task requires them; do not preload the whole `.claude/` tree.
- Commands: `/route-task` for explicit routing, `/project-health` for health checks, `/autopilot` for bounded maintenance, and `/verification-gate` before completion when relevant.
- Para operaciones quant sin skill explícito, consultar primero `.claude/loops/quant/00-quant-operations-router.md` para seleccionar el loop correcto.
- Do not run `/memoria-cargar` or `/memoria-guardar` automatically; use them only when persistent project memory is needed.
- Before unrelated work use `/clear`; during a long related task use `/compact` with the project compact instructions. Use `/context`, `/usage`, `/memory`, and `/mcp` to diagnose unexpected consumption.
