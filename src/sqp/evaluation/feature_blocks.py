"""Paired expanding-day ablations. Exploratory evidence, never promotion."""
from __future__ import annotations

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from sqp.evaluation.bootstrap import cluster_bootstrap_ci
from sqp.features.research import FeatureDataset
from sqp.features.temporal import daily_splits


def _learner(classification: bool):
    # Fixed regularization, no holdout-driven tuning. Imputation is fold-local.
    return make_pipeline(SimpleImputer(strategy="median", add_indicator=True,
                                       keep_empty_features=True),
                         StandardScaler(),
                         LogisticRegression(C=1.0, max_iter=2000, tol=1e-8, random_state=42)
                         if classification else Ridge(alpha=1.0))


def _loss(y: np.ndarray, prediction: np.ndarray, classification: bool) -> np.ndarray:
    if not classification:
        return np.abs(y - prediction)
    truth = np.eye(prediction.shape[1])[y.astype(int)]
    # Binary Brier on the home side; multiclass sum-of-squares for soccer.
    return np.sum((prediction - truth) ** 2, axis=1) / (2 if prediction.shape[1] == 2 else 1)


def evaluate_blocks(dataset: FeatureDataset, *, n_splits: int = 5,
                    n_boot: int = 2000, seed: int = 42,
                    alpha: float = 0.05) -> dict:
    """Each block alone, all blocks, and each leave-one-block-out ablation.

    Compares candidate to the SAME learned baseline, operational adapter and
    train-only constant. Missing blocks are declared, not silently imputed into
    fake evidence. CIs use dates (a coarser cluster than events), preserving
    all events of a day together; serial dependence across days remains a limit.
    """
    if not 0 < alpha < 1 or n_boot < 1:
        raise ValueError("alpha must be in (0,1), n_boot positive")
    source = dataset.frame
    available = {key: [c for c in cols if source[c].notna().any()]
                 for key, cols in dataset.blocks.items()}
    blocks = {key: cols for key, cols in available.items() if cols}
    missing = sorted(set(dataset.blocks) - set(blocks))
    all_cols = [c for cols in blocks.values() for c in cols]
    variants = {"baseline": [], **blocks, "all": all_cols}
    if len(blocks) > 1:
        variants.update({f"without_{key}": [c for c in all_cols if c not in cols]
                         for key, cols in blocks.items()})
    tasks = ["h2h"] + ([] if dataset.family == "tennis" else ["total_score"])
    comparisons = max(1, (len(variants) + 1 + sum(name.startswith("without_") for name in variants)) * len(tasks))
    result: dict = {"league": dataset.league, "family": dataset.family,
                   "status": "EXPLORATORY_NOT_FOR_PROMOTION", "n_games": len(source),
                   "missing_blocks": missing, "coverage": dataset.coverage,
                   "protocol": {"folds": n_splits, "bootstrap": n_boot, "seed": seed,
                                "familywise_alpha": alpha, "comparisons": comparisons,
                                "cluster": "date", "window": "strictly prior days",
                                "market_comparison": "NOT_VERIFIABLE: no aligned pregame odds supplied"},
                   "tasks": {}}
    for task in tasks:
        classification = task == "h2h"
        # Two-way sports cannot label a tie as an away win.
        d = source.loc[~source.is_draw].copy() if classification and dataset.family != "soccer" else source.copy()
        d = d.reset_index(drop=True)
        base_cols = ["base_home", "base_away", "base_draw"] if classification else ["base_total", "base_margin"]
        if classification:
            for c in base_cols:
                d[c] = np.log(np.clip(d[c], 1e-6, 1 - 1e-6))
        target = "target_h2h" if classification else "target_total"
        y = d[target].to_numpy()
        classes = np.arange(3 if dataset.family == "soccer" else 2)
        predictions: dict[str, list] = {name: [] for name in variants}
        operational, constant, indices, fold_info = [], [], [], []
        try:
            folds = list(daily_splits(d.date, n_splits))
        except ValueError as exc:
            result["tasks"][task] = {"status": "NOT_VERIFIABLE", "reason": str(exc)}
            continue
        usable = True
        for fold, (train, test) in enumerate(folds):
            if classification and not np.array_equal(np.unique(y[train]), classes):
                result["tasks"][task] = {"status": "NOT_VERIFIABLE", "reason": "training fold lacks an outcome class"}
                usable = False
                break
            fold_info.append({"fold": fold, "train_end": d.iloc[train[-1]].date,
                              "test_start": d.iloc[test[0]].date, "test_end": d.iloc[test[-1]].date,
                              "n_train": len(train), "n_test": len(test)})
            for name, extras in variants.items():
                # Constants/all-missing training columns cannot add signal. This
                # also keeps constant ablations numerically identical to baseline.
                cols = base_cols + [c for c in extras if d.iloc[train][c].nunique(dropna=False) > 1]
                model = _learner(classification)
                model.fit(d.iloc[train][cols], y[train])
                pred = model.predict_proba(d.iloc[test][cols]) if classification else model.predict(d.iloc[test][cols])
                predictions[name].append(pred)
            if classification:
                raw = np.exp(d.iloc[test][base_cols].to_numpy())
                raw = raw[:, [1, 2, 0]] if dataset.family == "soccer" else raw[:, [1, 0]]
                raw = raw / raw.sum(axis=1, keepdims=True)
                prior = np.bincount(y[train].astype(int), minlength=len(classes)) / len(train)
                constant.append(np.tile(prior, (len(test), 1)))
            else:
                raw = d.iloc[test].base_total.to_numpy()
                constant.append(np.full(len(test), np.median(y[train])))
            operational.append(raw)
            indices.extend(test.tolist())
        if not usable:
            continue
        evaluated = d.iloc[indices]
        observed = y[indices]
        pred_all = {name: np.concatenate(parts) for name, parts in predictions.items()}
        pred_all["operational"] = np.concatenate(operational)
        pred_all["constant"] = np.concatenate(constant)
        losses = {name: _loss(observed, pred, classification) for name, pred in pred_all.items()}
        summaries = []
        for name, loss in losses.items():
            delta = loss - losses["baseline"]
            lo, hi = cluster_bootstrap_ci(delta, evaluated.date.to_numpy(),
                                          n_boot=n_boot, seed=seed, alpha=alpha / comparisons)
            row = {"variant": name, "loss": float(loss.mean()),
                   "delta_vs_baseline": float(delta.mean()), "delta_lo": float(lo),
                   "delta_hi": float(hi), "improvement_detected": bool(hi < 0),
                   "delta_vs_operational": float((loss - losses["operational"]).mean())}
            if classification:
                p = np.clip(pred_all[name], 1e-12, 1)
                row["log_loss"] = float(-np.log(p[np.arange(len(observed)), observed.astype(int)]).mean())
            if name.startswith("without_"):
                # Positive means removing this block hurt the all-block model.
                removal = loss - losses["all"]
                rlo, rhi = cluster_bootstrap_ci(removal, evaluated.date.to_numpy(),
                                                n_boot=n_boot, seed=seed, alpha=alpha / comparisons)
                row.update(removal_cost=float(removal.mean()), removal_lo=float(rlo), removal_hi=float(rhi))
            summaries.append(row)
        result["tasks"][task] = {"status": "MEASURED", "metric": "brier" if classification else "mae",
                                 "n_evaluated": len(indices), "folds": fold_info,
                                 "scores": summaries}
    return result
