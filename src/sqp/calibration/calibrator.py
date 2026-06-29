"""Probability calibration (ported from the ML project, adapted to this base).

Two calibrators over estimated probabilities:
  * Isotonic regression (non-parametric, monotonic).
  * Beta calibration (parametric, 3-param logistic in log-odds space).

Trained out-of-sample with a TEMPORAL split (earlier games train, most recent
games validate) — never a random split — per the platform's modeling rules.
Fitted models persist under data/models/ and are applied by sport, since a model
can be well calibrated in one league and miscalibrated in another.

These produce calibrated ESTIMATED probabilities; they do not turn estimates
into certainties.
"""
from __future__ import annotations

import json
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from sqp.calibration.metrics import (calibration_report,
                                     expected_calibration_error)
from sqp.config import ROOT
from sqp.logging_config import get_logger

log = get_logger(__name__)

MODELS_DIR = ROOT / "data" / "models"


def _model_path(sport: str, name: str):
    return MODELS_DIR / f"{sport}_calibration_{name}.joblib"


@lru_cache(maxsize=128)
def _load_calibrator(path_str: str):
    """Load a persisted calibrator once per process (the daily loop applies it
    per candidate). Keyed by absolute path, so a retrain to a new file -- or a
    test that redirects MODELS_DIR -- is picked up without stale caching."""
    return joblib.load(path_str)


def _is_monotone_increasing(predict, lo: float = 0.01, hi: float = 0.99,
                            n: int = 99, tol: float = 1e-6) -> bool:
    """True if ``predict`` (a calibrator's ``predict`` method) is non-decreasing
    over ``[lo, hi]``. A calibrator that inverts rank order -- e.g. a degenerate
    beta fit that maps LOW estimated probabilities UP -- must be rejected
    regardless of its aggregate ECE, because ECE is a binned average that does
    NOT penalize non-monotonicity. ``predict`` is called once on the whole grid."""
    grid = np.linspace(lo, hi, n)
    vals = np.asarray(predict(grid), dtype=float)
    return bool(np.all(np.diff(vals) >= -tol))


def _persist_or_remove(model, path, keep: bool) -> bool:
    """Persist ``model`` to ``path`` when ``keep`` is True; otherwise remove any
    stale model already at ``path``. Returns whether a model is present at
    ``path`` afterwards. This is what makes calibration self-healing: a market
    whose calibrator stops helping is automatically dropped back to a no-op."""
    if keep:
        joblib.dump(model, str(path))
        return True
    path.unlink(missing_ok=True)
    return False


def _method_registry_path():
    return MODELS_DIR / "calibration_methods.json"


def _load_method_registry() -> dict:
    """Per-(league, market) winning calibrator method (the JSON backing
    ``method='auto'``). Returns {} when absent or unreadable, so a missing /
    corrupt registry degrades to a no-op rather than an error."""
    path = _method_registry_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _set_best_method(key: str, method: str | None) -> None:
    """Record (or clear with ``None``) the best apply-time method for ``key``.
    Self-healing like the model files: a retrain whose calibrators stop helping
    drops the group from the registry, so ``method='auto'`` falls back to a
    no-op for it. Read-modify-write a single JSON; training is sequential."""
    reg = _load_method_registry()
    if method is None:
        reg.pop(key, None)
    else:
        reg[key] = method
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    _method_registry_path().write_text(
        json.dumps(reg, indent=2, sort_keys=True), encoding="utf-8")


class BetaCalibrator:
    """Parametric beta calibration for estimated probabilities."""

    def __init__(self) -> None:
        self.a = 1.0
        self.b = 1.0
        self.c = 0.0

    def fit(self, probs: np.ndarray, outcomes: np.ndarray) -> "BetaCalibrator":
        from scipy.optimize import minimize

        def neg_log_loss(params: np.ndarray) -> float:
            a, b, c = params
            p = np.clip(probs, 1e-6, 1 - 1e-6)
            cal = 1 / (1 + np.exp(-(a * np.log(p) - b * np.log(1 - p) + c)))
            cal = np.clip(cal, 1e-6, 1 - 1e-6)
            return float(-np.mean(outcomes * np.log(cal) + (1 - outcomes) * np.log(1 - cal)))

        res = minimize(neg_log_loss, [1.0, 1.0, 0.0], method="Nelder-Mead")
        self.a, self.b, self.c = res.x
        return self

    def predict(self, probs: np.ndarray) -> np.ndarray:
        p = np.clip(probs, 1e-6, 1 - 1e-6)
        cal = 1 / (1 + np.exp(-(self.a * np.log(p) - self.b * np.log(1 - p) + self.c)))
        return np.clip(cal, 0.01, 0.99)


