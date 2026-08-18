# Claude Code project notes

- Use `graphify query`, `graphify path`, or `graphify explain` when `graphify-out/graph.json` exists; use raw source search when it is more direct. Run `graphify update .` after code changes when available.
- Load specialized loops, agents, playbooks, and memory only when the task requires them; do not preload the whole `.claude/` tree.
- Commands: `/route-task` for explicit routing, `/project-health` for health checks, `/autopilot` for bounded maintenance, and `/verification-gate` before completion when relevant.
- Do not run `/memoria-cargar` or `/memoria-guardar` automatically; use them only when persistent project memory is needed.
- Before unrelated work use `/clear`; during a long related task use `/compact` with the project compact instructions. Use `/context`, `/usage`, `/memory`, and `/mcp` to diagnose unexpected consumption.
