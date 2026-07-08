#!/usr/bin/env python
"""Closing Line Value (CLV) sobre las apuestas liquidadas reales.

CLI fino sobre sqp.audit.clv (el mismo analisis corre automaticamente en el
run diario via scripts/run_all.py): escribe data/bets/clv_YYYYMMDD.md y lo
imprime. Usa solo datos guardados (data/bets + data/odds), sin cuota API.

  python scripts/clv_analysis.py

Proxy de cierre = consenso mediano capturado; cobertura limitada. CLV es
diagnostico, no promesa de ganancia.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.audit.clv import daily_clv


def main() -> int:
    summary = daily_clv()
    print(Path(summary["path"]).read_text(encoding="utf-8"))
    print(f"\nReporte escrito en: {summary['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
