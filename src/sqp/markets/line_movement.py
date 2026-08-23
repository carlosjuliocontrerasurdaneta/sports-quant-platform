"""Pregame line movement from OddsStore snapshots for the pick pipeline.

At pick-generation time: load all captured odds for a league once, then for
each (event_id, market, selection, point) compute how the consensus implied
probability moved from the first to the most recent snapshot.

movement_pp > 0  = market moved TOWARD the pick (implied prob rose)
movement_pp < 0  = market moved AGAINST the pick (implied prob fell)
None             = fewer than 2 distinct snapshots, or no consensus at either end.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from sqp.audit.clv_movement import snapshot_consensus_price


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


def event_line_movement_pp(
    league_odds: pd.DataFrame,
    event_id: str,
    market: str,
    selection: str,
    point: float | None,
) -> float | None:
    """Return implied-prob movement in pp from oldest to newest snapshot.

    Positive = consensus moved toward the pick (favorable signal).
    Negative = consensus moved against the pick (adverse signal).
    None     = <2 snapshots or no consensus price at one or both ends.
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
    return (1.0 / last - 1.0 / ref) * 100.0
