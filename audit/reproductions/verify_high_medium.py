"""Minimal read-only reproductions for audit high/medium finding verification."""
from __future__ import annotations

import json
import math
import multiprocessing as mp
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from sqp.audit.clv import clv_segments
from sqp.backtesting.roi_engine import _match_index, _match_result
from sqp.domain.models import Event, EventOdds, MarketLine
from sqp.markets.edge import adjusted_edge
from sqp.pipeline.probabilities import (
    _consensus_counts,
    _consensus_lines,
    _decision_probability,
    _novig_probs,
)
from sqp.risk.clv_gate import gate_decisions
from sqp.settlement.settle import _grade
from sqp.storage.lock import locked


def event_odds(lines: list[MarketLine], event_id: str = "e1", start: str = "2026-01-01T12:00:00Z") -> EventOdds:
    event = Event(event_id, "test", "test", "Home", "Away", start)
    return EventOdds(event, lines)


def settlement_reproduction() -> dict:
    nan = float("nan")
    return {
        "totals_under_nan": _grade(pd.Series({"market": "totals", "selection": "Under", "line": nan}), 5, 4, "Home"),
        "totals_over_nan": _grade(pd.Series({"market": "totals", "selection": "Over", "line": nan}), 5, 4, "Home"),
        "spreads_home_nan": _grade(pd.Series({"market": "spreads", "selection": "Home", "line": nan}), 5, 4, "Home"),
        "totals_under_control_8_5": _grade(pd.Series({"market": "totals", "selection": "Under", "line": 8.5}), 5, 4, "Home"),
    }


def consensus_reproduction() -> dict:
    eo = event_odds([
        MarketLine("h2h", "good", "Home", 1.9),
        MarketLine("h2h", "bad", "Home", 1.0),
        MarketLine("h2h", "good", "Away", 2.0),
    ])
    key = ("h2h", "Home", None)
    cons = _consensus_lines(eo)
    return {"consensus_home": cons[key], "count_home": _consensus_counts(eo)[key]}


def nan_novig_reproduction() -> dict:
    eo = event_odds([
        MarketLine("h2h", "bad", "Home", float("nan")),
        MarketLine("h2h", "good", "Away", 2.0),
    ])
    cons = _consensus_lines(eo)
    fair = _novig_probs(cons, "h2h")
    return {
        "consensus_home_is_nan": math.isnan(cons[("h2h", "Home", None)]),
        "fair_home_is_nan": math.isnan(fair["Home"]),
        "fair_away_is_nan": math.isnan(fair["Away"]),
    }


def penalty_reproduction() -> dict:
    settings = SimpleNamespace(calibration_enabled=False, calibration_method="auto")
    _raw, decision = _decision_probability(0.60, 0.50, 0.50, "test", "h2h", settings)
    adj = adjusted_edge(decision, 2.0, 0.50, 2, uncertainty_penalty=0.35)
    return {
        "decision_probability": decision,
        "model_market_gap": 0.10,
        "decision_market_gap": abs(decision - 0.50),
        "penalty": adj.penalty,
        "effective_coefficient_on_model_gap": adj.penalty / 0.10,
    }


def clv_gate_reproduction() -> dict:
    rows = [
        {"league": "mlb", "market": "totals", "clv_pct": float("nan"), "beat_close": False}
        for _ in range(29)
    ]
    rows.append({"league": "mlb", "market": "totals", "clv_pct": float("inf"), "beat_close": True})
    segments = clv_segments(pd.DataFrame(rows), ["league", "market"])
    decided = gate_decisions(segments)
    row = decided.iloc[0]
    return {"n": int(row["n"]), "median_is_inf": math.isinf(row["median_clv_pct"]), "allowed": bool(row["allowed"])}


def matching_reproduction() -> dict:
    odds = {
        "early": event_odds([], "early", "2026-01-01T10:00:00Z"),
        "late": event_odds([], "late", "2026-01-01T20:00:00Z"),
    }
    idx = _match_index(odds)
    a = {"label": "A", "home": "Home", "away": "Away", "date": "2026-01-01"}
    b = {"label": "B", "home": "Home", "away": "Away", "date": "2026-01-01"}

    def assignments(results: list[dict]) -> dict:
        used: set[str] = set()
        return {r["label"]: _match_result(r, idx, used).event.event_id for r in results}

    return {"order_A_B": assignments([a, b]), "order_B_A": assignments([b, a])}


def median_execution_reproduction() -> dict:
    odd = [1.8, 2.0, 2.2]
    even = [1.8, 2.2]
    return {
        "odd_median": median(odd),
        "odd_median_is_offered": median(odd) in odd,
        "even_median": median(even),
        "even_median_is_offered": median(even) in even,
    }


def _lock_child(target: str) -> None:
    with patch.object(Path, "stat", side_effect=OSError("persistent stat failure")):
        with locked(Path(target), timeout_s=0.05, stale_s=300.0):
            pass


def lock_reproduction() -> dict:
    with TemporaryDirectory() as tmp:
        target = Path(tmp) / "state.csv"
        target.with_suffix(".csv.lock").write_text("", encoding="utf-8")
        process = mp.Process(target=_lock_child, args=(str(target),))
        process.start()
        process.join(0.5)
        alive_after_ten_timeouts = process.is_alive()
        if process.is_alive():
            process.terminate()
            process.join(2.0)
        return {"alive_after_0_5s_with_timeout_0_05s": alive_after_ten_timeouts}


def main() -> None:
    results = {
        "COR-01_COR-02": settlement_reproduction(),
        "COR-03": consensus_reproduction(),
        "QNT-03": nan_novig_reproduction(),
        "QNT-01": penalty_reproduction(),
        "QNT-04": clv_gate_reproduction(),
        "DAT-05": matching_reproduction(),
        "DAT-03": median_execution_reproduction(),
        "COR-04_PRF-02": lock_reproduction(),
    }
    print(json.dumps(results, indent=2, allow_nan=True, sort_keys=True))


if __name__ == "__main__":
    main()
