"""Modo precision (pick_mode: accuracy, decision 2026-07-27).

El objetivo del proyecto es maximizar el porcentaje de aciertos: la seleccion
deja de ser por edge y pasa a ser por probabilidad de decision calibrada
(blend modelo + no-vig) sobre un umbral configurable, SOLO moneyline (h2h).
El stake es plano (bankroll * max_stake_pct) y la cadena de flags de stake 0
(paused / suspect / shadow / clv gate) se mantiene intacta. Cada pick lleva
el flag "accuracy_mode" para el KPI de hit rate por liga y banda.
"""
from __future__ import annotations

import pandas as pd
import pytest

from sqp.config import ROOT, Settings


def _clean_pick_env(monkeypatch):
    monkeypatch.delenv("PICK_MODE", raising=False)
    monkeypatch.delenv("ACCURACY_THRESHOLD", raising=False)


def test_pick_mode_defaults_and_env(monkeypatch):
    _clean_pick_env(monkeypatch)
    s = Settings()
    assert s.pick_mode == "edge"           # default seguro: Settings() directo no cambia
    assert s.accuracy_threshold == pytest.approx(0.70)
    monkeypatch.setenv("PICK_MODE", "accuracy")
    monkeypatch.setenv("ACCURACY_THRESHOLD", "0.75")
    assert Settings().pick_mode == "accuracy"
    assert Settings().accuracy_threshold == pytest.approx(0.75)


def test_production_yaml_activates_accuracy_mode(monkeypatch):
    # configs/default.yaml activa el modo precision (objetivo 2026-07-27);
    # el env var (cuando esta) gana sobre el yaml, como el resto de flags.
    _clean_pick_env(monkeypatch)
    s = Settings.load()
    assert s.pick_mode == "accuracy"
    assert s.accuracy_threshold == pytest.approx(0.70)
    monkeypatch.setenv("PICK_MODE", "edge")
    assert Settings.load().pick_mode == "edge"


def test_validate_rejects_bad_pick_mode_and_threshold():
    s = Settings()
    s.pick_mode = "banana"
    with pytest.raises(ValueError):
        s.validate()
    s = Settings()
    s.pick_mode = "accuracy"
    s.accuracy_threshold = 0.40      # < 0.5: un "pick de precision" perdedor esperado
    with pytest.raises(ValueError):
        s.validate()
    s.accuracy_threshold = 1.0       # certeza: prohibido por lenguaje del proyecto
    with pytest.raises(ValueError):
        s.validate()
    s.accuracy_threshold = 0.70
    s.validate()


def test_accuracy_selected_helper():
    from sqp.pipeline.daily import _accuracy_selected
    assert _accuracy_selected("h2h", 0.72, 0.70, False)
    assert _accuracy_selected("h2h", 0.70, 0.70, False)          # umbral inclusivo
    assert not _accuracy_selected("h2h", 0.69, 0.70, False)
    assert not _accuracy_selected("spreads", 0.90, 0.70, False)  # solo moneyline
    assert not _accuracy_selected("totals", 0.90, 0.70, False)
    assert not _accuracy_selected("h2h", 0.90, 0.70, True)       # sin ancla no-vig valida


def test_accuracy_mode_demo_pipeline_selects_by_probability():
    from sqp.pipeline.daily import run_league
    settings = Settings.load()
    settings.pick_mode = "accuracy"
    settings.accuracy_threshold = 0.51   # bajo para garantizar picks sinteticos
    settings.shadow_mode = False
    run_league("nba", settings, mode="demo")
    f = ROOT / "data" / "predictions" / "demo" / "candidates_nba.csv"
    assert f.exists()
    c = pd.read_csv(f)
    assert not c.empty
    assert (c["market"] == "h2h").all()                          # solo moneyline
    assert (c["calibrated_probability"] >= 0.51).all()           # umbral cumplido
    flags = c["flags"].fillna("")
    assert flags.str.contains("accuracy_mode").all()
    flat = round(settings.bankroll * settings.risk.max_stake_pct, 2)
    plain = c[flags == "accuracy_mode"]                          # sin razon de stake 0
    assert not plain.empty
    assert (plain["stake"] == flat).all()                        # stake plano, no Kelly
    zeroed = c[flags != "accuracy_mode"]
    assert (zeroed["stake"] == 0).all()


def test_accuracy_mode_under_shadow_records_zero_stake():
    from sqp.pipeline.daily import run_league
    settings = Settings.load()
    settings.pick_mode = "accuracy"
    settings.accuracy_threshold = 0.51
    settings.shadow_mode = True
    run_league("nba", settings, mode="demo")
    f = ROOT / "data" / "predictions" / "demo" / "candidates_nba.csv"
    assert f.exists()
    c = pd.read_csv(f)
    assert not c.empty
    assert (c["stake"] <= 0).all()
    flags = c["flags"].fillna("")
    assert flags.str.contains("accuracy_mode").all()
    assert flags.str.contains("shadow_mode").any()
