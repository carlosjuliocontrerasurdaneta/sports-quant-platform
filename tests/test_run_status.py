"""Alerta de fallo del run diario (auditoria 2026-07-29, S-1).

El 2026-07-29 el run de produccion fallo (`LastTaskResult = 1`) y nadie se entero
durante 24 h: los BAT propagaban el codigo de salida correctamente, pero no habia
ningun consumidor. Estos tests fijan el contrato del centinela que cierra ese
hueco: los BAT lo escriben al fallar y lo borran al tener exito, y el health check
lo eleva a ERROR.
"""
from __future__ import annotations

import json

import pytest

from sqp.config import ROOT
from sqp.monitoring.run_status import (STATUS_FILENAME, clear_run_status,
                                       stage_path,
                                       read_run_status, record_run_failure)


# --- Escritura del centinela --------------------------------------------------

def test_record_failure_writes_sentinel(tmp_path):
    record_run_failure(tmp_path, stage="run", exit_code=1)
    assert stage_path(tmp_path, "run").exists()


def test_sentinel_captures_stage_and_exit_code(tmp_path):
    record_run_failure(tmp_path, stage="settle", exit_code=3)
    st = read_run_status(tmp_path)
    assert st is not None
    assert st["failed"] is True
    assert st["stage"] == "settle"
    assert st["exit_code"] == 3


def test_sentinel_records_utc_timestamp(tmp_path):
    record_run_failure(tmp_path, stage="run", exit_code=1)
    ts = read_run_status(tmp_path)["failed_at"]
    # ISO-8601 UTC: el resto del proyecto compara timestamps como texto.
    assert ts.endswith("Z") and len(ts) == 20 and ts[4] == "-" and ts[10] == "T"


def test_sentinel_is_valid_json(tmp_path):
    """Desde B-7 (2026-09-09) cada etapa tiene su PROPIO fichero, con la entrada
    plana dentro. Antes se indexaban por etapa dentro de un unico JSON, y antes
    de A-02 (2026-08-31) ni eso: sobrescribir el fichero entero borraba el fallo
    de la otra etapa."""
    record_run_failure(tmp_path, stage="run", exit_code=1)
    raw = stage_path(tmp_path, "run").read_text(encoding="utf-8")
    assert json.loads(raw)["failed"] is True
    assert json.loads(raw)["stage"] == "run"


def test_record_failure_creates_logs_dir_when_missing(tmp_path):
    """Un repo recien clonado no tiene logs/; el centinela no debe reventar."""
    record_run_failure(tmp_path, stage="run", exit_code=1)
    assert (tmp_path / "logs").is_dir()


# --- Borrado al tener exito ---------------------------------------------------

def test_clear_removes_an_existing_sentinel(tmp_path):
    record_run_failure(tmp_path, stage="run", exit_code=1)
    clear_run_status(tmp_path)
    assert read_run_status(tmp_path) is None


def test_clear_is_idempotent_without_sentinel(tmp_path):
    clear_run_status(tmp_path)  # no debe lanzar
    clear_run_status(tmp_path)
    assert read_run_status(tmp_path) is None


# --- Borrado por etapa --------------------------------------------------------
#
# El centinela solo se limpiaba desde DIARIO_COMPLETO.bat. Recuperarse a mano con
# el orden que manda el proyecto (SETTLE_ALL + RUN_DIARIO_ALL) dejaba el banner
# rojo "el ultimo run FALLO" sobre un tablero ya sano: paso el 2026-08-27. Una
# alarma que sigue sonando despues del arreglo se aprende a ignorar.

def test_clear_by_stage_removes_only_its_own_failure(tmp_path):
    record_run_failure(tmp_path, stage="run", exit_code=1)
    assert clear_run_status(tmp_path, "run") is True
    assert read_run_status(tmp_path) is None


def test_clear_by_stage_respects_the_other_stage(tmp_path):
    """Arreglar el run no arregla una liquidacion rota: son averias distintas,
    y la de liquidacion ABORTA el dia siguiente."""
    record_run_failure(tmp_path, stage="settle", exit_code=1)
    assert clear_run_status(tmp_path, "run") is False
    assert (read_run_status(tmp_path) or {})["stage"] == "settle"


