#!/usr/bin/env python
"""Manual / demo run: estimate probabilities + edge candidates for an EXPLICIT
list of leagues, printed as a table.

NOT the production entrypoint. Production is scripts/run_all.py (orchestrated by
RUN_DIARIO_ALL.bat): it auto-detects in-season leagues, applies the quota budget
guard, calibration, EV penalty and dynamic bankroll, and writes the consolidated
report. This script does none of that -- use it for quick manual checks and the
synthetic demo only.

Examples:
  python scripts/run_daily.py --sports mlb nba nfl nhl --mode demo
  python scripts/run_daily.py --sports nba wnba epl --mode live
"""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.config import Settings
from sqp.pipeline.daily import run_league, DISCLAIMER


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sports", nargs="+", required=True)
    ap.add_argument("--mode", choices=["demo", "live"], default=None)
    args = ap.parse_args()
    settings = Settings.load()
    for league in args.sports:
        df = run_league(league, settings, mode=args.mode)
        cols = ["home", "away", "home_win_estimated_probability",
                "away_win_estimated_probability", "over_estimated_probability"]
        print(f"\n=== {league.upper()} ===")
        print(df[[c for c in cols if c in df.columns]].round(4).to_string(index=False))
    print(f"\n{DISCLAIMER}")


if __name__ == "__main__":
    main()
