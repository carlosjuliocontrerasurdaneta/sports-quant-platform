"""Feature store for ML training datasets, on top of this platform's CSV results.

Adapts the ML project's parquet-based feature store to the base's architecture:
the source is the append-only ResultsStore (results_{league}.csv, home/away),
not parquet. Output: data/features/{league}_training_dataset.csv plus a manifest
that hashes the source so unchanged data is reused instead of rebuilt.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from sqp.config import ROOT
from sqp.features import mlb as mlb_features
from sqp.features.builders import CONFIGS, build_team_rolling_dataset
from sqp.features.common import write_state_csv
from sqp.logging_config import get_logger
from sqp.storage.results_store import ResultsStore
from sqp.storage.starters import StartersStore

log = get_logger(__name__)

# Leagues with an ML feature builder: nba/nfl/nhl (generic) + mlb (pitcher form).
SUPPORTED = set(CONFIGS) | {"mlb"}


def _features_dir(root: Path) -> Path:
    return root / "data" / "features"


def _state_dir(root: Path) -> Path:
    return root / "data" / "feature_store"


def _feature_path(root: Path, league: str) -> Path:
    return _features_dir(root) / f"{league}_training_dataset.csv"


def _manifest_path(root: Path, league: str) -> Path:
    return _state_dir(root) / f"{league}_manifest.json"


def _results_df(root: Path, league: str) -> pd.DataFrame:
    """Load stored results and rename to the builder's home_team/away_team schema."""
    rows = ResultsStore(root).load(league)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).rename(columns={"home": "home_team", "away": "away_team"})
    df["date"] = pd.to_datetime(df["date"])
    return df


def _mlb_results_df(root: Path) -> pd.DataFrame:
    """MLB results joined with starting pitchers (by game_id) for the builder."""
    rows = ResultsStore(root).load("mlb")
    if not rows:
        return pd.DataFrame()
    StartersStore(root).attach("mlb", rows)  # sets home_starter/away_starter in place
    df = pd.DataFrame(rows).rename(columns={"home": "home_team", "away": "away_team"})
    df["home_pitcher"] = df.get("home_starter", "")
    df["away_pitcher"] = df.get("away_starter", "")
    df["date"] = pd.to_datetime(df["date"])
    return df


def _source_hash(root: Path, league: str) -> str | None:
    p = ResultsStore(root).path(league)
    if not p.exists():
        return None
    h = hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def dataset_is_current(root: Path, league: str) -> bool:
    feat, man = _feature_path(root, league), _manifest_path(root, league)
    if not feat.exists() or not man.exists():
        return False
    try:
        m = json.loads(man.read_text(encoding="utf-8"))
    except Exception:
        return False
    return m.get("source_hash") == _source_hash(root, league)


def build_training_dataset(league: str, force: bool = False, root: Path = ROOT) -> pd.DataFrame:
    """Build (or reuse) the ML training dataset for a league with a feature
    builder (currently nba/nfl/nhl). Reuses the cached CSV when the source
    results file is unchanged, unless force=True."""
    if league not in SUPPORTED:
        raise ValueError(f"No feature builder for '{league}'. Available: {sorted(SUPPORTED)}")
    if not force and dataset_is_current(root, league):
        log.info("[%s] feature dataset current - reusing.", league)
        return pd.read_csv(_feature_path(root, league))

    if league == "mlb":
        df = _mlb_results_df(root)
        if df.empty:
            raise FileNotFoundError("No results for 'mlb'. Backfill results first.")
        out, stats = mlb_features.build_mlb_dataset(df)
        def _write_state() -> None:
            mlb_features.write_mlb_state(stats, _state_dir(root))
    else:
        df = _results_df(root, league)
        if df.empty:
            raise FileNotFoundError(f"No results for '{league}'. Backfill results first.")
        cfg = CONFIGS[league]
        out, team_stats = build_team_rolling_dataset(df, cfg)
        def _write_state() -> None:
            write_state_csv(league, team_stats, cfg.rolling_windows, cfg.ewm_span,
                            cfg.pts_default, _state_dir(root))

    _features_dir(root).mkdir(parents=True, exist_ok=True)
    out.to_csv(_feature_path(root, league), index=False)
    _write_state()

    _manifest_path(root, league).parent.mkdir(parents=True, exist_ok=True)
    _manifest_path(root, league).write_text(json.dumps({
        "source_hash": _source_hash(root, league),
        "rows": len(out),
        "min_date": str(out["date"].min()) if len(out) else None,
        "max_date": str(out["date"].max()) if len(out) else None,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    log.info("[%s] feature dataset: %d rows, %d cols", league, len(out), len(out.columns))
    return out
