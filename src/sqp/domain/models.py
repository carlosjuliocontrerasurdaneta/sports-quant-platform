"""Domain entities. All probabilities are *estimated probabilities*."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


@dataclass
class Event:
    event_id: str
    sport_key: str            # The Odds API sport key (e.g. basketball_nba)
    league: str               # internal league id (e.g. nba, epl)
    home: str
    away: str
    start_time: str           # ISO-8601 UTC
    data_label: str = "real"  # "real" | "demo_synthetic"
    home_pitcher: str | None = None  # baseball: probable/confirmed starter
    away_pitcher: str | None = None


@dataclass
class MarketLine:
    market: str               # h2h | spreads | totals
    bookmaker: str
    outcome: str              # team name | Draw | Over | Under
    price_decimal: float
    point: float | None = None  # spread or total line


@dataclass
class EventOdds:
    event: Event
    lines: list[MarketLine] = field(default_factory=list)


@dataclass
class EstimatedProbabilities:
    """Model output. Keys follow the simulation contract."""
    home_win_estimated_probability: float
    away_win_estimated_probability: float
    draw_estimated_probability: float | None = None  # soccer 3-way
    home_cover_estimated_probability: float | None = None
    away_cover_estimated_probability: float | None = None
    over_estimated_probability: float | None = None
    under_estimated_probability: float | None = None
    spread_line: float | None = None  # home handicap (negative = home favorite)
    total_line: float | None = None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class BetCandidate:
    event_id: str
    league: str
    market: str
    selection: str
    line: float | None
    price_decimal: float
    bookmaker: str
    estimated_probability: float  # probability actually used (after market shrink)
    implied_probability_novig: float
    estimated_edge: float
    kelly_stake_pct: float
    stake: float
    data_label: str
    model_probability: float = float("nan")  # raw model prob before market shrink
    # Probability actually used for edge/stake when calibration is enabled. Equals
    # estimated_probability when calibration is off or no model exists. The
    # uncalibrated estimated_probability remains the calibrator's training target.
    calibrated_probability: float = float("nan")
    flags: str = ""  # e.g. "edge_exceeds_max_plausible": flagged, not staked
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
