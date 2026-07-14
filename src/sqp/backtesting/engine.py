"""Walk-forward backtest: fit ratings strictly on past, estimate next game,
log estimated probability vs outcome. Temporal by construction (no random
splits). Realized ROI requires real historical odds; without them only
calibration metrics are reported.

Bias warnings that apply to any results: lookahead, leakage, survivorship,
selection, multiple testing, regime change.
"""
from __future__ import annotations
import math
import pandas as pd
from sqp.sports.registry import get_adapter
from sqp.calibration.metrics import brier_score, log_loss, expected_calibration_error, reliability_table
from sqp.domain.models import Event


def walk_forward_backtest(results: list[dict], league: str, family: str,
                          league_params: dict | None = None, warmup: int = 60) -> dict:
    adapter = get_adapter(league, family, league_params)
    probs, outcomes = [], []
    dates: list[str] = []
    draw_probs, draw_outcomes = [], []
    threeway_ll_terms: list[float] = []
    for i, r in enumerate(results):
        if i >= warmup:
            ev = Event(event_id=str(i), sport_key="bt", league=league,
                       home=r["home"], away=r["away"], start_time=str(r.get("date")),
                       data_label=r.get("data_label", "real"),
                       home_pitcher=r.get("home_starter"),
                       away_pitcher=r.get("away_starter"))
            est = adapter.estimate(ev, None, None)
            ph = est.home_win_estimated_probability
            if est.draw_estimated_probability is not None:
                # Three-way: binary metrics exclude draws, so the evaluated
                # probability must condition on no-draw or calibration is
                # mechanically overstated against draw-excluded frequencies.
                denom = ph + est.away_win_estimated_probability
                probs.append(ph / denom if denom > 0 else 0.5)
                draw_probs.append(est.draw_estimated_probability)
                draw_outcomes.append(1.0 if r["home_score"] == r["away_score"] else 0.0)
                if r["home_score"] > r["away_score"]:
                    p_outcome = ph
                elif r["home_score"] == r["away_score"]:
                    p_outcome = est.draw_estimated_probability
                else:
                    p_outcome = est.away_win_estimated_probability
                threeway_ll_terms.append(-math.log(max(1e-12, p_outcome)))
            else:
                probs.append(ph)
            outcomes.append(1.0 if r["home_score"] > r["away_score"] else
                            (0.5 if r["home_score"] == r["away_score"] else 0.0))
            dates.append(str(r.get("date")))
        adapter.observe(r)
    mask = [o in (0.0, 1.0) for o in outcomes]  # binary metrics exclude draws
    p = [x for x, m in zip(probs, mask) if m]
    y = [x for x, m in zip(outcomes, mask) if m]
    d = [x for x, m in zip(dates, mask) if m]
    return {
        "league": league, "n_games_evaluated": len(p),
        "brier_score": brier_score(p, y) if p else float("nan"),
        "log_loss": log_loss(p, y) if p else float("nan"),
        "ece": expected_calibration_error(p, y) if p else float("nan"),
        "reliability_table": reliability_table(p, y) if p else pd.DataFrame(),
        "observed_draw_rate": (sum(draw_outcomes) / len(draw_outcomes)) if draw_outcomes else None,
        "n_draws_observed": int(sum(draw_outcomes)),
        "n_threeway_evaluated": len(draw_outcomes),
        "mean_estimated_draw_probability": (sum(draw_probs) / len(draw_probs)) if draw_probs else None,
        "log_loss_threeway": (sum(threeway_ll_terms) / len(threeway_ll_terms)) if threeway_ll_terms else None,
        # Per-game series in temporal order, for rolling-origin holdout selection
        # in tuning (compute losses over arbitrary time windows without re-running).
        "binary_probs": p,
        "binary_outcomes": y,
        "binary_dates": d,
        "threeway_ll_series": list(threeway_ll_terms),
        "note": ("Calibration-only backtest. Three-way leagues are scored on "
                 "P(home | no draw) vs draw-excluded outcomes; draw calibration "
                 "is reported separately. Realized ROI requires real historical "
                 "odds; never infer profitability from calibration alone."),
    }
