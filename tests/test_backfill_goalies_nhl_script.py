"""CLI de `scripts/backfill_goalies_nhl.py`: codigo de salida, saneamiento de
`--end` contra `utc_today()` y el parametro `--root` para poder probar sin
tocar `data/` real (revision independiente de Fable, B1/B2, 2026-09-26)."""
from __future__ import annotations

import importlib.util
import sys
from datetime import timedelta
from pathlib import Path

import requests

from sqp.pipeline.goalie_backfill import Counts

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_cli():
    spec = importlib.util.spec_from_file_location(
        "backfill_goalies_nhl_cli", REPO_ROOT / "scripts" / "backfill_goalies_nhl.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_sale_con_codigo_distinto_de_cero_si_para_por_fallos_consecutivos(tmp_path, monkeypatch):
    """B1: hoy el script devuelve 0 aunque `run()` se haya detenido por
    fallos consecutivos; debe devolver un codigo distinto de cero para que un
    `.bat`/orquestador no trate el backfill parcial como exitoso."""
    from sqp.pipeline import goalie_backfill as gb

    def siempre_falla(date_str, session):
        raise requests.ConnectionError("caida simulada")

    monkeypatch.setattr(gb.nhl_api, "fetch_score", siempre_falla)

    cli = _load_cli()
    monkeypatch.setattr(sys, "argv", [
        "backfill_goalies_nhl.py",
        "--start", "2024-10-10", "--end", "2024-10-20",
        "--sleep", "0", "--root", str(tmp_path),
    ])
    assert cli.main() == 1


def test_sale_con_cero_si_termina_el_rango_sin_fallos(tmp_path, monkeypatch):
    from sqp.pipeline import goalie_backfill as gb

    monkeypatch.setattr(gb.nhl_api, "fetch_score", lambda date_str, session: {"games": []})

    cli = _load_cli()
    monkeypatch.setattr(sys, "argv", [
        "backfill_goalies_nhl.py",
        "--start", "2024-10-10", "--end", "2024-10-11",
        "--sleep", "0", "--root", str(tmp_path),
    ])
    assert cli.main() == 0


def test_end_no_anterior_a_hoy_utc_se_recorta_y_avisa(tmp_path, monkeypatch):
    """B2: pedir un rango que incluya hoy solo produce partidos "pendientes"
    en cada pasada (gameState != OFF/FINAL); el CLI debe recortar `--end` a
    antes de hoy UTC y avisar, en vez de aceptarlo tal cual."""
    cli = _load_cli()
    calls: dict = {}

    def fake_run(start, end, sleep_s, root):
        calls["start"], calls["end"], calls["root"] = start, end, root
        return Counts()

    monkeypatch.setattr(cli, "run", fake_run)
    hoy = cli.utc_today()
    monkeypatch.setattr(sys, "argv", [
        "backfill_goalies_nhl.py",
        "--start", "2024-10-10", "--end", hoy.isoformat(),
        "--root", str(tmp_path),
    ])
    assert cli.main() == 0
    assert calls["end"] == hoy - timedelta(days=1)
    assert calls["root"] == tmp_path


def test_root_se_pasa_a_run_para_no_tocar_data_real(tmp_path, monkeypatch):
    cli = _load_cli()
    calls: dict = {}

    def fake_run(start, end, sleep_s, root):
        calls["root"] = root
        return Counts()

    monkeypatch.setattr(cli, "run", fake_run)
    monkeypatch.setattr(sys, "argv", [
        "backfill_goalies_nhl.py",
        "--start", "2024-10-10", "--end", "2024-10-11",
        "--root", str(tmp_path),
    ])
    assert cli.main() == 0
    assert calls["root"] == tmp_path
