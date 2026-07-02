"""Training-data source for probability calibration.

The calibrator must learn from the probabilities the pipeline ACTUALLY served
(opening-anchored, from data/bets/settled_*.csv), not from the closing-anchored
backtest replay (build_pick_history). Training on the backtest makes the live
overconfidence unlearnable, because live probabilities are anchored to the
opening line while the backtest is anchored to the close. This projects the
settled bets onto the schema train_market_calibrators expects.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from sqp.audit.report import load_all_settled
from sqp.config import ROOT

TRAINING_COLS = ["league", "market", "date", "model_probability", "result"]


def load_settled_training_history(bets_dir: Path | None = None) -> pd.DataFrame:
    """Project settled live bets onto the calibration-training schema
    (league, market, date, model_probability, result).

    The training target is the PURE model probability (pre market-blend), not
    the blended ``estimated_probability``: calibrating the blend forces the
    calibrator to correct the model through a channel diluted 50% by the
    already-well-calibrated no-vig market. On settled data the reblended
    ``(1-s)*cal(p_model) + s*fair`` dominated ``cal(p_used)`` on BOTH OOS ECE
    and Brier at every temporal cut (docs/research/2026-07-02). Serving mirrors
    this: ``daily._decision_probability`` calibrates p_model before the shrink.
    Rows without ``model_probability`` are dropped -- mixing p_model and p_used
    targets in one calibrator would be incoherent.

    ``date`` is the real game date (``game_date``, falling back to
    ``generated_at``) truncated to YYYY-MM-DD, so the temporal split in
    ``train_calibration`` orders by when the game happened -- never by row order,
    which could otherwise place a validation game before its training games and
    leak. Rows with no usable date (both ``game_date`` and ``generated_at``
    empty or missing) are dropped -- valid settled bets always carry a timestamp,
    and an empty date would sort before all real ISO dates, undermining the
    leakage guard. Rows without a ``model_probability`` are also dropped
    (nothing to calibrate); push/void rows are kept and filtered downstream by
    ``train_market_calibrators``. Returns an empty frame with ``TRAINING_COLS``
    when there are no settled bets.
    """
    bets_dir = bets_dir or (ROOT / "data" / "bets")
    settled = load_all_settled(bets_dir)
    if settled.empty:
        return pd.DataFrame(columns=TRAINING_COLS)

    out = pd.DataFrame(index=settled.index)
    out["league"] = settled["league"].astype(str) if "league" in settled else ""
    out["market"] = settled["market"].astype(str) if "market" in settled else ""
    gd = (settled["game_date"].astype(str) if "game_date" in settled
          else pd.Series("", index=settled.index))
    gen = (settled["generated_at"].astype(str) if "generated_at" in settled
           else pd.Series("", index=settled.index))
    out["date"] = gd.where(gd.str.len() >= 10, gen).str[:10]
    if "model_probability" in settled:
        out["model_probability"] = pd.to_numeric(
            settled["model_probability"], errors="coerce")
    else:
        out["model_probability"] = pd.Series(float("nan"), index=settled.index)
    out["result"] = settled["result"].astype(str) if "result" in settled else ""
    out["date"] = out["date"].where(out["date"].str.len() >= 10, other=pd.NA)
    out = out.dropna(subset=["model_probability", "date"]).reset_index(drop=True)
    return out[TRAINING_COLS]


def stage_calibrators_from_settled(settings) -> list[dict]:
    """Stage per-(league, market) calibrator CANDIDATES from the settled live bets.

    Trains on the opening-anchored settled outcomes (see
    ``load_settled_training_history``) into STAGING only -- promotion into the
    live registry stays a deliberate, separate step (scripts/promote_calibration).
    Returns ``train_market_calibrators``' per-group summaries, or ``[]`` when
    calibration is disabled or there are no settled bets yet.
    """
    from sqp.calibration.calibrator import train_market_calibrators

    if not getattr(settings, "calibration_enabled", False):
        return []
    hist = load_settled_training_history()
    if hist.empty:
        return []
    # staging=True by default; the settled source calibrates the PURE model prob.
    return train_market_calibrators(hist, prob_col="model_probability")
