from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "route_model", ROOT / ".claude/hooks/route-model.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CONFIG = json.loads(
    (ROOT / ".claude/automation/model-routing.json").read_text(encoding="utf-8")
)


def test_full_audit_routes_to_orchestrator():
    route = MODULE.classify(
        "Realiza una auditoría completa y un análisis exhaustivo", CONFIG
    )
    assert route["id"] == "full-audit"
    assert route["model"] == "opus"
    assert route["primary_agent"] == "principal-orchestrator"


# Escalon caro y escalon barato, cerrados por igualdad de conjuntos y no por
# pertenencia: anadir una ruta a opus tiene que ser un acto deliberado que toque
# este literal, que es el unico freno de coste que no depende de que alguien se
# acuerde. Politica: .claude/automation/MODEL_ROUTING.md
OPUS_ROUTES = {"full-audit", "incident", "quant-incident"}
HAIKU_ROUTES = {"documentation"}


def test_main_model_matches_the_authorized_policy():
    # Three-way lock: settings.json, MODEL_ROUTING.md and this literal must agree.
    # Config/doc drift is the failure this repo keeps hitting (pick_mode 07-31,
    # model 08-04, and this very change on 08-18, que se aplico a settings.json y
    # model-routing.json pero no a la politica ni aqui). El check es exacto a
    # proposito: cambiar el modelo principal es un acto deliberado.
    settings = json.loads(
        (ROOT / ".claude/settings.json").read_text(encoding="utf-8")
    )
    # Main conversation model: claude-fable-5 by explicit human decision 2026-08-24
    # (supersedes sonnet 2026-08-18). Separate from the ROUTE default below, which
    # stays sonnet -- normal work is routed to sonnet ("Prefer Sonnet for normal
    # work"); only the interactive settings.json model changed.
    assert settings["model"] == "claude-fable-5"
    assert CONFIG["default"]["model"] == "sonnet"

    # RUTAS: sonnet es la norma; opus y haiku son las excepciones declaradas.
    allowed_route_models = {"opus", "sonnet", "haiku"}
    bad_routes = [
        r["id"] for r in CONFIG["routes"] if r.get("model") not in allowed_route_models
    ]
    assert bad_routes == [], f"rutas con modelo no permitido: {bad_routes}"
    assert {r["id"] for r in CONFIG["routes"] if r.get("model") == "opus"} == OPUS_ROUTES
    assert {r["id"] for r in CONFIG["routes"] if r.get("model") == "haiku"} == HAIKU_ROUTES

    # SUBAGENTES: politica independiente y sin cambios. Un especialista al que se
    # delega explicitamente declara opus o haiku, nunca sonnet.
    allowed_subagent_models = {"opus", "haiku"}
    bad_agents = [
        p.name
        for p in (ROOT / ".claude/agents").rglob("*.md")
        if not any(
            f"model: {model}" in p.read_text(encoding="utf-8")
            for model in allowed_subagent_models
        )
    ]
    assert bad_agents == [], f"agentes con modelo no permitido: {bad_agents}"

    policy = (ROOT / ".claude/automation/MODEL_ROUTING.md").read_text(
        encoding="utf-8"
    )
    assert "**Conversación principal:** `claude-fable-5`" in policy


def test_every_route_references_an_existing_loop_and_agents():
    names = {
        text.split("name:", 1)[1].splitlines()[0].strip()
        for path in (ROOT / ".claude/agents").rglob("*.md")
        for text in [path.read_text(encoding="utf-8")]
        if "name:" in text
    }
    for route in [CONFIG["default"], *CONFIG["routes"]]:
        loop = route.get("loop")
        if loop:
            path = ROOT / ".claude" / "loops" / loop
            assert path.exists(), (
                f"ruta {route.get('id', 'default')}: loop inexistente "
                f".claude/loops/{loop}"
            )
        for agent in [route.get("primary_agent"), *(route.get("support_agents") or [])]:
            if agent:
                assert agent in names, (
                    f"ruta {route.get('id', 'default')}: "
                    f"subagente inexistente {agent}"
                )


def test_quantitative_prompts_route_to_the_specialized_loops():
    expected = {
        "Genera las predicciones diarias": "quant/01-daily-prediction.md",
        "Actualiza un pick por cambio prepartido material": "quant/02-pregame-refresh.md",
        "Liquida los resultados de los partidos terminados": "quant/03-postgame-settlement.md",
        "Ejecuta la auditoría cuantitativa diaria": "quant/04-daily-audit.md",
        "Diagnostica las pérdidas de los picks": "quant/05-loss-diagnosis.md",
        "Monitorea la calibración sin promover artefactos": "quant/06-calibration-monitor.md",
        "Revisa el drift de datos y rendimiento": "quant/07-drift-monitor.md",
        "Recupera un problema de calidad de datos cuantitativos": "quant/08-data-quality-recovery.md",
        "Compara champion versus challenger": "quant/09-champion-challenger.md",
        "Ejecuta una recalibración controlada": "quant/10-controlled-recalibration.md",
        "Analiza la transición de temporada": "quant/11-season-transition.md",
        "Contén un incidente cuantitativo": "quant/12-quant-incident.md",
        "Realiza la mejora continua semanal cuantitativa": "quant/13-weekly-continuous-improvement.md",
    }
    for prompt, loop in expected.items():
        route = MODULE.classify(prompt, CONFIG)
        assert route["loop"] == loop, (prompt, route["id"], route["loop"])


def test_quant_incident_precedes_generic_incident_in_decision_engine():
    text = (ROOT / ".claude/automation/decision-engine.md").read_text(
        encoding="utf-8"
    )
    assert text.index("Quantitative production incident") < text.index(
        "Active non-quantitative incident or production outage"
    )


def test_router_finds_configuration_from_nested_working_directory(tmp_path):
    project = tmp_path / "project"
    nested = project / "src" / "package"
    config_dir = project / ".claude" / "automation"
    nested.mkdir(parents=True)
    config_dir.mkdir(parents=True)
    expected = config_dir / "model-routing.json"
    expected.write_text("{}", encoding="utf-8")
    assert MODULE.find_config_path(nested) == expected


def test_general_calibration_and_calibrator_changes_follow_decision_engine():
    analysis = MODULE.classify("Analiza exclusivamente la calibración", CONFIG)
    assert analysis["loop"] == "calibration.md"

    change = MODULE.classify("Cambia el calibrador activo", CONFIG)
    assert change["loop"] == "model.md"


def test_bug_routes_to_sonnet_python_engineer():
    # Un bugfix es trabajo normal, no un incidente critico: desde el 2026-08-18
    # va a sonnet. Solo full-audit/incident/quant-incident conservan opus.
    route = MODULE.classify("Corrige el bug del settlement", CONFIG)
    assert route["id"] == "bugfix"
    assert route["model"] == "sonnet"
    assert route["primary_agent"] == "python-engineer"


def test_documentation_routes_to_haiku():
    route = MODULE.classify("Actualiza la documentación README", CONFIG)
    assert route["id"] == "documentation"
    assert route["model"] == "haiku"
