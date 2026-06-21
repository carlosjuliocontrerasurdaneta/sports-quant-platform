"""Walk-forward grid search for per-league rating hyperparameters.

Guardrails (added after the 2026-06 audit found overfit overrides such as
dc_rho=+0.35 selected on ~30 observed draws): the raw grid argmin is ALWAYS
reported (``best_*``), but a value is only RECOMMENDED for writing when it

  (a) comes from enough evaluated games / observed draws, and
  (b) beats the family default by a log-loss margin.

The dc_rho grid is also clamped to a theoretically sound Dixon-Coles range. None
of this picks business values - it just refuses to overfit on thin samples and
refuses nonsensical draw-inflation values. A temporal holdout for the selection
itself is the recommended next hardening step (selection is still in-sample).
"""
from __future__ import annotations
import math
import pandas as pd
from sqp.logging_config import get_logger
from .engine import walk_forward_backtest

log = get_logger("sqp.tuning")

# Rolling-origin holdout: number of contiguous future test blocks and the share
# of the timeline reserved as the initial training seed before the first block.
DEFAULT_HOLDOUT_SPLITS = 4
HOLDOUT_MIN_TRAIN_FRAC = 0.4

DEFAULT_HOME_ADV_GRID: tuple[float, ...] = tuple(float(x) for x in range(0, 151, 15))
DEFAULT_DC_RHO_GRID: tuple[float, ...] = (-0.20, -0.15, -0.10, -0.05, 0.0, 0.05)

# Dixon-Coles draw inflation: rho < 0 inflates draws; values above ~0.05 or
# below ~-0.30 invert/overpower the correction and are not meaningful.
DC_RHO_BOUNDS: tuple[float, float] = (-0.30, 0.05)

# Acceptance thresholds (audit 2026-06). Parametrizable per call.
MIN_EVAL_HOME_ADV = 200     # evaluated binary games required to override home adv
MIN_DRAWS_DC_RHO = 80       # observed draws required to override dc_rho
IMPROVEMENT_MARGIN = 0.002  # required log-loss gain vs the family default


def _clamp_grid(grid: tuple[float, ...], bounds: tuple[float, float], name: str) -> tuple[float, ...]:
    lo, hi = bounds
    kept = tuple(x for x in grid if lo <= x <= hi)
    dropped = [x for x in grid if not (lo <= x <= hi)]
    if dropped:
        log.warning("[%s] grid values outside %s dropped: %s", name, bounds, dropped)
    if not kept:
        raise ValueError(f"{name} grid {grid} has no value within bounds {bounds}.")
    return kept


def _loss_at(table: pd.DataFrame, col: str, key_col: str, value: float, tol: float = 1e-9):
    hit = table[(table[key_col] - value).abs() <= tol]
    return float(hit[col].iloc[0]) if not hit.empty else None


def _decide(n: int, min_n: int, n_label: str, improvement: float, margin: float) -> tuple[bool, str]:
    if n < min_n:
        return False, f"insufficient sample ({n} {n_label} < {min_n}); family default kept."
    if improvement < margin:
        return False, (f"improvement {improvement:.4f} < margin {margin:.4f} vs default; "
                       "family default kept.")
    return True, f"accepted: {n} {n_label}, improvement {improvement:.4f} >= {margin:.4f}."


def _binary_nll_series(probs: list[float], outcomes: list[float]) -> list[float]:
    """Per-game negative log-likelihood for binary (home-win | no-draw) games."""
    series: list[float] = []
    for p, y in zip(probs, outcomes):
        p = min(1.0 - 1e-12, max(1e-12, p))
        series.append(-(y * math.log(p) + (1.0 - y) * math.log(1.0 - p)))
    return series


