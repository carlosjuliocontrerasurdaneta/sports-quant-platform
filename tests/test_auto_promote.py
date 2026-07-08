"""Auto-promoción de calibradores con gates (decisión 2026-07-08).

El ciclo diario se autocorrige promoviendo a LIVE exactamente lo que pasó los
gates OOS en staging (ECE + Brier + monotonía) Y validó sobre una muestra
mínima (n_val >= min_n_val, el guard que habría dejado fuera al candidato
escalón de n_val=9 del 2026-07-02). Lo que el retrain deja de recomendar se
demota (self-healing). Cada acción queda auditada en promotion_log.csv.
"""
import numpy as np
import pandas as pd
import pytest

from sqp.calibration import calibrator as cal


def _stage_overconfident(tmp_path, monkeypatch, league="mlb", market="h2h",
                         n=200, seed=0):
    """Deja un candidato gated en STAGING (mercado sobreconfiado sintético:
    prob estimada 0.70 vs frecuencia real ~0.40) y devuelve los summaries."""
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    rng = np.random.default_rng(seed)
    wins = rng.random(n) < 0.40
    hist = pd.DataFrame([
        {"league": league, "market": market,
         "date": f"2026-05-{1 + i % 28:02d}", "model_probability": 0.70,
         "result": "win" if w else "loss"}
        for i, w in enumerate(wins)])
    return cal.train_market_calibrators(hist, min_n=40,
                                        prob_col="model_probability")


def test_auto_promote_installs_gated_candidate(tmp_path, monkeypatch):
    results = _stage_overconfident(tmp_path, monkeypatch)
    assert cal._load_method_registry(staging=False) == {}  # antes: solo staging
    sync = cal.auto_promote_calibrators(results)
    assert sync["promoted"] == ["mlb_h2h"]
    assert "mlb_h2h" in cal._load_method_registry(staging=False)
    # El modelo promovido APLICA en live (deja de ser no-op) y corrige hacia
    # la frecuencia observada (~0.40), no hacia la estimada (0.70).
    out = cal.apply_calibration(np.array([0.70]), sport="mlb_h2h", method="auto")
    assert out[0] == pytest.approx(0.40, abs=0.15)


def test_auto_promote_skips_small_validation_sample(tmp_path, monkeypatch):
    # Gate extra de la promoción automática: staged pero con n_val por debajo
    # del mínimo NO se promueve (queda en staging para revisión/acumulación).
    results = _stage_overconfident(tmp_path, monkeypatch)
    sync = cal.auto_promote_calibrators(results, min_n_val=10_000)
    assert sync["promoted"] == []
    assert sync["skipped"] == ["mlb_h2h"]
    assert cal._load_method_registry(staging=False) == {}
    out = cal.apply_calibration(np.array([0.70]), sport="mlb_h2h", method="auto")
    assert out[0] == pytest.approx(0.70)  # live sigue no-op


def test_auto_promote_demotes_key_no_longer_staged(tmp_path, monkeypatch):
    # Self-healing: un mercado live que el retrain de hoy ya no recomienda
    # (ausente de staging) se demota a no-op, igual que la promoción manual full.
    results = _stage_overconfident(tmp_path, monkeypatch)
    cal.auto_promote_calibrators(results)
    assert "mlb_h2h" in cal._load_method_registry(staging=False)
    staging_reg = tmp_path / "models" / "staging" / "calibration_methods.json"
    staging_reg.write_text("{}", encoding="utf-8")  # nuevo retrain: nada gated
    sync = cal.auto_promote_calibrators([])
    assert sync["demoted"] == ["mlb_h2h"]
    assert cal._load_method_registry(staging=False) == {}
    out = cal.apply_calibration(np.array([0.70]), sport="mlb_h2h", method="auto")
    assert out[0] == pytest.approx(0.70)  # vuelve a no-op seguro


def test_auto_promote_writes_audit_log(tmp_path, monkeypatch):
    results = _stage_overconfident(tmp_path, monkeypatch)
    cal.auto_promote_calibrators(results)
    log = pd.read_csv(tmp_path / "models" / "promotion_log.csv")
    assert {"timestamp", "key", "action", "method", "n_val"} <= set(log.columns)
    row = log[log["action"] == "promoted"].iloc[0]
    assert row["key"] == "mlb_h2h"


def test_auto_promote_setting_defaults_off(monkeypatch):
    from sqp.config import Settings
    monkeypatch.delenv("CALIBRATION_AUTO_PROMOTE", raising=False)
    assert Settings().calibration_auto_promote is False


def test_auto_promote_enabled_in_default_config(monkeypatch):
    # Pin del estado de producción (decisión 2026-07-08): default.yaml activa
    # la autocorrección; el env var (si está) le gana al yaml.
    from sqp.config import Settings
    monkeypatch.delenv("CALIBRATION_AUTO_PROMOTE", raising=False)
    assert Settings.load().calibration_auto_promote is True
    monkeypatch.setenv("CALIBRATION_AUTO_PROMOTE", "false")
    assert Settings.load().calibration_auto_promote is False
