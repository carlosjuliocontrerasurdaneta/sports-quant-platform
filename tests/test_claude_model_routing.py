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
    # Main conversation model: claude-opus-5 by explicit human decision 2026-08-30
    # (supersedes claude-fable-5 2026-08-24, que superseduo a sonnet 2026-08-18).
    # Separate from the ROUTE default below, which stays sonnet -- normal work is
    # routed to sonnet ("Prefer Sonnet for normal work"); only the interactive
    # settings.json model changed.
    #
    # claude-opus-5 es a la vez el defecto Y el techo: el 2026-08-30 el operador
    # saco a claude-fable-5 de la jerarquia, asi que ya no hay un escalon por
    # encima al que escalar. El principio rector sigue intacto -- "el modelo
    # superior para lo que exige maximo razonamiento" -- y lo que cambio es cual
    # es ese modelo superior.
    #
    # Este literal estuvo en rojo desde antes del 2026-08-29 porque el cambio se
    # aplico a settings.json y docs/MODEL-ROUTING.md pero no aqui ni a la
    # politica (KI-021). El candado hizo exactamente lo que debia: sostener el
    # fallo hasta que un humano decidiera. Cerrado el 2026-08-30.
    assert settings["model"] == "claude-opus-5"
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
    assert "**Conversación principal:** `claude-opus-5`" in policy


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


def test_governing_principle_is_declared_and_takes_precedence():
    """PRINCIPIO RECTOR (orden del operador, 2026-08-25).

    "Priorizar siempre el modelo superior para las tareas que requieran el
    maximo nivel de razonamiento y delegar las demas segun complejidad y
    fortaleza de cada modelo." Se ancla aqui porque una politica que solo vive
    en prosa se erosiona sin que nada lo señale -- que es el modo de fallo que
    este archivo entero existe para impedir.
    """
    policy = (ROOT / ".claude/automation/MODEL_ROUTING.md").read_text(
        encoding="utf-8"
    )
    assert "## PRINCIPIO RECTOR" in policy
    for fragment in (
        "Priorizar siempre el modelo superior",
        "nivel de razonamiento",
        "Gobierna toda esta política",
        "Ante la duda entre dos escalones",
        "no revierte unilateralmente",
    ):
        assert fragment in policy, f"falta del principio rector: {fragment!r}"
    # La jerarquia de capacidad debe quedar explicita: sin ella "modelo superior"
    # es interpretable y el principio no es accionable.
    #
    # Son DOS afirmaciones distintas y el candado exige las dos, porque
    # confundirlas es como se rompio esto el 2026-08-30:
    #
    # 1. La jerarquia de CAPACIDAD es un hecho de Anthropic, no una politica de
    #    este proyecto. claude-fable-5 es el escalon mas alto y la documentacion
    #    oficial lo dice ("for the highest available capability, use Claude
    #    Fable 5"). Escribirla sin Fable seria afirmar algo falso.
    # 2. El REPARTO operativo de este proyecto (decision del operador
    #    2026-08-30): claude-opus-5 por defecto, claude-fable-5 reservado para
    #    maxima capacidad de razonamiento. Punto de partida y techo son cosas
    #    distintas -- empezar en Fable costaria el doble sin que la mayoria del
    #    volumen lo necesite, y no tenerlo disponible dejaria el principio
    #    rector sin destino al que escalar.
    assert "`claude-fable-5` > `claude-opus-5` > `claude-sonnet-5` > `claude-haiku-4-5`" in policy
    # El candado tiene dos lados: la jerarquia real y el reparto declarado. Sin
    # el segundo, mover el defecto o el techo en la prosa no rompe nada y la
    # politica vuelve a divergir en silencio -- que es el modo de fallo que este
    # archivo entero existe para impedir.
    assert "`claude-opus-5` es el modelo por defecto" in policy
    assert "`claude-fable-5` se reserva para máxima capacidad de razonamiento" in policy


def test_escalation_trigger_is_observable_and_not_self_assessed():
    """Enmienda 2026-08-25. Un principio que dice "escala si la tarea es dificil"
    lo evalua el propio modelo que va a ejecutarla, y uno mas debil subestima la
    dificultad porque no ve lo que no ve. El disparador tiene que ser observable
    ex ante y no admitir juicio, o el principio no es incumplible de forma
    detectable -- es un deseo, no una politica.
    """
    policy = (ROOT / ".claude/automation/MODEL_ROUTING.md").read_text(
        encoding="utf-8"
    )
    assert "Disparador de escalado" in policy
    assert "por CLASE de tarea, no por dificultad percibida" in policy
    # Las cinco clases observables.
    for clase in ("irreversible", "parámetros de riesgo", "cifras publicables",
                  "contradiga una decisión previa registrada",
                  "contrato de un artefacto persistido"):
        assert clase in policy, f"falta una clase del disparador: {clase!r}"
    # Precedencia sobre la ruta: sin esto la tabla por palabras clave gana y el
    # disparador queda decorativo.
    assert "precedencia sobre la ruta asignada" in policy


def test_measurement_outranks_model_capability():
    """Enmienda 2026-08-25. En este proyecto la restriccion vinculante nunca ha
    sido la capacidad de razonamiento sino la disciplina de medicion: las seis
    mediciones negativas salieron de EJECUTAR algo. Un modelo superior es mas
    peligroso sin datos, no menos -- produce narrativas mas convincentes sobre lo
    que no ha medido.
    """
    policy = (ROOT / ".claude/automation/MODEL_ROUTING.md").read_text(
        encoding="utf-8"
    )
    assert "Ningún escalón de modelo sustituye una medición" in policy
    assert "se mide antes de razonar" in policy
    # "superior" != "correcto": la no-reversion es regla de PROCESO, no de fondo.
    assert '"superior" ≠ "correcto"' in policy
