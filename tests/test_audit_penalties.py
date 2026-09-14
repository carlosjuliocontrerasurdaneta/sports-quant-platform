"""AUD-004: replay the configured policy or reject unavailable inputs."""
from statistics import stdev

import pytest

from sqp.backtesting.roi_engine import realized_roi_backtest
from sqp.config import RiskConfig
from sqp.domain.models import Event, EventOdds, MarketLine


@pytest.mark.parametrize("field", ["line_movement_penalty", "line_velocity_penalty"])
def test_missing_trajectory_rejected(field):
    with pytest.raises(ValueError, match="historical trajectories"):
        realized_roi_backtest([], {}, "mlb", "baseball", None,
                             RiskConfig(**{field: .5}), 1000)


def test_books_dispersion_changes_stake_by_the_documented_penalty():
    ev = Event("e", "bt", "mlb", "A", "B", "2026-09-10T20:00:00Z")
    eo = EventOdds(ev, [MarketLine("h2h", b, side, price)
                       for b, side, price in [("b1", "A", 2.), ("b2", "A", 2.6),
                                               ("b1", "B", 2.), ("b2", "B", 1.8)]])
    result = dict(date="2026-09-10", game_id="e", home="A", away="B",
                  home_score=3, away_score=2, neutral=False)
    stakes = []
    for coefficient in (0., .5):
        risk = RiskConfig(min_edge=0, market_shrink=0, max_plausible_edge=1,
                          books_spread_penalty=coefficient, kelly_fraction=1.,
                          max_stake_pct=1., max_daily_exposure_pct=0.)
        settled = realized_roi_backtest([result], {"e": eo}, "mlb", "baseball",
                                        None, risk, 1000, warmup=0)["settled"]
        row = settled[settled.selection == "A"].iloc[0]
        stakes.append(float(row.stake))
        price = float(row.price_decimal)
    # Kelly = EV / (odds - 1); spread penalty is subtracted from EV.
    expected_reduction = .5 * stdev([1 / 2., 1 / 2.6]) / (price - 1) * 1000
    assert stakes[0] - stakes[1] == pytest.approx(expected_reduction, abs=.02)