def test_clear_without_stage_removes_any_failure(tmp_path):
    record_run_failure(tmp_path, stage="settle", exit_code=1)
    assert clear_run_status(tmp_path) is True
    assert read_run_status(tmp_path) is None


def test_clear_reports_when_there_was_nothing_to_clear(tmp_path):
    assert clear_run_status(tmp_path) is False
    assert clear_run_status(tmp_path, "run") is False


# --- Lectura ------------------------------------------------------------------

def test_read_returns_none_when_no_sentinel(tmp_path):
    assert read_run_status(tmp_path) is None


def test_read_returns_none_on_corrupt_sentinel(tmp_path):
    """Un centinela corrupto NO debe tumbar el health check: degrada a 'sin
    fallo conocido' en lugar de propagar la excepcion."""
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / STATUS_FILENAME).write_text("{ no es json", encoding="utf-8")
    assert read_run_status(tmp_path) is None


# --- Integracion con el health check ------------------------------------------

def _error_de_etapa(root) -> str:
    """El error del centinela dentro del informe de salud, o "".

    Se localiza por el marcador estable `FALLIDA`, no por la prosa. El assert
    anterior exigia la subcadena "run diario", que dejo de ser cierta cuando el
    centinela paso a cubrir etapas de FUERA de la cadena diaria (AUD-MED-003):
    llamarle "run diario" a un fallo de la validacion OOS mensual manda a mirar
    el sitio equivocado. Fijar la prosa del aviso ademas no comprobaba nada util
    -- el mismo patron de assert por subcadena que este repositorio ya se ha
    encontrado antes."""
    from sqp.monitoring.health import generate_health_report
    for e in generate_health_report(root).get("errors", []):
        if "FALLIDA" in e:
            return e
    return ""


def test_health_report_is_error_when_last_run_failed(tmp_path):
    from sqp.monitoring.health import generate_health_report
    record_run_failure(tmp_path, stage="run", exit_code=1)
    assert generate_health_report(tmp_path)["status"] == "ERROR"
    assert _error_de_etapa(tmp_path) != ""


def test_health_error_names_the_failed_stage(tmp_path):
    record_run_failure(tmp_path, stage="settle", exit_code=1)
    assert "settle" in _error_de_etapa(tmp_path)


def test_health_error_names_the_bat_to_rerun(tmp_path):
    """Un aviso que no dice como recuperarse manda a buscar, y buscar es lo que
    no se hace cuando el aviso llega solo. Una etapa por cadena de produccion:
    con `stage` libre, un nombre sin traduccion daria un aviso mudo."""
    for etapa, bat in (("settle", "SETTLE_ALL.bat"),
                       ("run", "RUN_DIARIO_ALL.bat"),
                       ("validate_oos", "VALIDATE_OOS.bat"),
                       ("backfill", "BACKFILL_ALL.bat"),
                       ("capture_close", "CAPTURE_CLOSE.bat"),
                       ("refresh_ml", "REFRESH_ML.bat")):
        clear_run_status(tmp_path)
        record_run_failure(tmp_path, stage=etapa, exit_code=1)
        error = _error_de_etapa(tmp_path)
        assert etapa in error and bat in error, f"{etapa}: {error!r}"


