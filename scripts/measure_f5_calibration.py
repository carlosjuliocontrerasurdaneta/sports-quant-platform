#!/usr/bin/env python
"""Phase 2 validation harness for the F5 (first-5-innings) model.

Walk-forward, no API for grading (settles from inning-level outcomes). Derives
the F5 moneyline (three-way), F5 total O/U and F5 team totals from the engine's
starter-isolated F5 run distribution and measures calibration against realized
first-5-innings runs.

REQUIRES inning-level outcomes in the results CSV: columns `home_score_f5` and
`away_score_f5` (runs scored by each team in innings 1-5). These are NOT part of
the current historical data; backfilling them from the MLB Stats API linescore
consumes API quota and is gated on explicit approval. Without them this harness
exits 2 with the exact requirement, so the F5 model ships honestly UNVALIDATED
until the data lands.

Usage:
    python scripts/measure_f5_calibration.py --league mlb
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqp.config import ROOT
from sqp.domain.models import Event
from sqp.sports.registry import get_adapter
from sqp.storage.results_store import ResultsStore

F5_COLS = ("home_score_f5", "away_score_f5")
TOTAL_LINES = (3.5, 4.5, 5.5)


def _brier(ps: list[float], ys: list[float]) -> float:
    return sum((p - y) ** 2 for p, y in zip(ps, ys)) / len(ps)


def _measure(league: str, warmup: int) -> int:
    results = ResultsStore(ROOT).load(league)
    have_f5 = any(all(c in r for c in F5_COLS) for r in results[:200])
    if not have_f5:
        print(f"[{league}] F5 outcomes missing: need columns {F5_COLS} in "
              f"data/historical/results_{league}.csv (innings 1-5 runs per team).")
        print("  Backfill from the MLB Stats API linescore (consumes quota, "
              "requires approval). The F5 model is UNVALIDATED until then.")
        return 2

    from sqp.pipeline.daily import _league_meta
    meta = _league_meta(league)
    adapter = get_adapter(league, meta["family"], meta.get("league_params"))
    if not hasattr(adapter, "estimate_f5"):
        print(f"[{league}] adapter has no F5 model (estimate_f5).")
        return 2

    ml_p: list[float] = []   # P(home leads after 5), no-tie conditional
    ml_y: list[float] = []
    tot_p: dict[float, list[float]] = {L: [] for L in TOTAL_LINES}
    tot_y: dict[float, list[float]] = {L: [] for L in TOTAL_LINES}

    for i, r in enumerate(results):
        if i >= warmup and all(c in r for c in F5_COLS):
            try:
                h5, a5 = float(r["home_score_f5"]), float(r["away_score_f5"])
            except (TypeError, ValueError):
                adapter.observe(r)
                continue
            ev = Event(event_id=str(i), sport_key="bt", league=league,
                       home=r["home"], away=r["away"], start_time=str(r.get("date")),
                       home_pitcher=r.get("home_starter"),
                       away_pitcher=r.get("away_starter"))
            probs = adapter.estimate_f5(ev, total_line=None)
            if h5 != a5:  # moneyline excludes ties (three-way tie graded separately)
                denom = probs["home_win"] + probs["away_win"]
                ml_p.append(probs["home_win"] / denom if denom > 0 else 0.5)
                ml_y.append(1.0 if h5 > a5 else 0.0)
            t5 = h5 + a5
            for L in TOTAL_LINES:
                if t5 == L:
                    continue
                p = adapter.estimate_f5(ev, total_line=L)["over"]
                tot_p[L].append(p)
                tot_y[L].append(1.0 if t5 > L else 0.0)
        adapter.observe(r)

    print(f"\n{'='*60}\n  {league.upper()} F5 calibration (walk-forward)\n{'='*60}")
    if ml_p:
        print(f"  F5 moneyline: n={len(ml_p)} bias={sum(ml_p)/len(ml_p) - sum(ml_y)/len(ml_y):+.3f} "
              f"Brier={_brier(ml_p, ml_y):.4f}")
    for L in TOTAL_LINES:
        if tot_p[L]:
            ps, ys = tot_p[L], tot_y[L]
            print(f"  F5 total@{L}: n={len(ps)} estOver={sum(ps)/len(ps):.3f} "
                  f"obsOver={sum(ys)/len(ys):.3f} bias={sum(ps)/len(ps)-sum(ys)/len(ys):+.3f} "
                  f"Brier={_brier(ps, ys):.4f}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--league", default="mlb")
    ap.add_argument("--warmup", type=int, default=200)
    args = ap.parse_args()
    return _measure(args.league, args.warmup)


if __name__ == "__main__":
    sys.exit(main())
