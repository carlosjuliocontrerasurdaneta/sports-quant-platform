"""Training-data source for probability calibration.

The calibrator must learn from the probabilities the pipeline ACTUALLY served
(opening-anchored), not from the closing-anchored backtest replay
(build_pick_history). Training on the backtest makes the live overconfidence
unlearnable, because live probabilities are anchored to the opening line while
the backtest is anchored to the close.

Two serve-distribution sources project onto the schema
``train_market_calibrators`` expects:

- settled live bets (data/bets/settled_*.csv): the placed picks -- small and
  adversely selected (only edges past the floor ever settle).
- the served-probability stream (data/calibration/graded_*.csv): EVERY priced
  market side the pipeline evaluated, graded stake-0 by settlement. Unbiased
  per-event sample of the same serve distribution.

``load_calibration_training_history`` combines both, deduplicating the overlap
(every pick is also a served row) so picked games are not double-weighted.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from sqp.audit.report import load_all_settled
from sqp.config import ROOT

TRAINING_COLS = ["league", "market", "date", "model_probability", "result"]
_KEY_COL = "_dedup_key"


def _project_training(frame: pd.DataFrame, with_key: bool = False) -> pd.DataFrame:
    """Project graded rows (settled bets or served stream) onto TRAINING_COLS.

    The training target is the PURE model probability (pre market-blend), not
    the blended ``estimated_probability``: calibrating the blend forces the
    calibrator to correct the model through a channel diluted 50% by the
    already-well-calibrated no-vig market. On settled data the reblended
    ``(1-s)*cal(p_model) + s*fair`` dominated ``cal(p_used)`` on BOTH OOS ECE
    and Brier at every temporal cut (docs/research/2026-07-02). Serving mirrors
    this: ``daily._decision_probability`` calibrates p_model before the shrink.

    ``date`` is the real game date (``game_date``, falling back to
    ``generated_at``) truncated to YYYY-MM-DD, so the temporal split in
    ``train_calibration`` orders by when the game happened -- never by row order,
    which could otherwise place a validation game before its training games and
    leak. Rows with no usable date are dropped (an empty date would sort before
    all real ISO dates, undermining the leakage guard), as are rows without a
    ``model_probability`` (nothing to calibrate); push/void rows are kept and
    filtered downstream by ``train_market_calibrators``.

    ``with_key=True`` adds a dedup key (league, event, market, selection, line,
    generation day) so the settled and served sources can be combined without
    double-weighting the picks, which exist in both."""
    if frame.empty:
        return pd.DataFrame(columns=TRAINING_COLS + ([_KEY_COL] if with_key else []))
    out = pd.DataFrame(index=frame.index)
    out["league"] = frame["league"].astype(str) if "league" in frame else ""
    out["market"] = frame["market"].astype(str) if "market" in frame else ""
    gd = (frame["game_date"].astype(str) if "game_date" in frame
          else pd.Series("", index=frame.index))
    gen = (frame["generated_at"].astype(str) if "generated_at" in frame
           else pd.Series("", index=frame.index))
    out["date"] = gd.where(gd.str.len() >= 10, gen).str[:10]
    if "model_probability" in frame:
        out["model_probability"] = pd.to_numeric(
            frame["model_probability"], errors="coerce")
    else:
        out["model_probability"] = pd.Series(float("nan"), index=frame.index)
    out["result"] = frame["result"].astype(str) if "result" in frame else ""
    out["date"] = out["date"].where(out["date"].str.len() >= 10, other=pd.NA)
    if with_key:
        empty = pd.Series("", index=frame.index)
        eid = frame["event_id"].astype(str) if "event_id" in frame else empty
        sel = frame["selection"].astype(str) if "selection" in frame else empty
        # .map(str), not .astype(str): under pandas' string dtype astype keeps
        # NaN as NA, which would poison the whole key for h2h rows (line=None)
        # and exempt exactly the rows the dedup exists for.
        line = (pd.to_numeric(frame["line"], errors="coerce").map(str)
                if "line" in frame else empty)
        key = (out["league"] + "|" + eid + "|" + out["market"] + "|"
               + sel + "|" + line + "|" + gen.str[:10])
        # A key missing its event id or generation day cannot distinguish rows
        # (old-schema files); mark it NA so those rows are NEVER deduplicated
        # against each other -- only complete keys participate in the dedup.
        incomplete = (eid.str.len() == 0) | (gen.str[:10].str.len() < 10)
        out[_KEY_COL] = key.where(~incomplete, other=pd.NA)
    out = out.dropna(subset=["model_probability", "date"]).reset_index(drop=True)
    return out


def load_settled_training_history(bets_dir: Path | None = None) -> pd.DataFrame:
    """Settled live bets projected onto the calibration-training schema
    (league, market, date, model_probability, result). See ``_project_training``
    for the target/anti-leakage rules. Returns an empty frame with
    ``TRAINING_COLS`` when there are no settled bets."""
    bets_dir = bets_dir or (ROOT / "data" / "bets")
    return _project_training(load_all_settled(bets_dir))[TRAINING_COLS]


def _load_graded_served(cal_dir: Path | None = None) -> pd.DataFrame:
    """Concatenate every graded served-stream file (data/calibration/graded_*.csv).
    Demo rows never reach here (they live under data/calibration/demo/), but
    ``data_label`` is still filtered to 'real' as a cheap defense."""
    cal_dir = cal_dir or (ROOT / "data" / "calibration")
    frames = []
    for p in sorted(cal_dir.glob("graded_*.csv")):
        try:
            frames.append(pd.read_csv(p))
        except (pd.errors.EmptyDataError, pd.errors.ParserError):
            continue
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    if "data_label" in df.columns:
        df = df[df["data_label"].astype(str) == "real"]
    return df.reset_index(drop=True)


def load_served_training_history(cal_dir: Path | None = None) -> pd.DataFrame:
    """The graded served-probability stream projected onto the calibration
    training schema: every priced market side the pipeline evaluated, not just
    placed picks -- the unbiased serve-distribution sample."""
    return _project_training(_load_graded_served(cal_dir))[TRAINING_COLS]


def load_calibration_training_history(bets_dir: Path | None = None,
                                      cal_dir: Path | None = None) -> pd.DataFrame:
    """Settled bets UNION graded served stream, deduplicated.

    Every pick also exists in the served stream (capture happens before the
    stake filter), so a plain concat would double-weight exactly the adversely
    selected rows the stream is meant to dilute. Dedup key: (league, event,
    market, selection, line, generation day); settled wins (same run, same
    model probability -- the choice is cosmetic). Degrades gracefully to the
    settled-only history while the stream has no graded rows yet."""
    bets_dir = bets_dir or (ROOT / "data" / "bets")
    settled = _project_training(load_all_settled(bets_dir), with_key=True)
    served = _project_training(_load_graded_served(cal_dir), with_key=True)
    both = pd.concat([settled, served], ignore_index=True)
    # NaN keys (incomplete: old-schema rows) must not dedup against each other
    # -- pandas treats NaN as equal in duplicated() -- so they are exempted.
    dup = both[_KEY_COL].notna() & both.duplicated(subset=[_KEY_COL], keep="first")
    return both.loc[~dup, TRAINING_COLS].reset_index(drop=True)


def stage_calibrators_from_settled(settings) -> list[dict]:
    """Stage per-(league, market) calibrator CANDIDATES from the serve-anchored
    graded history (settled live bets UNION the graded served-probability
    stream, deduplicated -- see ``load_calibration_training_history``).

    Training lands in STAGING only -- promotion into the live registry stays a
    deliberate, separate step (scripts/promote_calibration). Returns
    ``train_market_calibrators``' per-group summaries, or ``[]`` when
    calibration is disabled or nothing is graded yet.
    """
    from sqp.calibration.calibrator import train_market_calibrators

    if not getattr(settings, "calibration_enabled", False):
        return []
    hist = load_calibration_training_history()
    if hist.empty:
        return []
    # staging=True by default; serve-anchored sources calibrate the PURE model prob.
    return train_market_calibrators(hist, prob_col="model_probability")
