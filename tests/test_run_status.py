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
    record_run_failure(tmp_path, stage="run", exit_code=1)
    raw = (tmp_path / "logs" / STATUS_FILENAME).read_text(encoding="utf-8")
    assert json.loads(raw)["failed"] is True


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
