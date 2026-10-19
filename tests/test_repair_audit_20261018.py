"""`scripts/repair_audit_20261018.py`: todo o nada antes de tocar datos.

Revision cruzada de Codex (2026-10-19), dos defectos reproducidos: (1) con el
historico ausente, AUD-008 no emparejaba nada y el script aplicaba igualmente
KI-071, dejando la reparacion a medias y sin poder reintentarse; (2) un fichero
que cambiaba tras planificar solo se detectaba al llegar a el, con los
anteriores ya reescritos. Solo datos sinteticos en tmp_path.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def mod(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location(
        "repair_audit_20261018", ROOT / "scripts" / "repair_audit_20261018.py")
    assert spec is not None and spec.loader is not None
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    monkeypatch.setattr(m, "ROOT", tmp_path)
    m.SHA_PLAN.clear()
    return m


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_aud008_without_history_aborts_before_writing(mod, tmp_path):
    cal = tmp_path / "data" / "calibration"
    cal.mkdir(parents=True)
    graded = cal / "graded_laliga.csv"
    pd.DataFrame([{
        "league": "laliga", "event_id": "e1", "home": "A", "away": "B",
        "start_time": "2026-09-01T18:00:00Z", "market": "totals", "selection": "Over",
        "line": 2.25, "price_decimal": 1.9, "stake": 0.0, "generated_at": "2026-08-30T10:00:00Z",
        "result": "win", "pnl": 0.0, "flags": ""}]).to_csv(graded, index=False)
    antes = _sha(graded)
    with pytest.raises(SystemExit, match="AUD-008"):
        mod.plan_aud008({})
    assert _sha(graded) == antes


def test_a_target_changed_after_planning_leaves_every_target_untouched(mod, tmp_path):
    bets = tmp_path / "data" / "bets"
    bets.mkdir(parents=True)
    a, b = bets / "settled_epl.csv", bets / "settled_mls.csv"
    for p in (a, b):
        pd.DataFrame({"x": [1, 2]}).to_csv(p, index=False)
        mod.SHA_PLAN[p] = _sha(p)
    pd.DataFrame({"x": [1, 2, 3]}).to_csv(b, index=False)     # la liquidacion anade una fila
    antes = {p: p.read_bytes() for p in (a, b)}
    with pytest.raises(SystemExit, match="cambio desde que se planifico"):
        mod.aplicar({a: pd.DataFrame({"x": [9]}), b: pd.DataFrame({"x": [9]})},
                    tmp_path / "backup", {})
    assert {p: p.read_bytes() for p in (a, b)} == antes


def test_apply_writes_all_targets_with_copies_and_manifest(mod, tmp_path):
    bets = tmp_path / "data" / "bets"
    bets.mkdir(parents=True)
    a = bets / "settled_epl.csv"
    pd.DataFrame({"x": [1, 2]}).to_csv(a, index=False)
    mod.SHA_PLAN[a] = _sha(a)
    original = a.read_bytes()
    man = mod.aplicar({a: pd.DataFrame({"x": [1]})}, tmp_path / "backup" / "t", {})
    assert man["estado"] == "aplicado"
    assert (tmp_path / "backup" / "t" / "data" / "bets" / "settled_epl.csv").read_bytes() == original
    assert pd.read_csv(a)["x"].tolist() == [1]
