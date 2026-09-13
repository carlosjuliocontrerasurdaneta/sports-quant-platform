"""scripts/open_dashboard.ps1 (AUD-HIGH-002, auditoria integral 2026-09-13).

Hasta el 2026-09-13 el script se omitia ("El reporte no es de hoy") justo el
dia en que el run diario no habia ocurrido, y el health_check solo corria
dentro del orquestador ausente: 4 de 7 dias sin run y sin senal. Ahora corre
el health_check al iniciar sesion y, con reporte viejo, avisa y abre igual.

Se ejecuta el .ps1 REAL sobre una copia aislada (root temporal) con un
health_check.py de mentira y SQP_DASHBOARD_NO_UI=1 (sin navegador ni modal).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from sqp.config import ROOT

pytestmark = pytest.mark.skipif(
    sys.platform != "win32" or shutil.which("powershell") is None,
    reason="el script es PowerShell de Windows")


def _sandbox(tmp_path: Path, *, report_age_days: float, health_rc: int) -> Path:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "data" / "predictions").mkdir(parents=True)
    shutil.copy(ROOT / "scripts" / "open_dashboard.ps1", tmp_path / "scripts")
    (tmp_path / "scripts" / "health_check.py").write_text(
        f"print('Pipeline health: FAKE'); raise SystemExit({health_rc})\n",
        encoding="utf-8")
    rep = tmp_path / "data" / "predictions" / "report_latest.html"
    rep.write_text("<html></html>", encoding="utf-8")
    ts = time.time() - report_age_days * 86400
    os.utime(rep, (ts, ts))
    return tmp_path


def _run(root: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "SQP_DASHBOARD_NO_UI": "1", "SQP_PYTHON": sys.executable}
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(root / "scripts" / "open_dashboard.ps1"), *args],
        capture_output=True, text=True, env=env, cwd=root, timeout=120)


def test_un_reporte_viejo_ya_no_se_omite_en_silencio(tmp_path):
    root = _sandbox(tmp_path, report_age_days=2.0, health_rc=0)
    r = _run(root)
    assert r.returncode == 0, r.stderr
    assert "AVISO" in r.stdout and "NO es de hoy" in r.stdout, r.stdout
    assert "se omite" not in r.stdout
    assert "Dashboard abierto" in r.stdout
    # El health_check se ejecuto al margen del orquestador y dejo rastro.
    assert "FAKE" in (root / "logs" / "open_dashboard.log").read_text(encoding="utf-8")
    # Y el marcador del dia se escribio: la siguiente sesion del dia no reabre.
    assert list((root / "logs").glob("dashboard_shown_*.flag"))


def test_un_health_check_en_error_tambien_avisa_con_reporte_de_hoy(tmp_path):
    root = _sandbox(tmp_path, report_age_days=0.0, health_rc=1)
    r = _run(root)
    assert r.returncode == 0, r.stderr
    assert "AVISO" in r.stdout and "ERROR" in r.stdout, r.stdout


def test_reporte_de_hoy_y_salud_ok_abre_sin_aviso(tmp_path):
    root = _sandbox(tmp_path, report_age_days=0.0, health_rc=0)
    r = _run(root)
    assert r.returncode == 0, r.stderr
    assert "AVISO" not in r.stdout and "Dashboard abierto" in r.stdout


def test_segunda_ejecucion_del_dia_se_omite_por_marcador(tmp_path):
    root = _sandbox(tmp_path, report_age_days=0.0, health_rc=0)
    _run(root)
    r = _run(root)
    assert "ya mostrado hoy" in r.stdout
