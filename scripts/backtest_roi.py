#!/usr/bin/env python
"""Realized-ROI backtest over captured historical odds (data/odds/).

Requires historical odds (scripts/backfill_historical_odds.py) and results
(scripts/backfill_results.py). Replays the live staking logic against pre-game
odds and grades against final scores.

  python scripts/backtest_roi.py --leagues mlb wnba
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.backtesting.roi_engine import load_closing_odds, realized_roi_backtest
from sqp.config import ROOT, Settings
from sqp.logging_config import get_logger
from sqp.pipeline.daily import _league_meta
from sqp.storage.results_store import ResultsStore
from sqp.storage.starters import StartersStore

log = get_logger("sqp.roi")

DISCLAIMER = ("Realized ROI over captured pre-game odds (single-snapshot proxy "
              "for closing, limited coverage). Estimated edge is not realized ROI; "
              "this is a backtest and never a profit guarantee.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", nargs="+", required=True)
    ap.add_argument("--warmup", type=int, default=60)
    ap.add_argument(
        "--bet-from-date",
        metavar="YYYY-MM-DD",
        default=None,
        help="Only bet/count games on or after this date. Earlier games still "
        "feed walk-forward ratings but are excluded from the ROI report. "
        "Use to separate the parameter-freeze date from the evaluation window.",
    )
    args = ap.parse_args()
    settings = Settings.load()
    failures = 0
    for league in args.leagues:
        odds = load_closing_odds(ROOT, league)
        if not odds:
            log.warning("[%s] no historical odds captured; run backfill_historical_odds.py.", league)
            failures += 1
            continue
        results = ResultsStore(ROOT).load(league)
        meta = _league_meta(league)
        if meta["family"] == "baseball":
            StartersStore(ROOT).attach(league, results)
        res = realized_roi_backtest(results, odds, league, meta["family"],
                                    meta.get("league_params"), risk=settings.risk,
                                    bankroll=settings.bankroll, warmup=args.warmup,
                                    bet_from_date=args.bet_from_date)
        print(f"\n=== {league.upper()} (realized ROI) ===")
        print(f"odds events: {len(odds)} | results matched: {res['n_events_matched']} | "
              f"bets: {res['n_bets']}")
        if res["n_bets"]:
            print(f"graded: {res['n_graded']} | staked: {res['staked']} | pnl: {res['pnl']} | "
                  f"REALIZED ROI: {res['realized_roi']:.2%}")
            print(f"mean estimated edge: {res['mean_estimated_edge']:.4f} "
                  f"(should approximate realized ROI if calibrated)")
            print(res["by_market"].to_string(index=False))
    print(f"\n{DISCLAIMER}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
