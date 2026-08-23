#!/usr/bin/env python
"""Walk-forward feature signal measurement.

For each league, fits features on prior games and measures correlation between
each feature signal and the actual outcome. No lookahead: each game is evaluated
using only results strictly before it.

H2H features correlate with home-win outcome (1=home win, 0.5=draw, 0=away win).
Totals features correlate with whether the game went Over a reference total.

Usage:
    python scripts/measure_features.py --leagues mlb mls
    python scripts/measure_features.py --leagues mlb --warmup 50 --totals-ref 8.5
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqp.config import ROOT
from sqp.features.rest_form import (
    team_avg_conceded,
    team_avg_margin,
    team_avg_scored,
    team_avg_total,
    team_h2h_form,
    team_over_rate,
    team_recent_form,
    team_recent_form_away,
    team_recent_form_home,
    team_rest_days,
    team_streak,
)
from sqp.sports.registry import get_adapter
from sqp.storage.results_store import ResultsStore


def _pearson(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Pearson r and two-tailed p-value (t-distribution approximation)."""
    n = len(xs)
    if n < 4:
        return 0.0, 1.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return 0.0, 1.0
    r = num / (dx * dy)
    r = max(-1.0, min(1.0, r))
    t = r * math.sqrt(n - 2) / math.sqrt(max(1e-12, 1 - r ** 2))
    # p-value via Student-t CDF approximation (Abramowitz & Stegun)
    df = n - 2
    x = df / (df + t * t)
    # regularized incomplete beta approximation
    try:
        p_one = 0.5 * _incomplete_beta(x, df / 2, 0.5)
        p_val = min(1.0, 2 * p_one)
    except Exception:
        p_val = 1.0
    return r, p_val


