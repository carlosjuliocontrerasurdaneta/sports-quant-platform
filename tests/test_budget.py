"""Quota budget guard: cost model, month rationing, and priority selection."""
from datetime import date

from sqp.pipeline.budget import (DEFAULT_PRIORITY, days_left_in_month,
                                 leagues_within_budget, request_cost_per_league)


def test_cost_per_league_markets_times_regions_plus_scores():
    assert request_cost_per_league("h2h,spreads,totals", "us") == 3 * 1 + 1
    assert request_cost_per_league("h2h,spreads,totals", "us,eu") == 3 * 2 + 1
    assert request_cost_per_league("h2h", "us", scores_cost=0) == 1


def test_days_left_in_month():
    assert days_left_in_month(date(2026, 6, 13)) == 18      # June has 30 days
    assert days_left_in_month(date(2026, 6, 30)) == 1
    assert days_left_in_month(date(2026, 2, 1)) == 28       # 2026 not a leap year


def test_guard_rations_quota_over_the_month_in_priority_order():
    active = ["chile", "mlb", "nba", "nhl", "wnba", "nfl"]
    # remaining 480, 30 days left, cost 4 -> ~ (480-20)/30//4 = 3 leagues/day
    sel = leagues_within_budget(active, DEFAULT_PRIORITY, remaining=480,
                                cost_per_league=4, days_left=30, safety_margin=20)
    assert sel == ["mlb", "nba", "nhl"]          # top priority, budget-bounded


def test_guard_more_budget_runs_more_leagues():
    active = ["mlb", "nba", "nhl", "wnba"]
    sel = leagues_within_budget(active, DEFAULT_PRIORITY, remaining=10_000,
                                cost_per_league=4, days_left=30)
    assert set(sel) == set(active)               # plenty of quota -> all run


def test_guard_hard_cap_and_none_remaining_fallback():
    active = ["mlb", "nba", "nhl", "wnba"]
    capped = leagues_within_budget(active, DEFAULT_PRIORITY, remaining=10_000,
                                   cost_per_league=4, days_left=30,
                                   max_leagues_per_day=2)
    assert capped == ["mlb", "nba"]
    # No live quota reading -> fall back to the hard cap (or nothing).
    assert leagues_within_budget(active, DEFAULT_PRIORITY, remaining=None,
                                 cost_per_league=4, days_left=30,
                                 max_leagues_per_day=2) == ["mlb", "nba"]
    assert leagues_within_budget(active, DEFAULT_PRIORITY, remaining=None,
                                 cost_per_league=4, days_left=30) == []


def test_guard_none_remaining_uses_conservative_fallback():
    # Quota unreadable + no hard cap: instead of selecting zero leagues (no picks
    # for the day), fall back to the top `fallback_leagues` in priority order.
    active = ["chile", "mlb", "nba", "nhl", "wnba"]
    sel = leagues_within_budget(active, DEFAULT_PRIORITY, remaining=None,
                                cost_per_league=4, days_left=30, fallback_leagues=3)
    assert sel == ["mlb", "nba", "nhl"]
    # A hard cap still takes precedence over the fallback when both are set.
    sel_capped = leagues_within_budget(active, DEFAULT_PRIORITY, remaining=None,
                                       cost_per_league=4, days_left=30,
                                       max_leagues_per_day=2, fallback_leagues=5)
    assert sel_capped == ["mlb", "nba"]


def test_guard_unknown_league_sorted_after_priority():
    active = ["zzz_league", "mlb"]
    sel = leagues_within_budget(active, DEFAULT_PRIORITY, remaining=10_000,
                                cost_per_league=1, days_left=1)
    assert sel[0] == "mlb" and "zzz_league" in sel