def test_every_cli_stage_translates_to_a_bat(tmp_path):
    """Las dos listas viven en modulos distintos (`scripts/run_status.py` y
    `sqp.monitoring.health`) y solo un test puede impedir que deriven: una etapa
    aceptada por el CLI y sin BAT asociado produce un aviso que no dice que
    re-ejecutar."""
    import importlib.util
    from sqp.monitoring.health import _BAT_POR_ETAPA
    spec = importlib.util.spec_from_file_location(
        "run_status_cli", ROOT / "scripts" / "run_status.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert set(mod.STAGES) == set(_BAT_POR_ETAPA)


def test_health_report_has_no_run_error_when_sentinel_absent(tmp_path):
    assert _error_de_etapa(tmp_path) == ""


# --- Banner del dashboard -----------------------------------------------------

def test_dashboard_banner_is_empty_without_failure(tmp_path):
    from sqp.audit.html_report import _run_alert_banner
    assert _run_alert_banner(tmp_path) == ""


def test_dashboard_banner_shows_stage_and_time(tmp_path):
    from sqp.audit.html_report import _run_alert_banner
    record_run_failure(tmp_path, stage="run", exit_code=1)
    banner = _run_alert_banner(tmp_path)
    assert "run" in banner
    assert read_run_status(tmp_path)["failed_at"] in banner
    assert "FALL" in banner.upper()


def test_dashboard_banner_escapes_its_content(tmp_path):
    """El centinela es un archivo del disco: su contenido no se inyecta crudo."""
    from sqp.audit.html_report import _run_alert_banner
    record_run_failure(tmp_path, stage="run", exit_code=1)
    p = stage_path(tmp_path, "run")
    data = json.loads(p.read_text(encoding="utf-8"))
    data["stage"] = "<script>alert(1)</script>"
    p.write_text(json.dumps(data), encoding="utf-8")
    banner = _run_alert_banner(tmp_path)
    assert "<script>" not in banner
    assert "&lt;script&gt;" in banner


# --- Contrato con los BAT -----------------------------------------------------

@pytest.mark.parametrize("bat", ["DIARIO_COMPLETO.bat", "RUN_DIARIO_ALL.bat",
                                 "SETTLE_ALL.bat"])
def test_bat_invokes_the_sentinel_helper(bat):
    """Los tres BAT de produccion deben registrar el fallo. Sin esto el centinela
    existe pero nadie lo escribe, que es exactamente el fallo original."""
    from sqp.config import ROOT
    text = (ROOT / bat).read_text(encoding="utf-8", errors="replace")
    assert "run_status" in text, f"{bat} no registra el estado del run"


def test_diario_completo_clears_sentinel_on_success():
    from sqp.config import ROOT
    text = (ROOT / "DIARIO_COMPLETO.bat").read_text(encoding="utf-8", errors="replace")
    assert "--clear" in text, "DIARIO_COMPLETO.bat no limpia el centinela al terminar OK"


# --- A-02: el fallo de una etapa no puede borrar el de la otra ----------------

def test_a02_settle_failure_survives_a_later_run_failure_and_its_clear(tmp_path):
    """La secuencia que dejaba la liquidacion rota y el tablero en verde.

    `record_run_failure` sobrescribia el fichero entero, asi que el fallo de
    `settle` desaparecia al registrarse el de `run`; despues
    `RUN_DIARIO_ALL.bat --clear --only-stage run` encontraba `stage == "run"`,
    daba el visto bueno y borraba el centinela. Resultado: liquidacion nunca
    ejecutada, health en verde y banner apagado, rompiendo el contrato
    SETTLE->RUN de CLAUDE.md (auditoria 2026-08-31, A-02).
    """
    record_run_failure(tmp_path, stage="settle", exit_code=1)
    record_run_failure(tmp_path, stage="run", exit_code=1)
    assert clear_run_status(tmp_path, "run") is True

    st = read_run_status(tmp_path)
    assert st is not None, "el fallo de liquidacion se perdio"
    assert st["stage"] == "settle"
    assert st["exit_code"] == 1


def test_a02_settle_failure_wins_when_both_stages_are_broken(tmp_path):
    """Con las dos rotas manda la liquidacion: aborta el run del dia siguiente."""
    record_run_failure(tmp_path, stage="run", exit_code=2)
    record_run_failure(tmp_path, stage="settle", exit_code=3)
    st = read_run_status(tmp_path)
    assert st["stage"] == "settle" and st["exit_code"] == 3
    assert st["stages"] == ["run", "settle"]


def test_a02_clearing_both_stages_removes_the_sentinel(tmp_path):
    record_run_failure(tmp_path, stage="settle", exit_code=1)
    record_run_failure(tmp_path, stage="run", exit_code=1)
    assert clear_run_status(tmp_path, "run") is True
    assert clear_run_status(tmp_path, "settle") is True
    assert read_run_status(tmp_path) is None
    assert not (tmp_path / "logs" / STATUS_FILENAME).exists()


def test_a02_legacy_flat_sentinel_is_still_honoured(tmp_path):
    """Un centinela escrito por la version anterior debe seguir avisando tras
    actualizar, o el arreglo estrenaria una ventana ciega."""
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / STATUS_FILENAME).write_text(json.dumps({
        "failed": True, "stage": "settle", "exit_code": 1,
        "failed_at": "2026-08-30T11:00:00Z"}), encoding="utf-8")
    st = read_run_status(tmp_path)
    assert st is not None and st["stage"] == "settle"
    assert clear_run_status(tmp_path, "run") is False   # no es su etapa
    assert clear_run_status(tmp_path, "settle") is True


