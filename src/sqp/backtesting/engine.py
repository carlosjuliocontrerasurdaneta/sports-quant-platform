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


def _market_summary(probs: list[float], outcomes: list[float]) -> dict:
    """Metricas de un mercado binario, con el SESGO DIRECCIONAL al frente.

    `bias` = probabilidad media estimada - tasa observada. Es la metrica que el
    arnes existia para poder calcular: el Brier mezcla direccion y afilamiento,
    asi que un modelo que sobreestima sistematicamente puede tener buen Brier.
    El bug del `home_scoring_bonus` (2026-08-18) era exactamente eso.
    """
    n = len(probs)
    mean_p = sum(probs) / n
    observed = sum(outcomes) / n
    return {"n": n,
            "brier": brier_score(probs, outcomes),
            "log_loss": log_loss(probs, outcomes),
            "ece": expected_calibration_error(probs, outcomes),
            "mean_probability": mean_p,
            "observed_rate": observed,
            "bias": mean_p - observed}


def walk_forward_backtest(results: list[dict], league: str, family: str,
                          league_params: dict | None = None, warmup: int = 60,
                          spread_lines: tuple[float, ...] = (),
                          total_lines: tuple[float, ...] = ()) -> dict:
    """Backtest temporal. Sin `spread_lines`/`total_lines` el resultado es
    identico al historico (los cinco scripts que ya lo llaman no se mueven).

    Con lineas, evalua ademas esos mercados contra lineas FIJAS de referencia:
    el desenlace sale del marcador, asi que no hace falta historico de cuotas.
    Los empujes (marcador exactamente en la linea) se excluyen, igual que los
    empates en las metricas binarias del moneyline.
    """
    adapter = get_adapter(league, family, league_params)
    probs, outcomes = [], []
    market_probs: dict[str, list[float]] = {}
    market_outcomes: dict[str, list[float]] = {}

    def _record(key: str, p: float | None, covered: bool, push: bool) -> None:
        if p is None or push:
            return
        market_probs.setdefault(key, []).append(p)
        market_outcomes.setdefault(key, []).append(1.0 if covered else 0.0)
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
            margin = r["home_score"] - r["away_score"]
            total = r["home_score"] + r["away_score"]
            for s in spread_lines:
                # `poisson_match_probs`/`normal_margin_probs` cubren con
                # `margin > -spread_line` y empujan en la igualdad.
                _record(f"spreads@{s}",
                        adapter.estimate(ev, s, None).home_cover_estimated_probability,
                        margin > -s, margin == -s)
            for t in total_lines:
                _record(f"totals@{t}",
                        adapter.estimate(ev, None, t).over_estimated_probability,
                        total > t, total == t)
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
        # Spreads/totals contra lineas fijas. Vacio salvo que se pidan lineas.
        "markets": {k: _market_summary(v, market_outcomes[k])
                    for k, v in market_probs.items() if v},
        "note": ("Calibration-only backtest. Three-way leagues are scored on "
                 "P(home | no draw) vs draw-excluded outcomes; draw calibration "
                 "is reported separately. Realized ROI requires real historical "
                 "odds; never infer profitability from calibration alone."),
    }
