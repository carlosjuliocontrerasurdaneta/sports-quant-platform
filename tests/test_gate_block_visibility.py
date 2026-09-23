"""El centinela `prediction_gate.blocked` tiene que verse (AUD-013, ronda
audit-2026-09-23; CLAUDE-005).

Mientras existe, el gate niega todo indefinidamente -- direccion segura --,
pero solo lo delataba un warning en logs/run_diario.log: `pipeline_health.json`
no decia nada y `gate_status.py` lo describia como "registro ausente o
ilegible" aunque el registro existiera y se leyera.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from sqp.monitoring.health import generate_health_report
from sqp.risk.prediction_gate import (PREDICTION_GATE_BLOCK_FILENAME,
                                      PREDICTION_GATE_FILENAME,
                                      prediction_gate_block)

ROOT = Path(__file__).resolve().parents[1]


def _bloquear(root: Path, *, registro: bool = True) -> Path:
    bets = root / "data" / "bets"
    bets.mkdir(parents=True, exist_ok=True)
    if registro:
        (bets / PREDICTION_GATE_FILENAME).write_text(json.dumps({
            "generated_at": "2026-09-22T15:15:26+00:00",
            "markets": {"mlb|h2h": {"allowed": False, "n": 10,
                                    "reason": "muestra_insuficiente"}}}),
            encoding="utf-8")
    (bets / PREDICTION_GATE_BLOCK_FILENAME).write_text(json.dumps({
        "blocked_at": "2026-09-23T12:00:00+00:00",
        "reason": "prediction_gate.json existe pero no se puede leer"}),
        encoding="utf-8")
    return bets


def test_sin_centinela_no_hay_bloqueo(tmp_path):
    assert prediction_gate_block(tmp_path) is None


def test_un_centinela_ilegible_sigue_siendo_un_bloqueo(tmp_path):
    (tmp_path / PREDICTION_GATE_BLOCK_FILENAME).write_text("{no json", encoding="utf-8")
    assert prediction_gate_block(tmp_path)["reason"] == "centinela ilegible"


def test_health_avisa_del_centinela_con_motivo_y_ruta(tmp_path):
    _bloquear(tmp_path)
    r = generate_health_report(root=tmp_path)
    avisos = [w for w in r["warnings"] if "BLOQUEADO" in w]
    assert len(avisos) == 1
    assert PREDICTION_GATE_BLOCK_FILENAME in avisos[0]
    assert "no se puede leer" in avisos[0]


def test_health_sin_centinela_no_avisa(tmp_path):
    r = generate_health_report(root=tmp_path)
    assert not [w for w in r["warnings"] if "BLOQUEADO" in w]


def test_gate_status_distingue_el_centinela_del_registro_ausente(tmp_path,
                                                                 monkeypatch,
                                                                 capsys):
    spec = importlib.util.spec_from_file_location(
        "gate_status_block", ROOT / "scripts" / "gate_status.py")
    cli = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = cli
    spec.loader.exec_module(cli)
    _bloquear(tmp_path)
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["gate_status.py"])
    assert cli.main() == 0
    salida = capsys.readouterr().out
    assert "CENTINELA DE BLOQUEO" in salida
    assert "registro ausente o ilegible" not in salida
