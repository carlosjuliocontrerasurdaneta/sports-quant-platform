#!/usr/bin/env python
"""Print the bankroll ledger: initial + realized PnL + manual adjustments.

Use this to verify the running balance against the settlement audit BEFORE
enabling dynamic staking (BANKROLL_DYNAMIC / configs/default.yaml bankroll.dynamic).

  python scripts/bankroll_status.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.config import ROOT, Settings
from sqp.risk.bankroll import BankrollLedger


def main() -> int:
    settings = Settings.load()
    ledger = BankrollLedger(root=ROOT, initial=settings.bankroll)
    s = ledger.summary()
    print("=== Bankroll ledger (real bets only) ===")
    print(f"  initial            : {s['initial']:.2f}")
    print(f"  realized PnL        : {s['realized_pnl']:+.2f}  ({s['n_graded']} graded bets)")
    print(f"  manual adjustments  : {s['adjustments']:+.2f}")
    print("  --------------------------------")
    print(f"  CURRENT BALANCE     : {s['current_balance']:.2f}")
    print(f"  total staked        : {s['total_staked']:.2f}")
    print(f"  realized ROI        : {s['realized_roi']:+.2%}")
    print(f"  max drawdown        : {s['max_drawdown']:.2f}")
    print(f"  dynamic staking     : {'ON' if settings.bankroll_dynamic else 'OFF (static)'}")
    print("\nEstimated probabilities only; realized ROI is a backtest/field figure, "
          "not a profit guarantee.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
