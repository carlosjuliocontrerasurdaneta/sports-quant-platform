---
name: quant-soccer
description: >
  Soccer quantitative specialist (multi-league) for the Sports Quant Platform. Use
  whenever the user asks to analyze soccer/fútbol matches in ANY league, estimate
  1X2/handicap/total goals probabilities, add or configure a league, tune the
  Poisson/Dixon-Coles model, or audit soccer calibration — including women's
  competitions, cups, and South American leagues, even if they just say "picks de
  fútbol" or name two clubs.
---

# Quant Soccer (multi-league)

Operates the `soccer` family adapter: independent Poisson per team, 3-way (1X2).
Leagues are CONFIGURATION (`configs/leagues/soccer.yaml`): adding one = one YAML
entry with sport_key + league scoring environment. Calibration per league, always.

## Market mapping
- 1X2 → Poisson grid (home/draw/away). De-vig must be 3-way (power method).
- Asian/European handicap → grid margins (quarter-lines need split-stake logic — roadmap).
- Total goals → grid sum vs 2.5 (or league-typical line).

## Roadmap to Dixon-Coles
Independent Poisson underprices draws and low-scoring correlation. Implement the
Dixon-Coles tau adjustment for scores ≤1 as the first model upgrade; expect the
biggest gain in low-scoring leagues (Serie A, Brasileirão, Chile).

## Priority features (adjust λ)
1. Attack/defense strength per team (replaces the Elo tilt with explicit rates).
2. xG for/against (where vendor data exists) — much more stable than goals.
3. Home advantage varies WILDLY by league/country: estimate per league, never global.
4. Rotation in cups and congested calendars (UCL weeks depress domestic favorites).
5. Motivation asymmetries: relegation battles, dead rubbers, cup priorities.

## Rules
- Minor leagues: worse data, lower limits, h2h may be the only liquid market —
  verify markets actually populate before promising spreads/totals.
- Women's leagues (Frauen-Bundesliga, UWCL) are first-class: own configs, own calibration.
- All outputs are estimated probabilities; never certainties or guaranteed profit.