# --- Contrato del orquestador diario (KI-036) ---------------------------------
#
# Los .bat no los cubre ninguna puerta del CI: ni ruff, ni mypy, ni pytest los
# ejecutan. Estos tests leen el fichero y fijan las propiedades estructurales que
# importan, que es lo mas que se puede comprobar sin lanzar produccion.

def _diario() -> str:
    return (ROOT / "DIARIO_COMPLETO.bat").read_text(encoding="utf-8", errors="ignore")


def test_el_orquestador_no_borra_etapas_que_no_arregla():
    """REGRESION del 2026-09-06. `--clear` a secas borra el centinela ENTERO.

    Era correcto cuando solo existian `settle` y `run` y este bat ejecutaba las
    dos. Al ampliar el centinela a siete etapas ese borrado pasa a apagar en
    silencio las alarmas que el bat NO arregla: un run diario correcto habria
    matado el aviso de `validate_oos` -- fallado desde el 2026-09-01 y sin
    reintento hasta el 2026-10-01 -- al dia siguiente de crearlo.
    """
    bat = _diario()
    ejecutables = [ln.strip() for ln in bat.splitlines()
                   if not ln.strip().upper().startswith("REM")]
    clears = [ln for ln in ejecutables if "run_status.py --clear" in ln]
    assert clears, "el orquestador debe limpiar el centinela al terminar bien"
    for ln in clears:
        assert "--only-stage" in ln, f"borrado sin ambito: {ln!r}"


def test_el_guard_de_arbol_limpio_corre_antes_de_liquidar():
    """Abortar solo no cuesta nada ANTES de tocar datos. Si el guard corriera
    despues de `SETTLE_ALL`, la liquidacion ya habria escrito."""
    bat = _diario()
    guard = bat.index("SQP_TREE_DIRTY")
    settle = bat.index("call \"%~dp0SETTLE_ALL.bat\"")
    assert guard < settle, "el guard debe preceder a la liquidacion"


def test_el_guard_tiene_escape_documentado_y_falla_abierto_sin_git():
    """Dos propiedades que lo hacen operable: se puede saltar a proposito para
    recuperacion, y la AUSENCIA de git no detiene el pipeline del dinero -- "no
    se puede comprobar" no es "esta sucio"."""
    bat = _diario()
    assert "SQP_SKIP_TREE_GUARD" in bat
    assert "git rev-parse --git-dir" in bat, "debe detectar si git esta disponible"
    i_rev = bat.index("git rev-parse --git-dir")
    i_status = bat.index("git status --porcelain -- src scripts configs")
    assert i_rev < i_status, "la comprobacion de git va antes de usarlo"


def test_el_guard_solo_vigila_codigo_que_produccion_ejecuta():
    """El ambito NO puede incluir los ficheros del operador: estan casi siempre
    modificados y bloquearian el run todos los dias, que es exactamente como se
    aprende a saltarse un guard."""
    bat = _diario()
    linea = next(ln for ln in bat.splitlines()
                 if "git status --porcelain -- src scripts configs" in ln
                 and not ln.strip().upper().startswith("REM"))
    ambito = linea.split("--porcelain --")[1].split("2^>nul")[0].strip()
    assert set(ambito.split()) == {"src", "scripts", "configs", "*.bat"}, ambito


def test_el_aborto_del_guard_queda_registrado():
    """Un aborto que solo se imprime en una consola que nadie mira es invisible,
    que es la enfermedad que esta sesion lleva todo el dia corrigiendo."""
    bat = _diario()
    assert "--fail --stage guard_arbol" in bat
    from sqp.monitoring.health import _BAT_POR_ETAPA
    assert "guard_arbol" in _BAT_POR_ETAPA


# --- El banner tampoco puede depender solo del centinela (AUD-HIGH-002) -------

