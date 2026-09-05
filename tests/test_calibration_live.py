"""Live wiring of the probability calibrator: composite (league, market) keys,
per-market training from pick history, and the off-by-default pipeline invariant.
SYNTHETIC data only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from sqp.calibration import calibrator as cal
from sqp.calibration.calibrator import (apply_calibration, calibrate_probability,
                                        calibration_key, train_calibration,
                                        train_market_calibrators)
from sqp.config import ROOT, Settings
from sqp.pipeline.daily import run_league


def _miscalibrated(n: int = 3000, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    p = rng.uniform(0.1, 0.9, n)
    true_p = np.clip(p ** 1.8, 0.02, 0.98)
    won = (rng.uniform(size=n) < true_p).astype(float)
    return pd.DataFrame({"probability": p, "won": won})


def test_calibration_off_unless_opted_in(monkeypatch):
    # The dataclass default (no yaml override, no env) is OFF: calibration is
    # opt-in. (The shipped default.yaml is an operator choice and may be on.)
    monkeypatch.delenv("CALIBRATION_ENABLED", raising=False)
    assert Settings().calibration_enabled is False


def test_calibration_key_composite():
    assert calibration_key("mlb", "h2h") == "mlb_h2h"
    assert calibration_key("mlb") == "mlb"


def test_calibrate_probability_noop_without_model():
    # No model for this (league, market) -> input returned unchanged.
    assert calibrate_probability(0.62, "no_such_league", "h2h") == 0.62


@pytest.mark.slow
def test_calibrate_probability_uses_composite_key(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    cal._load_calibrator.cache_clear()
    df = _miscalibrated()
    train_calibration(df, prob_col="probability", outcome_col="won", sport="mlb_h2h")

    # calibrate_probability(league, market) resolves to the "mlb_h2h" model
    got = calibrate_probability(0.85, "mlb", "h2h")
    want = float(apply_calibration(np.array([0.85]), sport="mlb_h2h")[0])
    assert got == want
    assert 0.01 <= got <= 0.99
    assert got != 0.85                          # a miscalibrated model moves it
    # a different market has no model -> still a no-op
    assert calibrate_probability(0.85, "mlb", "totals") == 0.85


def _history(n_h2h: int, n_totals_small: int = 5) -> pd.DataFrame:
    rng = np.random.default_rng(3)
    rows = []
    for i in range(n_h2h):
        p = float(rng.uniform(0.2, 0.8))
        won = "win" if rng.uniform() < p ** 1.8 else "loss"
        rows.append({"league": "mlb", "market": "h2h", "date": f"2026-01-{i % 28 + 1:02d}",
                     "estimated_probability": p, "result": won})
    for i in range(n_totals_small):  # too few to train
        rows.append({"league": "mlb", "market": "totals", "date": "2026-02-01",
                     "estimated_probability": 0.55, "result": "win"})
    rows.append({"league": "mlb", "market": "h2h", "date": "2026-01-15",
                 "estimated_probability": 0.5, "result": "push"})  # excluded from n
    return pd.DataFrame(rows)


@pytest.mark.slow
def test_train_market_calibrators_groups_skips_and_persists(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    cal._load_calibrator.cache_clear()
    res = train_market_calibrators(_history(n_h2h=300), min_n=40)
    by_market = {(r["league"], r["market"]): r for r in res}

    h2h = by_market[("mlb", "h2h")]
    assert h2h["trained"] is True
    assert h2h["n"] == 300                       # push excluded from the graded count
    assert "raw_val_ece" in h2h and "cal_val_ece" in h2h
    # The retrain STAGES the candidate; it does NOT go live in the same cycle.
    # (The extremity gate drops this fixture's small-sample isotonic tail, so
    # the surviving candidate may be the beta model -- assert on the method
    # actually persisted, not on a hardcoded one.)
    assert h2h["persisted"] is True
    staged = list((tmp_path / "models" / "staging").glob("mlb_h2h_calibration_*.joblib"))
    assert staged
    assert not list((tmp_path / "models").glob("mlb_h2h_calibration_*.joblib"))
    assert "mlb_h2h" not in cal._load_method_registry()          # live untouched
    assert cal.calibrate_probability(0.85, "mlb", "h2h", method="auto") == 0.85

    totals = by_market[("mlb", "totals")]
    assert totals["trained"] is False            # 5 graded < min_n
    assert not (tmp_path / "models" / "staging" / "mlb_totals_calibration_iso.joblib").exists()


def test_train_market_calibrators_empty_history_is_safe():
    assert train_market_calibrators(pd.DataFrame()) == []


@pytest.mark.slow
def test_group_summaries_propagate_gate_verdicts_and_brier(tmp_path, monkeypatch):
    """El resumen por (liga, mercado) debe traer los veredictos del gate y el
    Brier crudo OOS, para que el CLI y el log del run diario puedan decir POR QUE
    un candidato se descarto sin reproducir el fit a mano (caso mlb_spreads
    2026-07-02: mejoraba ECE, lo freno el Brier, el log no lo decia)."""
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    cal._load_calibrator.cache_clear()
    trained = [r for r in train_market_calibrators(_history(n_h2h=300), min_n=40)
               if r.get("trained")]
    assert trained
    for r in trained:
        esperado = {"ece_ok", "brier_ok", "monotone_ok", "extreme_ok",
                    "resolution_ok"}
        assert set(r["iso_gate"]) == esperado
        assert set(r["beta_gate"]) == esperado
        assert "raw_val_brier" in r


@pytest.mark.slow
def test_demo_pipeline_calibrated_equals_estimated_when_disabled():
    # With calibration off, the decision probability equals the stored estimated
    # probability: enabling the flag is the only thing that diverges them.
    settings = Settings.load()
    settings.calibration_enabled = False  # force off regardless of shipped config
    settings.pick_mode = "edge"  # la mecanica probada es del selector por edge
    run_league("nba", settings, mode="demo")
    f = ROOT / "data" / "predictions" / "demo" / "candidates_nba.csv"
    c = pd.read_csv(f)
    assert "calibrated_probability" in c.columns
    assert np.allclose(c["calibrated_probability"], c["estimated_probability"])


def test_el_cli_calibra_el_mismo_objetivo_que_el_flujo_diario(monkeypatch, tmp_path):
    """AUD-006 (Codex, 2026-09-05).

    El camino MANUAL ajustaba la curva sobre `model_probability` mientras el
    DIARIO la ajusta sobre `adjusted_probability` (= `_p_adj`), para los mismos
    mercados. No es nominal: 2.216 filas del stream graduado tienen las dos
    columnas distintas. Se intercepta la llamada al entrenador para comprobar
    QUE columna recibe, sin entrenar ni promover nada.
    """
    import importlib.util
    import sys
    from pathlib import Path as _P

    import pandas as pd

    ruta = _P(__file__).resolve().parents[1] / "scripts" / "train_calibration.py"
    spec = importlib.util.spec_from_file_location("train_calibration_probe", ruta)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["train_calibration_probe"] = mod
    spec.loader.exec_module(mod)

    hist = pd.DataFrame([{
        "league": "mlb", "market": "h2h", "event_id": "e1", "selection": "A",
        "line": None, "date": "2026-09-01", "model_probability": 0.4,
        "adjusted_probability": 0.7, "implied_probability_novig": 0.5,
        "result": "win"}])
    visto = {}

    def espia(h, **kw):
        visto["prob_col"] = kw.get("prob_col")
        return []

    monkeypatch.setattr(mod, "train_market_calibrators", espia)
    monkeypatch.setattr(mod, "load_calibration_training_history", lambda: hist)
    monkeypatch.setattr(sys, "argv", ["train_calibration.py", "--source", "combined"])
    mod.main()
    assert visto["prob_col"] == "adjusted_probability", (
        "el CLI debe calibrar la MISMA variable que sirve produccion")
