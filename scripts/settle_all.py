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
    for lg in leagues:
        try:
            settled = fetch_and_settle(lg, settings, days_from=args.days_from)
        except Exception as exc:
            log.error("[%s] fallo al liquidar: %s", lg, exc)
            continue
        if not settled.empty:
            total_new += len(settled)
            log.info("[%s] %d nuevas liquidadas | ROI del lote: %.1f%%",
                     lg, len(settled), realized_roi(settled) * 100)
        else:
            log.info("[%s] sin nuevas liquidaciones.", lg)

    path = settlement_audit_report()
    log.info("Total nuevas liquidadas: %d. Auditoria -> %s", total_new, path)
    print(f"Liquidadas {total_new} apuestas nuevas. Auditoria: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
