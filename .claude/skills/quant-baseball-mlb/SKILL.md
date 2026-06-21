---
name: quant-baseball-mlb
description: >
  MLB quantitative analysis specialist for the Sports Quant Platform. Use this skill
  whenever the user asks to analyze MLB games, estimate moneyline/runline/total
  probabilities, evolve the MLB adapter, add pitcher or bullpen features, or audit
  MLB calibration — even if they just say "los picks de béisbol" or mention a team.
---

# Quant Baseball (MLB)

Operates the `baseball` family adapter (Poisson runs model) in SQP.

## Market mapping
- Moneyline → P(home wins) from run distribution.
- Runline → spread ±1.5 on the Poisson grid (pushes excluded).
- Total → sum of team run distributions vs the line.

## Priority features (adjust λ_home/λ_away BEFORE the distribution step)
1. **Starting pitcher** (largest single factor): FIP/xFIP, K-BB%, recent pitch count.
   Source: MLB public Stats API (`providers/mlb_statsapi.py` already fetches probables).
2. Bullpen quality and fatigue (innings last 3 days).
3. Offensive quality: wOBA, wRC+ vs LHP/RHP splits.
4. Park factors (run environment per stadium) and weather/wind (especially totals).
5. Lineups when posted.

## Rules
- Never estimate a game without a confirmed/probable starter; flag "pitcher unknown".
- λ adjustments must be bounded (±35%) and logged for audit.
- Calibrate per season segment (April ≠ September).
- Risks: late pitcher scratches, lineup timing, small-sample splits, weather drift.
- All outputs are estimated probabilities; never certainties or guaranteed profit.
