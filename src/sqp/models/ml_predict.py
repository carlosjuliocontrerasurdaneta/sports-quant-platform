"""Inference with the trained ML models (parallel to the simulation path).

NO ESTA CONECTADO AL PIPELINE DE PICKS (auditoria 2026-08-28, AUD-LOW-003).
`predict_moneyline` y `predict_total` no tienen ningun llamador en `src/` ni en
`scripts/`: solo los ejercita `tests/test_ml_models.py`. Las probabilidades que
llegan a los candidatos las produce la ruta de simulacion
(`sqp.sports.adapters` -> Elo/Poisson/ratings), no estos modelos.

Sin embargo los modelos SI se reentrenan de forma programada: la tarea
`SQP_Refresh_ML_Cdev` ejecuta `REFRESH_ML.bat` -> `scripts/train_models.py`. Es
decir, se gasta computo periodico en artefactos que nadie consume, y el nombre
de la tarea sugiere lo contrario a quien mire el Programador.

Decision pendiente del operador: conectar la mezcla (para eso existe el
`--oos` de `train_models.py`, que mide si compensa) o retirar la tarea. No se
toca el Programador de tareas sin orden explicita.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sqp.config import ROOT

_log = logging.getLogger(__name__)


def _bundle_path(root: Path, sport: str, name: str) -> Path:
    return root / "data" / "models" / f"{sport}_{name}_model.joblib"


def _check_hash(path: Path) -> None:
    """Warn if the sha256 sidecar exists and does not match the file."""
    sidecar = path.with_suffix(path.suffix + ".sha256")
    if not sidecar.exists():
        return
    expected = sidecar.read_text(encoding="utf-8").strip()
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    if h.hexdigest() != expected:
        _log.warning("joblib integrity check FAILED for %s — file may have been "
                     "modified since training; loading anyway", path.name)


def _load(root: Path, sport: str, name: str):
    path = _bundle_path(root, sport, name)
    if not path.exists():
        raise FileNotFoundError(f"No {name} model for '{sport}': {path}. Train it first.")
    _check_hash(path)
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
        from sqp.calibration.calibrator import apply_calibration, calibration_key
        p = apply_calibration(p, sport=calibration_key(sport, "h2h"))
    return np.clip(p, 0.01, 0.99)


def predict_total(features, sport: str, root: Path = ROOT) -> np.ndarray:
    """Estimated total (runs/points/goals) from the trained regressor."""
    model, cols = _load(root, sport, "totals")
    X = pd.DataFrame(features).reindex(columns=cols)
    return model.predict(X.to_numpy(dtype=float))
