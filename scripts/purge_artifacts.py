#!/usr/bin/env python
"""Purga de artefactos regenerables/expirados (retencion por defecto: 90 dias).

Allowlist estricta (ver sqp.pipeline.cleanup.purge_old_artifacts): copias en
data/predictions/archive/, reportes data/bets/clv_*.md y contadores
data/odds/.closing_credits_*. NUNCA toca datos crudos, settled_*.csv ni
modelos. Corre semanalmente desde BACKFILL_ALL.bat (best-effort).

  python scripts/purge_artifacts.py
  python scripts/purge_artifacts.py --days 120
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.config import ROOT
from sqp.pipeline.cleanup import PURGE_RETENTION_DAYS, purge_old_artifacts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=PURGE_RETENTION_DAYS,
                    help="Retencion en dias (default %(default)s)")
    args = ap.parse_args()
    out = purge_old_artifacts(ROOT, days=args.days)
    print(f"Purga (> {args.days} dias): " +
          ", ".join(f"{k}={v}" for k, v in out.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
