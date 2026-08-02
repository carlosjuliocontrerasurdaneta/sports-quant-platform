"""Trained ML models (ported from the ML project, adapted to this base).

Gradient-boosted moneyline (classifier on home_win) and totals (regressor)
models, trained with a TEMPORAL CV split (TimeSeriesSplit) — never random — per
the platform's modeling rules. Feature columns are DERIVED from the training
dataset (numeric columns minus labels/metadata), so each sport uses whatever the
feature builder produced. Models persist under data/models/ with the feature
list bundled, plus a JSON registry (the base has no SQLite).

This produces estimated probabilities, not certainties.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from sqp.calibration.metrics import calibration_report
from sqp.config import ROOT
from sqp.logging_config import get_logger

log = get_logger(__name__)

# Columns that are labels/metadata — never model inputs.
NON_FEATURE_COLS = {
    "date", "game_id", "season", "week", "home_team", "away_team",
    "home_score", "away_score", "home_win",
    "total_pts", "total_runs", "total_goals",
    "home_pitcher", "away_pitcher",
}
TOTAL_COL = {"mlb": "total_runs", "nba": "total_pts", "nfl": "total_pts", "nhl": "total_goals"}


def feature_columns(df: pd.DataFrame) -> list[str]:
    """Numeric feature columns of a training dataset (labels/metadata excluded)."""
    return [c for c in df.columns
            if c not in NON_FEATURE_COLS and pd.api.types.is_numeric_dtype(df[c])]


def _clf_pipeline() -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", GradientBoostingClassifier(
            n_estimators=300, max_depth=4, learning_rate=0.05,
            subsample=0.8, min_samples_leaf=20, random_state=42)),
    ])


def _reg_pipeline() -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", GradientBoostingRegressor(
            n_estimators=300, max_depth=4, learning_rate=0.05,
            subsample=0.8, min_samples_leaf=20, random_state=42)),
    ])


def _models_dir(root: Path) -> Path:
    return root / "data" / "models"


def _register(root: Path, entry: dict) -> None:
    path = _models_dir(root) / "registry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    reg: list = []
    if path.exists():
        try:
            reg = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            # Never discard a corrupt registry silently: keep the bytes for
            # forensics and start a fresh list (data-integrity rule).
            backup = path.with_name(
                f"{path.name}.corrupt-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}")
            path.replace(backup)
            log.warning("registry.json ilegible; respaldado en %s y reiniciado", backup.name)
            reg = []
    reg.append(entry)
    path.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")


def _persist(root: Path, model, features: list[str], sport: str, name: str,
             metrics: dict) -> Path:
    _models_dir(root).mkdir(parents=True, exist_ok=True)
    path = _models_dir(root) / f"{sport}_{name}_model.joblib"
    joblib.dump({"model": model, "features": features}, str(path))
    _register(root, {
        "sport": sport, "model": name,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "path": str(path), "n_features": len(features), "metrics": metrics,
    })
    log.info("[%s] %s model saved: %s", sport, name, metrics)
    return path


def train_moneyline(df: pd.DataFrame, sport: str, root: Path = ROOT,
                    feature_cols: list[str] | None = None) -> dict:
    cols = feature_cols or feature_columns(df)
    d = df.sort_values("date").dropna(subset=["home_win"] + cols)
    if len(d) < 50:
        raise ValueError(f"[{sport}] too few rows to train moneyline: {len(d)}")
    X, y = d[cols].to_numpy(float), d["home_win"].to_numpy(int)
    model = _clf_pipeline()
    cv = cross_val_score(model, X, y, cv=TimeSeriesSplit(n_splits=5), scoring="roc_auc")
    model.fit(X, y)
    metrics = {"cv_roc_auc_mean": float(cv.mean()), "cv_roc_auc_std": float(cv.std()),
               "n_train": int(len(y)), "cv": "TimeSeriesSplit(5)"}
    path = _persist(root, model, cols, sport, "moneyline", metrics)
    return {"path": str(path), "features": cols, "metrics": metrics}


def train_totals(df: pd.DataFrame, sport: str, root: Path = ROOT,
                 feature_cols: list[str] | None = None) -> dict:
    target = TOTAL_COL[sport]
    cols = feature_cols or feature_columns(df)
    d = df.sort_values("date").dropna(subset=[target] + cols)
    if len(d) < 50:
        raise ValueError(f"[{sport}] too few rows to train totals: {len(d)}")
    X, y = d[cols].to_numpy(float), d[target].to_numpy(float)
    model = _reg_pipeline()
    cv = cross_val_score(model, X, y, cv=TimeSeriesSplit(n_splits=5),
                         scoring="neg_mean_absolute_error")
    model.fit(X, y)
    metrics = {"cv_mae_mean": float(-cv.mean()), "cv_mae_std": float(cv.std()),
               "n_train": int(len(y)), "cv": "TimeSeriesSplit(5)"}
    path = _persist(root, model, cols, sport, "totals", metrics)
    return {"path": str(path), "features": cols, "metrics": metrics}


def oos_moneyline_metrics(df: pd.DataFrame, sport: str, val_fraction: float = 0.20,
                          feature_cols: list[str] | None = None) -> dict:
    """Train on the earlier games, score the most recent val_fraction, and return
    the calibration report. This is the evidence gate for deciding whether (and
    how much) to blend ML with the simulation model — see sqp.models.blend."""
    cols = feature_cols or feature_columns(df)
    d = df.sort_values("date").dropna(subset=["home_win"] + cols).reset_index(drop=True)
    split = int(len(d) * (1.0 - val_fraction))
    tr, va = d.iloc[:split], d.iloc[split:]
    if len(tr) < 50 or len(va) < 10:
        raise ValueError(f"[{sport}] not enough rows for OOS eval: {len(tr)}/{len(va)}")
    model = _clf_pipeline()
    model.fit(tr[cols].to_numpy(float), tr["home_win"].to_numpy(int))
    p = model.predict_proba(va[cols].to_numpy(float))[:, 1]
    return calibration_report(p, va["home_win"].to_numpy(int))
