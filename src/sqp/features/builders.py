"""Generic rolling-form dataset builder for the major team sports.

The ML project shipped three near-identical NBA/NFL/NHL builders that differed
only in constants and a couple of field names. This is the consolidated version:
one pure function driven by a per-sport config. MLB keeps a dedicated builder
(pitcher/FIP features) — added in a later step.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from sqp.features.common import get_team_features, update_team_stats


@dataclass(frozen=True)
class SportFeatureConfig:
    sport: str
    rolling_windows: list[int]
    ewm_span: int
    pts_default: float          # league-average points/goals for cold-start
    rest_cap: int               # cap on rest-days feature
    total_col: str = "total_pts"


CONFIGS: dict[str, SportFeatureConfig] = {
    "nba": SportFeatureConfig("nba", [5, 10, 20], 10, 114.5, 15, "total_pts"),
    "nfl": SportFeatureConfig("nfl", [4, 8, 16], 6, 23.2, 21, "total_pts"),
    "nhl": SportFeatureConfig("nhl", [5, 10, 20], 10, 3.15, 5, "total_goals"),
}


def build_team_rolling_dataset(df: pd.DataFrame, cfg: SportFeatureConfig) -> tuple[pd.DataFrame, dict]:
    """Build a pregame training dataset from games with home_team/away_team/
    home_score/away_score (+ optional date, game_id, season, week).

    Returns (dataset, final_team_state). Pure: no files written. Features for
    each game are computed BEFORE that game's result is folded in, so there is
    no leakage.
    """
    needed = {"home_team", "away_team", "home_score", "away_score"}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"build dataset for {cfg.sport}: missing columns {sorted(missing)}")

    df = df.dropna(subset=["home_team", "away_team", "home_score", "away_score"])
    if "week" in df.columns:
        sort_cols = ["date", "week"]
    elif "game_id" in df.columns:
        sort_cols = ["date", "game_id"]
    else:
        sort_cols = ["date"]
    df = df.sort_values([c for c in sort_cols if c in df.columns]).reset_index(drop=True)

    team_stats: dict[str, dict] = {}
    rows: list[dict] = []
    for _, r in df.iterrows():
        home, away = str(r["home_team"]), str(r["away_team"])
        hf = get_team_features(home, team_stats, cfg.rolling_windows, cfg.ewm_span,
                               cfg.pts_default, game_date=r.get("date"), rest_cap=cfg.rest_cap)
        af = get_team_features(away, team_stats, cfg.rolling_windows, cfg.ewm_span,
                               cfg.pts_default, game_date=r.get("date"), rest_cap=cfg.rest_cap)

        home_score, away_score = float(r["home_score"]), float(r["away_score"])
        home_win = int(home_score > away_score)

        row: dict = {
            "date": r.get("date"),
            "game_id": r.get("game_id", ""),
            "season": r.get("season", ""),
            "home_team": home,
            "away_team": away,
            "home_score": home_score,
            "away_score": away_score,
            "home_win": home_win,
            cfg.total_col: home_score + away_score,
        }
        if "week" in df.columns:
            row["week"] = r.get("week", "")
        for k, v in hf.items():
            row[f"home_{k}"] = v
        for k, v in af.items():
            row[f"away_{k}"] = v
        row["diff_pts_ewm"] = hf["pts_ewm"] - af["pts_ewm"]
        row["diff_pa_ewm"] = hf["pa_ewm"] - af["pa_ewm"]
        row["diff_rest_days"] = hf["rest_days"] - af["rest_days"]
        rows.append(row)

        update_team_stats(home, home_score, away_score, home_win == 1, team_stats,
                          cfg.pts_default, game_date=r.get("date"))
        update_team_stats(away, away_score, home_score, home_win == 0, team_stats,
                          cfg.pts_default, game_date=r.get("date"))

    return pd.DataFrame(rows), team_stats
