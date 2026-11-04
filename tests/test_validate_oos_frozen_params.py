"""AUD-004: `frozen_train` y `family_default` de scripts/validate_oos.py deben
conservar los parametros canonicos NO tuneados (park_bound, pitcher_bound,
avg_total...) y diferir de `full_history` solo en las claves tuneadas."""
from __future__ import annotations

import importlib.util

import pytest

from sqp.config import ROOT
from sqp.pipeline.daily import _league_meta


@pytest.fixture
def cli(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "validate_oos_frozen", ROOT / "scripts" / "validate_oos.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    seen: list[dict] = []

    def fake_wf(train, league, family, params, warmup=0):
        seen.append(dict(params))
        return {"log_loss": 0.69}

    def fake_ha(train, league, family, league_params=None, **kw):
        seen.append(dict(league_params))
        return {"recommended_home_adv": 33.0}

    def fake_rho(train, league, family, league_params=None, **kw):
        seen.append(dict(league_params))
        return {"recommended_dc_rho": -0.07}

    monkeypatch.setattr(mod, "walk_forward_backtest", fake_wf)
    monkeypatch.setattr(mod, "tune_home_advantage", fake_ha)
    monkeypatch.setattr(mod, "tune_dc_rho", fake_rho)
    mod._seen = seen
    return mod


def test_frozen_mlb_conserva_park_y_pitcher_bound_canonicos(cli):
    canon = _league_meta("mlb")["league_params"]
    assert canon["pitcher_bound"] != 0.0 and "park_bound" in canon
    frozen = cli._freeze_on_train([], "mlb", "baseball", False, 0, 1, canon)
    assert frozen["pitcher_bound"] == canon["pitcher_bound"]
    assert frozen["park_bound"] == canon["park_bound"]
    assert frozen["elo_home_adv"] == 33.0  # tuneado: sobrescribe
    # la busqueda nunca parte de los valores tuneados sobre toda la historia
    assert cli._seen and all("elo_home_adv" not in s for s in cli._seen)


def test_frozen_futbol_conserva_avg_total_y_default_sin_claves_tuneadas(cli):
    canon = _league_meta("epl")["league_params"]
    frozen = cli._freeze_on_train([], "epl", "soccer", True, 0, 1, canon)
    assert frozen["avg_total"] == canon["avg_total"]
    assert frozen["dc_rho"] == -0.07
    default = cli._family_default(canon)
    assert default["avg_total"] == canon["avg_total"]
    assert not set(default) & set(cli.TUNED_KEYS)
    # full_history difiere de family_default solo en las claves tuneadas
    assert {k: v for k, v in canon.items() if k not in cli.TUNED_KEYS} == default
