"""First-5-innings (F5) derived market for baseball.

F5 is starter-dominated: the starting pitcher throws essentially all of innings
1-5, while the bullpen governs 6-9. A naive proration (lam_F5 = phi * lam_full)
is a deterministic rescale of the full-game view and therefore adds NO edge over
it. The edge hypothesis is that the starter matters MORE in F5 than in the full
game; `f5_starter_emphasis` is the tunable knob, neutral (=proration) by default.

These tests fix the model's PROPERTIES, not a magic number, and do not claim the
F5 model is validated: validation needs inning-level outcomes not yet backfilled.
"""
from __future__ import annotations

from sqp.domain.models import Event
from sqp.sports.registry import get_adapter

PHI = 5.0 / 9.0


def _ev(home_pitcher=None, away_pitcher=None) -> Event:
    return Event(event_id="x", sport_key="bt", league="mlb", home="A", away="B",
                 start_time="2026-06-12", home_pitcher=home_pitcher,
                 away_pitcher=away_pitcher)


def _fit_elite_away_starter():
    """Adapter where 'Ace' is an elite (run-suppressing) starter."""
    adapter = get_adapter("mlb", "baseball")
    rows = []
    for i in range(12):
        rows.append({"date": f"2026-05-{i+1:02d}", "home": "C", "away": "A",
                     "home_score": 1, "away_score": 4, "away_starter": "Ace",
                     "home_starter": "Filler One"})
    adapter.fit_results(rows)
    return adapter


def test_f5_neutral_emphasis_is_pure_proration():
    # Unknown starters (factor 1.0), default park (no-op): F5 = phi * full.
    adapter = get_adapter("mlb", "baseball")
    full_h, full_a = adapter._rates(_ev())
    f5_h, f5_a = adapter.f5_rates(_ev())
    assert abs(f5_h / full_h - PHI) < 1e-9
    assert abs(f5_a / full_a - PHI) < 1e-9


def test_f5_total_is_below_full_total():
    adapter = _fit_elite_away_starter()
    ev = _ev(away_pitcher="Ace")
    full_h, full_a = adapter._rates(ev)
    f5_h, f5_a = adapter.f5_rates(ev)
    assert (f5_h + f5_a) < (full_h + full_a)


def test_emphasis_amplifies_the_starter_beyond_proration():
    # An elite away starter suppresses the HOME team. With emphasis > 1 the F5
    # home lambda drops BELOW the pure-proration value; emphasis = 1 recovers it.
    adapter = _fit_elite_away_starter()
    ev = _ev(away_pitcher="Ace")
    adapter.params["f5_starter_emphasis"] = 1.0
    neutral_h, _ = adapter.f5_rates(ev)
    adapter.params["f5_starter_emphasis"] = 2.0
    amplified_h, _ = adapter.f5_rates(ev)
    assert amplified_h < neutral_h


def test_f5_h2h_is_three_way_with_tie_mass():
    # F5 has no extra innings, so a tie after 5 is a real outcome with mass.
    adapter = get_adapter("mlb", "baseball")
    probs = adapter.estimate_f5(_ev(), total_line=4.5)
    assert probs["draw"] > 0.0
    assert abs(probs["home_win"] + probs["draw"] + probs["away_win"] - 1.0) < 1e-9
    assert 0.0 < probs["over"] < 1.0


def test_f5_lambdas_are_bounded_below():
    adapter = _fit_elite_away_starter()
    adapter.params["f5_starter_emphasis"] = 50.0  # absurd amplification
    f5_h, f5_a = adapter.f5_rates(_ev(away_pitcher="Ace"))
    assert f5_h >= 0.05 and f5_a >= 0.05
