"""Blend simulation and ML probabilities (option B), disabled by default.

The blend weight must be chosen from out-of-sample evidence per league
(sqp.models.ml_train.oos_moneyline_metrics) — never guessed. Default weight 0.0
means pure simulation, so importing/wiring this is safe until the evidence says
ML helps and by how much.
"""
from __future__ import annotations

import numpy as np


def blend_probabilities(p_sim, p_ml, weight: float = 0.0) -> np.ndarray:
    """Convex blend: result = (1-weight)*p_sim + weight*p_ml.

    weight is the ML share in [0, 1]; 0.0 = pure simulation (blend off).
    """
    w = float(min(max(weight, 0.0), 1.0))
    p_sim = np.asarray(p_sim, dtype=float)
    p_ml = np.asarray(p_ml, dtype=float)
    return np.clip((1.0 - w) * p_sim + w * p_ml, 0.01, 0.99)
