"""Pipeline health report (ported/generalized from the ML project).

Checks, per ML league (mlb/nba/nfl/nhl), the presence/freshness of: stored
results, the feature dataset, the trained moneyline/totals models and the
calibration model. Emits OK/WARN with actionable warnings. Read-only except for
writing the JSON report under data/output/.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from sqp.config import ROOT
from sqp.logging_config import get_logger
from sqp.monitoring.run_status import read_run_status
from sqp.storage.served_store import ServedStore

log = get_logger(__name__)

ML_LEAGUES = ["mlb", "nba", "nfl", "nhl"]
STALE_FEATURES_DAYS = 14.0
# The Odds API /scores only lists ~3 days back: a pending served row older than
# this will never grade from the daily settlement feed (audit 2026-07-24, M-25/M-26).
SERVED_EXPIRED_DAYS = 3.0


def _rows(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        return int(len(pd.read_csv(path)))
    except Exception as exc:
        # An unreadable file trips the same check as an absent one (both land in
        # the None/0 branch, so nothing passes silently), but the report could
        # not tell them apart: "no stored results" reads as "never ingested"
        # when the truth is "ingested and now corrupt" -- a different repair.
        log.warning("%s existe pero no se pudo leer (%s); se cuenta como sin filas.",
                    path, exc)
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


def _served_pending_expired(root: Path) -> dict[str, int]:
    """league -> count of served rows still pending whose event started more
    than SERVED_EXPIRED_DAYS ago. Covers EVERY league with a served stream (not
    just the 4 ML leagues), closing the blind spot where rows rot silently
    until pending()'s 7-day cutoff drops them."""
    store = ServedStore(root)
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=SERVED_EXPIRED_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    out: dict[str, int] = {}
    for lg in store.leagues():
        try:
            pending = store.pending(lg, now=now)
            if pending.empty:
                continue
            n = int((pending["start_time"].astype(str) < cutoff).sum())
            if n:
                out[lg] = n
        except Exception as exc:
            log.warning("[%s] could not scan the served pending stream: %s", lg, exc)
    return out


def generate_health_report(root: Path = ROOT) -> dict:
    data = root / "data"
    leagues: dict[str, dict] = {}
    warnings: list[str] = []
    # Missing artifacts are ERRORS (the pipeline cannot produce estimates
    # without them); staleness and grading backlogs are WARNINGS. The split
    # gives scripts/health_check.py a meaningful exit code (audit 2026-07-24, M-1).
    errors: list[str] = []

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
            errors.append(f"{lg}: no stored results (run scripts/backfill_results.py)")
        if features_rows in (None, 0):
            errors.append(f"{lg}: feature dataset missing/empty (run scripts/build_features.py)")
        elif features_age_days is not None and features_age_days > STALE_FEATURES_DAYS:
            warnings.append(f"{lg}: features stale ({features_age_days}d)")
        if not moneyline_exists:
            errors.append(f"{lg}: no moneyline model (run scripts/train_models.py)")

    # Fallo del ultimo run diario: es un ERROR porque significa que el pipeline
    # de produccion no completo, y sin esto el fallo es invisible -- el del
    # 2026-07-29 estuvo 24 h sin detectar (auditoria 2026-07-29, S-1).
    run_status = read_run_status(root)
    if run_status and run_status.get("failed"):
        errors.append(
            f"run diario FALLIDO en la etapa '{run_status.get('stage', '?')}' "
            f"(exit {run_status.get('exit_code', '?')}, "
            f"{run_status.get('failed_at', 'fecha desconocida')}); "
            f"revisar logs/ y re-ejecutar DIARIO_COMPLETO.bat")

    served_expired = _served_pending_expired(root)
    for lg, n in sorted(served_expired.items()):
        warnings.append(f"{lg}: {n} served row(s) pending beyond the scores "
                        f"window (>{SERVED_EXPIRED_DAYS:.0f}d; will not grade "
                        f"from the daily feed)")

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "leagues": leagues,
        "registry_exists": (data / "models" / "registry.json").exists(),
        "served_pending_expired": served_expired,
        "status": "ERROR" if errors else ("WARN" if warnings else "OK"),
        "errors": errors,
        "warnings": warnings,
    }

    out = data / "output" / "pipeline_health.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Health report: %s (%d errors, %d warnings)",
             report["status"], len(errors), len(warnings))
    return report
