"""Matchup-specific totals (fixes the league-constant total bug) and the
edge-plausibility cap that flags miscalibrated selections instead of staking them.
"""
import pandas as pd
from sqp.config import ROOT, RiskConfig, Settings
from sqp.domain.models import Event
from sqp.models.team_scoring import TeamScoringRates
from sqp.pipeline.daily import run_league
from sqp.sports.registry import get_adapter


def _ev(home: str, away: str) -> Event:
    return Event(event_id="x", sport_key="bt", league="nba", home=home, away=away,
                 start_time="2099-01-01T00:00:00Z")


def test_scoring_rates_cold_start_falls_back_to_league_constant():
    sr = TeamScoringRates()
    assert sr.expected_total("A", "B", fallback_total=224.0) == 224.0


def test_scoring_rates_are_matchup_specific():
    sr = TeamScoringRates(prior_games=6.0)
    for _ in range(15):
        sr.update("A", "B", 130, 128)   # high-scoring pair
        sr.update("C", "D", 95, 92)     # low-scoring pair
    assert sr.expected_total("A", "B", 224.0) > sr.expected_total("C", "D", 224.0)


def test_normal_adapter_total_is_matchup_specific():
    adapter = get_adapter("nba", "basketball")
    rows = []
    for i in range(15):
        rows.append({"date": f"2026-01-{i+1:02d}", "home": "A", "away": "B",
                     "home_score": 130, "away_score": 128})
        rows.append({"date": f"2026-01-{i+1:02d}", "home": "C", "away": "D",
                     "home_score": 95, "away_score": 92})
    adapter.fit_results(rows)
    line = 224.0
    ab = adapter.estimate(_ev("A", "B"), None, line)
    cd = adapter.estimate(_ev("C", "D"), None, line)
    # The old league-constant model returned identical totals for every game.
    assert ab.over_estimated_probability != cd.over_estimated_probability
    assert ab.over_estimated_probability > cd.over_estimated_probability


def _nhl_ev(home: str, away: str) -> Event:
    return Event(event_id="x", sport_key="bt", league="nhl", home=home, away=away,
                 start_time="2099-01-01T00:00:00Z")


def test_poisson_adapter_total_is_matchup_specific():
    adapter = get_adapter("nhl", "hockey")
    rows = []
    for i in range(15):
        rows.append({"date": f"2026-01-{i+1:02d}", "home": "A", "away": "B",
                     "home_score": 6, "away_score": 5})   # high-scoring pair
        rows.append({"date": f"2026-01-{i+1:02d}", "home": "C", "away": "D",
                     "home_score": 1, "away_score": 0})   # low-scoring pair
    adapter.fit_results(rows)
    line = 6.0
    ab = adapter.estimate(_nhl_ev("A", "B"), None, line)
    cd = adapter.estimate(_nhl_ev("C", "D"), None, line)
    assert ab.over_estimated_probability > cd.over_estimated_probability


def test_poisson_scoring_totals_toggle_off_is_league_constant():
    # With the feature off, the total no longer depends on the matchup.
    adapter = get_adapter("nhl", "hockey", {"scoring_totals": False})
    rows = []
    for i in range(15):
        rows.append({"date": f"2026-01-{i+1:02d}", "home": "A", "away": "B",
                     "home_score": 6, "away_score": 5})
        rows.append({"date": f"2026-01-{i+1:02d}", "home": "C", "away": "D",
                     "home_score": 1, "away_score": 0})
    adapter.fit_results(rows)
    ab = adapter.estimate(_nhl_ev("A", "B"), None, 6.0)
    cd = adapter.estimate(_nhl_ev("C", "D"), None, 6.0)
    assert abs(ab.over_estimated_probability - cd.over_estimated_probability) < 1e-9


def test_risk_config_has_plausibility_cap_default():
    assert RiskConfig().max_plausible_edge == 0.15


def test_edge_cap_flags_and_unstakes_implausible_candidates():
    settings = Settings.load()
    settings.risk.market_shrink = 0.0  # isolate the cap from the shrink dampener
    run_league("nba", settings, mode="demo")
    f = ROOT / "data" / "predictions" / "demo" / "candidates_nba.csv"
    c = pd.read_csv(f)
    c["flags"] = c["flags"].fillna("")
    # Every staked candidate is within the plausibility cap.
    staked = c[c["stake"] > 0]
    assert (staked["estimated_edge"] <= settings.risk.max_plausible_edge + 1e-9).all()
    # Flagged candidates are recorded for audit but never staked.
    flagged = c[c["flags"] != ""]
    assert len(flagged) >= 1
    assert (flagged["stake"] == 0).all()
    assert (flagged["estimated_edge"] > settings.risk.max_plausible_edge).all()


def test_market_shrink_blends_model_toward_market():
    settings = Settings.load()
    s = settings.risk.market_shrink
    assert 0.0 <= s <= 1.0
    run_league("nba", settings, mode="demo")
    c = pd.read_csv(ROOT / "data" / "predictions" / "demo" / "candidates_nba.csv")
    # Where a market anchor exists, the used probability is the convex blend
    # (1-s)*model + s*market, so it lies between the two and matches the formula.
    anchored = c[c["implied_probability_novig"].notna()]
    assert len(anchored) >= 1
    expected = (1 - s) * anchored["model_probability"] + s * anchored["implied_probability_novig"]
    assert (expected - anchored["estimated_probability"]).abs().max() < 1e-3
    # Shrinking toward market never increases the edge vs the raw model.
    raw_edge = anchored["model_probability"] * anchored["price_decimal"] - 1
    assert (anchored["estimated_edge"] <= raw_edge + 1e-9).all()
