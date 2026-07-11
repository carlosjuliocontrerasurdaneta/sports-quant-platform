"""Pipeline health report (ported/generalized from the ML project).

Checks, per ML league (mlb/nba/nfl/nhl), the presence/freshness of: stored
results, the feature dataset, the trained moneyline/totals models and the
calibration model. Emits OK/WARN with actionable warnings. Read-only except for
writing the JSON report under data/output/.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from sqp.config import ROOT
from sqp.logging_config import get_logger

log = get_logger(__name__)

ML_LEAGUES = ["mlb", "nba", "nfl", "nhl"]
STALE_FEATURES_DAYS = 14.0


def _rows(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        return int(len(pd.read_csv(path)))
    except Exception:
        return None


def _age_days(path: Path) -> float | None:
    if not path.exists():
        return None
    return round((time.time() - path.stat().st_mtime) / 86400.0, 1)


def _live_calibration_markets(models_dir: Path, league: str) -> list[str]:
    """Markets whose per-(league, market) calibrator is actually live.

    The pipeline resolves ``calibration_methods.json`` and files named
    ``<league>_<market>_calibration_<iso|beta>.joblib``. The old health check
    looked only for ``<league>_calibration_iso.joblib`` and therefore reported
    calibration=False even while three MLB market models were active.
    """
    registry = models_dir / "calibration_methods.json"
    try:
        methods = json.loads(registry.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(methods, dict):
        return []
    prefix = f"{league}_"
    out: list[str] = []
    for key, method in methods.items():
        if not str(key).startswith(prefix):
            continue
        suffix = {"isotonic": "iso", "beta": "beta"}.get(str(method))
        if suffix and (models_dir / f"{key}_calibration_{suffix}.joblib").exists():
            out.append(str(key)[len(prefix):])
    return sorted(out)


def generate_health_report(root: Path = ROOT) -> dict:
    data = root / "data"
    leagues: dict[str, dict] = {}
    warnings: list[str] = []

    for lg in ML_LEAGUES:
        results = data / "historical" / f"results_{lg}.csv"
        feats = data / "features" / f"{lg}_training_dataset.csv"
        ml_model = data / "models" / f"{lg}_moneyline_model.joblib"
        tot_model = data / "models" / f"{lg}_totals_model.joblib"
        calibration_markets = _live_calibration_markets(data / "models", lg)
        results_rows = _rows(results)
        features_rows = _rows(feats)
        features_age_days = _age_days(feats)
        moneyline_exists = ml_model.exists()

        info = {
            "results_rows": results_rows,
            "features_rows": features_rows,
            "features_age_days": features_age_days,
            "moneyline_model": moneyline_exists,
            "totals_model": tot_model.exists(),
            "calibration": bool(calibration_markets),
            "calibration_markets": calibration_markets,
            "model_age_days": _age_days(ml_model),
        }
        leagues[lg] = info

        if results_rows in (None, 0):
            warnings.append(f"{lg}: no stored results (run scripts/backfill_results.py)")
        if features_rows in (None, 0):
            warnings.append(f"{lg}: feature dataset missing/empty (run scripts/build_features.py)")
        elif features_age_days is not None and features_age_days > STALE_FEATURES_DAYS:
            warnings.append(f"{lg}: features stale ({features_age_days}d)")
        if not moneyline_exists:
            warnings.append(f"{lg}: no moneyline model (run scripts/train_models.py)")

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "leagues": leagues,
        "registry_exists": (data / "models" / "registry.json").exists(),
        "status": "WARN" if warnings else "OK",
        "warnings": warnings,
    }

    out = data / "output" / "pipeline_health.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Health report: %s (%d warnings)", report["status"], len(warnings))
    return report
