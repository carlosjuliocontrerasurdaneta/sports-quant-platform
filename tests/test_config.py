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


def test_missing_config_file_fails_fast_instead_of_disarming_risk(monkeypatch,
                                                                  tmp_path):
    # The whole risk stack lives ONLY in configs/default.yaml: shadow_mode, the
    # CLV gate and the degradation monitor all default to False on the dataclass,
    # and max_plausible_edge defaults to 0.15 (twice the shipped 0.075). Silently
    # skipping a missing file therefore turned `shadow_mode: true` into real
    # stakes with no control layer and no warning (audit 2026-08-04, C-2).
    monkeypatch.setattr("sqp.config.CONFIG_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        Settings.load()


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


# --- divergencia entre el yaml versionado y el entorno -------------------------

def test_risk_override_from_env_is_logged(monkeypatch, caplog):
    """Un parametro de RIESGO que viene del entorno y difiere del yaml debe
    quedar en el log.

    El mecanismo se verifica con un valor distinto del que declara el yaml
    (0.08). El yaml fue alineado a 0.08 el 2026-08-23; el test usa 0.15
    para crear la divergencia y probar la deteccion, que es lo que importa."""
    monkeypatch.setenv("KELLY_FRACTION", "0.15")
    with caplog.at_level("WARNING"):
        s = Settings.load()
    assert s.risk.kelly_fraction == 0.15
    assert "KELLY_FRACTION" in caplog.text
    assert "0.08" in caplog.text and "0.15" in caplog.text


def test_no_warning_when_env_matches_the_yaml(monkeypatch, caplog):
    """Mismo valor en ambos sitios no es divergencia: no debe ensuciar el log."""
    monkeypatch.setenv("MIN_EDGE", "0.02")  # el yaml tambien declara 0.02
    with caplog.at_level("WARNING"):
        Settings.load()
    assert "MIN_EDGE" not in caplog.text


def test_no_warning_when_env_is_absent(monkeypatch, caplog):
    monkeypatch.delenv("KELLY_FRACTION", raising=False)
    with caplog.at_level("WARNING"):
        Settings.load()
    assert "KELLY_FRACTION" not in caplog.text
