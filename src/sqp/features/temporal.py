"""Daily information boundary shared by feature builders and ML validation."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit


def ordered_games(df: pd.DataFrame) -> pd.DataFrame:
    """Require dates; a start time alone does not establish result availability."""
    if "date" not in df:
        raise ValueError("pregame features require date")
    out = df.copy()
    days = pd.to_datetime(out["date"], errors="raise", utc=True)
    if days.isna().any():
        raise ValueError("pregame features require non-null dates")
    out["date"] = days.dt.strftime("%Y-%m-%d")
    return out.sort_values(["date"] + (["game_id"] if "game_id" in out else []),
                           kind="stable").reset_index(drop=True)


def daily_splits(dates, n_splits: int = 5):
    """Expanding folds with complete dates on each side, never split a day."""
    days = pd.to_datetime(pd.Series(dates), errors="raise", utc=True).dt.normalize()
    if days.isna().any() or not days.is_monotonic_increasing:
        raise ValueError("validation requires non-null chronological dates")
    unique = days.drop_duplicates().to_numpy()
    for train, test in TimeSeriesSplit(n_splits=n_splits).split(unique):
        yield (np.flatnonzero(days.isin(unique[train]).to_numpy()),
               np.flatnonzero(days.isin(unique[test]).to_numpy()))


def holdout_start(dates, fraction: float = 0.20) -> int:
    if not 0 < fraction < 1:
        raise ValueError("holdout fraction must be in (0, 1)")
    days = pd.to_datetime(pd.Series(dates), errors="raise", utc=True).dt.normalize()
    if days.isna().any() or not days.is_monotonic_increasing or len(days) < 2:
        raise ValueError("holdout requires chronological dates")
    boundary = days.iloc[min(len(days) - 1, int(len(days) * (1 - fraction)))]
    return int((days < boundary).sum())
