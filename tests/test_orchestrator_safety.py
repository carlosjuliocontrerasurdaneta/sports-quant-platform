"""Safety contracts for the Windows daily orchestrators."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"{name}_safety_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _settings():
    return SimpleNamespace(
        bankroll=1000.0, bankroll_dynamic=False,
        risk=SimpleNamespace(max_total_exposure_pct=0.10),
        calibration_auto_promote=True, calibration_enabled=True,
        clv_gate_min_n=30,
    )


def test_demo_run_never_touches_live_audit_or_calibration(monkeypatch):
    mod = _load_script("run_all")
    monkeypatch.setattr(mod.Settings, "load", staticmethod(_settings))
    monkeypatch.setattr(mod, "_supported_leagues", lambda: {"mlb": "baseball_mlb"})
    monkeypatch.setattr(mod, "run_league", lambda *a, **k: None)
    monkeypatch.setattr(mod, "apply_global_exposure_cap", lambda *a, **k: 1.0)
    monkeypatch.setattr(mod, "consolidated_report", lambda *a, **k: "demo.md")

    def forbidden(*args, **kwargs):
        raise AssertionError("demo attempted to mutate/read live audit state")

    for name in ("settlement_audit_report", "daily_clv", "build_pick_history",
                 "stage_calibrators_from_settled"):
        monkeypatch.setattr(mod, name, forbidden)
    monkeypatch.setattr(sys, "argv", ["run_all.py", "--mode", "demo", "--no-html"])
    assert mod.main() == 0


def test_live_pipeline_failure_returns_nonzero_and_preserves_prior_file(monkeypatch):
    mod = _load_script("run_all")
    monkeypatch.setattr(mod.Settings, "load", staticmethod(_settings))
    monkeypatch.setattr(mod, "_supported_leagues", lambda: {"mlb": "baseball_mlb"})
    monkeypatch.setattr(mod, "_select_live", lambda *a, **k: (["mlb"], {"mlb"}))
    monkeypatch.setattr(mod, "unsettled_completed_picks", lambda *a, **k: {})
    monkeypatch.setattr(mod, "prune_stale_candidates", lambda *a, **k: [])
    monkeypatch.setattr(mod, "apply_global_exposure_cap", lambda *a, **k: 1.0)
    monkeypatch.setattr(mod, "run_league",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(sys, "argv", ["run_all.py", "--mode", "live", "--no-report"])
    assert mod.main() == 1


def test_settlement_failure_propagates_to_batch_exit_status(monkeypatch, tmp_path):
    mod = _load_script("settle_all")
    pred = tmp_path / "data" / "predictions"
    pred.mkdir(parents=True)
    (pred / "candidates_mlb.csv").write_text("event_id\ne1\n", encoding="utf-8")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod.Settings, "load", staticmethod(_settings))
    monkeypatch.setattr(mod, "fetch_and_settle",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(mod, "settlement_audit_report", lambda: "audit.md")
    monkeypatch.setattr(sys, "argv", ["settle_all.py"])
    assert mod.main() == 1
