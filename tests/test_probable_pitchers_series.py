"""Probable-pitcher attachment for multi-game series.

Regression guard: two games of the same matchup on consecutive days must each
receive their OWN announced starters. The previous implementation keyed the
probables map on (home, away) only, so the later game overwrote the earlier one
and both events estimated with identical pitchers (same probability to 6 dp).
"""
from sqp.domain.models import Event, EventOdds
from sqp.pipeline.daily import _attach_probable_pitchers, _prior_day
from sqp.sports.team_names import normalize_key


class _FakeProbablesProvider:
    """Stands in for MLBStatsProvider.fetch_probable_pitchers (keyed by date)."""

    def __init__(self, by_date: dict[str, list[dict]]):
        self.by_date = by_date
        self.requested_days: list[str] = []

    def fetch_probable_pitchers(self, date_iso: str) -> list[dict]:
        self.requested_days.append(date_iso)
        return self.by_date.get(date_iso, [])


def _event(start_time: str) -> EventOdds:
    return EventOdds(
        event=Event(event_id=start_time, sport_key="baseball_mlb", league="mlb",
                    home="Arizona Diamondbacks", away="Los Angeles Angels",
                    start_time=start_time, data_label="real"),
        lines=[])


def test_prior_day_handles_month_and_year_boundaries():
    assert _prior_day("2026-06-16") == "2026-06-15"
    assert _prior_day("2026-03-01") == "2026-02-28"
    assert _prior_day("2026-01-01") == "2025-12-31"
    assert _prior_day("not-a-date") is None


def test_series_games_get_distinct_starters():
    # Two LAA @ ARI games on consecutive official dates (Arizona is UTC-7, so a
    # ~18:41 local first pitch is the next UTC day -> official date = UTC date-1).
    provider = _FakeProbablesProvider({
        "2026-06-15": [{"date": "2026-06-15", "commence": "2026-06-16T01:41:00Z",
                        "home": "Arizona Diamondbacks", "away": "Los Angeles Angels",
                        "home_pitcher": "Game1 Home Ace", "away_pitcher": "Game1 Away Arm"}],
        "2026-06-16": [{"date": "2026-06-16", "commence": "2026-06-17T01:41:00Z",
                        "home": "Arizona Diamondbacks", "away": "Los Angeles Angels",
                        "home_pitcher": "Game2 Home Ace", "away_pitcher": "Game2 Away Arm"}],
    })
    game1 = _event("2026-06-16T01:41:00Z")  # official date 2026-06-15
    game2 = _event("2026-06-17T01:41:00Z")  # official date 2026-06-16

    _attach_probable_pitchers([game1, game2], "mlb", provider=provider)

    assert game1.event.home_pitcher == "Game1 Home Ace"
    assert game1.event.away_pitcher == "Game1 Away Arm"
    assert game2.event.home_pitcher == "Game2 Home Ace"
    assert game2.event.away_pitcher == "Game2 Away Arm"
    # The whole point: the two games must NOT collapse onto one matchup.
    assert game1.event.home_pitcher != game2.event.home_pitcher


def test_unmatched_event_stays_without_starter():
    provider = _FakeProbablesProvider({})  # no announcements available
    game = _event("2026-06-16T01:41:00Z")
    _attach_probable_pitchers([game], "mlb", provider=provider)
    assert game.event.home_pitcher is None
    assert game.event.away_pitcher is None


def test_divergent_vendor_spellings_match_after_normalize():
    # The Odds API and the MLB Stats API spell teams differently (punctuation,
    # casing). Probables are keyed by the MLB spelling; the event by the odds one.
    provider = _FakeProbablesProvider({
        "2026-06-15": [{"date": "2026-06-15", "commence": "2026-06-16T01:41:00Z",
                        "home": "St Louis Cardinals", "away": "Los Angeles Angels",
                        "home_pitcher": "Ace One", "away_pitcher": "Arm Two"}],
    })

    def _odds_event() -> EventOdds:
        return EventOdds(
            event=Event(event_id="x", sport_key="baseball_mlb", league="mlb",
                        home="St. Louis Cardinals", away="LOS ANGELES ANGELS",
                        start_time="2026-06-16T01:41:00Z", data_label="real"),
            lines=[])

    # Without a normalizer the raw keys differ and nothing attaches (the bug).
    raw = _odds_event()
    _attach_probable_pitchers([raw], "mlb", provider=provider)
    assert raw.event.home_pitcher is None

    # With the normalizer the same team is recognized across vendors.
    fixed = _odds_event()
    _attach_probable_pitchers([fixed], "mlb", normalize=normalize_key, provider=provider)
    assert fixed.event.home_pitcher == "Ace One"
    assert fixed.event.away_pitcher == "Arm Two"


def test_provider_failure_is_best_effort():
    class _Boom:
        def fetch_probable_pitchers(self, date_iso: str):
            raise RuntimeError("statsapi down")

    game = _event("2026-06-16T01:41:00Z")
    _attach_probable_pitchers([game], "mlb", provider=_Boom())  # must not raise
    assert game.event.home_pitcher is None
