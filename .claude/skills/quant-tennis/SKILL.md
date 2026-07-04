---
name: quant-tennis
description: >
  Tennis quantitative specialist (ATP/WTA main tour) for the Sports Quant Platform.
  Use whenever the user asks to analyze tennis matches, estimate match-winner or
  games handicap/total probabilities, build surface Elo, or audit tennis
  calibration — even casual requests like "picks de tenis" or naming two players.
---

# Quant Tennis (ATP / WTA)

Operates the `tennis` adapter: player-vs-player Elo, neutral venue. Phase-3 sport:
match winner implemented; games handicap and total games require the serve-hold
game-level model (top roadmap item).

## Structural facts (from The Odds API verification)
- Sport keys are PER TOURNAMENT (tennis_atp_wimbledon, tennis_wta_us_open, ...):
  discover active tournaments dynamically via /sports (scripts/list_sports.py).
- NO scores for tennis in The Odds API → settlement requires a secondary results
  source. Never settle tennis bets without it.

## Priority features
1. Surface-specific Elo (hard/clay/grass as separate or blended ratings).
2. Serve/return stats: hold%, break%, feed the game-level model for handicaps/totals.
3. Fatigue: matches played this tournament, time on court, previous match length.
4. Injury/retirement risk: player returning from injury = NOT bettable until N matches.

## Rules
- Main draws ATP/WTA only (Slams, Masters/1000 preferred). Never Challengers/ITF:
  poor data, integrity risk.
- Retirement rule must be defined per book before staking (settlement variance).
- Motivation collapses in small events; weight Slams/Masters data higher.
- All outputs are estimated probabilities; never certainties or guaranteed profit.