def train_calibration(df: pd.DataFrame, prob_col: str = "probability",
                      outcome_col: str = "home_win", sport: str = "mlb",
                      val_fraction: float = 0.20) -> dict:
    """Fit isotonic + beta calibrators on the earlier games and validate on the
    most recent ``val_fraction``. Persists both models and returns OOS metrics."""
    df2 = df.dropna(subset=[prob_col, outcome_col]).reset_index(drop=True)
    if len(df2) < 40:
        raise ValueError(f"Not enough data to calibrate: {len(df2)} rows (need >=40)")

    split = int(len(df2) * (1.0 - val_fraction))
    train_df, val_df = df2.iloc[:split], df2.iloc[split:]

    train_probs = train_df[prob_col].to_numpy(dtype=float)
    train_outcomes = train_df[outcome_col].to_numpy(dtype=float)
    val_probs = val_df[prob_col].to_numpy(dtype=float)
    val_outcomes = val_df[outcome_col].to_numpy(dtype=float)

    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(train_probs, train_outcomes)

    beta = BetaCalibrator().fit(train_probs, train_outcomes)

    raw_val_ece = float(expected_calibration_error(val_probs, val_outcomes))
    iso_val_probs = np.clip(iso.predict(val_probs), 0.01, 0.99)
    val_metrics = calibration_report(iso_val_probs, val_outcomes)
    beta_val_probs = np.clip(beta.predict(val_probs), 0.01, 0.99)
    beta_val_ece = float(expected_calibration_error(beta_val_probs, val_outcomes))

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    iso_path, beta_path = _model_path(sport, "iso"), _model_path(sport, "beta")
    # Self-healing gate: persist a calibrator only when it does NOT worsen the
    # out-of-sample ECE; otherwise drop it (and clean any stale prior model at
    # that path) so live application falls back to a safe no-op. Each model is
    # gated independently because the apply-time method (iso/beta) is
    # configurable. Without this, every retrain re-persisted worsening models
    # (e.g. low-sample markets), silently degrading the live picks.
    # Gate on TWO conditions: (1) the calibrator must not worsen OOS ECE, and
    # (2) it must be monotone non-decreasing. A non-monotone fit (a degenerate
    # beta that maps low probabilities UP) can have an acceptable aggregate ECE
    # while inverting rank order -- which manufactured phantom edges on mlb
    # spreads -- so monotonicity is a hard, ECE-independent requirement.
    iso_persisted = _persist_or_remove(
        iso, iso_path,
        val_metrics["ece"] <= raw_val_ece and _is_monotone_increasing(iso.predict))
    beta_persisted = _persist_or_remove(
        beta, beta_path,
        beta_val_ece <= raw_val_ece and _is_monotone_increasing(beta.predict))
    _load_calibrator.cache_clear()  # drop any stale cached model at these paths

    # Per-group best method for method="auto": among the calibrators that beat
    # the raw OOS ECE, record the lowest-ECE one so the live pipeline picks per
    # (league, market) instead of a single global method. None when neither
    # helps -> the group stays a no-op under "auto".
    ranked: list[tuple[str, float]] = []
    if iso_persisted:
        ranked.append(("isotonic", val_metrics["ece"]))
    if beta_persisted:
        ranked.append(("beta", beta_val_ece))
    best_method = min(ranked, key=lambda r: r[1])[0] if ranked else None
    _set_best_method(sport, best_method)

    log.info("[%s] Calibration fit on %d rows, val %d | raw ECE %.4f -> iso %.4f "
             "(%s) / beta %.4f (%s)", sport, len(train_df), len(val_df), raw_val_ece,
             val_metrics["ece"], "kept" if iso_persisted else "dropped",
             beta_val_ece, "kept" if beta_persisted else "dropped")
    return {
        "iso_path": str(iso_path),
        "beta_path": str(beta_path),
        "n_train": len(train_df),
        "n_val": len(val_df),
        "raw_val_ece": raw_val_ece,
        "beta_val_ece": beta_val_ece,
        "val_metrics": val_metrics,
        "iso_persisted": iso_persisted,
        "beta_persisted": beta_persisted,
        "persisted": iso_persisted or beta_persisted,
        "best_method": best_method,
    }


