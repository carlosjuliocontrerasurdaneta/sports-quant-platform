"""Calibration metrics. Calibration is reported PER LEAGUE even though the
engine is shared: a model can be calibrated in NHL and miscalibrated in NFL.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def brier_score(probs, outcomes) -> float:
    p, y = np.asarray(probs, float), np.asarray(outcomes, float)
    return float(np.mean((p - y) ** 2))


def log_loss(probs, outcomes, eps: float = 1e-12) -> float:
    p = np.clip(np.asarray(probs, float), eps, 1 - eps)
    y = np.asarray(outcomes, float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def reliability_table(probs, outcomes, n_bins: int = 10) -> pd.DataFrame:
    """Tabla de fiabilidad por bin. Descarta los pares no finitos.

    `np.digitize(nan, bins)` devuelve `n_bins + 1`, que tras el `-1` y el `clip`
    aterriza en el bin superior: un solo NaN contaminaba
    `mean_estimated_probability` de ese bin y, como `Series.sum()` omite NaN
    mientras el denominador seguia contando esas filas,
    `expected_calibration_error` devolvia un ECE DEFLACTADO -- silencioso y en la
    direccion que aparenta mejor calibracion (auditoria 2026-08-31, BT-04).
    Fallar o excluir es correcto; sub-reportar la metrica que gobierna los gates
    de entrenamiento, no.
    """
    p, y = np.asarray(probs, float), np.asarray(outcomes, float)
    finite = np.isfinite(p) & np.isfinite(y)
    if not finite.all():
        p, y = p[finite], y[finite]
    bins = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(p, bins) - 1, 0, n_bins - 1)
    rows = []
    for b in range(n_bins):
        mask = idx == b
        if mask.sum() == 0:
            continue
        rows.append({
            "bin_low": bins[b], "bin_high": bins[b + 1], "n": int(mask.sum()),
            "mean_estimated_probability": float(p[mask].mean()),
            "observed_frequency": float(y[mask].mean()),
        })
    return pd.DataFrame(rows)


def expected_calibration_error(probs, outcomes, n_bins: int = 10) -> float:
    tbl = reliability_table(probs, outcomes, n_bins)
    if tbl.empty:
        return float("nan")
    n = tbl["n"].sum()
    return float((tbl["n"] / n * (tbl["mean_estimated_probability"] - tbl["observed_frequency"]).abs()).sum())


def calibration_report(probs, outcomes) -> dict:
    """One-shot calibration summary for estimated probabilities vs outcomes.
    Reports ECE, Brier and log loss together so callers (e.g. the calibrator)
    can validate out-of-sample without recomputing each metric."""
    p, y = np.asarray(probs, float), np.asarray(outcomes, float)
    return {
        "ece": expected_calibration_error(p, y),
        "brier_score": brier_score(p, y),
        "log_loss": log_loss(p, y),
        "n_samples": int(len(p)),
        "mean_estimated_probability": float(p.mean()) if len(p) else float("nan"),
        "observed_frequency": float(y.mean()) if len(y) else float("nan"),
    }
