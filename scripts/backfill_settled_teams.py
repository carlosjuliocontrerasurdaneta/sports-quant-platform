#!/usr/bin/env python
"""One-time backfill of home/away/game_date on settled bets from odds snapshots.

  python scripts/backfill_settled_teams.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.config import ROOT
from sqp.logging_config import get_logger
from sqp.settlement.backfill_teams import backfill_settled_file, teams_from_odds

log = get_logger("sqp.backfill_teams")


def main() -> int:
    bets_dir = ROOT / "data" / "bets"
    odds_dir = ROOT / "data" / "odds"
    total_filled = total_unresolved = 0
    for sf in sorted(bets_dir.glob("settled_*.csv")):
        league = sf.stem.replace("settled_", "")
        meta = teams_from_odds(odds_dir, league)
        filled, unresolved = backfill_settled_file(sf, meta)
        total_filled += filled
        total_unresolved += unresolved
        log.info("[%s] backfilled %d, unresolved %d", league, filled, unresolved)
    print(f"Backfill done: {total_filled} filled, {total_unresolved} unresolved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
