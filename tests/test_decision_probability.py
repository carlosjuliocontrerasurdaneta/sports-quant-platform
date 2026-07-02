"""Serving de calibración sobre p_model puro (research 2026-07-02).

La calibración debe aplicarse a la probabilidad PURA del modelo ANTES del
shrink al mercado (p_decision = (1-s)*cal(p_model) + s*fair), no a la mezcla
después. p_used almacenada sigue siendo la mezcla CRUDA (sin calibrar), para
que el retrain nunca entrene sobre salidas calibradas."""
from types import SimpleNamespace

import pytest

import sqp.pipeline.daily as daily

_ON = SimpleNamespace(calibration_enabled=True, calibration_method="auto")
_OFF = SimpleNamespace(calibration_enabled=False, calibration_method="auto")


def test_disabled_decision_equals_raw_blend():
    p_used, p_decision = daily._decision_probability(
        0.70, fair=0.50, shrink=0.5, league="mlb", market="h2h", settings=_OFF)
    assert p_used == pytest.approx(0.60)       # 0.5*0.70 + 0.5*0.50
    assert p_decision == pytest.approx(p_used)  # sin calibración: idénticas


def test_noop_calibrator_decision_equals_raw_blend():
    # Registro live vacío (estado actual): calibrate_probability es no-op, así
    # que el cambio de serving es byte-idéntico al comportamiento previo.
    p_used, p_decision = daily._decision_probability(
        0.70, fair=0.50, shrink=0.5, league="no_such_league", market="h2h",
        settings=_ON)
    assert p_decision == pytest.approx(p_used)


def test_calibration_applies_to_pure_model_before_blend(monkeypatch):
    seen = {}

    def fake_cal(p, league, market, method):
        seen["p"] = p
        return 0.55  # deflacta el modelo sobreconfiado 0.70 -> 0.55

    monkeypatch.setattr(daily, "calibrate_probability", fake_cal)
    p_used, p_decision = daily._decision_probability(
        0.70, fair=0.50, shrink=0.5, league="mlb", market="spreads", settings=_ON)
    assert seen["p"] == pytest.approx(0.70)     # calibró p_model PURO, no la mezcla
    assert p_used == pytest.approx(0.60)        # la mezcla almacenada sigue CRUDA
    assert p_decision == pytest.approx(0.525)   # 0.5*0.55 + 0.5*0.50


def test_no_market_anchor_uses_calibrated_model(monkeypatch):
    monkeypatch.setattr(daily, "calibrate_probability",
                        lambda p, league, market, method: 0.55)
    p_used, p_decision = daily._decision_probability(
        0.70, fair=None, shrink=0.5, league="mlb", market="h2h", settings=_ON)
    assert p_used == pytest.approx(0.70)        # sin ancla: mezcla = p_model crudo
    assert p_decision == pytest.approx(0.55)    # decisión = cal(p_model)
