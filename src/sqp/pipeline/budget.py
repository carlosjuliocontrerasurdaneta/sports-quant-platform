"""Quota budget guard for the daily multi-league run.

Each Odds API /odds request costs (markets x regions) credits against the
plan's monthly quota (production runs on a 20k-credit plan, not the 500-request
free tier). Unrationed, running every in-season league daily still burns quota
fast in the autumn (15-20 active leagues). This guard rations the REAL remaining quota
(read from the API response headers) evenly over the days left in the month, so
the daily run never exhausts the plan mid-month. It is plan-agnostic: raise the
plan and the same code automatically runs more leagues.
"""
from __future__ import annotations
import calendar
from datetime import date

# Priority order: when the budget can't cover every active league, the most
# valuable (highest-volume / best-modeled) leagues run first.
DEFAULT_PRIORITY: tuple[str, ...] = (
    "mlb", "nba", "nhl", "wnba", "nfl", "ncaaf", "ncaab", "wncaab",
    "epl", "laliga", "seriea", "bundesliga", "ligue1", "ucl", "mls",
    "brasileirao", "ligamx", "chile", "uwcl", "frauen_bundesliga",
)


def request_cost_per_league(markets: str, regions: str, scores_cost: int = 1) -> int:
    """Estimated Odds API credits per league per day: (markets x regions) for
    the /odds call plus a flat /scores cost for has_scores leagues."""
    n_markets = max(1, len([m for m in markets.split(",") if m.strip()]))
    n_regions = max(1, len([r for r in regions.split(",") if r.strip()]))
    return n_markets * n_regions + max(0, scores_cost)


def days_left_in_month(today: date) -> int:
    last_day = calendar.monthrange(today.year, today.month)[1]
    return last_day - today.day + 1


def leagues_within_budget(active: list[str], priority: tuple[str, ...], *,
                          remaining: int | None, cost_per_league: int,
                          days_left: int, safety_margin: int = 20,
                          max_leagues_per_day: int | None = None,
                          fallback_leagues: int = 0) -> list[str]:
    """Select, in priority order, as many active leagues as the rationed budget
    allows. `remaining` is the API's live quota.

    When `remaining is None` (the live quota could not be read) the budget cannot
    be rationed, so selection falls back to a fixed count: the hard cap
    `max_leagues_per_day` if set, else `fallback_leagues`. The latter defaults to
    0 (fail closed), but the live caller passes a small conservative number so an
    unreadable quota does not silently produce zero picks -- callers should also
    log when they hit this path.
    """
    cost = max(1, cost_per_league)
    ranked = ([lg for lg in priority if lg in active]
              + sorted(lg for lg in active if lg not in priority))
    if remaining is None:
        n = max_leagues_per_day if max_leagues_per_day is not None else fallback_leagues
    else:
        usable = max(0, remaining - max(0, safety_margin))
        n = int((usable / max(1, days_left)) // cost)
        if max_leagues_per_day is not None:
            n = min(n, max_leagues_per_day)
    return ranked[:max(0, n)]
