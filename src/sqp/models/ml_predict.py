"""Inference with the trained ML models (parallel to the simulation path).

NO ESTA CONECTADO AL PIPELINE DE PICKS (auditoria 2026-08-28, AUD-LOW-003).
`predict_moneyline` y `predict_total` no tienen ningun llamador en `src/` ni en
`scripts/`: solo los ejercita `tests/test_ml_models.py`. Las probabilidades que
llegan a los candidatos las produce la ruta de simulacion
(`sqp.sports.adapters` -> Elo/Poisson/ratings), no estos modelos.

Hasta el 2026-08-29 los modelos SI se reentrenaban de forma programada -- la
tarea semanal `SQP_Refresh_ML_Cdev` ejecutaba `REFRESH_ML.bat` --, gastando
computo en artefactos que nadie consumia. **El operador retiro esa tarea el
2026-08-29.** `REFRESH_ML.bat` sigue existiendo y funciona: ahora es manual.

Para conectar la mezcla algun dia, la evidencia se produce con
`scripts/train_models.py --oos`, que mide si compensa antes de tocar nada.
Definicion de la tarea retirada, por si hay que restaurarla:
`docs/ops/SQP_Refresh_ML_Cdev.task.xml`.
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
    """Se NIEGA a seguir si el sidecar sha256 existe y no cuadra.

    Hasta el 2026-09-10 avisaba y cargaba igualmente ("loading anyway"), es
    decir: no era un control. El proyecto ya habia decidido lo contrario para el
    MISMO problema cuatro dias antes -- `calibration/calibrator.py:65-80`
    devuelve None y sirve en crudo, con esta razon escrita: *"un control cuyo
    veredicto no cambia lo que pasa despues no es un control (AUD-LOW-001). Y el
    fichero se abre con `joblib.load`, que es deserializacion de pickle"*. La
    correccion se aplico a uno solo de los dos cargadores que hacen `joblib.load`
    de un artefacto de disco (auditoria integral 2026-09-10, AUD-MED-012).

    Sin sidecar NO se falla: los `.joblib` entrenados antes de que `_persist`
    empezara a escribirlo no lo tienen, y romper su carga seria una regresion.
    Lo que no puede seguir pasando es que un digest que NO cuadra deje pasar el
    pickle igualmente.
    """
    sidecar = path.with_suffix(path.suffix + ".sha256")
    if not sidecar.exists():
        return
    expected = sidecar.read_text(encoding="utf-8").strip()
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    if h.hexdigest() != expected:
        raise ValueError(
            f"integridad joblib FALLIDA en {path.name}: el digest no coincide "
            "con su sidecar .sha256. El fichero cambio desde el entrenamiento y "
            "NO se deserializa (joblib.load ejecuta pickle). Re-entrena el "
            "modelo o restaura el artefacto original.")


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
