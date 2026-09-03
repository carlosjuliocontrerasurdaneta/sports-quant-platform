"""Ruta de calibracion per-game (sqp.calibration.pergame): pares simetrizados
del walk-forward, entrenamiento bajo clave sandbox *_h2h_pergame (staging,
nunca aplicada por produccion) y evaluacion cruzada sobre la distribucion de
servicio (picks liquidados). Pendiente del 2026-06-23: corregir la
sobreconfianza del moneyline con miles de juegos en vez de ~200 picks."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

import sqp.calibration.calibrator as cal
from sqp.backtesting.engine import walk_forward_backtest
from sqp.calibration.pergame import (cross_evaluate_on_settled,
                                     pergame_pairs_from_results,
                                     train_pergame_calibrator)

LEAGUE, FAMILY = "testlg", "basketball"


def _results(n: int = 140) -> list[dict]:
    """Juegos sinteticos: 8 equipos con fuerza creciente; gana el mas fuerte
    con ruido deterministico para que el Elo produzca probs variadas."""
    rows = []
    for i in range(n):
        h, a = f"T{i % 8}", f"T{(i // 8 + i) % 8}"
        if h == a:
            a = f"T{(i + 1) % 8}"
        sh, sa = int(h[1]), int(a[1])
        upset = (i % 5 == 0)
        home_wins = (sh >= sa) != upset
        rows.append({"home": h, "away": a,
                     "date": f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}",
                     "home_score": 100 + (10 if home_wins else -10),
                     "away_score": 100, "data_label": "real"})
    return rows


def test_engine_returns_aligned_binary_dates():
    res = walk_forward_backtest(_results(), LEAGUE, FAMILY, warmup=60)
    assert "binary_dates" in res
    assert len(res["binary_dates"]) == len(res["binary_probs"])
    assert res["binary_dates"] == sorted(res["binary_dates"])


def test_pergame_pairs_are_symmetrized_by_game():
    df = pergame_pairs_from_results(_results(), LEAGUE, FAMILY, warmup=60)
    assert set(df.columns) >= {"probability", "won", "date", "event_id"}
    assert len(df) == 2 * df["event_id"].nunique()
    for _, g in df.groupby("event_id"):
        assert len(g) == 2
        assert abs(g["probability"].sum() - 1.0) < 1e-9   # p y 1-p
        assert abs(g["won"].sum() - 1.0) < 1e-9           # y y 1-y
        assert g["date"].nunique() == 1


def test_train_pergame_uses_sandbox_key_and_staging_only(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    r = train_pergame_calibrator(LEAGUE, family=FAMILY, results=_results(),
                                 warmup=60)
    key = f"{LEAGUE}_h2h_pergame"
    assert r["key"] == key
    assert "iso_gate" in r and "beta_gate" in r
    # lo persistido vive SOLO en staging, bajo la clave sandbox
    for name, persisted in (("iso", r["iso_persisted"]),
                            ("beta", r["beta_persisted"])):
        assert cal._model_path(key, name, staging=True).exists() is persisted
        assert not cal._model_path(key, name).exists()
    # el registro LIVE no gana ninguna entrada (produccion aplica <liga>_h2h)
    assert key not in cal._load_method_registry()
    assert f"{LEAGUE}_h2h" not in cal._load_method_registry()


def test_cross_evaluate_scores_raw_pergame_and_live(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    key = f"{LEAGUE}_h2h_pergame"
    # calibrador per-game staged: encoge hacia 0.5 (compresivo, pasa gates)
    iso = IsotonicRegression(out_of_bounds="clip")
    grid = np.linspace(0.05, 0.95, 50)
    iso.fit(grid, 0.5 + (grid - 0.5) * 0.5)
    path = cal._model_path(key, "iso", staging=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    cal._persist_or_remove(iso, path, True)
    cal._set_best_method(key, "isotonic", staging=True)
    # picks liquidados sinteticos sobreconfiados (sirve como distro de servicio)
    rng = np.random.default_rng(7)
    probs = rng.uniform(0.55, 0.8, 120)
    hist = pd.DataFrame({
        "league": LEAGUE, "market": "h2h",
        "date": pd.date_range("2026-05-01", periods=120).astype(str),
        "model_probability": probs,
        "result": np.where(rng.uniform(size=120) < 0.5, "win", "loss"),
        "event_id": [f"e{i}" for i in range(120)],
    })
    out = cross_evaluate_on_settled(LEAGUE, hist=hist, recent_fraction=0.5)
    assert out["n_eval"] == 60
    for block in ("raw", "pergame", "live"):
        assert np.isfinite(out[block]["ece"]) and np.isfinite(out[block]["brier"])
    # el modelo sobreconfiado (0.55-0.8 vs 50% real) mejora al comprimir
    assert out["pergame"]["ece"] < out["raw"]["ece"]
    # sin calibrador live para testlg_h2h, "live" == raw (no-op)
    assert abs(out["live"]["ece"] - out["raw"]["ece"]) < 1e-12


def test_cross_evaluate_without_staged_model_reports_none(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    hist = pd.DataFrame({
        "league": LEAGUE, "market": "h2h",
        "date": ["2026-05-01"] * 50, "model_probability": [0.6] * 50,
        "result": ["win", "loss"] * 25, "event_id": [f"e{i}" for i in range(50)],
    })
    out = cross_evaluate_on_settled(LEAGUE, hist=hist)
    assert out["pergame"] is None
    assert np.isfinite(out["raw"]["ece"])


def _hist_dos_columnas(adjusted) -> pd.DataFrame:
    """Historia liquidada donde `adjusted_probability` y `model_probability`
    DIFIEREN, para poder distinguir cual de las dos se evalua."""
    return pd.DataFrame({
        "league": LEAGUE, "market": "h2h",
        "date": ["2026-05-01"] * 50,
        "model_probability": [0.60] * 50,
        "adjusted_probability": adjusted,
        "result": ["win", "loss"] * 25,
        "event_id": [f"e{i}" for i in range(50)],
    })


def test_cross_evaluate_scores_the_column_production_calibrates(tmp_path, monkeypatch):
    """Mide `adjusted_probability`, que es lo que produccion calibra.

    Hasta el 2026-09-03 media `model_probability` (auditoria integral,
    AUD-MED-001). Era un no-op mientras los coeficientes de ajuste valieran 0.0
    -- por eso ningun test lo vio: todos construian historias donde ambas
    columnas coincidian o solo existia una --, pero la evaluacion decide una
    promocion de calibrador, y con un coeficiente activo habria comparado sobre
    una distribucion que produccion ya no sirve.

    Las dos columnas se separan a proposito (0.60 vs 0.90) para que el test
    DISTINGA: con la columna equivocada `mean_prob` seria 0.60.
    """
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    out = cross_evaluate_on_settled(LEAGUE, hist=_hist_dos_columnas([0.90] * 50))
    assert out["n_eval"] == 10
    assert abs(out["raw"]["mean_prob"] - 0.90) < 1e-12, (
        "la evaluacion cruzada no esta midiendo `adjusted_probability`")


def test_cross_evaluate_falls_back_to_model_probability(tmp_path, monkeypatch):
    """Esquema antiguo: sin `adjusted_probability` (o con NaN) usa la cruda.

    Mismo contrato que `calibration.data._project_training`. `hist` es
    inyectable, asi que exigir la columna convertiria en KeyError lo que antes
    devolvia un resultado valido.
    """
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    con_nan = cross_evaluate_on_settled(
        LEAGUE, hist=_hist_dos_columnas([float("nan")] * 50))
    assert abs(con_nan["raw"]["mean_prob"] - 0.60) < 1e-12
    sin_columna = _hist_dos_columnas([0.90] * 50).drop(
        columns=["adjusted_probability"])
    out = cross_evaluate_on_settled(LEAGUE, hist=sin_columna)
    assert abs(out["raw"]["mean_prob"] - 0.60) < 1e-12
    assert out["n_eval"] == 10