def rolling_origin_improvement(loss_by_value: dict[float, list[float]],
                               default_value: float, n_splits: int,
                               min_train_frac: float = HOLDOUT_MIN_TRAIN_FRAC) -> dict | None:
    """Rolling-origin holdout estimate of how the in-sample selection generalizes.

    ``loss_by_value`` maps each grid value (and the default) to its per-game loss
    series, all aligned in temporal order. The timeline after an initial training
    seed is split into ``n_splits`` contiguous future blocks. For each block the
    best value is chosen on everything before it (train) and scored on the block
    (held-out, never seen by that selection). Returns the mean held-out
    improvement of the selection procedure vs the default, or None if there is
    not enough data to validate.
    """
    if n_splits < 2 or default_value not in loss_by_value:
        return None
    n = len(loss_by_value[default_value])
    if n < (n_splits + 1) * 10:  # too few games per block to be meaningful
        return None
    start = max(1, int(n * min_train_frac))
    bounds = [start + round((n - start) * k / n_splits) for k in range(n_splits + 1)]
    values = list(loss_by_value)
    improvements: list[float] = []
    selections: list[float] = []
    for k in range(n_splits):
        tr_end, te_lo, te_hi = bounds[k], bounds[k], bounds[k + 1]
        if te_hi <= te_lo or tr_end < 1:
            continue
        sel = min(values, key=lambda v: sum(loss_by_value[v][:tr_end]) / tr_end)
        block = te_hi - te_lo
        sel_test = sum(loss_by_value[sel][te_lo:te_hi]) / block
        def_test = sum(loss_by_value[default_value][te_lo:te_hi]) / block
        improvements.append(def_test - sel_test)
        selections.append(sel)
    if not improvements:
        return None
    return {"mean_oos_improvement": sum(improvements) / len(improvements),
            "selections": selections, "n_folds": len(improvements)}


def _gate(n: int, min_n: int, n_label: str, insample_improvement: float, margin: float,
          loss_by_value: dict[float, list[float]], default_value: float,
          n_splits: int) -> tuple[bool, str, float | None]:
    """Acceptance gate. With a rolling-origin holdout (n_splits>=2 and enough
    data) the margin is applied to the OUT-OF-SAMPLE improvement; otherwise it
    falls back to the in-sample improvement. The sample-size gate always holds."""
    ro = rolling_origin_improvement(loss_by_value, default_value, n_splits) if n_splits >= 2 else None
    if ro is None:
        accepted, reason = _decide(n, min_n, n_label, insample_improvement, margin)
        return accepted, reason, None
    oos = ro["mean_oos_improvement"]
    if n < min_n:
        return False, f"insufficient sample ({n} {n_label} < {min_n}); family default kept.", oos
    if oos < margin:
        return False, (f"holdout OOS improvement {oos:.4f} < margin {margin:.4f} "
                       f"({ro['n_folds']} folds); family default kept."), oos
    return True, (f"accepted: {n} {n_label}, rolling-origin OOS improvement "
                  f"{oos:.4f} >= {margin:.4f} ({ro['n_folds']} folds)."), oos


def tune_home_advantage(results: list[dict], league: str, family: str,
                        league_params: dict | None = None,
                        grid: tuple[float, ...] = DEFAULT_HOME_ADV_GRID,
                        warmup: int = 60, default_home_adv: float = 60.0,
                        min_eval: int = MIN_EVAL_HOME_ADV,
                        margin: float = IMPROVEMENT_MARGIN,
                        n_splits: int = 0) -> dict:
    rows: list[dict] = []
    loss_series: dict[float, list[float]] = {}
    for ha in grid:
        params = dict(league_params or {})
        params["elo_home_adv"] = float(ha)
        res = walk_forward_backtest(results, league, family, params, warmup=warmup)
        rows.append({"elo_home_adv": float(ha), "log_loss": res["log_loss"],
                     "brier_score": res["brier_score"], "ece": res["ece"],
                     "n": res["n_games_evaluated"]})
        loss_series[float(ha)] = _binary_nll_series(res["binary_probs"], res["binary_outcomes"])
    table = pd.DataFrame(rows)
    best = table.loc[table["log_loss"].idxmin()]
    n_eval = int(best["n"])
    base_ll = _loss_at(table, "log_loss", "elo_home_adv", float(default_home_adv))
    if base_ll is None:  # default not on the grid: evaluate it explicitly
        params = dict(league_params or {})
        params["elo_home_adv"] = float(default_home_adv)
        dres = walk_forward_backtest(results, league, family, params, warmup=warmup)
        base_ll = dres["log_loss"]
        loss_series[float(default_home_adv)] = _binary_nll_series(
            dres["binary_probs"], dres["binary_outcomes"])
    insample_improvement = base_ll - float(best["log_loss"])
    accepted, reason, oos = _gate(n_eval, min_eval, "evaluated games", insample_improvement,
                                  margin, loss_series, float(default_home_adv), n_splits)
    return {"league": league,
            "best_home_adv": float(best["elo_home_adv"]),        # raw grid argmin
            "best_log_loss": float(best["log_loss"]),
            "default_home_adv": float(default_home_adv),
            "default_log_loss": float(base_ll),
            "n_eval": n_eval, "improvement": insample_improvement,
            "oos_improvement": oos,
            "accepted": accepted, "reason": reason,
            "recommended_home_adv": float(best["elo_home_adv"]) if accepted else float(default_home_adv),
            "table": table,
            "note": ("Grid search gated by a rolling-origin holdout when enabled "
                     "(selection validated out-of-sample), else in-sample with "
                     "sample-size and margin gates. Re-validate after season changes.")}


