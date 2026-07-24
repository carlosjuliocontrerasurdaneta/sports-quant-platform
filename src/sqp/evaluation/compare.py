"""Head-to-head comparison of the simulation model vs the trained ML model, on
the SAME out-of-sample holdout, per league. This is the evidence gate for the
blend decision (option B): it reports calibration for simulation, ML and a grid
of blends, and recommends the ML blend weight that minimises log loss on the
FIRST half of the holdout (ties favour LESS ML, i.e. the smaller weight); the
recommendation's honest metric is then reported on the disjoint second half
(audit 2026-07-24, M-27: selecting and scoring on the same slice inflated it).

Simulation probability is the Elo baseline (the core of the moneyline estimate),
walk-forward over the same ordered games as the ML holdout — so both models are
scored on identical games. Calibration only; never infer profit from this.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from sqp.calibration.metrics import calibration_report
from sqp.config import ROOT
from sqp.models.blend import blend_probabilities
from sqp.models.elo import EloRatings
from sqp.models.ml_train import _clf_pipeline, feature_columns
from sqp.sports.registry import FAMILY_PARAMS, LEAGUE_OVERRIDES
from sqp.storage.feature_store import build_training_dataset

LEAGUE_FAMILY = {"mlb": "baseball", "nba": "basketball", "nfl": "football", "nhl": "hockey"}
BLEND_GRID = (0.25, 0.5, 0.75)


def _sim_probs(df: pd.DataFrame, league: str) -> np.ndarray:
    """Walk-forward Elo P(home win) for each game, using family/league params."""
    family = LEAGUE_FAMILY[league]
    params = {**FAMILY_PARAMS[family], **LEAGUE_OVERRIDES.get(league, {})}
    elo = EloRatings(k=float(params.get("elo_k", 20.0)),
                     home_advantage=float(params.get("elo_home_adv", 60.0)),
                     mov_scaling=bool(params.get("elo_mov", False)))
    probs = []
    for r in df.itertuples(index=False):
        probs.append(elo.expected_home_win(r.home_team, r.away_team))
        elo.update(r.home_team, r.away_team, float(r.home_score), float(r.away_score))
    return np.asarray(probs, dtype=float)


def compare_league(league: str, val_fraction: float = 0.20, root: Path = ROOT) -> dict:
    if league not in LEAGUE_FAMILY:
        raise ValueError(f"compare_league supports {sorted(LEAGUE_FAMILY)}, got '{league}'")

    df = build_training_dataset(league, root=root).sort_values("date").reset_index(drop=True)
    cols = feature_columns(df)
    split = int(len(df) * (1.0 - val_fraction))
    if split < 50 or len(df) - split < 10:
        raise ValueError(f"[{league}] not enough rows: {split}/{len(df) - split}")

    # Simulation probs for every game (walk-forward), then take the holdout slice.
    sim_all = _sim_probs(df, league)
    sim_hold = sim_all[split:]

    # ML: train on the earlier games, predict the holdout.
    model = _clf_pipeline()
    model.fit(df.iloc[:split][cols].to_numpy(float), df.iloc[:split]["home_win"].to_numpy(int))
    ml_hold = model.predict_proba(df.iloc[split:][cols].to_numpy(float))[:, 1]

    y = df.iloc[split:]["home_win"].to_numpy(int)

    out: dict = {
        "league": league, "n_holdout": int(len(y)),
        "sim": calibration_report(sim_hold, y),
        "ml": calibration_report(ml_hold, y),
    }
    grid = {0.0: out["sim"]["log_loss"], 1.0: out["ml"]["log_loss"]}
    for w in BLEND_GRID:
        rep = calibration_report(blend_probabilities(sim_hold, ml_hold, w), y)
        out[f"blend_{w}"] = rep
        grid[w] = rep["log_loss"]
    out["grid_log_loss"] = grid

    # Weight SELECTION on the first half of the holdout, honest evaluation on
    # the disjoint second half; ties favour less ML.
    mid = max(1, len(y) // 2)

    def _ll(p, yy) -> float:
        return calibration_report(p, yy)["log_loss"]

    sel = {0.0: _ll(sim_hold[:mid], y[:mid]), 1.0: _ll(ml_hold[:mid], y[:mid])}
    for w in BLEND_GRID:
        sel[w] = _ll(blend_probabilities(sim_hold[:mid], ml_hold[:mid], w), y[:mid])
    best = min(sel.items(), key=lambda kv: (kv[1], kv[0]))[0]
    if best == 0.0:
        eval_p = sim_hold[mid:]
    elif best == 1.0:
        eval_p = ml_hold[mid:]
    else:
        eval_p = blend_probabilities(sim_hold[mid:], ml_hold[mid:], best)
    out["selection_log_loss"] = sel
    out["recommended_ml_weight"] = best
    out["recommended_oos_log_loss"] = (_ll(eval_p, y[mid:])
                                       if mid < len(y) else float("nan"))
    return out
