---
name: quant-basketball
description: >
  Basketball quantitative specialist (NBA, WNBA, NCAAB, WNCAAB) for the Sports Quant
  Platform. Use whenever the user asks to analyze basketball games, estimate
  moneyline/spread/total probabilities, tune pace or rating features, add a
  basketball league, or audit basketball calibration — including women's leagues
  and college, even if they just mention a team or "picks de basket".
---

# Quant Basketball (NBA / WNBA / NCAAB / WNCAAB)

Operates the `basketball` family adapter (Normal margin model). One adapter, four
leagues: parameters differ (see `sports/registry.py` LEAGUE_OVERRIDES), calibration
is tracked separately per league.

## Market mapping
- Margin ~ N(μ = Elo_diff × points_per_elo, σ ≈ 10.5–12 by league).
- Total ~ N(league avg adjusted by pace/efficiency, σ ≈ 14–19).

## Priority features (adjust μ_margin and μ_total)
1. Pace (possessions/48) — drives totals more than anything.
2. Offensive/Defensive Rating (pts per 100 poss), eFG%.
3. Injuries and load management (star availability swings NBA lines 3–7 pts).
4. Rest: back-to-backs, 3-in-4, travel.
5. College only: home crowd variance, conference strength, massive team count —
   require min 10 rated games before emitting candidates.

## Rules
- WNBA/WNCAAB are first-class leagues, never afterthoughts: own overrides, own
  calibration reports, own reliability tables.
- Late injury news invalidates estimates: re-run before tip-off.
- Garbage time pollutes margin data; prefer non-garbage metrics when vendor allows.
- All outputs are estimated probabilities; never certainties or guaranteed profit.
