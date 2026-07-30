from __future__ import annotations
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("route_model", ROOT/".claude/hooks/route-model.py")
assert SPEC and SPEC.loader
MODULE=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MODULE)
CONFIG=json.loads((ROOT/".claude/automation/model-routing.json").read_text(encoding="utf-8"))

def test_full_audit_routes_to_orchestrator():
    route=MODULE.classify("Realiza una auditoría completa y un análisis exhaustivo", CONFIG)
    assert route["id"]=="full-audit"
    assert route["model"]=="opus"
    assert route["primary_agent"]=="principal-orchestrator"

def test_no_route_uses_an_unavailable_model():
    """fable estaba enrutado en 5 rutas y 10 agentes, pero la cuenta no tiene
    créditos de Fable 5: los subagentes más críticos (auditoría, modelado,
    calibración, riesgo) fallaban al arrancar (auditoría 2026-07-29, K-004).
    Este test evita que un modelo sin entitlement vuelva a entrar por descuido."""
    UNAVAILABLE={"fable"}
    bad_routes=[r["id"] for r in CONFIG["routes"] if r.get("model") in UNAVAILABLE]
    assert bad_routes==[], f"rutas con modelo no disponible: {bad_routes}"
    bad_agents=[p.name for p in (ROOT/".claude/agents").rglob("*.md")
                if any(f"model: {m}" in p.read_text(encoding="utf-8") for m in UNAVAILABLE)]
    assert bad_agents==[], f"agentes con modelo no disponible: {bad_agents}"

def test_every_route_references_an_existing_loop_and_agents():
    """El validador aceptaba rutas cuyo `loop` o `support_agents` no existieran
    en disco (auditoría 2026-07-29, K-015)."""
    names={m.split("name:",1)[1].splitlines()[0].strip()
           for p in (ROOT/".claude/agents").rglob("*.md")
           for m in [p.read_text(encoding="utf-8")] if "name:" in m}
    # route-model.py resuelve el loop como `.claude/loops/<loop>` (ver linea 26).
    for r in CONFIG["routes"]:
        loop=r.get("loop")
        if loop:
            path=ROOT/".claude"/"loops"/loop
            assert path.exists(), f"ruta {r['id']}: loop inexistente .claude/loops/{loop}"
        for a in r.get("support_agents") or []:
            assert a in names, f"ruta {r['id']}: subagente de apoyo inexistente {a}"

def test_bug_routes_to_opus_python_engineer():
    route=MODULE.classify("Corrige el bug del settlement", CONFIG)
    assert route["id"]=="bugfix"
    assert route["model"]=="opus"

def test_documentation_routes_to_haiku():
    route=MODULE.classify("Actualiza la documentación README", CONFIG)
    assert route["id"]=="documentation"
    assert route["model"]=="haiku"
