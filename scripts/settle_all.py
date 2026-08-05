#!/usr/bin/env python
"""Settle every league that has pending candidates, then write the realized-ROI
audit report. Idempotent (a bet already settled is never graded twice).

  python scripts/settle_all.py --days-from 2
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.audit.report import settlement_audit_report
from sqp.config import ROOT, Settings
from sqp.logging_config import get_logger
from sqp.pipeline.cleanup import unsettled_completed_picks
from sqp.settlement.runner import fetch_and_settle, realized_roi
from sqp.storage.served_store import ServedStore

log = get_logger("sqp.settle_all")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days-from", type=int, default=2)
    args = ap.parse_args()
    settings = Settings.load()

    pred = ROOT / "data" / "predictions"
    # Union: leagues with pending candidates AND leagues that only have a
    # served-probability stream to grade (a day with zero candidates still
    # produced calibration rows for every priced market side).
    leagues = sorted(
        {p.stem.replace("candidates_", "") for p in pred.glob("candidates_*.csv")}
        | set(ServedStore(ROOT).leagues()))
    if not leagues:
        log.warning("No hay candidatos ni stream servido que liquidar.")
    total_new = 0
    failed: list[str] = []
    for lg in leagues:
        try:
            settled = fetch_and_settle(lg, settings, days_from=args.days_from)
        except Exception as exc:
            failed.append(lg)
            log.error("[%s] fallo al liquidar: %s", lg, exc)
            continue
        if not settled.empty:
            total_new += len(settled)
            log.info("[%s] %d nuevas liquidadas | ROI del lote: %.1f%%",
                     lg, len(settled), realized_roi(settled) * 100)
        else:
            log.info("[%s] sin nuevas liquidaciones.", lg)

    # Best-effort: failing to WRITE the report is not a data-integrity problem,
    # so it must not abort a day whose settlement actually succeeded.
    try:
        path = settlement_audit_report()
        log.info("Total nuevas liquidadas: %d. Auditoria -> %s", total_new, path)
        print(f"Liquidadas {total_new} apuestas nuevas. Auditoria: {path}")
    except Exception as exc:
        log.error("No se pudo escribir el reporte de auditoria: %s", exc)
        print(f"Liquidadas {total_new} apuestas nuevas. Auditoria: NO ESCRITA.")

    # DIARIO_COMPLETO.bat relies on this exit status to abort before the daily
    # run. Abort only for the case the guarantee exists for: a league that failed
    # to settle AND still holds commenced, ungraded picks, which the daily run
    # would make permanently ungradeable by overwriting candidates_<league>.csv
    # (M2 window). A transient failure -- exhausted quota, a 5xx -- on a league
    # with nothing at risk threatens no data, and aborting there cost a full day
    # of evidence: under shadow mode the scarce resource is settled sample, not
    # capital. run_all.py keeps its own per-league M2 guard either way.
    if not failed:
        return 0
    at_risk = unsettled_completed_picks(
        ROOT / "data" / "predictions", ROOT / "data" / "bets", failed)
    if at_risk:
        for lg, n in sorted(at_risk.items()):
            log.error("[%s] fallo al liquidar con %d picks ya comenzados sin "
                      "liquidar: se ABORTA el dia para no volverlos no graduables.",
                      lg, n)
        return 1
    log.warning("%d liga(s) fallaron al liquidar (%s) pero ninguna retiene picks "
                "comenzados sin liquidar: el dia continua.",
                len(failed), ", ".join(failed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
