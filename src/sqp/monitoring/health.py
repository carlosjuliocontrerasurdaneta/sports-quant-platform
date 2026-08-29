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
from sqp.storage.served_store import KEY_COLS, ServedStore

log = get_logger(__name__)

ML_LEAGUES = ["mlb", "nba", "nfl", "nhl"]
STALE_FEATURES_DAYS = 14.0
# The Odds API /scores only lists ~3 days back: a pending served row older than
# this will never grade from the daily settlement feed (audit 2026-07-24, M-25/M-26).
SERVED_EXPIRED_DAYS = 3.0
# Ventana de escaneo de `ServedStore.pending`. Se reusa aqui para separar lo
# ACCIONABLE (una fila que acaba de expirar: el proveedor puede estar roto ahora)
# de la perdida acumulada. No es un umbral nuevo: es el que ya define el store.
PENDING_MAX_AGE_DAYS = 7.0


def _rows(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        return int(len(pd.read_csv(path, usecols=[0])))
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


def _served_pending_expired(root: Path) -> tuple[dict[str, int], dict[str, int]]:
    """(recientes, total) por liga de filas servidas que ya NO pueden graduarse.

    Una fila es irrecuperable en cuanto su evento empezo hace mas de
    ``SERVED_EXPIRED_DAYS``: el feed de marcadores deja de listarlo.

    Esta funcion NO puede apoyarse en ``store.pending``, que es justo lo que
    hacia: ese metodo descarta las filas de mas de ``PENDING_MAX_AGE_DAYS``
    porque su proposito es acotar el trabajo de la liquidacion. Heredando ese
    corte, el aviso solo veia la ventana de 3 a 7 dias y las mas viejas
    desaparecian en silencio -- exactamente el punto ciego que decia cerrar.
    Medido el 2026-08-29: reportaba 4 filas mientras habia 154 irrecuperables,
    150 de ellas invisibles por antiguas.

    Se devuelven dos conteos porque responden a preguntas distintas:

    - ``recientes`` (expiradas dentro de la ventana de escaneo): ACCIONABLE. Un
      repunte aqui significa que un proveedor puede estar roto AHORA y todavia
      se esta a tiempo de arreglarlo. Se apaga solo.
    - ``total``: la perdida acumulada de datos de calibracion. No es accionable
      -- esas filas no vuelven -- pero tiene que ser visible y auditable, no un
      numero que nadie puede ver. Va al informe, no al aviso: una alarma que no
      se puede apagar deja de leerse.
    """
    store = ServedStore(root)
    now = datetime.now(timezone.utc)
    expirada = (now - timedelta(days=SERVED_EXPIRED_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    reciente = (now - timedelta(days=PENDING_MAX_AGE_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    recientes: dict[str, int] = {}
    total: dict[str, int] = {}
    for lg in store.leagues():
        try:
            served = store._load(store.served_path(lg))
            if served.empty or "start_time" not in served.columns:
                continue
            graded = store._load(store.graded_path(lg))
            if not graded.empty and set(KEY_COLS).issubset(graded.columns) \
                    and set(KEY_COLS).issubset(served.columns):
                hechas = {tuple(map(str, r))
                          for r in graded[KEY_COLS].values.tolist()}
                served = served[[tuple(map(str, r)) not in hechas
                                 for r in served[KEY_COLS].values.tolist()]]
            if served.empty:
                continue
            st = served["start_time"].astype(str)
            n_total = int((st < expirada).sum())
            if n_total:
                total[lg] = n_total
            n_reciente = int(((st < expirada) & (st >= reciente)).sum())
            if n_reciente:
                recientes[lg] = n_reciente
        except Exception as exc:
            log.warning("[%s] could not scan the served pending stream: %s", lg, exc)
    return recientes, total


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

    served_expired, served_expired_total = _served_pending_expired(root)
    for lg, n in sorted(served_expired.items()):
        warnings.append(f"{lg}: {n} served row(s) pending beyond the scores "
                        f"window (>{SERVED_EXPIRED_DAYS:.0f}d; will not grade "
                        f"from the daily feed)")
    # La perdida acumulada NO es un warning: no se puede arreglar y una alarma
    # permanente deja de leerse. Va al informe para que sea auditable y se pueda
    # seguir su tendencia.
    perdidas = sum(served_expired_total.values())
    if perdidas:
        log.info("Filas servidas irrecuperables acumuladas: %d (%s). No es "
                 "accionable; se registra para seguimiento.", perdidas,
                 ", ".join(f"{lg}={n}" for lg, n in sorted(
                     served_expired_total.items())))

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "leagues": leagues,
        "registry_exists": (data / "models" / "registry.json").exists(),
        "served_pending_expired": served_expired,
        "served_pending_expired_total": served_expired_total,
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