def train_market_calibrators(hist: pd.DataFrame, *, min_n: int = 40) -> list[dict]:
    """Train one calibrator per (league, market) from a consolidated pick history
    (columns: league, market, date, estimated_probability, result).

    Both isotonic and beta models are fitted and persisted per group (the
    apply-time method picks which one); the outcome is whether the selection won
    (graded bets only; push/void excluded), so this calibrates the estimated
    probability against realized frequency per market. Groups with fewer than
    ``min_n`` graded bets are skipped (recorded ``trained=False``) -- and since
    the live application is a no-op without a model, an untrained market simply
    stays uncalibrated. Returns one summary dict per group.
    """
    out: list[dict] = []
    if hist is None or hist.empty:
        return out
    graded = hist[hist["result"].isin(["win", "loss"])].copy()
    graded["won"] = (graded["result"] == "win").astype(float)
    for (league, market), g in graded.groupby(["league", "market"]):
        if "date" in g.columns:
            g = g.sort_values("date")
        df = pd.DataFrame({"probability": g["estimated_probability"].to_numpy(dtype=float),
                           "won": g["won"].to_numpy(dtype=float)}).dropna()
        rec = {"league": str(league), "market": str(market), "n": int(len(df)),
               "trained": False}
        if len(df) < min_n:
            out.append(rec)
            continue
        try:
            r = train_calibration(df, prob_col="probability", outcome_col="won",
                                  sport=calibration_key(str(league), str(market)))
            rec.update({"trained": True, "raw_val_ece": r["raw_val_ece"],
                        "cal_val_ece": r["val_metrics"]["ece"],
                        "beta_val_ece": r["beta_val_ece"], "n_val": r["n_val"],
                        "iso_persisted": r["iso_persisted"],
                        "best_method": r["best_method"],
                        "persisted": r["persisted"]})
        except ValueError as exc:
            rec["error"] = str(exc)
        out.append(rec)
    return out


def apply_calibration(probs: np.ndarray, sport: str = "mlb",
                      method: str = "isotonic") -> np.ndarray:
    """Apply a previously trained calibrator for ``sport``.

    ``method='auto'`` resolves the per-(league, market) winner recorded at
    training time (``calibration_methods.json``); an unregistered group, an
    unknown method, or a missing model all fall back to returning the input
    probabilities unchanged (safe no-op)."""
    if method == "auto":
        method = _load_method_registry().get(sport)
        if method is None:
            return probs
    name = {"isotonic": "iso", "beta": "beta"}.get(method)
    if name is None:
        return probs
    path = _model_path(sport, name)
    if not path.exists():
        return probs
    cal = _load_calibrator(str(path))
    return np.clip(cal.predict(probs), 0.01, 0.99)


def calibration_key(sport: str, market: str | None = None) -> str:
    """Composite model key. Markets are calibrated separately (a model can be
    well calibrated on moneyline yet biased on totals), so the live key is
    ``"<league>_<market>"`` -- e.g. ``"mlb_h2h"`` -- reusing the per-sport
    persistence/api unchanged."""
    return f"{sport}_{market}" if market else sport


def calibrate_probability(p: float, sport: str, market: str | None = None,
                          method: str = "isotonic") -> float:
    """Calibrate a single estimated probability for ``(sport, market)``. Returns
    ``p`` unchanged when no model exists (safe no-op), so callers can apply it
    unconditionally behind a feature flag."""
    key = calibration_key(sport, market)
    out = apply_calibration(np.asarray([p], dtype=float), sport=key, method=method)
    return float(out[0])
