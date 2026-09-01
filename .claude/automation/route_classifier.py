#!/usr/bin/env python3
"""Clasificador de rutas: prompt -> loop, subagente principal y subagentes de apoyo.

RETIRADO COMO HOOK el 2026-09-01 (decision del operador). Esta logica vivio en
`.claude/hooks/route-model.py` con un `main()` que leia stdin y emitia el JSON
de `UserPromptSubmit`, pero ese hook **nunca estuvo cableado**: `settings.json`
solo declara `PostToolUse` y `Stop`, asi que las 24 rutas de
`model-routing.json` llevaban meses sin ejecutarse mientras varios tests las
validaban en verde. Codigo muerto con candado.

Se retiro en vez de cablearlo, por cuatro razones (auditoria 2026-09-01):

1. Aunque se cableara, solo inyecta texto consultivo: **no asigna modelo**. El
   mecanismo real es el parametro `model` de la herramienta `Agent` (ver
   `## REGLA DE DESPACHO` en `.claude/automation/MODEL_ROUTING.md`).
2. Se disparaba en CADA prompt, gastando contexto siempre para acertar rara vez.
3. La clasificacion por palabras clave falla con prompts reales: "¿Y
   MODEL-ROUTING.md?" no casa con ningun keyword y cae a la ruta `default`.
4. El modo de fallo dominante de este repo es la deriva entre artefactos
   duplicados (KI-021); retirar quita una pieza que mantener sincronizada.

Lo que SOBREVIVE es la logica, que si vale: la tabla codifica que loop y que
especialista corresponden a cada clase de solicitud. Se consume **bajo demanda**
desde `/route-task`, no en cada turno.

Este modulo no tiene `main()` a proposito: no es ejecutable como hook. Si algun
dia se quiere reactivar la inyeccion automatica, hay que anadir el bloque
`UserPromptSubmit` a `settings.json` Y volver a escribir un lanzador -- las dos
cosas, deliberadamente, para que no vuelva a existir un hook que parece vivo y
no lo esta.
"""
from __future__ import annotations
from pathlib import Path


def classify(prompt: str, config: dict) -> dict:
    normalized = prompt.casefold()
    routes = sorted(
        config.get("routes", []),
        key=lambda route: route.get("priority", 0),
        reverse=True,
    )
    for route in routes:
        if any(term.casefold() in normalized for term in route.get("keywords", [])):
            return route
    return config["default"] | {"id": "default", "support_agents": []}


def find_config_path(cwd: Path) -> Path:
    """Find model-routing.json from the project root or a nested cwd."""
    start = cwd.resolve()
    for candidate in (start, *start.parents):
        path = candidate / ".claude" / "automation" / "model-routing.json"
        if path.is_file():
            return path
    raise FileNotFoundError(
        f".claude/automation/model-routing.json not found from {start}"
    )
