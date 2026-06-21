---
name: quant-american-football
description: >
  American football quantitative specialist (NFL, NCAAF) for the Sports Quant
  Platform. Use whenever the user asks to analyze NFL or college football games,
  estimate moneyline/spread/total probabilities, work with EPA features, key
  numbers, or audit football calibration — even casual requests like "picks de
  la NFL" or naming a matchup.
---

# Quant American Football (NFL / NCAAF)

Operates the `football` family adapter (Normal margin model, σ ≈ 13.5 NFL / 15.5 NCAAF).

## Market mapping & the key-number caveat
Margins cluster on 3 and 7. The Normal model is acceptable for moneyline and totals
but UNDERPRICES spread moves across key numbers. Treat spreads of 2.5–3.5 and 6.5–7.5
with extra margin requirements (raise min_edge) until the discrete margin model
(empirical margin mass function) is implemented.

## Priority features (adjust μ_margin and μ_total)
1. EPA/play offense & defense (best single team-strength signal).
2. Success rate, early-down efficiency.
3. QB status — a QB change is a regime change, not a feature tweak: suppress
   candidates until the market settles.
4. Rest (bye weeks, short weeks), travel, weather (wind > 15mph hits totals).
5. NFL sample is tiny (17 games): heavy regularization, wide priors, slow Elo K is
   wrong here — K=24 with MOV scaling, but cap early-season confidence.

## Rules
- NCAAF: hundreds of teams, huge rating spread; require min 8 rated games and cap
  estimated probabilities at 0.95 (blowout markets are not our edge).
- All outputs are estimated probabilities; never certainties or guaranteed profit.
