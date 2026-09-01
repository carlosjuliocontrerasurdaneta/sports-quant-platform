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

from sqp.monitoring.run_status import (STATUS_FILENAME, clear_run_status,
                                       read_run_status, record_run_failure)


# --- Escritura del centinela --------------------------------------------------

def test_record_failure_writes_sentinel(tmp_path):
    record_run_failure(tmp_path, stage="run", exit_code=1)
    assert (tmp_path / "logs" / STATUS_FILENAME).exists()


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
    """El centinela se indexa POR ETAPA desde 2026-08-31 (A-02): sobrescribir el
    fichero entero borraba el fallo de la otra etapa."""
    record_run_failure(tmp_path, stage="run", exit_code=1)
    raw = (tmp_path / "logs" / STATUS_FILENAME).read_text(encoding="utf-8")
    assert json.loads(raw)["stages"]["run"]["failed"] is True


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

def test_health_report_is_error_when_last_run_failed(tmp_path):
    from sqp.monitoring.health import generate_health_report
    record_run_failure(tmp_path, stage="run", exit_code=1)
    r = generate_health_report(tmp_path)
    assert r["status"] == "ERROR"
    assert any("run diario" in e.lower() for e in r["errors"])


def test_health_error_names_the_failed_stage(tmp_path):
    from sqp.monitoring.health import generate_health_report
    record_run_failure(tmp_path, stage="settle", exit_code=1)
    joined = " ".join(generate_health_report(tmp_path)["errors"])
    assert "settle" in joined


def test_health_report_has_no_run_error_when_sentinel_absent(tmp_path):
    from sqp.monitoring.health import generate_health_report
    r = generate_health_report(tmp_path)
    assert not any("run diario" in e.lower() for e in r.get("errors", []))


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
    p = tmp_path / "logs" / STATUS_FILENAME
    data = json.loads(p.read_text(encoding="utf-8"))
    data["stages"]["run"]["stage"] = "<script>alert(1)</script>"
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
