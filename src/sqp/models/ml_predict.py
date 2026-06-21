"""Inference with the trained ML models (parallel to the simulation path)."""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sqp.config import ROOT


def _bundle_path(root: Path, sport: str, name: str) -> Path:
    return root / "data" / "models" / f"{sport}_{name}_model.joblib"


def _load(root: Path, sport: str, name: str):
    path = _bundle_path(root, sport, name)
    if not path.exists():
        raise FileNotFoundError(f"No {name} model for '{sport}': {path}. Train it first.")
    b = joblib.load(str(path))
    return b["model"], b["features"]


def predict_moneyline(features, sport: str, root: Path = ROOT,
                      calibrate: bool = False) -> np.ndarray:
    """Estimated P(home win) from the trained model. Accepts a DataFrame or a
    dict of columns; columns are reindexed to the model's training order (missing
    features become NaN and are imputed). Optionally applies the calibrator."""
    model, cols = _load(root, sport, "moneyline")
    X = pd.DataFrame(features).reindex(columns=cols)
    p = model.predict_proba(X.to_numpy(dtype=float))[:, 1]
    if calibrate:
        from sqp.calibration.calibrator import apply_calibration
        p = apply_calibration(p, sport=sport)
    return np.clip(p, 0.01, 0.99)


def predict_total(features, sport: str, root: Path = ROOT) -> np.ndarray:
    """Estimated total (runs/points/goals) from the trained regressor."""
    model, cols = _load(root, sport, "totals")
    X = pd.DataFrame(features).reindex(columns=cols)
    return model.predict(X.to_numpy(dtype=float))
