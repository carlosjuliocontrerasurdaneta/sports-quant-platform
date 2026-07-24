"""MLB feature builder (ported from the ML project, adapted to this base).

MLB differs from the generic team-sport builder: features are in RUNS (not
points) and include per-STARTER pitcher form (rolling runs allowed). Inputs come
from this platform's results store joined with the starters store by game_id, so
the builder expects columns: date, game_id, home_team, away_team, home_score,
away_score, and optional home_pitcher / away_pitcher (starter names).

All features are pregame (past games only) — no leakage.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from sqp.features.common import rest_days

ROLLING_WINDOWS = [7, 14, 30]
EWM_SPAN = 15
RUN_DEFAULT = 4.5


def _default_team_state() -> dict:
    return {"games": 0, "wins": 0, "rf": 0.0, "ra": 0.0,
            "rf_history": [], "ra_history": [], "last_game_date": None}


def _get_team_features(team: str, stats: dict, game_date=None) -> dict:
    s = stats.get(team, _default_team_state())
    games = max(s["games"], 1)
    hist_rf, hist_ra = s["rf_history"], s["ra_history"]

    feats = {"games": s["games"], "win_rate": s["wins"] / games,
             "rf_avg": s["rf"] / games, "ra_avg": s["ra"] / games}
    for w in ROLLING_WINDOWS:
        feats[f"rf_l{w}"] = np.mean(hist_rf[-w:]) if hist_rf else RUN_DEFAULT
        feats[f"ra_l{w}"] = np.mean(hist_ra[-w:]) if hist_ra else RUN_DEFAULT
        feats[f"run_diff_l{w}"] = feats[f"rf_l{w}"] - feats[f"ra_l{w}"]
    feats["rf_ewm"] = (float(pd.Series(hist_rf).ewm(span=EWM_SPAN).mean().iloc[-1])
                       if hist_rf else RUN_DEFAULT)
    feats["ra_ewm"] = (float(pd.Series(hist_ra).ewm(span=EWM_SPAN).mean().iloc[-1])
                       if hist_ra else RUN_DEFAULT)
    feats["run_diff_ewm"] = feats["rf_ewm"] - feats["ra_ewm"]

    feats["rest_days"] = rest_days(s.get("last_game_date"), game_date, cap=15)
    return feats


def _update_team_stats(team: str, rf: float, ra: float, won: bool, stats: dict,
                       game_date=None) -> None:
    if team not in stats:
        stats[team] = _default_team_state()
    s = stats[team]
    s["games"] += 1
    s["wins"] += int(won)
    s["rf"] += rf
    s["ra"] += ra
    s["rf_history"].append(rf)
    s["ra_history"].append(ra)
    if game_date is not None:
        s["last_game_date"] = str(pd.Timestamp(game_date).date())


def _get_pitcher_features(pitcher: str, stats: dict) -> dict:
    s = stats.get(f"__p_{pitcher}", {"starts": 0, "ra_history": []})
    hist = s["ra_history"]
    return {
        "ra_l5": np.mean(hist[-5:]) if hist else RUN_DEFAULT,
        "ra_l10": np.mean(hist[-10:]) if hist else RUN_DEFAULT,
        "ra_ewm": float(pd.Series(hist).ewm(span=5).mean().iloc[-1]) if hist else RUN_DEFAULT,
        "starts": s["starts"],
    }


def _update_pitcher_stats(pitcher: str, ra: float, stats: dict) -> None:
    if not pitcher:
        return
    key = f"__p_{pitcher}"
    if key not in stats:
        stats[key] = {"starts": 0, "ra_history": []}
    stats[key]["starts"] += 1
    stats[key]["ra_history"].append(ra)


def build_mlb_dataset(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Build the MLB training dataset. Returns (dataset, final_stats). Pure."""
    needed = {"home_team", "away_team", "home_score", "away_score"}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"build MLB dataset: missing columns {sorted(missing)}")

    df = df.dropna(subset=["home_team", "away_team", "home_score", "away_score"])
    sort_cols = ["date", "game_id"] if "game_id" in df.columns else ["date"]
    df = df.sort_values([c for c in sort_cols if c in df.columns]).reset_index(drop=True)

    stats: dict[str, dict] = {}
    rows: list[dict] = []
    for _, r in df.iterrows():
        home, away = str(r["home_team"]), str(r["away_team"])
        home_pitcher = str(r.get("home_pitcher", "") or "")
        away_pitcher = str(r.get("away_pitcher", "") or "")

        hf = _get_team_features(home, stats, game_date=r.get("date"))
        af = _get_team_features(away, stats, game_date=r.get("date"))
        hp = _get_pitcher_features(home_pitcher, stats)
        ap = _get_pitcher_features(away_pitcher, stats)

        hs, as_ = float(r["home_score"]), float(r["away_score"])
        home_win = int(hs > as_)

        row: dict = {
            "date": r.get("date"), "game_id": r.get("game_id", ""),
            "home_team": home, "away_team": away,
            "home_score": hs, "away_score": as_,
            "home_win": home_win, "total_runs": hs + as_,
            "home_pitcher": home_pitcher, "away_pitcher": away_pitcher,
        }
        for k, v in hf.items():
            row[f"home_{k}"] = v
        for k, v in af.items():
            row[f"away_{k}"] = v
        row.update({f"home_p_{k}": v for k, v in hp.items()})
        row.update({f"away_p_{k}": v for k, v in ap.items()})
        rows.append(row)

        _update_team_stats(home, hs, as_, home_win == 1, stats, game_date=r.get("date"))
        _update_team_stats(away, as_, hs, home_win == 0, stats, game_date=r.get("date"))
        _update_pitcher_stats(home_pitcher, as_, stats)  # pitcher allowed the away runs
        _update_pitcher_stats(away_pitcher, hs, stats)
    return pd.DataFrame(rows), stats


def write_mlb_state(stats: dict, out_dir: Path) -> None:
    """Persist team and pitcher state CSVs for daily inference."""
    out_dir.mkdir(parents=True, exist_ok=True)
    team_rows, pitcher_rows = [], []
    for key, state in stats.items():
        if key.startswith("__p_"):
            pitcher = key[4:]
            if pitcher:
                pitcher_rows.append({"pitcher": pitcher, **_get_pitcher_features(pitcher, stats)})
        else:
            f = _get_team_features(key, stats)
            # rest_days congelado (3.0 sin game_date): fuera del estado; se
            # recomputa desde last_game_date al servir (auditoria 2026-07-24, M-31).
            f.pop("rest_days", None)
            team_rows.append({"team": key, **f, "last_game_date": state.get("last_game_date")})
    pd.DataFrame(team_rows).to_csv(out_dir / "mlb_team_state.csv", index=False)
    pd.DataFrame(pitcher_rows).to_csv(out_dir / "mlb_pitcher_state.csv", index=False)
