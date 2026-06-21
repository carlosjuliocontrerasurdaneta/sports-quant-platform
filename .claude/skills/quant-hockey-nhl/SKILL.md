---
name: quant-hockey-nhl
description: >
  NHL quantitative specialist for the Sports Quant Platform. Use whenever the user
  asks to analyze NHL games, estimate moneyline/puckline/total probabilities, add
  goalie or xG features, or audit NHL calibration — even casual requests like
  "picks de hockey" or naming teams.
---

# Quant Hockey (NHL)

Operates the `hockey` family adapter (Poisson goals; regulation draws split 50/50
pending an explicit OT/shootout model).

## Market mapping
- Moneyline → Poisson grid + draw reallocation (OT model is the top roadmap item:
  3-on-3 OT + shootout ≈ coin-flip weighted by shooter/goalie quality).
- Puckline → ±1.5 on the goal grid.
- Total → goal sum vs line (5.5/6/6.5 dominate).

## Priority features (adjust λ)
1. **Confirmed goalie** (the single biggest factor): GSAx, recent save%.
   Never emit candidates on unconfirmed goalies — flag and wait.
2. Expected goals (xGF%, 5v5) — far more stable than raw goals.
3. Special teams: PP%/PK% interaction.
4. Shooting% / save% regression (PDO ≈ 100 reversion is the core NHL inefficiency).
5. Rest, travel, back-to-backs (backup goalie probability rises).

## Rules
- Low-scoring variance: edges are small, lines are sharp; respect min_edge strictly.
- All outputs are estimated probabilities; never certainties or guaranteed profit.