def tune_dc_rho(results: list[dict], league: str, family: str,
                league_params: dict | None = None,
                grid: tuple[float, ...] = DEFAULT_DC_RHO_GRID, warmup: int = 60,
                bounds: tuple[float, float] = DC_RHO_BOUNDS,
                min_draws: int = MIN_DRAWS_DC_RHO,
                margin: float = IMPROVEMENT_MARGIN,
                n_splits: int = 0) -> dict:
    """Dixon-Coles rho for three-way leagues, scored by three-way log loss
    (the binary conditional metric is insensitive to draw mass)."""
    grid = _clamp_grid(grid, bounds, "dc_rho")
    rows: list[dict] = []
    loss_series: dict[float, list[float]] = {}
    n_draws = 0
    for rho in grid:
        params = dict(league_params or {})
        params["dc_rho"] = float(rho)
        res = walk_forward_backtest(results, league, family, params, warmup=warmup)
        if res["log_loss_threeway"] is None:
            raise ValueError(f"League '{league}' produced no draw estimates; "
                             "dc_rho only applies to three-way (soccer) leagues.")
        n_draws = res["n_draws_observed"]
        rows.append({"dc_rho": float(rho), "log_loss_threeway": res["log_loss_threeway"],
                     "mean_estimated_draw_probability": res["mean_estimated_draw_probability"],
                     "observed_draw_rate": res["observed_draw_rate"],
                     "n": res["n_games_evaluated"]})
        loss_series[float(rho)] = list(res["threeway_ll_series"])
    table = pd.DataFrame(rows)
    best = table.loc[table["log_loss_threeway"].idxmin()]
    base_ll = _loss_at(table, "log_loss_threeway", "dc_rho", 0.0)
    if base_ll is None:  # independent-Poisson baseline (rho=0) not on the grid
        params = dict(league_params or {})
        params["dc_rho"] = 0.0
        dres = walk_forward_backtest(results, league, family, params, warmup=warmup)
        base_ll = dres["log_loss_threeway"]
        loss_series[0.0] = list(dres["threeway_ll_series"])
    insample_improvement = base_ll - float(best["log_loss_threeway"])
    accepted, reason, oos = _gate(int(n_draws), min_draws, "observed draws",
                                  insample_improvement, margin, loss_series, 0.0, n_splits)
    return {"league": league,
            "best_dc_rho": float(best["dc_rho"]),                # raw grid argmin
            "best_log_loss_threeway": float(best["log_loss_threeway"]),
            "default_log_loss_threeway": float(base_ll),
            "n_draws": int(n_draws), "improvement": insample_improvement,
            "oos_improvement": oos,
            "accepted": accepted, "reason": reason,
            "recommended_dc_rho": float(best["dc_rho"]) if accepted else 0.0,
            "table": table,
            "note": ("Grid clamped to a sound Dixon-Coles range and scored by "
                     "three-way log loss; gated by a rolling-origin holdout when "
                     "enabled, else in-sample. Re-validate after season changes.")}
