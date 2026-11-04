"""AUD-002 (ronda audit-2026-11-03): el guard de arbol sucio de
DIARIO_COMPLETO.bat ya no pierde el dia al primer vistazo; ESPERA a que el arbol
quede limpio (patron de la espera de red [0c]) y solo aborta al agotar el plazo.

El BAT REAL se ejecuta en un repo git TEMPORAL con interprete y scripts
simulados: no toca produccion, `data/` ni `logs/` del proyecto, y no hay red.
SETTLE_ALL.bat es un simulado que deja un marcador y falla (rc 1), de modo que
"el flujo continuo tras el guard" se observa por ese marcador sin ejecutar nada
real.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from sqp.config import ROOT

pytestmark = pytest.mark.skipif(
    sys.platform != "win32" or shutil.which("git") is None
    or shutil.which("powershell") is None,
    reason="requiere cmd, PowerShell y git de Windows")

_ARCHIVO_SUCIO = "src/sqp/modulo.py"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   cwd=repo, check=True, capture_output=True)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    (r / "scripts").mkdir(parents=True)
    (r / "src" / "sqp").mkdir(parents=True)
    (r / "data" / "predictions").mkdir(parents=True)
    shutil.copy(ROOT / "DIARIO_COMPLETO.bat", r / "DIARIO_COMPLETO.bat")
    for nombre in ("rotate_log.cmd", "wait_for_clean_tree.ps1"):
        shutil.copy(ROOT / "scripts" / nombre, r / "scripts" / nombre)
    # Simulados: registran la llamada y salen bien.
    (r / "scripts" / "run_status.py").write_text(
        "import sys\n"
        "open('run_status_calls.txt', 'a').write(' '.join(sys.argv[1:]) + '\\n')\n",
        encoding="utf-8")
    (r / "scripts" / "health_check.py").write_text("", encoding="utf-8")
    (r / "SETTLE_ALL.bat").write_text(
        "@echo off\r\necho x> settle_llamado.txt\r\nexit /b 1\r\n", encoding="ascii")
    (r / _ARCHIVO_SUCIO).write_text("X = 1\n", encoding="utf-8")
    (r / "data" / "predictions" / "p.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    _git(r, "init", "-q")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "base")
    return r


def _ensuciar(repo: Path) -> None:
    (repo / _ARCHIVO_SUCIO).write_text("X = 2  # sin commitear\n", encoding="utf-8")


def _limpiar(repo: Path) -> None:
    (repo / _ARCHIVO_SUCIO).write_text("X = 1\n", encoding="utf-8")


def _limpiar_al_esperar(repo: Path, plazo_s: float = 100.0) -> None:
    fin = time.monotonic() + plazo_s
    while time.monotonic() < fin:
        try:
            if "se re-evalua" in _log(repo):
                time.sleep(1.5)
                _limpiar(repo)
                return
        except OSError:
            pass
        time.sleep(0.3)


def _lanzar(repo: Path, **extra: str) -> subprocess.Popen:
    env = {**os.environ, "SQP_PYTHON": sys.executable, "SQP_SKIP_NET_WAIT": "1",
           "SQP_TREE_WAIT_INTERVAL_S": "1", **extra}
    for k in ("SQP_SKIP_TREE_GUARD", "SQP_SKIP_TREE_WAIT"):
        if k not in extra:
            env.pop(k, None)
    return subprocess.Popen(
        ["cmd", "/c", str(repo / "DIARIO_COMPLETO.bat")], cwd=repo, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace")


def _log(repo: Path) -> str:
    return (repo / "logs" / "diario_completo.log").read_text(
        encoding="utf-8", errors="replace")


def test_arbol_sucio_agota_el_plazo_aborta_con_centinela_y_data_intacta(repo):
    antes = (repo / "data" / "predictions" / "p.csv").read_bytes()
    _ensuciar(repo)
    t0 = time.monotonic()
    p = _lanzar(repo, SQP_TREE_WAIT_MAX_MIN="0.05")  # 3 s
    p.communicate(timeout=120)
    espera = time.monotonic() - t0
    assert p.returncode == 1
    assert espera >= 3, "debe ESPERAR el plazo antes de abortar"
    log = _log(repo)
    assert "se re-evalua cada 1 s" in log and "SUCIO" in log
    assert "tras 0.05 min de espera" in log
    assert "ABORTADO ANTES DE LIQUIDAR" in log
    llamadas = (repo / "run_status_calls.txt").read_text(encoding="utf-8")
    assert "--fail --stage guard_arbol" in llamadas, "falta el centinela ROJO"
    assert not (repo / "settle_llamado.txt").exists(), "no debe liquidar"
    assert (repo / "data" / "predictions" / "p.csv").read_bytes() == antes


def test_si_el_arbol_se_limpia_durante_la_espera_el_flujo_continua(repo):
    _ensuciar(repo)
    p = _lanzar(repo, SQP_TREE_WAIT_MAX_MIN="1")
    # Se limpia cuando el BAT YA esta esperando (marcador del log), no a ciegas
    # por tiempo: el arranque del BAT tarda segundos variables.
    threading.Thread(target=_limpiar_al_esperar, args=(repo,), daemon=True).start()
    p.communicate(timeout=120)
    log = _log(repo)
    assert "ABORTADO ANTES DE LIQUIDAR" not in log
    assert "Arbol limpio tras la espera" in log
    # REG-002: el array vacio ya no se desenrolla a $null; un arbol limpio no
    # se registra como fallo de git.
    assert "arbol limpio; se continua." in log
    assert "git no pudo comprobar" not in log
    assert (repo / "settle_llamado.txt").exists(), "debe seguir hasta liquidar"
    llamadas = (repo / "run_status_calls.txt").read_text(encoding="utf-8")
    assert "guard_arbol" not in llamadas
    assert "--stage settle" in llamadas  # el simulado de SETTLE falla a proposito


def test_escape_skip_tree_wait_aborta_al_instante(repo):
    _ensuciar(repo)
    p = _lanzar(repo, SQP_SKIP_TREE_WAIT="1", SQP_TREE_WAIT_MAX_MIN="1")
    p.communicate(timeout=120)
    assert p.returncode == 1
    assert "SQP_SKIP_TREE_WAIT activo" in _log(repo)
    assert "se re-evalua" not in _log(repo)
    assert not (repo / "settle_llamado.txt").exists()
    assert "--stage guard_arbol" in (repo / "run_status_calls.txt").read_text(
        encoding="utf-8")


def test_arbol_limpio_no_espera(repo):
    p = _lanzar(repo, SQP_TREE_WAIT_MAX_MIN="1")
    p.communicate(timeout=120)
    assert "[0a]" not in _log(repo)
    assert (repo / "settle_llamado.txt").exists()
