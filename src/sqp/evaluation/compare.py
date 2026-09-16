"""Head-to-head comparison of the simulation model vs the trained ML model, on
the SAME out-of-sample holdout, per league. This is the evidence gate for the
blend decision (option B): it reports calibration for simulation, ML and a grid
of blends, and recommends the ML blend weight that minimises log loss on the
FIRST half of the holdout (ties favour LESS ML, i.e. the smaller weight); the
recommendation's honest metric is then reported on the disjoint second half
(audit 2026-07-24, M-27: selecting and scoring on the same slice inflated it).

Simulation probability comes from the configured sporting adapter,
walk-forward by complete days over the same games as the ML holdout — both models are
scored on identical games. Calibration only; never infer profit from this.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from sqp.calibration.metrics import calibration_report
from sqp.config import ROOT
from sqp.domain.models import Event
from sqp.features.temporal import holdout_start
from sqp.features.mlb import pitcher_name
from sqp.models.blend import blend_probabilities
from sqp.models.ml_train import _clf_pipeline, feature_columns
from sqp.sports.registry import get_adapter
from sqp.storage.feature_store import build_training_dataset

LEAGUE_FAMILY = {"mlb": "baseball", "nba": "basketball", "nfl": "football", "nhl": "hockey"}
BLEND_GRID = (0.25, 0.5, 0.75)


def _sim_probs(df: pd.DataFrame, league: str) -> np.ndarray:
    """Actual configured adapter, with prior-day state like the canonical replay."""
    from sqp.pipeline.daily import _league_meta
    meta = _league_meta(league)
    adapter = get_adapter(league, meta["family"], meta.get("league_params"))
    probs = []
    pending: list[dict] = []
    for r in df.itertuples(index=False):
        day = str(r.date)[:10]
        if pending and pending[0]["date"] != day:
            for prior in pending:
                adapter.observe(prior)
            pending.clear()
        hp, ap = pitcher_name(getattr(r, "home_pitcher", None)), pitcher_name(getattr(r, "away_pitcher", None))
        event = Event(str(r.game_id), "comparison", league, r.home_team, r.away_team, day,
                      home_pitcher=hp, away_pitcher=ap)
        probs.append(adapter.estimate(event, None, None).home_win_estimated_probability)
        pending.append({"date": day, "home": r.home_team, "away": r.away_team,
                        "home_score": float(r.home_score), "away_score": float(r.away_score),
                        "home_starter": hp, "away_starter": ap,
                        "neutral": getattr(r, "neutral", False)})
    return np.asarray(probs, dtype=float)


def compare_league(league: str, val_fraction: float = 0.20, root: Path = ROOT) -> dict:
    if league not in LEAGUE_FAMILY:
        raise ValueError(f"compare_league supports {sorted(LEAGUE_FAMILY)}, got '{league}'")

    df = build_training_dataset(league, root=root).sort_values("date").reset_index(drop=True)
    cols = feature_columns(df)
    split = holdout_start(df["date"], val_fraction)
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
    mid = holdout_start(df.iloc[split:]["date"], 0.5)
    if mid < 1 or mid >= len(y):
        raise ValueError("blend selection and evaluation require distinct dates")

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
