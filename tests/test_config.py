"""Settings env overrides for the risk caps."""
import pytest

from sqp.config import Settings


def test_exposure_caps_overridable_by_env(monkeypatch):
    # Env wins over yaml/dataclass default for both the per-league daily cap (M1)
    # and the global cross-league cap (C1).
    monkeypatch.setenv("MAX_DAILY_EXPOSURE_PCT", "0.07")
    monkeypatch.setenv("MAX_TOTAL_EXPOSURE_PCT", "0.05")
    s = Settings.load()
    assert s.risk.max_daily_exposure_pct == 0.07
    assert s.risk.max_total_exposure_pct == 0.05


def test_exposure_caps_fall_back_to_config_without_env(monkeypatch):
    monkeypatch.delenv("MAX_DAILY_EXPOSURE_PCT", raising=False)
    monkeypatch.delenv("MAX_TOTAL_EXPOSURE_PCT", raising=False)
    s = Settings.load()
    # Shipped configs/default.yaml ships 0.10 for both.
    assert s.risk.max_daily_exposure_pct == 0.10
    assert s.risk.max_total_exposure_pct == 0.10


@pytest.mark.parametrize("name,value", [
    ("KELLY_FRACTION", "1.1"),
    ("MARKET_SHRINK", "-0.1"),
    ("MAX_TOTAL_EXPOSURE_PCT", "2"),
    ("CLV_GATE_MIN_N", "0"),
])
def test_invalid_risk_configuration_fails_fast(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        Settings.load()
