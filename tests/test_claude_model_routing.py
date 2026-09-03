from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def cita_el_modelo(texto: str, model_id: str) -> bool:
    """True solo si `model_id` aparece como TOKEN COMPLETO, no como prefijo.

    `assert "claude-fable-5" in docs` es una comprobacion por SUBCADENA, y por
    eso no vio la deriva del 2026-09-03: `docs/MODEL-ROUTING.md` habia pasado a
    decir `claude-fable-5.1` -- un identificador que no existe en el catalogo de
    Anthropic -- en sus cinco apariciones, incluida la linea ejecutable
    `claude --model claude-fable-5.1`. El ID correcto ya no aparecia suelto en
    ninguna parte del fichero y aun asi las 33 aserciones pasaban en verde,
    porque "claude-fable-5" es prefijo de "claude-fable-5.1".

    Es exactamente el modo de fallo que la cuarta punta del candado existe para
    impedir, asi que la comprobacion se hace por token: se rechaza cualquier
    sufijo formado por caracteres de identificador, punto o guion.
    """
    return re.search(rf"{re.escape(model_id)}(?![\w.-])", texto) is not None


# El clasificador dejo de ser un hook el 2026-09-01: nunca estuvo cableado
# (`settings.json` solo declara PostToolUse y Stop), asi que estos tests
# validaban en verde codigo que no se ejecutaba. La logica sobrevive como
# modulo consumido bajo demanda por `/route-task`; lo que se retiro es el
# `main()` que emitia el JSON de `UserPromptSubmit`.
SPEC = importlib.util.spec_from_file_location(
    "route_classifier", ROOT / ".claude/automation/route_classifier.py"
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
    # Four-way lock: settings.json, MODEL_ROUTING.md, this literal AND
    # docs/MODEL-ROUTING.md (test_docs_model_routing_is_the_fourth_prong_of_the_lock)
    # must agree. Config/doc drift is the failure this repo keeps hitting
    # (pick_mode 07-31, model 08-04, and this very change on 08-18, que se
    # aplico a settings.json y model-routing.json pero no a la politica ni
    # aqui). La cuarta punta se anadio el 2026-09-01: docs/MODEL-ROUTING.md
    # participo en KI-021 -- este mismo comentario lo nombraba como una de las
    # puntas que derivaron -- y sin embargo el candado nunca lo comprobo; su
    # linea 75 siguio afirmando "model": "sonnet" (residuo del 2026-08-18)
    # durante dos correcciones sucesivas sin que nada lo señalara. El check es
    # exacto a proposito: cambiar el modelo principal es un acto deliberado.
    settings = json.loads(
        (ROOT / ".claude/settings.json").read_text(encoding="utf-8")
    )
    # Main conversation model: claude-opus-5 by explicit human decision 2026-08-30
    # (supersedes claude-fable-5 2026-08-24, que superseduo a sonnet 2026-08-18).
    # Separate from the ROUTE default below, which stays sonnet -- normal work is
    # routed to sonnet ("Prefer Sonnet for normal work"); only the interactive
    # settings.json model changed.
    #
    # claude-opus-5 es el PUNTO DE PARTIDA, no el techo. El techo es
    # claude-fable-5, reservado para maxima capacidad de razonamiento
    # (b3f9cfb, 2026-08-30). Este comentario afirmaba lo contrario -- que Fable
    # habia salido de la jerarquia -- y sobrevivio a esa correccion,
    # contradiciendo a las aserciones de mas abajo en este mismo fichero.
    # Corregido el 2026-09-01 por la auditoria integral.
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


def test_policy_never_claims_opus_is_also_the_ceiling():
    """El techo es claude-fable-5. Opus 5 es solo el punto de partida.

    Los candados existentes exigian la PRESENCIA de las frases correctas, pero
    nada impedia que otra seccion del mismo fichero afirmase lo contrario -- y
    eso fue exactamente lo que paso: `b3f9cfb` (2026-08-30) restituyo Fable 5
    como destino del escalado y actualizo el reparto operativo, pero dejo vivo
    en "Politica autorizada" un parrafo que decia que Opus 5 era "a la vez el
    punto de partida y el techo". El fichero se contradijo a si mismo durante
    dos dias sin que nada lo señalara.

    Un principio rector con dos lecturas opuestas dentro del mismo documento no
    es un principio: es una ambiguedad que se resuelve a conveniencia. Este test
    fija la ausencia, no solo la presencia.
    """
    policy = (ROOT / ".claude/automation/MODEL_ROUTING.md").read_text(
        encoding="utf-8"
    )
    prohibidas = (
        "a la vez el punto de partida **y el techo**",
        "a la vez el defecto Y el techo",
        "ya no hay un escalon por encima",
        "ya no hay un escalón por encima",
        "sacó a `claude-fable-5` de la jerarquía",
    )
    presentes = [f for f in prohibidas if f in policy]
    assert presentes == [], (
        "la politica vuelve a afirmar que Opus 5 es el techo, contradiciendo al "
        f"reparto operativo y al principio rector: {presentes}")
    # Y la afirmacion positiva correspondiente, para que la ausencia de arriba no
    # se pueda satisfacer borrando la seccion entera.
    assert "El techo es\n  `claude-fable-5`" in policy or "El techo es `claude-fable-5`" in policy


def test_claude_md_states_the_principle_as_governing_not_advisory():
    """`CLAUDE.md` es lo que se carga en cada sesion. Si ahi el principio figura
    como "advisory only", el modelo que lo lee no tiene por que aplicarlo -- y
    CLAUDE.md tiene precedencia sobre las skills. Orden del operador
    (2026-09-01): es EL PRINCIPIO RECTOR, no una sugerencia.

    El matiz tecnico que si es cierto -- que editar CLAUDE.md no cambia el
    modelo activo de la sesion -- se conserva, porque es un hecho del harness y
    no una rebaja de la politica.
    """
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "advisory only" not in text, (
        "CLAUDE.md rebaja el principio rector a consejo")
    assert "governing principle" in text.lower()
    assert cita_el_modelo(text, "claude-fable-5")
    # El hecho del harness sobrevive a la subida de rango.
    assert "does not change the active model" in text or \
           "itself changes the active model" in text


def test_docs_model_routing_is_the_fourth_prong_of_the_lock():
    """Cuarta punta del candado (2026-09-01). El candado se autodenominaba
    "three-way" y su propio comentario nombraba a docs/MODEL-ROUTING.md como una
    de las puntas que derivaron en KI-021 -- pero nunca lo comprobo. Resultado:
    la linea 75 del doc siguio afirmando `"model": "sonnet"` (residuo del
    2026-08-18) a traves de DOS correcciones sucesivas del resto de puntas,
    incluida b3f9cfb, sin que nada lo señalara.

    El valor se DERIVA de settings.json en vez de duplicarse: si el modelo
    principal cambia, este assert obliga a actualizar la cara de usuario en el
    mismo acto, que es exactamente la deriva que se acaba de encontrar.
    """
    settings = json.loads(
        (ROOT / ".claude/settings.json").read_text(encoding="utf-8")
    )
    docs = (ROOT / "docs/MODEL-ROUTING.md").read_text(encoding="utf-8")
    # El doc debe citar el modelo REAL del proyecto...
    assert f'"model": "{settings["model"]}"' in docs
    # ...y no puede quedar viva ninguna afirmacion del valor superseduo.
    assert '"model": "sonnet"' not in docs, (
        "docs/MODEL-ROUTING.md vuelve a afirmar el modelo de 2026-08-18")
    # Coherencia con el reparto operativo: Fable 5 es el destino del escalado,
    # no el punto de partida; sin estas frases el doc puede volver a contar una
    # politica distinta de la de .claude/automation/MODEL_ROUTING.md.
    assert cita_el_modelo(docs, "claude-fable-5"), (
        "docs/MODEL-ROUTING.md no cita `claude-fable-5` como token completo; "
        "un sufijo como `claude-fable-5.1` no es un modelo que exista")
    assert "destino del disparador de escalado" in docs
    assert "no el punto de partida" in docs


def test_policy_declares_the_dispatch_mechanism():
    """REGLA DE DESPACHO (2026-09-01). La politica decia QUE modelo corresponde
    a cada clase de tarea pero no POR QUE MECANISMO se aplica, y por eso no se
    aplicaba nunca: 26 de 27 subagentes declaraban `model: opus` y nadie pasaba
    un modelo al delegar. El mecanismo real es el parametro `model` del Agent
    tool, que tiene precedencia sobre el frontmatter; las cinco clases del
    disparador se despachan con el a claude-fable-5. Sin esta seccion el techo
    de la politica es inalcanzable en la practica.
    """
    policy = (ROOT / ".claude/automation/MODEL_ROUTING.md").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(policy.split())
    assert "## REGLA DE DESPACHO" in policy
    assert "parámetro `model` de la herramienta `Agent`" in normalized
    assert "`sonnet | opus | haiku | fable`" in normalized
    assert "precedencia sobre el frontmatter" in normalized
    # Las cinco clases van a Fable 5 y por este mecanismo, no por la tabla.
    assert "Las cinco clases del disparador de escalado van a `claude-fable-5`" \
        in normalized
    assert 'se despacha con `model: "fable"`' in normalized
    assert "solo esta regla despacha a Fable 5" in normalized


def test_classifier_carries_no_model_rules_of_its_own():
    """El clasificador devuelve la RUTA. No decide modelo, ni lo reinterpreta.

    El 2026-09-01 se encontro en el entonces `route-model.py` un downgrade
    oculto opus->sonnet cuando `priority < 115`: una tercera regla de modelo que
    no estaba ni en la politica ni en la tabla ni en ningun doc. Era codigo
    muerto (las tres rutas opus tienen prioridad >= 115), pero habria degradado
    en silencio cualquier ruta opus futura de prioridad baja, contradiciendo el
    literal OPUS_ROUTES de este mismo fichero.

    Al retirarse el hook, el modulo se quedo SOLO con `classify` y
    `find_config_path`: ya no hay ninguna linea que lea, escriba o transforme un
    modelo. Este test fija esa ausencia, que es una garantia mas fuerte que la
    anterior -- entonces habia que contar ocurrencias de `recommended_model`
    para detectar una reinterpretacion; ahora cualquier mencion a un modelo en
    este fichero es sospechosa por definicion.
    """
    mod = (ROOT / ".claude/automation/route_classifier.py").read_text(encoding="utf-8")
    codigo = "\n".join(
        ln for ln in mod.splitlines()
        if not ln.lstrip().startswith("#")
    ).split('"""')[-1]          # descarta el docstring de modulo y los comentarios

    assert "115" not in codigo, "el clasificador recupero el umbral de downgrade"
    for termino in ("recommended_model", "opus", "sonnet", "haiku", "fable"):
        assert termino not in codigo, (
            f"el clasificador volvio a razonar sobre modelos ({termino!r}); "
            "la tabla es la unica fuente de modelo por ruta y el despacho lo "
            "hace el parametro `model` del Agent tool")


def test_the_route_classifier_is_not_wired_as_a_hook():
    """Retirada del hook (2026-09-01, decision del operador).

    El hook `UserPromptSubmit` nunca estuvo cableado: `settings.json` solo
    declara `PostToolUse` y `Stop`. Durante meses las 24 rutas no se ejecutaron
    mientras estos tests las validaban en verde -- codigo muerto con candado.
    Se retiro el lanzador y sobrevivio la logica, que se consume bajo demanda
    desde `/route-task`.

    Este test fija las dos mitades de esa decision para que no se deshaga a
    medias: el fichero del hook no vuelve, y el modulo no recupera un `main()`
    que lo convierta otra vez en algo invocable como hook.
    """
    assert not (ROOT / ".claude/hooks/route-model.py").exists(), (
        "el hook retirado reaparecio; si se quiere reactivar hay que cablear "
        "tambien UserPromptSubmit en settings.json -- las dos cosas")
    mod = (ROOT / ".claude/automation/route_classifier.py").read_text(encoding="utf-8")
    assert "def main(" not in mod
    assert "UserPromptSubmit" not in mod.split('"""')[-1]


# Excepciones declaradas: hooks que existen a proposito SIN estar cableados.
# Vacio hoy. Anadir una ruta aqui es una decision consciente que queda escrita;
# olvidarse de cablear, no. Esa es toda la diferencia que este candado protege.
HOOKS_NO_CABLEADOS_A_PROPOSITO: frozenset[str] = frozenset()


def test_every_hook_script_is_actually_wired_in_settings():
    """Un hook que existe pero no esta cableado es codigo muerto con candado.

    Es la MISMA averia que `test_the_route_classifier_is_not_wired_as_a_hook`
    documenta para `route-model.py` -- "durante meses las 24 rutas no se
    ejecutaron mientras estos tests las validaban en verde" --, y volvio a pasar
    el 2026-09-03 (auditoria integral, AUD-HIGH-001): se escribieron
    `require-dispatch-model.sh`, `crossreview-on-stop.sh` y
    `mark-crossreview-pending.sh`, se preparo hasta la linea de `.gitignore` del
    centinela, y ninguno se registro en `settings.json`. Los tres afirmaban en su
    cabecera cerrar un control -- KI-023 y la revision cruzada de codigo de
    riesgo -- y ninguno se ejecutaba nunca.

    Aquel test fija UNA instancia; este cierra la CLASE: cualquier `.sh` en
    `.claude/hooks/` debe aparecer en el `settings.json` VERSIONADO, o figurar en
    `HOOKS_NO_CABLEADOS_A_PROPOSITO`.

    Se comprueba contra `settings.json` y no contra `settings.local.json` a
    proposito: el local esta en `.gitignore` (linea 26), asi que no existe en CI.
    Un hook cableado solo ahi seguiria siendo un control que no viaja con el
    repositorio -- exactamente el fallo que esto persigue.
    """
    hooks_dir = ROOT / ".claude/hooks"
    settings = (ROOT / ".claude/settings.json").read_text(encoding="utf-8")
    presentes = {p.name for p in hooks_dir.glob("*.sh")}
    assert presentes, "no se encontro ningun hook: la ruta de busqueda cambio"
    huerfanos = sorted(n for n in presentes - HOOKS_NO_CABLEADOS_A_PROPOSITO
                       if n not in settings)
    assert not huerfanos, (
        f"hooks presentes en {hooks_dir} pero NO cableados en "
        f".claude/settings.json: {huerfanos}. Un hook sin cablear no se ejecuta "
        "jamas: cablealo, o declaralo en HOOKS_NO_CABLEADOS_A_PROPOSITO "
        "explicando por que existe sin estar activo.")


def test_settings_hooks_reference_only_existing_scripts():
    """El reverso: ningun `settings.json` que apunte a un hook inexistente.

    Sin esto, renombrar o borrar un `.sh` deja una entrada colgada que falla en
    silencio en cada disparo (el harness no puede ejecutar lo que no existe) y
    el control se pierde igual que si nunca se hubiera cableado.
    """
    cfg = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
    referenciados = [
        c["command"].rsplit("/", 1)[-1].strip('"')
        for grupos in cfg.get("hooks", {}).values()
        for g in grupos for c in g.get("hooks", [])
        if c.get("type") == "command" and ".claude/hooks/" in c.get("command", "")
    ]
    assert referenciados, "settings.json dejo de cablear hooks del proyecto"
    faltantes = sorted(n for n in set(referenciados)
                       if not (ROOT / ".claude/hooks" / n).exists())
    assert not faltantes, (
        f"settings.json cablea hooks que no existen en disco: {faltantes}")
