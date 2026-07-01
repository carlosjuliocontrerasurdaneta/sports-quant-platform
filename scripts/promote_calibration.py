#!/usr/bin/env python
"""Review and promote STAGED calibrators into the live pipeline.

The daily retrain (scripts/run_all.py -> train_market_calibrators) only writes
CANDIDATE calibrators to data/models/staging/. It never promotes them into
production in the same cycle, so a degenerate daily fit cannot auto-install
itself. This script is the deliberate, separate promotion step:

  python scripts/promote_calibration.py                 # dry-run: show diff + preview
  python scripts/promote_calibration.py --yes           # promote ALL staged candidates
  python scripts/promote_calibration.py --keys mlb_h2h  # promote only these keys

By default it is a DRY RUN: it prints, per (league_market) key, the live method
vs the staged candidate and a probability-grid preview of what the candidate
would do -- so you can catch a degenerate map (e.g. one that pushes favorites
toward 0.9, the mlb_spreads regression) BEFORE it reaches production. Promotion
happens only with --yes (or --keys). These are ESTIMATED probabilities -- not
certainties, not a profit guarantee.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.calibration.calibrator import (_load_method_registry, _model_path,
                                        promote_calibrators)
from sqp.logging_config import get_logger

log = get_logger("sqp.promote_calibration")

_GRID = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]


def _preview(key: str, method: str) -> str:
    """One-line grid preview of the STAGED candidate for ``key`` (loads the staged
    model directly so it reflects the candidate, not the live model)."""
    name = {"isotonic": "iso", "beta": "beta"}.get(method)
    path = _model_path(key, name, staging=True) if name else None
    if path is None or not path.exists():
        return "  (no staged model file)"
    model = joblib.load(str(path))
    cal = np.clip(model.predict(np.asarray(_GRID, dtype=float)), 0.01, 0.99)
    return "  " + "  ".join(f"{p:.2f}->{c:.2f}" for p, c in zip(_GRID, cal))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true",
                    help="Promote all staged candidates (skip dry-run).")
    ap.add_argument("--keys", type=str, default=None,
                    help="Comma-separated keys to promote (implies promotion).")
    args = ap.parse_args()

    staged = _load_method_registry(staging=True)
    live = _load_method_registry()
    if not staged:
        print("No hay candidatos en staging. Nada que promover.")
        return 0

    print("=== DIFF staging vs live (probabilidad ESTIMADA calibrada) ===")
    for key in sorted(staged):
        print(f"[{key}] live={live.get(key, 'no-op')} -> staged={staged[key]}")
        print(_preview(key, staged[key]))
    # Markets currently live that the latest retrain no longer recommends.
    for key in sorted(set(live) - set(staged)):
        print(f"[{key}] live={live[key]} -> staged=no-op (se DEGRADARÍA en promoción completa)")

    keys = [k.strip() for k in args.keys.split(",")] if args.keys else None
    if not (args.yes or keys):
        print("\nDRY RUN. Revisa la previsualización. Para promover: --yes "
              "(todos) o --keys k1,k2 (selección).")
        return 0

    promoted = promote_calibrators(keys=keys)
    print(f"\nPromovidos a producción: {promoted or 'ninguno'}")
    log.info("Calibradores promovidos: %s", promoted)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