def _incomplete_beta(x: float, a: float, b: float, iters: int = 200) -> float:
    """Regularized incomplete beta I_x(a,b) via continued fraction (Lentz method)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(math.log(x) * a + math.log(1 - x) * b - lbeta) / a
    # Use symmetry when x > (a+1)/(a+b+2)
    if x > (a + 1) / (a + b + 2):
        return 1.0 - _incomplete_beta(1 - x, b, a, iters)
    # Lentz continued fraction
    f, C, D = 1e-30, 1e-30, 0.0
    for m in range(iters):
        for step in (0, 1):
            if m == 0 and step == 0:
                num = 1.0
            elif step == 0:
                num = m * (b - m) * x / ((a + 2 * m - 1) * (a + 2 * m))
            else:
                num = -(a + m) * (a + b + m) * x / ((a + 2 * m) * (a + 2 * m + 1))
            D = 1.0 + num * D
            if abs(D) < 1e-30:
                D = 1e-30
            D = 1.0 / D
            C = 1.0 + num / C
            if abs(C) < 1e-30:
                C = 1e-30
            f *= C * D
            if abs(C * D - 1.0) < 1e-8:
                break
    return front * (f - 1.0)


def _measure_league(league: str, warmup: int, totals_ref: float | None,
                    n_form: int = 5, n_long: int = 10) -> None:
    results = ResultsStore(ROOT).load(league)
    if len(results) < warmup + 10:
        print(f"  [{league}] insufficient data ({len(results)} games, need {warmup + 10})")
        return

    meta_path = ROOT / "configs" / "leagues"
    try:
        from sqp.pipeline.daily import _league_meta
        meta = _league_meta(league)
    except Exception as e:
        print(f"  [{league}] could not load meta: {e}")
        return

    adapter = get_adapter(league, meta["family"], meta.get("league_params"))
    normalize = adapter.normalize

    # Per-team rolling history (keyed by normalized name): avoids O(n²) full
    # list scans by keeping only the last n_long+1 games per team.
    from collections import defaultdict, deque
    team_hist: dict[str, deque] = defaultdict(lambda: deque(maxlen=n_long + 2))

    # Feature signals → outcome pairs
    signals: dict[str, list[float]] = {
        "streak_diff": [], "form_diff": [], "h2h_home": [],
        "rest_diff": [], "margin_diff": [],
        "form_home_role_diff": [],
        "off_def_margin": [],
        "avg_total_combined": [], "over_rate_combined": [],
    }
    outcomes_h2h: list[float] = []
    totals_seen: list[float] = []
    ref_line = totals_ref or 0.0  # updated per game when totals_ref is None

    # Prime the index with warmup games
    for r in results[:warmup]:
        try:
            hn = normalize(str(r.get("home", "")))
            an = normalize(str(r.get("away", "")))
            team_hist[hn].append(r)
            team_hist[an].append(r)
        except Exception:
            pass

    for r in results[warmup:]:
        try:
            hs = float(r["home_score"])
            aws = float(r["away_score"])
        except (KeyError, TypeError, ValueError):
            _hn = normalize(str(r.get("home", "")))
            _an = normalize(str(r.get("away", "")))
            team_hist[_hn].append(r)
            team_hist[_an].append(r)
            continue

        home, away = str(r["home"]), str(r["away"])
        hn, an = normalize(home), normalize(away)
        ref_date = str(r.get("date", ""))[:10]
        actual_total = hs + aws

        # Build team-scoped prior slices (small, already sorted chronologically)
        prior_h = list(team_hist[hn])
        prior_a = list(team_hist[an])
        # H2H prior: intersect both teams' histories
        h2h_ids = {id(x) for x in prior_h}
        prior_h2h = [x for x in prior_a if id(x) in h2h_ids]

        if hs > aws:
            out_h2h = 1.0
        elif aws > hs:
            out_h2h = 0.0
        else:
            out_h2h = 0.5

        # --- compute signals using compact per-team histories ---
        streak_h = team_streak(home, prior_h, normalize)
        streak_a = team_streak(away, prior_a, normalize)
        form_h = team_recent_form(home, prior_h, n_form, normalize)
        form_a = team_recent_form(away, prior_a, n_form, normalize)
        h2h = team_h2h_form(home, away, prior_h2h, n_long, normalize)
        rest_h = team_rest_days(home, prior_h, ref_date, normalize)
        rest_a = team_rest_days(away, prior_a, ref_date, normalize)
        margin_h = team_avg_margin(home, prior_h, n_long, normalize)
        margin_a = team_avg_margin(away, prior_a, n_long, normalize)
        form_hh = team_recent_form_home(home, prior_h, n_form, normalize)
        form_aa = team_recent_form_away(away, prior_a, n_form, normalize)
        sc_h = team_avg_scored(home, prior_h, n_long, normalize)
        cc_h = team_avg_conceded(home, prior_h, n_long, normalize)
        sc_a = team_avg_scored(away, prior_a, n_long, normalize)
        cc_a = team_avg_conceded(away, prior_a, n_long, normalize)
        avg_tot_h = team_avg_total(home, prior_h, n_long, normalize)
        avg_tot_a = team_avg_total(away, prior_a, n_long, normalize)
        if totals_ref is None:
            ref_line = actual_total
        over_h = team_over_rate(home, prior_h, ref_line, n_long, normalize)
        over_a = team_over_rate(away, prior_a, ref_line, n_long, normalize)

        # H2H signals
        signals["streak_diff"].append(float(streak_h - streak_a))
        outcomes_h2h.append(out_h2h)

        if form_h is not None and form_a is not None:
            signals["form_diff"].append(form_h - form_a)
        if h2h is not None:
            signals["h2h_home"].append(h2h - 0.5)
        if rest_h is not None and rest_a is not None:
            signals["rest_diff"].append(float(rest_h - rest_a))
        if margin_h is not None and margin_a is not None:
            signals["margin_diff"].append(margin_h - margin_a)
        if form_hh is not None and form_aa is not None:
            signals["form_home_role_diff"].append(form_hh - form_aa)
        have_off_def = all(x is not None for x in [sc_h, cc_h, sc_a, cc_a])
        if have_off_def:
            signals["off_def_margin"].append(
                (sc_h + cc_a - sc_a - cc_h) / 2.0)  # type: ignore[operator]

        # Totals signals
        totals_seen.append(actual_total)
        if avg_tot_h is not None and avg_tot_a is not None:
            signals["avg_total_combined"].append((avg_tot_h + avg_tot_a) / 2.0)
        if over_h is not None and over_a is not None:
            signals["over_rate_combined"].append((over_h + over_a) / 2.0)

    # Report
    print(f"\n{'='*60}")
    print(f"  {league.upper()}  |  {len(results)} total games  |  {len(outcomes_h2h)} test games")
    if totals_seen:
        avg_t = sum(totals_seen) / len(totals_seen)
        print(f"  Avg total in test: {avg_t:.2f}  |  Over ref line ({ref_line:.1f}): "
              f"{sum(1 for t in totals_seen if t > ref_line)}/{len(totals_seen)}")
    print(f"{'='*60}")

    h2h_features = ["streak_diff", "form_diff", "h2h_home", "rest_diff",
                    "margin_diff", "form_home_role_diff", "off_def_margin"]
    totals_features = ["avg_total_combined", "over_rate_combined"]

    print(f"\n{'Feature':<25} {'n':>5} {'r':>7} {'p':>7}  {'signal'}")
    print("-" * 60)
    print("  -- H2H/SPREADS (signal vs home win outcome) --")
    for feat in h2h_features:
        vals = signals[feat]
        if len(vals) < len(outcomes_h2h):
            outs = outcomes_h2h[-len(vals):]
        else:
            outs = outcomes_h2h
        pairs = [(v, o) for v, o in zip(vals, outs)]
        if len(pairs) < 10:
            print(f"  {feat:<23} {'<10':>5}")
            continue
        xs, ys = zip(*pairs)
        r, p = _pearson(list(xs), list(ys))
        sig = "***" if p < 0.01 else ("**" if p < 0.05 else ("*" if p < 0.10 else ""))
        suggested = round(r * 0.05, 4)  # conservative scaling: r=1 -> coef=0.05
        print(f"  {feat:<23} {len(pairs):>5} {r:>+7.3f} {p:>7.4f}  {sig:<4} "
              f"(suggested coef ~{suggested:+.4f})")

    print("\n  -- TOTALS (signal vs actual total) --")
    for feat in totals_features:
        vals = signals[feat]
        ys = totals_seen[-len(vals):] if len(vals) < len(totals_seen) else totals_seen
        pairs = [(v, o) for v, o in zip(vals, ys)]
        if len(pairs) < 10:
            print(f"  {feat:<23} {'<10':>5}")
            continue
        xs, ys2 = zip(*pairs)
        r, p = _pearson(list(xs), list(ys2))
        sig = "***" if p < 0.01 else ("**" if p < 0.05 else ("*" if p < 0.10 else ""))
        print(f"  {feat:<23} {len(pairs):>5} {r:>+7.3f} {p:>7.4f}  {sig}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--leagues", nargs="+", required=True,
                    help="League ids to measure (e.g. mlb mls epl)")
    ap.add_argument("--warmup", type=int, default=50,
                    help="Games used to build initial ratings before measuring (default 50)")
    ap.add_argument("--totals-ref", type=float, default=None,
                    help="Fixed totals reference line for over-rate calculation. "
                         "Default: use each game's actual total as its own reference "
                         "(measures whether teams tend to play in high/low scoring games).")
    ap.add_argument("--n-form", type=int, default=5,
                    help="Window for form/streak features (default 5)")
    ap.add_argument("--n-long", type=int, default=10,
                    help="Window for margin/h2h/scoring features (default 10)")
    args = ap.parse_args()

    print("\nFeature signal measurement (walk-forward, no lookahead)")
    print("Correlation with outcome. * p<0.10  ** p<0.05  *** p<0.01")
    print("suggested coef is conservative (r * 0.05); validate OOS before using.\n")

    for league in args.leagues:
        _measure_league(league, args.warmup, args.totals_ref, args.n_form, args.n_long)
    return 0


if __name__ == "__main__":
    sys.exit(main())
