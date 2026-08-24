#!/usr/bin/env python
"""Phase 0 of the derivatives pre-registration (2026-08-24): team-total marginal
calibration, walk-forward, no API.

Necessary-condition test: a team_totals market cannot carry real edge if the
engine's per-team marginal score distribution is miscalibrated. This measures
that marginal against realized per-team runs with strict temporal ordering: each
game is estimated from an adapter fit ONLY on prior games.

For each game and each team side, derives P(team runs > L) from the engine's own
marginal `score_pmf(lam_team, max_score, dispersion_k)` -- the same distribution
the Poisson/NegBin adapter uses -- and settles against the realized team runs.

Pre-registered pass thresholds (fixed before running):
  - |bias| <= 0.03 per line (bias = mean P(Over) - observed Over rate), n >= 300
  - ECE <= 0.05 aggregated over lines
  - Brier(engine) <= Brier(walk-forward base rate) per line (engine adds skill)

Usage:
    python scripts/measure_team_totals_calibration.py --league mlb
    python scripts/measure_team_totals_calibration.py --league mlb --warmup 200
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqp.config import ROOT
from sqp.models.distributions import score_pmf
from sqp.sports.base import Event
from sqp.sports.registry import get_adapter
from sqp.storage.results_store import ResultsStore

LINES = (2.5, 3.5, 4.5, 5.5)
BIAS_MAX = 0.03
ECE_MAX = 0.05


def _tail_over(lam: float, line: float, max_score: int, k: float | None) -> float:
    """P(team runs > line) from the engine marginal. Lines are half-integers,
    so there is no push mass to handle."""
    pmf = score_pmf(lam, max_score, k)
    thr = int(line) + 1  # runs strictly greater than the .5 line
    return sum(pmf[thr:]) / max(1e-12, sum(pmf))


def _brier(ps: list[float], ys: list[float]) -> float:
    return sum((p - y) ** 2 for p, y in zip(ps, ys)) / len(ps)


def _ece(ps: list[float], ys: list[float], bins: int = 10) -> float:
    n = len(ps)
    tot = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, p in enumerate(ps) if (lo <= p < hi or (b == bins - 1 and p == 1.0))]
        if not idx:
            continue
        conf = sum(ps[i] for i in idx) / len(idx)
        acc = sum(ys[i] for i in idx) / len(idx)
        tot += (len(idx) / n) * abs(conf - acc)
    return tot


def _measure(league: str, warmup: int, home_bonus: float | None = None,
             zero_sum: bool = False) -> int:
    results = ResultsStore(ROOT).load(league)
    from sqp.pipeline.daily import _league_meta
    meta = _league_meta(league)
    adapter = get_adapter(league, meta["family"], meta.get("league_params"))
    if not hasattr(adapter, "_rates"):
        print(f"[{league}] adapter has no per-team lambda (_rates); "
              f"team_totals not derivable for this family.")
        return 2
    max_score = adapter.params.get("max_score", 15)
    disp_k = adapter.params.get("dispersion_k")

    # Candidate model tweaks (reversible, offline only; the registry is untouched).
    # Home-only bonus override recomputes lambdas inside the adapter. Zero-sum keeps
    # the configured bonus b but shifts b/2 from home to away, conserving the gap
    # while lowering the total -- so it can be compared head to head.
    base_bonus = float(adapter.params.get("home_scoring_bonus", 0.0))
    if home_bonus is not None:
        adapter.params["home_scoring_bonus"] = home_bonus
    zs_shift = base_bonus / 2.0 if zero_sum else 0.0
    tag = ("baseline" if home_bonus is None and not zero_sum
           else f"zero_sum(b={base_bonus})" if zero_sum
           else f"home_bonus={home_bonus}")

    # engine probs/outcomes and walk-forward base-rate, per (side, line)
    ep: dict[tuple, list[float]] = {}
    ey: dict[tuple, list[float]] = {}
    bp: dict[tuple, list[float]] = {}      # base-rate predictions (running)
    over_ct: dict[tuple, list[float]] = {}  # [overs, total] seen so far

    for i, r in enumerate(results):
        if i >= warmup:
            try:
                hs, aws = float(r["home_score"]), float(r["away_score"])
            except (KeyError, TypeError, ValueError):
                adapter.observe(r)
                continue
            ev = Event(event_id=str(i), sport_key="bt", league=league,
                       home=r["home"], away=r["away"], start_time=str(r.get("date")),
                       data_label=r.get("data_label", "real"),
                       home_pitcher=r.get("home_starter"),
                       away_pitcher=r.get("away_starter"))
            lam_h, lam_a = adapter._rates(ev)
            if zs_shift:
                lam_h, lam_a = max(0.1, lam_h - zs_shift), max(0.1, lam_a - zs_shift)
            for side, lam, runs in (("home", lam_h, hs), ("away", lam_a, aws)):
                for L in LINES:
                    key = (side, L)
                    p = _tail_over(lam, L, max_score, disp_k)
                    y = 1.0 if runs > L else 0.0
                    ep.setdefault(key, []).append(p)
                    ey.setdefault(key, []).append(y)
                    seen = over_ct.setdefault(key, [0.0, 0.0])
                    base = seen[0] / seen[1] if seen[1] >= 30 else 0.5
                    bp.setdefault(key, []).append(base)
                    seen[0] += y
                    seen[1] += 1.0
        adapter.observe(r)

    # Report
    print(f"\n{'='*72}")
    print(f"  {league.upper()} team_totals marginal calibration (walk-forward)")
    print(f"  max_score={max_score}  dispersion_k={disp_k}  warmup={warmup}  [{tag}]")
    print(f"{'='*72}")
    print(f"{'side/line':<12} {'n':>6} {'estOver':>8} {'obsOver':>8} "
          f"{'bias':>7} {'Brier':>7} {'BrierBase':>9} {'skill':>6}")
    print("-" * 72)

    fails: list[str] = []
    all_p: list[float] = []
    all_y: list[float] = []
    for side in ("home", "away"):
        for L in LINES:
            key = (side, L)
            ps, ys, bps = ep[key], ey[key], bp[key]
            n = len(ps)
            est = sum(ps) / n
            obs = sum(ys) / n
            bias = est - obs
            br = _brier(ps, ys)
            brb = _brier(bps, ys)
            skill = "yes" if br <= brb else "NO"
            flag = ""
            if n >= 300 and abs(bias) > BIAS_MAX:
                flag = " <-BIAS"
                fails.append(f"{side}@{L} bias={bias:+.3f}")
            if n >= 300 and br > brb:
                flag += " <-SKILL"
                fails.append(f"{side}@{L} no skill (Brier {br:.4f} > base {brb:.4f})")
            print(f"{side+'@'+str(L):<12} {n:>6} {est:>8.3f} {obs:>8.3f} "
                  f"{bias:>+7.3f} {br:>7.4f} {brb:>9.4f} {skill:>6}{flag}")
            all_p.extend(ps)
            all_y.extend(ys)

    ece = _ece(all_p, all_y)
    print("-" * 72)
    print(f"  Aggregate ECE = {ece:.4f}  (threshold {ECE_MAX})")
    if ece > ECE_MAX:
        fails.append(f"ECE={ece:.4f} > {ECE_MAX}")

    print(f"\n{'='*72}")
    if fails:
        print("  PHASE 0 RESULT: FAIL")
        print("  -> marginal miscalibration to FIX; do NOT spend API credits.")
        for f in fails:
            print(f"     - {f}")
    else:
        print("  PHASE 0 RESULT: PASS")
        print("  -> necessary condition met; team_totals eligible for Phase 1")
        print("     (requires human approval + API credit budget).")
    print(f"{'='*72}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--league", default="mlb", help="League id (default mlb)")
    ap.add_argument("--warmup", type=int, default=200,
                    help="Games to fit before measuring (default 200)")
    ap.add_argument("--home-bonus", type=float, default=None,
                    help="OFFLINE candidate: override home-only home_scoring_bonus.")
    ap.add_argument("--zero-sum", action="store_true",
                    help="OFFLINE candidate: shift the configured bonus b/2 from "
                         "home to away (conserves the gap, lowers the total).")
    args = ap.parse_args()
    if args.zero_sum and args.home_bonus is not None:
        print("error: --zero-sum and --home-bonus are mutually exclusive",
              file=sys.stderr)
        return 2
    return _measure(args.league, args.warmup, args.home_bonus, args.zero_sum)


if __name__ == "__main__":
    sys.exit(main())