def _predicciones_viejas(root, dias_atras: float = 3.0):
    import os
    import time
    d = root / "data" / "predictions"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "predictions_mlb.csv"
    p.write_text("event_id\n1\n", encoding="utf-8")
    t = time.time() - dias_atras * 86400
    os.utime(p, (t, t))


def test_el_banner_avisa_de_un_pipeline_parado_sin_centinela(tmp_path):
    """El tablero mostraba picks de hace dos dias con el banner APAGADO porque
    nadie habia escrito el centinela. Ahora la edad del ultimo artefacto basta."""
    from sqp.audit.html_report import _run_alert_banner
    _predicciones_viejas(tmp_path)
    assert not (tmp_path / "logs" / STATUS_FILENAME).exists()
    banner = _run_alert_banner(tmp_path)
    assert "NO ha generado nada" in banner
    assert "DIARIO_COMPLETO.bat" in banner


def test_el_banner_de_parada_precede_al_de_etapa(tmp_path):
    """"No ha corrido" describe la situacion mejor que cualquier etapa concreta,
    y ademas cubre el caso en que no hay centinela."""
    from sqp.audit.html_report import _run_alert_banner
    _predicciones_viejas(tmp_path)
    record_run_failure(tmp_path, stage="settle", exit_code=1)
    assert "NO ha generado nada" in _run_alert_banner(tmp_path)


def test_con_el_pipeline_al_dia_el_banner_vuelve_a_ser_el_de_etapa(tmp_path):
    from sqp.audit.html_report import _run_alert_banner
    _predicciones_viejas(tmp_path, dias_atras=0.1)
    record_run_failure(tmp_path, stage="settle", exit_code=1)
    banner = _run_alert_banner(tmp_path)
    assert "NO ha generado nada" not in banner
    assert "settle" in banner


# --- El orquestador tiene que dejar rastro (AUD-MED-001, auditoria 2026-09-08) -

def _diario() -> str:
    from sqp.config import ROOT
    return (ROOT / "DIARIO_COMPLETO.bat").read_text(encoding="utf-8", errors="replace")


def test_diario_completo_escribe_en_un_log_propio():
    """No escribia NADA: todos sus echo iban a la consola, y bajo el Programador
    de tareas no hay consola. El fallo del 2026-09-07 (0x1 a las 12:00) no dejo
    ni una linea, y por eso su causa raiz es hoy indeterminable."""
    t = _diario()
    assert r"logs\diario_completo.log" in t
    assert ":log" in t, "no existe la subrutina que escribe en consola Y fichero"


def test_las_tres_ramas_de_error_dejan_rastro():
    """Son las que mas importan: si el aborto no se escribe, el fallo es
    indiagnosticable justo cuando hay que diagnosticarlo."""
    t = _diario()
    for etiqueta in (":error_arbol", ":error_settle", ":error_run"):
        i = t.index("\n" + etiqueta)
        fin = t.find("exit /b 1", i)
        bloque = t[i:fin]
        assert "call :log" in bloque, f"{etiqueta} no escribe en el log"
        assert "diario_completo.log" in bloque, (
            f"{etiqueta} no manda al log la salida de sus diagnosticos")


def test_la_redireccion_del_log_precede_al_echo():
    """`echo %~1>> fichero` se come el ultimo caracter si es un digito: cmd lo
    lee como descriptor. Las lineas del aviso de arbol atrasado terminan en un
    SHA, que acaba en digito la mitad de las veces."""
    t = _diario()
    assert r">>logs\diario_completo.log echo %~1" in t
    # Se ignoran los REM: el comentario del BAT explica el defecto citando el
    # idioma malo, y prohibir la cadena prohibiria explicarlo (misma leccion que
    # el escaneo de `.csv.tmp` en test_storage.py).
    codigo = "\n".join(linea for linea in t.splitlines()
                       if not linea.strip().upper().startswith("REM"))
    assert "echo %~1>>" not in codigo


# --- El arbol atrasado tambien avisa (AUD-MED-004, auditoria 2026-09-08) -------

def test_el_guard_comprueba_tambien_si_el_arbol_esta_ATRASADO():
    """Comprobaba solo si estaba SUCIO. El 2026-09-08 este clon iba 2 commits por
    detras de origin/main -- uno de ellos una correccion de codigo publicada
    desde otra sesion -- y nada lo decia. Produccion ejecuta el arbol de trabajo."""
    t = _diario()
    assert "git fetch" in t, "sin fetch se compara contra una referencia obsoleta"
    assert "@{u}" in t
    assert "rev-parse HEAD" in t


