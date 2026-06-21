#!/usr/bin/env python
"""Diagnose cross-vendor team-name mismatches WITHOUT spending API quota.

Compares the team names in the stored results history (which build the Elo
ratings) against the team names in the most recent persisted odds snapshot
(the live events). Names that appear in the odds but have no rating are exactly
the ones you must add to configs/leagues/team_aliases.yaml so that live
candidates can be generated.

Only the home/away columns of the latest monthly odds snapshot are read.

Example:
  python scripts/audit_team_names.py --leagues epl nba ligamx
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pandas as pd
from sqp.config import ROOT
from sqp.sports.team_names import get_team_normalizer
from sqp.storage.results_store import ResultsStore


def _latest_odds_team_names(league: str) -> set[str]:
    """Distinct team names from the most recent persisted odds snapshot."""
    files = sorted((ROOT / "data" / "odds").glob(f"odds_{league}_*.csv"))
    if not files:
        return set()
    df = pd.read_csv(files[-1], usecols=["home", "away"])
    return set(df["home"].dropna()) | set(df["away"].dropna())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", nargs="+", required=True)
    args = ap.parse_args()

    store = ResultsStore(ROOT)
    issues = 0
    for league in args.leagues:
        norm = get_team_normalizer(league)
        results = store.load(league)
        rated = ({norm(r["home"]) for r in results}
                 | {norm(r["away"]) for r in results})
        odds_names = _latest_odds_team_names(league)

        print(f"\n=== {league} ===")
        if not results:
            print("  no stored results: run scripts/backfill_results.py first.")
        if not odds_names:
            print("  no persisted odds snapshot: run the live pipeline once first.")
            continue

        unmatched = sorted({n for n in odds_names if norm(n) not in rated})
        matched = len(odds_names) - len(unmatched)
        print(f"  event teams: {len(odds_names)} | with ratings: {matched} "
              f"| UNMATCHED: {len(unmatched)}")
        for n in unmatched:
            print(f"    NO RATING: {n!r}  (key: {norm(n)!r})")
        if unmatched:
            issues += 1
            print("  -> map each unmatched name to a stored-results name in "
                  "configs/leagues/team_aliases.yaml, then re-run.")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
