from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".claude/skills"
ROUTER = ROOT / ".claude/loops/quant/00-quant-operations-router.md"

# Hasta el 2026-09-18 los loops eran ficheros de `.claude/loops/` y las skills
# solo los apuntaban ("Leer y seguir ..."); se fundieron en las skills. Una skill
# es OPERATIVA (lleva un loop) si conserva el bloque de guardarrailes expandido.
QUANT_SKILLS = {
    "champion-challenger", "controlled-recalibration", "daily-audit",
    "daily-operations", "data-quality-recovery", "drift-monitor",
    "loss-diagnosis", "pregame-refresh", "quant-incident", "review-calibration",
    "season-transition", "weekly-improvement",
}
GENERAL_SKILLS = {
    "bugfix", "documentation", "feature-engineering", "full-audit", "incident",
    "model-change", "provider-integration",
}


def _skill(name: str) -> Path:
    return SKILLS / name / "SKILL.md"


def _load_health_module():
    path = ROOT / "scripts/claude_project_health.py"
    spec = importlib.util.spec_from_file_location("claude_project_health", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_root_claude_markdown_is_plain_utf8_without_nul_bytes():
    raw = (ROOT / "CLAUDE.md").read_bytes()
    assert b"\x00" not in raw
    raw.decode("utf-8")


def test_health_recognizes_active_and_terminal_task_states():
    health = _load_health_module()
    assert health.current_task_is_active("Status: active\nResult: N/A\n")
    assert health.current_task_is_active("Status: in-progress\n")
    for terminal in ("idle", "closed"):
        assert not health.current_task_is_active(f"Status: {terminal}\n")
    assert not health.current_task_is_active("Status: closed (PASS)\n")


def test_default_configuration_requires_human_calibrator_promotion():
    cfg = yaml.safe_load((ROOT / "configs/default.yaml").read_text(encoding="utf-8"))
    assert cfg["calibration"]["auto_promote"] is False


def test_quant_state_contract_has_no_loop_specific_done_contradiction():
    states = (ROOT / ".claude/loops/quant/STATES.md").read_text(encoding="utf-8")
    assert "solo un loop" not in states
    assert "Un loop periódico" not in states
    assert "Precedencia" in states


def test_orchestrator_defines_supporting_loop_handoffs():
    orchestrator = (ROOT / ".claude/ORCHESTRATOR.md").read_text(encoding="utf-8")
    assert "Supporting loops and handoffs" in orchestrator
    normalized = " ".join(orchestrator.split())
    assert "must not replace the task header" in normalized


def test_daily_audit_does_not_require_stake_for_clv():
    loop = _skill("daily-audit").read_text(encoding="utf-8")
    assert "CLV solo es válido" not in loop
    normalized = " ".join(loop.split())
    assert "CLV requiere una cuota de entrada" in normalized


def test_all_general_loops_finish_through_verification_gate():
    missing = [
        name
        for name in sorted(GENERAL_SKILLS)
        if "/verification-gate" not in _skill(name).read_text(encoding="utf-8")
    ]
    assert missing == []


def _guardrail_block(path: Path, heading: str) -> str:
    """Bloque de vinetas que sigue a `heading`, hasta la primera linea no-vineta."""
    block: list[str] = []
    started = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() == heading:
            started = True
            continue
        if not started:
            continue
        if line.startswith("- "):
            block.append(line)
        elif line.strip():
            break
    return "\n".join(block)


# ---------------------------------------------------------------------------
# El bloque de reglas comunes esta duplicado en cada skill operativa a
# proposito: una skill se carga sola, asi que debe ser autocontenida. El riesgo
# no es la duplicacion sino la deriva -- que una copia cambie y las demas no.
# ---------------------------------------------------------------------------


def _carriers(heading: str) -> set[str]:
    """Skills que llevan el bloque `heading` (ademas del router, para quant)."""
    return {
        p.parent.name
        for p in SKILLS.glob("*/SKILL.md")
        if _guardrail_block(p, heading)
    }


def test_quant_skills_share_an_identical_common_rules_block():
    assert _carriers("## Reglas comunes") == QUANT_SKILLS, (
        "el conjunto de skills quant cambio: actualizar QUANT_SKILLS y el router"
    )
    blocks = {name: _guardrail_block(_skill(name), "## Reglas comunes") for name in QUANT_SKILLS}
    blocks["00-quant-operations-router.md"] = _guardrail_block(ROUTER, "## Reglas comunes")
    assert all(blocks.values()), f"skill sin bloque de reglas comunes: {blocks}"
    assert len(set(blocks.values())) == 1, "las reglas comunes derivaron entre skills"


def test_general_skills_share_an_identical_guardrail_block():
    assert _carriers("## Common guardrails") == GENERAL_SKILLS, (
        "el conjunto de skills generales cambio: actualizar GENERAL_SKILLS"
    )
    blocks = {name: _guardrail_block(_skill(name), "## Common guardrails") for name in GENERAL_SKILLS}
    assert all(blocks.values()), f"skill sin bloque de guardrails: {blocks}"
    assert len(set(blocks.values())) == 1, "los guardrails derivaron entre skills"


def test_no_skill_still_points_at_a_deleted_loop():
    """La fusion del 2026-09-18 no deja punteros a ficheros que ya no existen."""
    stale = {
        p.parent.name: sorted(set(hits))
        for p in SKILLS.glob("*/SKILL.md")
        if (hits := [
            m for m in re.findall(r"\.claude/loops/[A-Za-z0-9_./-]+\.md", p.read_text(encoding="utf-8"))
            if not (ROOT / m).is_file()
        ])
    }
    assert stale == {}


# ---------------------------------------------------------------------------
# Hay dos tablas de enrutamiento a las skills quant: `model-routing.json`, que
# consume el clasificador `route_classifier.py`, y la tabla del router 00, que
# lee el orquestador ya dentro del contexto quant. Deben apuntar al mismo
# conjunto: una skill nueva registrada solo en una de las dos queda
# inalcanzable o invisible.
# ---------------------------------------------------------------------------


def test_quant_router_table_matches_model_routing_config():
    config = json.loads(
        (ROOT / ".claude/automation/model-routing.json").read_text(encoding="utf-8")
    )
    routed = {
        route["skill"]
        for route in config["routes"]
        if route["id"].startswith("quant-")
    }
    region = ROUTER.read_text(encoding="utf-8").split("<!-- generated: quant-routes -->", 1)[1]
    region = region.split("<!-- endgenerated: quant-routes -->", 1)[0]
    tabulated = {
        name for _, name in re.findall(r"\| `([a-z0-9-]+)` \| `([a-z0-9-]+)` \|", region)
    }
    assert tabulated == routed, (
        f"la tabla del router 00 y model-routing.json divergieron: "
        f"solo en la tabla {sorted(tabulated - routed)}, "
        f"solo en el json {sorted(routed - tabulated)}"
    )
    assert QUANT_SKILLS == routed, (
        f"skills quant sin ruta declarada: {sorted(QUANT_SKILLS - routed)}; "
        f"rutas a skills inexistentes: {sorted(routed - QUANT_SKILLS)}"
    )


def test_quant_loop_common_spelling_is_consistent():
    bad = [
        p.name
        for p in [ROUTER, ROUTER.with_name("STATES.md"), *(_skill(n) for n in QUANT_SKILLS)]
        if " segun " in p.read_text(encoding="utf-8")
    ]
    assert bad == []


# ---------------------------------------------------------------------------
# B-1: un resultado PASS/DONE debe traer la evidencia que STATES.md exige.
# Motivacion: el 2026-08-04 current-task.md cerro en `Result: PASS` con la suite
# en 5 failed y ruff/mypy sin ejecutar. STATES.md ya lo prohibia -- "si no puede
# determinarse a partir de un artefacto o de la salida de un comando, el
# resultado es BLOCKED, nunca PASS" -- pero nada lo hacia cumplir.
# ---------------------------------------------------------------------------

_PASS_NO_EVIDENCE = """# Current Task

Status: closed
Result: PASS

## Objective

Algo que se dio por bueno sin medirlo.
"""

_PASS_WITH_EVIDENCE = """# Current Task

Status: closed
Result: PASS

## Comandos ejecutados y codigos de salida

| Comando | Salida | Codigo |
|---|---|---|
| `pytest -q` | 618 passed | 0 |

## Artefactos producidos

- `audit/latest/VALIDATION.md`
"""

_BLOCKED_NO_EVIDENCE = """# Current Task

Status: active
Result: BLOCKED

## Objective

Bloqueado a la espera de aprobacion humana.
"""


def test_pass_without_evidence_is_flagged():
    mod = _load_health_module()
    missing = mod.pass_result_missing_evidence(_PASS_NO_EVIDENCE)
    assert missing, "un PASS sin comandos ni artefactos debe senalarse"


def test_pass_with_commands_and_artifacts_is_accepted():
    mod = _load_health_module()
    assert mod.pass_result_missing_evidence(_PASS_WITH_EVIDENCE) == []


def test_blocked_result_does_not_require_evidence():
    # BLOCKED es precisamente el resultado honesto cuando falta evidencia:
    # exigirsela lo volveria imposible de declarar.
    mod = _load_health_module()
    assert mod.pass_result_missing_evidence(_BLOCKED_NO_EVIDENCE) == []


def test_live_current_task_satisfies_its_own_evidence_contract():
    # El archivo real del repositorio debe cumplir la regla que impone.
    mod = _load_health_module()
    text = (ROOT / ".claude/automation/runtime/current-task.md").read_text(
        encoding="utf-8")
    assert mod.pass_result_missing_evidence(text) == []


# ---------------------------------------------------------------------------
# El CI estuvo ROJO 75 runs seguidos (2026-08-06 a 2026-09-05) y este mismo
# script contestaba "ok". No fallo la deteccion: nada MIRABA. Estos tests fijan
# que ahora mira, y --lo que importa mas-- que un CI rojo es ERROR y que "no se
# pudo comprobar" no se confunde con "esta bien".
# ---------------------------------------------------------------------------

def _health_con_gh(monkeypatch, *, returncode=0, stdout="", stderr="", boom=None):
    """Carga el modulo de salud con `gh` simulado."""
    health = _load_health_module()
    import subprocess as _sp

    # El ORIGINAL, capturado antes de parchear: `health.subprocess` es el modulo
    # global, asi que delegar en `_sp.run` dentro del doble se llamaria a si
    # mismo (RecursionError, visto al escribir esto).
    real_run = _sp.run

    def fake_run(cmd, *a, **kw):
        if cmd and cmd[0] == "gh":
            if boom is not None:
                raise boom
            return _sp.CompletedProcess(cmd, returncode, stdout, stderr)
        return real_run(cmd, *a, **kw)  # git y demas, sin tocar

    monkeypatch.setattr(_sp, "run", fake_run)
    return health


def _run_json(conclusion, *, status="completed", created="2026-09-05T07:06:00Z"):
    return json.dumps([{"conclusion": conclusion, "status": status,
                        "createdAt": created}])


def test_a_red_ci_is_an_error_not_a_warning(monkeypatch):
    """La decision que este candado protege. Degradarlo a aviso repetiria el
    fallo en otra forma: con el CI rojo NADA se integra con garantias."""
    health = _health_con_gh(monkeypatch, stdout=_run_json("failure"))
    assert health.ci_status()[0] == "failure"
    report = json.loads(_capturar(health))
    assert report["facts"]["ci_main"] == "failure"
    assert any("ROJO" in e for e in report["errors"])
    assert report["status"] == "error"


def test_a_green_ci_raises_nothing(monkeypatch):
    """Discriminacion: el aviso solo aparece cuando toca."""
    health = _health_con_gh(monkeypatch, stdout=_run_json("success"))
    report = json.loads(_capturar(health))
    assert report["facts"]["ci_main"] == "success"
    assert not any("CI" in e for e in report["errors"])


def test_an_unverifiable_ci_is_not_taken_as_healthy(monkeypatch):
    """Sin `gh`, sin auth o sin red, la respuesta honesta es "no lo se", no
    "esta bien". Un health check que calla ante la duda es como el que no
    miraba."""
    health = _health_con_gh(monkeypatch, boom=FileNotFoundError("gh"))
    estado, _ = health.ci_status()
    assert estado == "no_verificable"
    report = json.loads(_capturar(health))
    assert any("sin confirmar" in w for w in report["warnings"])


def test_gh_failure_is_unverifiable_not_green(monkeypatch):
    health = _health_con_gh(monkeypatch, returncode=1, stderr="gh: not logged in")
    assert health.ci_status() == ("no_verificable", "gh: not logged in")


def test_a_running_ci_is_neither_green_nor_red(monkeypatch):
    health = _health_con_gh(monkeypatch,
                            stdout=_run_json(None, status="in_progress"))
    assert health.ci_status()[0] == "en_curso"


def _capturar(health) -> str:
    """`main()` imprime el informe; se captura para poder aseverarlo."""
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        health.main()
    return buf.getvalue()