def test_el_aviso_distingue_ir_POR_DETRAS_de_ir_POR_DELANTE():
    """Comparar SHA por igualdad confunde dos situaciones opuestas.

    Ir por DELANTE (commits locales sin publicar) es el estado normal entre un
    arreglo y su push, y ahi produccion ejecuta codigo mas NUEVO, no mas viejo:
    avisar seria una alarma diaria y falsa, y una alarma que suena sin motivo es
    una alarma que se aprende a ignorar. Solo importa lo que le FALTA a esta
    maquina, que es `git rev-list --count HEAD..@{u}`.
    """
    t = _diario()
    assert "rev-list --count HEAD.." in t
    assert 'if "%SQP_DETRAS%"=="0" goto :tree_ok' in t
    assert "POR DETRAS" in t


def test_el_aviso_de_arbol_atrasado_NO_aborta():
    """Detener el pipeline del dinero por un commit de documentacion seria un
    modo de fallo nuevo y desproporcionado. Avisa, no aborta."""
    t = _diario()
    i = t.index("POR DETRAS de")
    bloque = t[i:t.index(":tree_ok", i)]
    assert "no aborta" in bloque
    assert "goto :error" not in bloque, (
        "el aviso de arbol atrasado saltaria a una rama de error")


def test_el_fetch_no_puede_bloquear_el_pipeline():
    """Un aviso consultivo no puede parar el pipeline del dinero.

    La primera version acotaba el fetch SOLO con `GIT_HTTP_LOW_SPEED_LIMIT/TIME`,
    y eso limita la velocidad de TRANSFERENCIA HTTP: no cubre la espera de un
    gestor de credenciales ni la duracion total del subproceso. Bajo el
    Programador de tareas no hay escritorio, asi que un git que pida credenciales
    se queda esperando a nadie y bloquea la liquidacion. Lo señalo la revision
    cruzada de Codex (2026-09-08) y era correcto.

    Medido con un `git` que se cuelga 120 s y un plazo de 8 s: aborta a los 8,7 s
    con codigo 124 y el proceso matado; con git real, 0 en 0,9 s.
    """
    t = _diario()
    # 1. Nada interactivo puede quedarse esperando.
    assert "GIT_TERMINAL_PROMPT=0" in t
    assert "GCM_INTERACTIVE=never" in t
    assert "GIT_ASKPASS=" in t
    # 2. Plazo de PARED, no de velocidad de transferencia.
    assert "SQP_FETCH_TIMEOUT_MS" in t
    assert "WaitForExit(" in t
    # 3. Y al agotarse se MATA el proceso, no se deja huerfano.
    assert "$p.Kill()" in t
    # 4. Falla ABIERTO: el codigo del plazo se avisa y se continua.
    i = t.index("if errorlevel 124")
    bloque = t[i:t.index(":tree_ok", i)]
    assert "se continua" in bloque
    assert "goto :error" not in bloque
    # Los limites de velocidad se conservan: abortan una transferencia
    # estancada DENTRO del plazo, que sigue siendo util.
    assert "GIT_HTTP_LOW_SPEED_LIMIT" in t
    assert "GIT_HTTP_LOW_SPEED_TIME" in t


def test_sin_upstream_la_comprobacion_se_salta_sin_fallar():
    """Falla ABIERTO, igual que el guard de arbol sucio: "no se puede comprobar"
    no es "esta atrasado"."""
    t = _diario()
    assert "if not defined SQP_UPSTREAM" in t


# --- Atomicidad del centinela -------------------------------------------------
#
# Auditoria integral 2026-09-08 (segunda pasada). El centinela se escribia con
# `write_text` DIRECTO sobre el destino, sin temporal ni reemplazo atomico. Es
# el unico mecanismo por el que un fallo de cualquier BAT llega al health check
# y al banner del tablero: si el proceso muere a mitad del volcado, queda JSON
# truncado, `_read_stages` lo declara ilegible y devuelve {} -- el fallo recien
# registrado DESAPARECE, y el sistema vuelve a verde con la averia dentro.

