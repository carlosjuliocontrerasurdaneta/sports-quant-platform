"""`scripts/repair_ki079_20261107.py`: re-graduacion del evento NCAAF de KI-079,
todo o nada. Solo datos sinteticos en tmp_path; los recuentos congelados se
sustituyen por los del conjunto sintetico.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
EID = "7d7f757d2bf4cb7b6d8bbfe9589d25a2"


@pytest.fixture()
def mod(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location(
        "repair_ki079_20261107", ROOT / "scripts" / "repair_ki079_20261107.py")
    assert spec is not None and spec.loader is not None
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    monkeypatch.setattr(m, "ROOT", tmp_path)
    monkeypatch.setattr(m, "_cargar_resultados", lambda: _store(25, 18))
    m.SHA_PLAN.clear()
    return m


def _store(hs: int, as_: int) -> list[dict]:
    return [{"date": "2026-10-17", "home": "Buffalo Bulls", "away": "UMass Minutemen",
             "game_id": "1", "home_score": hs, "away_score": as_, "neutral": False}]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _row(market, sel, line, result, **kw):
    r = {"event_id": EID, "league": "ncaaf", "home": "Buffalo Bulls",
         "away": "UMass Minutemen", "start_time": "2026-10-17T17:00:00Z",
         "market": market, "selection": sel, "line": line, "price_decimal": 1.9,
         "stake": 0.0, "flags": "", "result": result, "pnl": 0.0, "zzz": "k"}
    r.update(kw)
    return r


def _setup(tmp_path):
    cal = tmp_path / "data" / "calibration"
    bets = tmp_path / "data" / "bets"
    cal.mkdir(parents=True)
    bets.mkdir(parents=True)
    # Marcador real 25-18: total 43, margen 7 (local).
    graded = pd.DataFrame([
        _row("totals", "Over", 42.5, "loss"),                     # -> win
        _row("totals", "Under", 42.5, "win"),                     # -> loss
        _row("spreads", "Buffalo Bulls", -7.0, "win", flags="x"),  # -> push
        _row("h2h", "Buffalo Bulls", float("nan"), "win"),        # sin cambio
        _row("totals", "Over", 50.5, "loss", event_id="otro", home="X", away="Y"),    # otro evento
    ])
    settled = pd.DataFrame([
        _row("totals", "Over", 42.5, "loss", start_time=None),
        _row("h2h", "Buffalo Bulls", float("nan"), "win", start_time=None),
    ]).drop(columns=["start_time"])
    gp, sp = cal / "graded_ncaaf.csv", bets / "settled_ncaaf.csv"
    graded.to_csv(gp, index=False)
    settled.to_csv(sp, index=False)
    return gp, sp


def _freeze(mod):
    mod.ESPERADO_CAMBIOS = {"graded_ncaaf": 3, "settled_ncaaf": 1}
    mod.ESPERADO_TRANSICIONES = {
        "graded_ncaaf": {"totals:loss->win": 1, "totals:win->loss": 1,
                         "spreads:win->push": 1},
        "settled_ncaaf": {"totals:loss->win": 1},
    }


def test_plan_applies_correct_transitions_and_preserves_shape(mod, tmp_path):
    gp, sp = _setup(tmp_path)
    _freeze(mod)
    antes_g, antes_s = pd.read_csv(gp), pd.read_csv(sp)
    plan = mod.planificar()
    assert plan is not None
    cambios, informe = plan
    g, s = cambios[gp], cambios[sp]
    assert g["result"].tolist() == ["win", "loss", "push", "win", "loss"]
    assert g["flags"].tolist() == ["regrade_ki079", "regrade_ki079", "x;regrade_ki079", "", ""]
    assert s["result"].tolist() == ["win", "win"]
    assert s["flags"].fillna("").tolist() == ["regrade_ki079", ""]
    for nuevo, antes in ((g, antes_g), (s, antes_s)):
        assert list(nuevo.columns) == list(antes.columns)
        assert len(nuevo) == len(antes)
        cols = [c for c in antes.columns if c not in ("result", "pnl", "flags")]
        pd.testing.assert_frame_equal(nuevo[cols], antes[cols])
    assert informe["ficheros"]["graded_ncaaf"]["cambiadas"] == 3


def test_wrong_change_count_aborts_without_writing(mod, tmp_path):
    gp, sp = _setup(tmp_path)
    _freeze(mod)
    mod.ESPERADO_CAMBIOS["graded_ncaaf"] = 4
    antes = (_sha(gp), _sha(sp))
    with pytest.raises(SystemExit, match="cambios"):
        mod.planificar()
    assert (_sha(gp), _sha(sp)) == antes


def test_wrong_store_score_aborts(mod, tmp_path, monkeypatch):
    gp, sp = _setup(tmp_path)
    _freeze(mod)
    monkeypatch.setattr(mod, "_cargar_resultados", lambda: _store(24, 18))
    antes = (_sha(gp), _sha(sp))
    with pytest.raises(SystemExit, match="marcador del store"):
        mod.planificar()
    assert (_sha(gp), _sha(sp)) == antes


def test_target_changed_after_planning_leaves_every_target_untouched(mod, tmp_path):
    gp, sp = _setup(tmp_path)
    _freeze(mod)
    cambios, informe = mod.planificar()
    with sp.open("a", encoding="utf-8") as fh:        # la liquidacion anade una fila
        fh.write("extra\n")
    antes = {p: p.read_bytes() for p in (gp, sp)}
    with pytest.raises(SystemExit, match="cambio desde que se planifico"):
        mod.aplicar(cambios, tmp_path / "backup" / "t", informe)
    assert {p: p.read_bytes() for p in (gp, sp)} == antes


def test_apply_writes_backup_with_original_sha_and_manifest(mod, tmp_path):
    gp, sp = _setup(tmp_path)
    _freeze(mod)
    sha_g, sha_s = _sha(gp), _sha(sp)
    cambios, informe = mod.planificar()
    destino = tmp_path / "backup" / "t"
    man = mod.aplicar(cambios, destino, informe)
    assert man["estado"] == "aplicado"
    assert _sha(destino / "data" / "calibration" / "graded_ncaaf.csv") == sha_g
    assert _sha(destino / "data" / "bets" / "settled_ncaaf.csv") == sha_s
    assert (destino / "MANIFEST.json").exists()
    f = man["ficheros"]["data\\calibration\\graded_ncaaf.csv"
                        if "\\" in str(Path("a/b")) else "data/calibration/graded_ncaaf.csv"]
    assert f["sha256_antes"] == sha_g and f["sha256_despues"] == _sha(gp)
    assert pd.read_csv(gp)["result"].tolist() == ["win", "loss", "push", "win", "loss"]


def test_second_run_is_idempotent_and_writes_nothing(mod, tmp_path, monkeypatch):
    gp, sp = _setup(tmp_path)
    _freeze(mod)
    monkeypatch.setattr(mod, "BACKUP", tmp_path / "backup")
    monkeypatch.setattr("sys.argv", ["x", "--apply"])
    assert mod.main() == 0
    despues = (_sha(gp), _sha(sp))
    mod.SHA_PLAN.clear()
    assert mod.planificar() is None
    assert mod.main() == 0
    assert (_sha(gp), _sha(sp)) == despues


def test_changed_row_with_stake_aborts(mod, tmp_path):
    gp, sp = _setup(tmp_path)
    _freeze(mod)
    df = pd.read_csv(gp)
    df.loc[0, "stake"] = 5.0
    df.to_csv(gp, index=False)
    with pytest.raises(SystemExit, match="stake"):
        mod.planificar()
