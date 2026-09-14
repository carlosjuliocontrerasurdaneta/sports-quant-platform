"""AUD-001: final scores are unavailable to every prediction on their day."""
import pytest

from sqp.backtesting.engine import walk_forward_backtest
from sqp.backtesting.roi_engine import realized_roi_backtest
from sqp.config import RiskConfig
from sqp.domain.models import Event, EventOdds, MarketLine


@pytest.mark.parametrize("timestamps", [False, True])
def test_daily_batch_excludes_later_results(timestamps):
    early = dict(date="2026-09-01", home="A", away="B", game_id="2",
                 home_score=1, away_score=0, neutral=False)
    late = dict(early, game_id="1", home_score=10)
    if timestamps:
        early["start_time"] = "2026-09-01T10:00:00Z"
        late["start_time"] = "2026-09-01T20:00:00Z"
    odds = {
        eid: EventOdds(Event(eid, "bt", "mlb", "A", "B",
                            f"2026-09-01T{hour}:00:00Z", "real"),
                       [MarketLine("h2h", "book", side, 2.0) for side in ("A", "B")])
        for eid, hour in [("early", 10), ("late", 20)]
    }
    risk = RiskConfig(min_edge=0., market_shrink=0., max_plausible_edge=1.)
    if not timestamps:
        # Without times the existing matcher refuses ambiguous doubleheaders.
        # A single odds event still exercises same-day adapter isolation.
        odds.pop("late")
    roi_probs = []
    calibration = []
    for later in (late, dict(late, home_score=0, away_score=10)):
        roi = realized_roi_backtest([early, later], odds, "mlb", "baseball",
                                    None, risk, 1000, warmup=0)["settled"]
        roi_probs.append(roi.loc[roi.event_id == "early", "estimated_probability"].tolist())
        calibration.append(walk_forward_backtest(
            [later, early], "mlb", "baseball", warmup=0, total_lines=(8.5,)))
    assert roi_probs[0] and roi_probs[0] == roi_probs[1]
    assert calibration[0]["binary_probs"] == calibration[1]["binary_probs"]
    assert calibration[0]["markets"]["totals@8.5"]["probs"] == calibration[1]["markets"]["totals@8.5"]["probs"]
    prior = dict(late, date="2026-08-31")
    control = walk_forward_backtest([prior, early], "mlb", "baseball", warmup=1)
    assert control["binary_probs"][0] != calibration[0]["binary_probs"][0]
