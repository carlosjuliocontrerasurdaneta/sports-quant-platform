"""Calibrador ausente: trazabilidad (defecto b, 2026-11-13).

`live_calibration_state` es la unica resolucion del calibrador live (la comparte
`apply_calibration`); `run_league` marca `uncalibrated` en `flags` cuando el
mercado se sirve en crudo, loguea UNA linea por liga y solo alarma (WARNING)
cuando el registro afirma un calibrador que no se aplica. La mera ausencia no es
alarma (health.py)."""
from __future__ import annotations

import json
import logging

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.isotonic import IsotonicRegression

import sqp.calibration.calibrator as cal
from sqp.config import Settings
from sqp.monitoring import health
from sqp.pipeline import daily
from sqp.providers.synthetic import SyntheticProvider

LEAGUE = "nba"
_X = np.linspace(0.01, 0.99, 99)


def _put_model(models_dir, key, y=None):
    y = 0.05 + 0.9 * _X if y is None else y
    m = IsotonicRegression(out_of_bounds="clip").fit(_X, y)
    path = models_dir / f"{key}_calibration_iso.joblib"
    joblib.dump(m, str(path))
    cal._write_hash(path)
    return path


def _registry(models_dir, entries):
    (models_dir / "calibration_methods.json").write_text(
        json.dumps(entries), encoding="utf-8")


@pytest.fixture()
def models(tmp_path, monkeypatch):
    d = tmp_path / "models"
    d.mkdir()
    monkeypatch.setattr(cal, "MODELS_DIR", d)
    return d


# ------------------------------------------------------------------ estados --
def _arrange_state(state, models):
    key = "nba_h2h"
    if state == "applied":
        _registry(models, {key: "isotonic"})
        _put_model(models, key)
    elif state == "none":
        _registry(models, {})
    elif state == "unknown_method":
        _registry(models, {key: "platt"})
    elif state == "missing_file":
        _registry(models, {key: "isotonic"})
    elif state == "bad_digest":
        _registry(models, {key: "isotonic"})
        p = _put_model(models, key)
        cal._hash_sidecar(p).write_text("0" * 64, encoding="utf-8")
    elif state == "structural_defect":
        _registry(models, {key: "isotonic"})
        _put_model(models, key, y=np.full_like(_X, 0.49))
    return key


@pytest.mark.parametrize("state", ["applied", "none", "unknown_method",
                                   "missing_file", "bad_digest",
                                   "structural_defect"])
def test_live_calibration_state_six_states_and_apply_agrees(models, state):
    key = _arrange_state(state, models)
    assert cal.live_calibration_state(key, "auto") == state
    probs = np.array([0.2, 0.5, 0.8])
    out = cal.apply_calibration(probs, sport=key, method="auto")
    if state == "applied":
        assert not np.allclose(out, probs)       # se aplico de verdad
    else:
        assert np.array_equal(out, probs)        # crudo: no pueden divergir


# ------------------------------------------------------------- run_league ---
class _FakeClient:
    last_response_cached = True

    def __init__(self, events):
        self._events = events

    def is_sport_active(self, sport_key):      # noqa: ARG002
        return True

    def fetch_odds(self, *a, **k):             # noqa: ARG002
        return self._events

    def fetch_scores(self, *a, **k):           # noqa: ARG002
        return []


@pytest.fixture
def live(tmp_path, monkeypatch, models):
    sp = SyntheticProvider("basketball")
    results = sp.fetch_results(LEAGUE)
    events = sp.fetch_odds(LEAGUE, three_way=False)
    monkeypatch.setattr(daily, "ROOT", tmp_path)
    monkeypatch.setattr(daily, "OddsAPIClient", lambda *a, **k: _FakeClient(events))
    monkeypatch.setattr(daily, "_fetch_recent_scores", lambda *a, **k: [])

    class _RS:
        def __init__(self, root):
            pass

        def load(self, league):                # noqa: ARG002
            return results

    monkeypatch.setattr(daily, "ResultsStore", _RS)
    (tmp_path / "data" / "bets").mkdir(parents=True)
    return tmp_path


