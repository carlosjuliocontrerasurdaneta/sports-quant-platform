"""Pregame line movement from OddsStore snapshots for the pick pipeline.

At pick-generation time: load all captured odds for a league once, then for
each (event_id, market, selection, point) compute how the consensus implied
probability moved from the first to the most recent snapshot, and how fast.

movement_pp > 0         = market moved TOWARD the pick (implied prob rose)
movement_pp < 0         = market moved AGAINST the pick (implied prob fell)
velocity_pp_per_h > 0   = fast move toward; < 0 = fast move against
None                    = fewer than 2 distinct snapshots or no consensus price.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from sqp.audit.clv_movement import snapshot_consensus_price


@dataclass(frozen=True)
class LineMovement:
    movement_pp: float
    velocity_pp_per_h: float  # movement_pp / lookback_h; 0 when lookback_h == 0
    n_snapshots: int
    lookback_h: float


def load_league_odds(league: str, odds_dir: Path) -> pd.DataFrame:
    """Load all captured odds for a league from data/odds/ CSVs.

    Returns an empty DataFrame when no files exist (e.g. demo mode or new league).
    """
    files = sorted(odds_dir.glob(f"odds_{league}_*.csv"))
    if not files:
        return pd.DataFrame()
    return pd.concat(
        [pd.read_csv(f, low_memory=False) for f in files],
        ignore_index=True,
    )


def event_line_movement(
    league_odds: pd.DataFrame,
    event_id: str,
    market: str,
    selection: str,
    point: float | None,
) -> LineMovement | None:
    """Return movement and velocity from oldest to newest snapshot.

    movement_pp: implied-prob delta in pp (negative = adverse for pick).
    velocity_pp_per_h: movement_pp / hours between first and last snapshot.
    None when <2 snapshots or no consensus price at one or both ends.
    """
    if league_odds.empty:
        return None
    event_odds = league_odds[league_odds["event_id"].astype(str) == str(event_id)]
    if event_odds.empty:
        return None
    ts = pd.to_datetime(event_odds["captured_at"], errors="coerce", utc=True)
    valid = event_odds[ts.notna()]
    if valid.empty:
        return None
    stamps = sorted(pd.to_datetime(valid["captured_at"], utc=True).unique())
    if len(stamps) < 2:
        return None
    valid_ts = pd.to_datetime(valid["captured_at"], utc=True)
    ref = snapshot_consensus_price(
        valid[valid_ts == stamps[0]], market, selection, point
    )
    last = snapshot_consensus_price(
        valid[valid_ts == stamps[-1]], market, selection, point
    )
    if ref is None or last is None:
        return None
    movement_pp = (1.0 / last - 1.0 / ref) * 100.0
    lookback_h = float((stamps[-1] - stamps[0]).total_seconds() / 3600.0)
    velocity_pp_per_h = movement_pp / lookback_h if lookback_h > 0.0 else 0.0
    return LineMovement(
        movement_pp=movement_pp,
        velocity_pp_per_h=velocity_pp_per_h,
        n_snapshots=len(stamps),
        lookback_h=lookback_h,
    )