def test_una_escritura_truncada_no_deja_el_centinela_ilegible(tmp_path,
                                                              monkeypatch):
    """Simula el corte a mitad del volcado sobre el nombre BUENO.

    Con `write_text` directo eso dejaba JSON truncado: `_read_stages` lo declara
    ilegible, devuelve {} y el fallo recien registrado desaparece. Escribiendo
    en un temporal y reemplazando, el destino nunca esta a medias -- por eso
    aqui ni siquiera se llega a truncar nada."""
    from pathlib import Path as _Path

    real = _Path.write_text

    destinos = {stage_path(tmp_path, e).name for e in ("settle", "run")}

    def trunca(self, data, *a, **kw):
        if self.name in destinos:
            real(self, str(data)[: len(str(data)) // 2], *a, **kw)
            raise RuntimeError("corte a mitad de volcado")
        return real(self, data, *a, **kw)

    monkeypatch.setattr(_Path, "write_text", trunca)
    record_run_failure(tmp_path, stage="settle", exit_code=3)
    record_run_failure(tmp_path, stage="run", exit_code=1)

    for etapa in ("settle", "run"):
        assert json.loads(stage_path(tmp_path, etapa).read_text(
            encoding="utf-8"))["stage"] == etapa
    assert read_run_status(tmp_path) is not None


def test_el_centinela_nunca_se_escribe_directamente_sobre_el_destino(tmp_path,
                                                                    monkeypatch):
    """Contrato, no implementacion: escribir sobre el nombre bueno es lo que
    permite verlo a medias. Cualquier regreso a `write_text` rompe esto."""
    from pathlib import Path as _Path

    real = _Path.write_text
    # Los destinos REALES tras B-7. Comprobar el nombre del fichero unico
    # anterior dejaria la prueba vacia: ya nadie escribe ahi.
    destinos = {stage_path(tmp_path, e).name for e in ("run", "settle")}

    def espia(self, *a, **kw):
        assert self.name not in destinos, (
            f"escritura directa sobre el destino {self.name}")
        return real(self, *a, **kw)

    monkeypatch.setattr(_Path, "write_text", espia)
    record_run_failure(tmp_path, stage="run", exit_code=1)
    record_run_failure(tmp_path, stage="settle", exit_code=2)
    clear_run_status(tmp_path, "run")
    assert read_run_status(tmp_path)["stage"] == "settle"


# --- B-7: un fichero por etapa ------------------------------------------------
#
# Orden del operador, 2026-09-09. `record_run_failure` y `clear_run_status`
# hacian read-modify-write sobre un unico JSON, y con cinco tareas programadas
# que pueden solaparse dos procesos intercalados perdian la etapa del otro:
# borrar en silencio una alarma vigente, que es justo lo que este centinela
# existe para impedir. La salida no arbitra entre lock y no-lock: elimina la
# seccion critica.

def test_un_proceso_intercalado_no_borra_la_alarma_del_otro(tmp_path):
    """La carrera de B-7, reproducida.

    Un segundo proceso registra `settle` DESPUES de que el primero haya decidido
    lo que va a escribir y ANTES de que lo escriba. Con el fichero unico, el
    primero persistia la foto que leyo -- sin `settle` -- y la alarma del segundo
    desaparecia. Con un fichero por etapa no hay foto que persistir."""
    from sqp.monitoring import run_status as mod

    real = mod.atomic_write_json
    interpuesto: list = []

    def otro_proceso(payload, out, **kw):
        if not interpuesto:                       # solo en la primera escritura
            interpuesto.append(out)
            mod.record_run_failure(tmp_path, stage="settle", exit_code=3)
        return real(payload, out, **kw)

    mod.atomic_write_json = otro_proceso
    try:
        mod.record_run_failure(tmp_path, stage="run", exit_code=1)
    finally:
        mod.atomic_write_json = real

    st = read_run_status(tmp_path)
    assert st is not None
    assert set(st["stages"]) == {"settle", "run"}, (
        "la alarma del proceso intercalado se perdio")
    assert st["stage"] == "settle", "con las dos rotas manda la liquidacion"


def test_registrar_una_etapa_no_lee_las_demas(tmp_path):
    """La propiedad estructural de la que sale lo anterior: sin lectura previa
    no hay read-modify-write que perder."""
    from sqp.monitoring import run_status as mod

    record_run_failure(tmp_path, stage="settle", exit_code=3)
    leidos: list = []
    real = mod._leer_json

    def espia(p):
        leidos.append(p.name)
        return real(p)

    mod._leer_json = espia
    try:
        record_run_failure(tmp_path, stage="run", exit_code=1)
    finally:
        mod._leer_json = real
    assert leidos == [], f"se leyeron centinelas ajenos: {leidos}"


def test_limpiar_una_etapa_no_lee_ni_reescribe_las_demas(tmp_path):
    record_run_failure(tmp_path, stage="settle", exit_code=3)
    record_run_failure(tmp_path, stage="run", exit_code=1)
    antes = stage_path(tmp_path, "settle").read_bytes()

    assert clear_run_status(tmp_path, "run") is True

    assert not stage_path(tmp_path, "run").exists()
    assert stage_path(tmp_path, "settle").read_bytes() == antes, (
        "limpiar una etapa reescribio el fichero de otra")


# --- B-7: el nombre de etapa es ahora parte de una ruta -----------------------

@pytest.mark.parametrize("malo", ["../../evil", "run/../..", "RUN", "con espacio",
                                  "", "a" * 41, "run.json"])
def test_una_etapa_con_nombre_invalido_se_rechaza(tmp_path, malo):
    """Antes el nombre viajaba DENTRO del JSON y daba igual. Ahora nombra un
    fichero, asi que un `../..` escribiria fuera de `logs/`. Es el riesgo que
    introduce el cambio de disposicion, cerrado en el mismo sitio."""
    with pytest.raises(ValueError):
        record_run_failure(tmp_path, stage=malo, exit_code=1)
    assert read_run_status(tmp_path) is None
    assert not (tmp_path / "evil.json").exists()


# --- B-7: migracion del centinela anterior ------------------------------------

def test_el_centinela_anterior_se_reparte_y_no_pierde_avisos(tmp_path):
    """Al actualizar puede haber un centinela vigente en el formato viejo. Si la
    migracion lo perdiera, la actualizacion APAGARIA una alarma real."""
    logs = tmp_path / "logs"
    logs.mkdir(parents=True)
    (logs / STATUS_FILENAME).write_text(json.dumps({"stages": {
        "settle": {"failed": True, "stage": "settle", "exit_code": 3,
                   "failed_at": "2026-09-01T12:00:00Z"},
        "backfill": {"failed": True, "stage": "backfill", "exit_code": 1,
                     "failed_at": "2026-09-01T09:00:00Z"},
    }}), encoding="utf-8")

    # Se ve ANTES de migrar: la lectura une las dos fuentes.
    assert set(read_run_status(tmp_path)["stages"]) == {"settle", "backfill"}

    record_run_failure(tmp_path, stage="run", exit_code=1)   # dispara la migracion

    assert not (logs / STATUS_FILENAME).exists(), "el legado no se retiro"
    for etapa in ("settle", "backfill", "run"):
        assert stage_path(tmp_path, etapa).exists()
    st = read_run_status(tmp_path)
    assert set(st["stages"]) == {"settle", "backfill", "run"}
    assert st["stage"] == "settle"


def test_ante_la_misma_etapa_manda_el_formato_vigente(tmp_path):
    record_run_failure(tmp_path, stage="run", exit_code=7)
    logs = tmp_path / "logs"
    (logs / STATUS_FILENAME).write_text(json.dumps({"stages": {
        "run": {"failed": True, "stage": "run", "exit_code": 99,
                "failed_at": "2020-01-01T00:00:00Z"}}}), encoding="utf-8")
    assert read_run_status(tmp_path)["exit_code"] == 7


def test_limpiar_una_etapa_que_solo_estaba_en_el_legado(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir(parents=True)
    (logs / STATUS_FILENAME).write_text(json.dumps({"stages": {
        "backfill": {"failed": True, "stage": "backfill", "exit_code": 1,
                     "failed_at": "2026-09-01T09:00:00Z"}}}), encoding="utf-8")
    assert clear_run_status(tmp_path, "backfill") is True
    assert read_run_status(tmp_path) is None
    assert not (logs / STATUS_FILENAME).exists()