def _settings(**over):
    s = Settings.load()
    s.pick_mode = "edge"
    s.shadow_mode = False
    s.clv_gate_enabled = False
    s.prediction_gate_enabled = False
    s.risk.max_plausible_edge = 10.0
    for k, v in over.items():
        setattr(s, k, v)
    return s


def _served(root):
    return pd.read_csv(root / "data" / "calibration" / f"served_{LEAGUE}.csv")


def _cands(root):
    df = pd.read_csv(root / "data" / "predictions" / f"candidates_{LEAGUE}.csv")
    df["flags"] = df["flags"].fillna("").astype(str)
    return df


def test_empty_registry_marks_uncalibrated_in_served_and_candidates(live, models):
    _registry(models, {})
    daily.run_league(LEAGUE, _settings(), mode="live")
    s, c = _served(live), _cands(live)
    assert s["flags"].str.contains("uncalibrated").all()
    assert not c.empty and c["flags"].str.contains("uncalibrated").all()


def test_applied_calibrator_is_not_marked_but_other_markets_are(live, models):
    _registry(models, {"nba_h2h": "isotonic"})
    _put_model(models, "nba_h2h")
    daily.run_league(LEAGUE, _settings(), mode="live")
    s = _served(live)
    h2h = s[s["market"] == "h2h"]
    otros = s[s["market"] != "h2h"]
    assert not h2h.empty and not otros.empty
    assert not h2h["flags"].str.contains("uncalibrated").any()
    assert otros["flags"].str.contains("uncalibrated").all()


def test_calibration_disabled_marks_uncalibrated(live, models):
    _registry(models, {"nba_h2h": "isotonic"})
    _put_model(models, "nba_h2h")
    daily.run_league(LEAGUE, _settings(calibration_enabled=False), mode="live")
    assert _served(live)["flags"].str.contains("uncalibrated").all()


def test_one_info_line_and_no_warning_for_plain_absence(live, models, caplog):
    _registry(models, {})
    with caplog.at_level(logging.INFO, logger="sqp.pipeline"):
        daily.run_league(LEAGUE, _settings(), mode="live")
    crudo = [r for r in caplog.records if "sin calibrador aplicado" in r.getMessage()]
    assert len(crudo) == 1 and crudo[0].levelno == logging.INFO
    assert not [r for r in caplog.records
                if "afirma un calibrador" in r.getMessage()]


def test_warning_when_registry_claims_a_calibrator_that_is_not_applied(
        live, models, caplog):
    _registry(models, {"nba_h2h": "isotonic"})        # fichero ausente
    with caplog.at_level(logging.INFO, logger="sqp.pipeline"):
        daily.run_league(LEAGUE, _settings(), mode="live")
    avisos = [r for r in caplog.records if "afirma un calibrador" in r.getMessage()]
    assert len(avisos) == 1 and avisos[0].levelno == logging.WARNING
    assert "h2h=missing_file" in avisos[0].getMessage()


# ------------------------------------------------------------------- health --
def test_health_lists_league_market_pairs_without_calibration(tmp_path):
    models_dir = tmp_path / "data" / "models"
    models_dir.mkdir(parents=True)
    (models_dir / "calibration_methods.json").write_text(
        json.dumps({"nba_h2h": "isotonic"}), encoding="utf-8")
    (models_dir / "nba_h2h_calibration_iso.joblib").write_bytes(b"x")
    cal_dir = tmp_path / "data" / "calibration"
    cal_dir.mkdir(parents=True)
    pd.DataFrame({"market": ["h2h", "totals", "h2h", "spreads"]}).to_csv(
        cal_dir / "served_nba.csv", index=False)
    inv = health._served_calibration_inventory(tmp_path)
    assert inv == {"nba": ["h2h"]}
    assert health._served_markets_without_calibration(tmp_path, inv) == [
        "nba|spreads", "nba|totals"]
