"""Gate de CLV por (liga, mercado): decision, registro y precedencia de flags."""
import pandas as pd

from sqp.risk.clv_gate import (CLV_GATE_FILENAME, gate_decisions, load_clv_gate,
                               market_allowed, write_clv_gate)


def _segments() -> pd.DataFrame:
    return pd.DataFrame([
        {"league": "mlb", "market": "totals", "n": 40, "median_clv_pct": 0.012},
        {"league": "mlb", "market": "h2h", "n": 60, "median_clv_pct": -0.004},
        {"league": "wnba", "market": "spreads", "n": 5, "median_clv_pct": 0.09},
        {"league": "nhl", "market": "h2h", "n": 30, "median_clv_pct": 0.0},
    ])


def test_gate_requires_min_n_and_strictly_positive_median():
    out = gate_decisions(_segments(), min_n=30)
    allowed = {(r.league, r.market): r.allowed for r in out.itertuples()}
    assert allowed[("mlb", "totals")]           # n suficiente + mediana positiva
    assert not allowed[("mlb", "h2h")]          # mediana negativa
    assert not allowed[("wnba", "spreads")]     # muestra insuficiente
    assert not allowed[("nhl", "h2h")]          # mediana 0 no basta (estricto)


def test_write_and_load_roundtrip(tmp_path):
    write_clv_gate(_segments(), tmp_path, min_n=30)
    gate = load_clv_gate(tmp_path)
    assert market_allowed(gate, "mlb", "totals")
    assert not market_allowed(gate, "mlb", "h2h")
    assert not market_allowed(gate, "wnba", "spreads")
    assert not market_allowed(gate, "ncaab", "totals")  # sin entrada -> deny


def test_empty_registry_is_still_written_and_denies(tmp_path):
    write_clv_gate(pd.DataFrame(), tmp_path)
    assert (tmp_path / CLV_GATE_FILENAME).exists()
    assert load_clv_gate(tmp_path) == {}
    assert not market_allowed(load_clv_gate(tmp_path), "mlb", "totals")


def test_missing_or_corrupt_registry_denies(tmp_path):
    assert load_clv_gate(tmp_path) == {}
    (tmp_path / CLV_GATE_FILENAME).write_text("{not json", encoding="utf-8")
    assert load_clv_gate(tmp_path) == {}
    (tmp_path / CLV_GATE_FILENAME).write_text('{"markets": []}', encoding="utf-8")
    assert load_clv_gate(tmp_path) == {}  # markets con tipo invalido -> deny


def test_zero_stake_flag_clv_precedence():
    from sqp.pipeline.daily import _zero_stake_flag
    assert _zero_stake_flag(False, False, False, clv_blocked=True) == "clv_gate"
    # shadow supera al gate: los reportes conservan shadow_mode mientras dura
    assert _zero_stake_flag(False, False, True, clv_blocked=True) == "shadow_mode"
    assert _zero_stake_flag(True, False, False, clv_blocked=True) == "market_paused"
    assert _zero_stake_flag(False, False, False, clv_blocked=False) is None


def test_settings_clv_gate_defaults_and_env(monkeypatch):
    from sqp.config import Settings
    monkeypatch.delenv("CLV_GATE_ENABLED", raising=False)
    monkeypatch.delenv("CLV_GATE_MIN_N", raising=False)
    s = Settings()
    assert s.clv_gate_enabled is False and s.clv_gate_min_n == 30
    monkeypatch.setenv("CLV_GATE_ENABLED", "1")
    monkeypatch.setenv("CLV_GATE_MIN_N", "50")
    s = Settings()
    assert s.clv_gate_enabled is True and s.clv_gate_min_n == 50


def test_daily_clv_rewrites_gate_registry(tmp_path):
    # Sin apuestas liquidadas, la auditoria igual reescribe el registro con
    # markets vacio (default-deny explicito) y lo reporta en el resumen.
    from sqp.audit.clv import daily_clv
    summary = daily_clv(tmp_path, tmp_path)
    assert (tmp_path / CLV_GATE_FILENAME).exists()
    assert summary["gate_allowed"] == []
    assert summary["gate_path"].endswith(CLV_GATE_FILENAME)
