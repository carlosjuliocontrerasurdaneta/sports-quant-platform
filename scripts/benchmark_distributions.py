"""Paired benchmark against the pre-optimization scalar SciPy dispatch.

Same model, parameters and aggregation; only PMF evaluation is swapped. This
measures distribution computation, NOT full pipeline or predictive accuracy.
"""
from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import timeit
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import scipy
from scipy.stats import nbinom, poisson

from sqp.models import distributions as d


def scalar_pmf(lam, max_goals=15, k=None):
    if k is None or k <= 0:
        return [poisson.pmf(i, lam) for i in range(max_goals + 1)]
    return [nbinom.pmf(i, k, k / (k + lam)) for i in range(max_goals + 1)]


def benchmark(number: int = 300, repeats: int = 5) -> dict:
    if number <= 0 or repeats <= 0:
        raise ValueError("number and repeats must be positive")
    output = {}
    for name, means, options in [
        ("MLB", (4.6, 4.3), dict(max_goals=25, dispersion_k=3.8)),
        ("NHL", (2.9, 2.8), dict(max_goals=15, score_rho=-0.06)),
        ("soccer", (1.6, 1.1), dict(max_goals=10, three_way=True, dc_rho=-0.1)),
    ]:
        def run(): return d.poisson_match_probs(*means, -1.5, 6.0, **options)
        optimized = run()
        with patch.object(d, "score_pmf", scalar_pmf):
            baseline = run()
            old_ms = statistics.median(timeit.repeat(run, number=number, repeat=repeats)) * 1000 / number
        new_ms = statistics.median(timeit.repeat(run, number=number, repeat=repeats)) * 1000 / number
        if baseline != optimized:
            raise AssertionError(f"{name}: optimization changed model output")
        output[name] = {"scalar_ms_per_event": old_ms, "vectorized_ms_per_event": new_ms,
                        "speedup": old_ms / new_ms, "exact_probability_parity": True}
    return {"python": platform.python_version(), "platform": platform.platform(),
            "numpy": np.__version__, "scipy": scipy.__version__,
            "events_per_repeat": number, "repeats": repeats, "results": output}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--number", type=int, default=300)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps(benchmark(args.number, args.repeats), indent=2))
