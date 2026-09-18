"""Independent audit evidence. Synthetic inputs, mocked I/O, no data writes.

Run from the repository: python -B audit/latest/openai/reproduce.py
Assertions characterize the defects on the reviewed revision, not desired behavior.
"""
import json
from pathlib import Path
import sys
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

import pandas as pd
import sqp.logging_config as logging_config

logging_config._file_handler_resuelto = True

from sqp.audit.report import _segment_audit
from sqp.backtesting.roi_engine import _summarize
from sqp.config import Settings
from sqp.domain.models import Event, EventOdds, MarketLine, EstimatedProbabilities
from sqp.models.distributions import poisson_match_probs, score_pmf
from sqp.pipeline import daily
from sqp.pipeline.probabilities import _consensus_lines, _execution_prices
from sqp.settlement.runner import realized_roi
from sqp.settlement.settle import _grade, settle_candidates


def quarter_pricing():
    probabilities = poisson_match_probs(1.5, 1, -.25, 2.25, three_way=True, max_goals=30)
    results = []
    for market, selection, line, key in [
        ("spreads", "A", -.25, "home_cover"),
        ("totals", "Over", 2.25, "over"),
    ]:
        mass = dict.fromkeys(["win", "loss", "push", "half_win", "half_loss", "void"], 0.)
        row = pd.Series(dict(market=market, selection=selection, line=line, away="B"))
        for home, ph in enumerate(score_pmf(1.5, 30)):
            for away, pa in enumerate(score_pmf(1, 30)):
                mass[_grade(row, home, away, "A", True)] += ph * pa
        win_units = mass["win"] + .5 * mass["half_win"]
        loss_units = mass["loss"] + .5 * mass["half_loss"]
        actual_ev = win_units - loss_units
        reported_ev = probabilities[key] * 2 - 1
        assert actual_ev > 0 > reported_ev
        results.append(dict(market=market, line=line, mass=mass,
                            observed_probability=probabilities[key],
                            expected_decision_probability=win_units / (win_units + loss_units),
                            observed_ev_at_2=reported_ev, expected_ev_at_2=actual_ev))
    return results


def partial_roi():
    row = dict(league="test", event_id="e", home="A", away="B", market="spreads",
               selection="A", line=-.75, price_decimal=2., stake=20.,
               estimated_probability=.6, estimated_edge=.2)
    settled = settle_candidates(pd.DataFrame([row]), {"e": (1, 0, "A")}, True)
    summary = _summarize("test", settled, 1)
    expected = realized_roi(settled)
    assert expected == .5 and summary["realized_roi"] == 0
    assert summary["pnl"] == 10 and summary["staked"] == 0
    assert _segment_audit(settled, ["league"]).empty
    # A full win plus a half win: the backtest overstates ROI instead of zeroing it.
    mixed = pd.concat([settled, settled.assign(result="win", pnl=20.)], ignore_index=True)
    mixed_summary = _summarize("test", mixed, 2)
    assert realized_roi(mixed) == .75 and mixed_summary["realized_roi"] == 1.5
    return dict(result="half_win", stake=20., pnl=10., expected_roi=expected,
                observed_roi=summary["realized_roi"], observed_staked=summary["staked"],
                observed_segment_rows=0, mixed_expected_roi=.75, mixed_observed_roi=1.5)


def execution_config():
    settings = Settings()
    settings.calibration_enabled = False
    settings.weather.enabled = False
    settings.execution.books = ("accessible",)
    settings.execution.max_uplift = .15
    settings.risk.uncertainty_penalty = 0
    settings.risk.low_book_penalty = 0
    settings.risk.anomaly_extra_penalty = 0
    odds = EventOdds(Event("synthetic", "basketball_nba", "nba", "A", "B", "2099-01-01T00:00:00Z"),
        [MarketLine("h2h", book, side, price) for book, side, price in [
            ("one", "A", 1.9), ("two", "A", 2.), ("accessible", "A", 2.1),
            ("one", "B", 2.), ("two", "B", 2.), ("accessible", "B", 2.)]])
    adapter = Mock()
    adapter.params = {}
    adapter.normalize = lambda name: name
    adapter.reliability_warning.return_value = None
    adapter.estimate.return_value = EstimatedProbabilities(
        home_win_estimated_probability=.55, away_win_estimated_probability=.45)
    provider = Mock()
    provider.fetch_results.return_value = []
    provider.fetch_odds.return_value = [odds]
    served_store = Mock()
    served_store.append_served.return_value = 0
    def capture(league, rows, candidates, mode):
        return candidates
    with patch.object(daily, "get_adapter", return_value=adapter), \
         patch.object(daily, "SyntheticProvider", return_value=provider), \
         patch.object(daily, "ServedStore", return_value=served_store), \
         patch.object(daily, "_finalize", side_effect=capture):
        candidates = daily.run_league("nba", settings, mode="demo")
    candidate = next(c for c in candidates if c.selection == "A")
    expected_price, expected_book = _execution_prices(
        odds, _consensus_lines(odds), settings.execution.books,
        max_uplift=settings.execution.max_uplift)[("h2h", "A", None)]
    assert candidate.price_decimal == 2. and expected_price == 2.1
    assert candidate.bookmaker == "consensus_median" and expected_book == "accessible"
    return dict(observed_price=candidate.price_decimal, observed_book=candidate.bookmaker,
                expected_price=expected_price, expected_book=expected_book)


if __name__ == "__main__":
    print(json.dumps({"OPENAI-001": quarter_pricing(), "OPENAI-002": partial_roi(),
                      "OPENAI-003": execution_config()}, indent=2, allow_nan=False))
