#!/usr/bin/env python
"""Head-to-head: simulation vs ML vs blend, out-of-sample, per league.

Prints calibration (Brier/log-loss/ECE) for the simulation (Elo) model, the ML
model, and a blend grid, plus the recommended ML blend weight (min holdout log
loss; ties favour less ML). This is the evidence for whether to enable option B.

Example:
  python scripts/compare_models.py --leagues nba mlb nhl nfl
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.evaluation.compare import LEAGUE_FAMILY, compare_league


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", nargs="+", default=sorted(LEAGUE_FAMILY),
                    choices=sorted(LEAGUE_FAMILY))
    args = ap.parse_args()
    for lg in args.leagues:
        try:
            r = compare_league(lg)
            s, m = r["sim"], r["ml"]
            print(f"\n[{lg}] holdout n={r['n_holdout']}")
            print(f"  sim:  Brier={s['brier_score']:.4f} logloss={s['log_loss']:.4f} ECE={s['ece']:.4f}")
            print(f"  ml :  Brier={m['brier_score']:.4f} logloss={m['log_loss']:.4f} ECE={m['ece']:.4f}")
            print(f"  recommended ML blend weight = {r['recommended_ml_weight']} "
                  f"(grid logloss { {k: round(v, 4) for k, v in r['grid_log_loss'].items()} })")
        except Exception as exc:
            print(f"[SKIP] {lg}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
