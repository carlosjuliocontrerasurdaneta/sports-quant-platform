"""Generic rolling-form dataset builder for the major team sports.

The ML project shipped three near-identical NBA/NFL/NHL builders that differed
only in constants and a couple of field names. This is the consolidated version:
one pure function driven by a per-sport config. MLB keeps a dedicated builder
(pitcher/FIP features) — added in a later step.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from sqp.features.common import get_team_features, update_team_stats
from sqp.features.temporal import ordered_games


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
    home_score/away_score and date (+ optional game_id, season, week).

    Returns (dataset, final_team_state). Pure: no files written. Features for
    each game use only results from earlier UTC days. Start times alone do not
    establish when other same-day results became available.
    """
    needed = {"home_team", "away_team", "home_score", "away_score"}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"build dataset for {cfg.sport}: missing columns {sorted(missing)}")

    df = df.dropna(subset=["home_team", "away_team", "home_score", "away_score"])
    df = ordered_games(df)

    team_stats: dict[str, dict] = {}
    rows: list[dict] = []
    pending: list[tuple] = []

    def flush() -> None:
        for home, away, hs, aws, day in pending:
            update_team_stats(home, hs, aws, hs > aws, team_stats,
                              cfg.pts_default, game_date=day)
            update_team_stats(away, aws, hs, aws > hs, team_stats,
                              cfg.pts_default, game_date=day)
        pending.clear()

    for _, r in df.iterrows():
        if pending and pending[0][-1] != r["date"]:
            flush()
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

        pending.append((home, away, home_score, away_score, r["date"]))

    flush()

    return pd.DataFrame(rows), team_stats
