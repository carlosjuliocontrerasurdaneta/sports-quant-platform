#!/usr/bin/env python
"""Walk-forward feature signal measurement.

For each league, fits features on prior games and measures correlation between
each feature signal and the actual outcome. No lookahead: each game is evaluated
using only results strictly before it.

H2H features correlate with home-win outcome (1=home win, 0.5=draw, 0=away win).
Totals features correlate with whether the game went Over a reference total.

The totals over-rate reference line defaults to the median total of the warmup
games (a fixed, pregame-available constant). Using each game's own actual total
as the reference is endogenous and only available via --per-game-ref for
diagnostics; its totals correlations are spurious, not predictive signal.

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
    """Pearson correlation with a nominal (not dependence-adjusted) p-value."""
    if len(xs) != len(ys):
        raise ValueError("feature/target lengths differ")
    if len(xs) < 4 or not all(math.isfinite(v) for v in xs + ys):
        return 0.0, 1.0
    if len(set(xs)) < 2 or len(set(ys)) < 2:
        return 0.0, 1.0
    from scipy.stats import pearsonr
    result = pearsonr(xs, ys)
    return float(result.statistic), float(result.pvalue)


def _measure_league(league: str, warmup: int, totals_ref: float | None,
                    n_form: int = 5, n_long: int = 10,
                    per_game_ref: bool = False) -> None:
    results = sorted(ResultsStore(ROOT).load(league), key=lambda r: str(r.get("date", "")))
    if 0 < warmup < len(results):
        boundary = str(results[warmup].get("date", ""))[:10]
        while warmup > 0 and str(results[warmup - 1].get("date", ""))[:10] == boundary:
            warmup -= 1
    if len(results) < warmup + 10:
        print(f"  [{league}] insufficient data ({len(results)} games, need {warmup + 10})")
        return

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
    targets: dict[str, list[float]] = {key: [] for key in signals}

    def record(name: str, value: float, outcome: float) -> None:
        signals[name].append(value)
        targets[name].append(outcome)

    outcomes_h2h: list[float] = []
    totals_seen: list[float] = []

    # Prime the index with warmup games and collect their totals so we can derive
    # a FIXED, pregame-available reference line (median of past totals). Using the
    # game's own actual total as the reference (per_game_ref) is endogenous: a high
    # actual total mechanically lowers the measured historical over-rate, producing
    # a spurious negative correlation with the target. That mode is diagnostic only.
    warmup_totals: list[float] = []
    for r in results[:warmup]:
        try:
            hn = normalize(str(r.get("home", "")))
            an = normalize(str(r.get("away", "")))
            team_hist[hn].append(r)
            team_hist[an].append(r)
            warmup_totals.append(float(r["home_score"]) + float(r["away_score"]))
        except (KeyError, TypeError, ValueError):
            pass

    if totals_ref is not None:
        ref_line = totals_ref
    elif warmup_totals:
        srt = sorted(warmup_totals)
        ref_line = srt[len(srt) // 2]  # median of warmup totals (past-only, fixed)
    else:
        ref_line = 0.0

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

        if not math.isfinite(hs) or not math.isfinite(aws):
            continue
        home, away = str(r["home"]), str(r["away"])
        hn, an = normalize(home), normalize(away)
        ref_date = str(r.get("date", ""))[:10]
        actual_total = hs + aws

        # Build team-scoped prior slices (small, already sorted chronologically)
        prior_h = [x for x in team_hist[hn] if str(x.get("date", ""))[:10] < ref_date]
        prior_a = [x for x in team_hist[an] if str(x.get("date", ""))[:10] < ref_date]
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
        game_ref = actual_total if per_game_ref else ref_line
        over_h = team_over_rate(home, prior_h, game_ref, n_long, normalize)
        over_a = team_over_rate(away, prior_a, game_ref, n_long, normalize)

        # H2H signals
        record("streak_diff", float(streak_h - streak_a), out_h2h)
        outcomes_h2h.append(out_h2h)

        if form_h is not None and form_a is not None:
            record("form_diff", form_h - form_a, out_h2h)
        if h2h is not None:
            record("h2h_home", h2h - 0.5, out_h2h)
        if rest_h is not None and rest_a is not None:
            record("rest_diff", float(rest_h - rest_a), out_h2h)
        if margin_h is not None and margin_a is not None:
            record("margin_diff", margin_h - margin_a, out_h2h)
        if form_hh is not None and form_aa is not None:
            record("form_home_role_diff", form_hh - form_aa, out_h2h)
        have_off_def = all(x is not None for x in [sc_h, cc_h, sc_a, cc_a])
        if have_off_def:
            record("off_def_margin",
                (sc_h + cc_a - sc_a - cc_h) / 2.0, out_h2h)  # type: ignore[operator]

        # Totals signals
        totals_seen.append(actual_total)
        if avg_tot_h is not None and avg_tot_a is not None:
            record("avg_total_combined", (avg_tot_h + avg_tot_a) / 2.0, actual_total)
        if over_h is not None and over_a is not None:
            record("over_rate_combined", (over_h + over_a) / 2.0, actual_total)

        # Fold the game just evaluated into both teams' histories, AFTER using
        # them. Without this the index only ever grew during the warmup priming
        # and in the unreadable-score branch, so every test game was scored
        # against the same <=n_long+2 games frozen at the warmup boundary: the
        # features became a constant per team and the "walk-forward" correlation
        # measured a team fixed effect, not a signal (audit 2026-08-31, F-02).
        # On pure random scores the broken harness still emitted `**`.
        # The append goes last on purpose -- moving it earlier is lookahead.
        team_hist[hn].append(r)
        team_hist[an].append(r)

    # Report
    print("Nominal p-values; dependence/multiplicity require evaluate_feature_blocks.py.")
    print(f"\n{'='*60}")
    print(f"  {league.upper()}  |  {len(results)} total games  |  {len(outcomes_h2h)} test games")
    if totals_seen:
        avg_t = sum(totals_seen) / len(totals_seen)
        ref_mode = "per-game (ENDOGENOUS)" if per_game_ref else "fixed"
        print(f"  Avg total in test: {avg_t:.2f}  |  Over ref line ({ref_line:.1f}, "
              f"{ref_mode}): {sum(1 for t in totals_seen if t > ref_line)}/{len(totals_seen)}")
    print(f"{'='*60}")

    h2h_features = ["streak_diff", "form_diff", "h2h_home", "rest_diff",
                    "margin_diff", "form_home_role_diff", "off_def_margin"]
    totals_features = ["avg_total_combined", "over_rate_combined"]

    print(f"\n{'Feature':<25} {'n':>5} {'r':>7} {'p':>7}  {'signal'}")
    print("-" * 60)
    print("  -- H2H/SPREADS (signal vs home win outcome) --")
    for feat in h2h_features:
        vals = signals[feat]
        pairs = list(zip(vals, targets[feat]))
        if len(pairs) < 10:
            print(f"  {feat:<23} {'<10':>5}")
            continue
        xs, ys = zip(*pairs)
        r, p = _pearson(list(xs), list(ys))
        sig = "***" if p < 0.01 else ("**" if p < 0.05 else ("*" if p < 0.10 else ""))
        print(f"  {feat:<23} {len(pairs):>5} {r:>+7.3f} {p:>7.4f}  {sig}")

    print("\n  -- TOTALS (signal vs actual total) --")
    for feat in totals_features:
        vals = signals[feat]
        ys = targets[feat]
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
                         "Default: median total of the warmup games (past-only, fixed "
                         "and pregame-available). This avoids endogeneity.")
    ap.add_argument("--per-game-ref", action="store_true",
                    help="DIAGNOSTIC ONLY: use each game's actual total as its own "
                         "over-rate reference. This is ENDOGENOUS (the reference is the "
                         "target) and yields spurious correlations; do not treat its "
                         "totals numbers as predictive signal.")
    ap.add_argument("--n-form", type=int, default=5,
                    help="Window for form/streak features (default 5)")
    ap.add_argument("--n-long", type=int, default=10,
                    help="Window for margin/h2h/scoring features (default 10)")
    args = ap.parse_args()

    print("\nFeature signal measurement (walk-forward, no lookahead)")
    print("Correlation with outcome. * p<0.10  ** p<0.05  *** p<0.01")
    print("Nominal p-values only; validate with temporal ablations before changing coefficients.\n")

    if args.per_game_ref and args.totals_ref is not None:
        print("error: --per-game-ref and --totals-ref are mutually exclusive",
              file=sys.stderr)
        return 2
    if args.per_game_ref:
        print("WARNING: --per-game-ref is ENDOGENOUS; totals correlations are not "
              "predictive signal.\n")

    for league in args.leagues:
        _measure_league(league, args.warmup, args.totals_ref, args.n_form,
                        args.n_long, per_game_ref=args.per_game_ref)
    return 0


if __name__ == "__main__":
    sys.exit(main())
