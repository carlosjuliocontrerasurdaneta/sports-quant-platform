"""Rest / back-to-back margin adjustment (sqp.models.rest). See RestModel."""
from sqp.models.rest import RestModel


def test_no_op_when_points_per_day_zero():
    m = RestModel(points_per_day=0.0)
    m.observe("A", "B", "2026-06-01")
    assert m.margin_adjustment("A", "B", "2026-06-05") == 0.0


def test_rested_home_gets_positive_margin_short_rest_away_negative():
    m = RestModel(points_per_day=1.0, max_rest=4)
    # Both played on 06-01; home plays again 06-05 (4 days rest), away 06-02
    # then again 06-05 would be... set up an explicit rest gap instead:
    m.observe("Home", "X", "2026-06-01")   # Home last game 06-01
    m.observe("Away", "Y", "2026-06-04")   # Away last game 06-04
    # Game on 06-05: home rest 4, away rest 1 -> +1.0*(4-1) = +3 to home margin.
    assert m.margin_adjustment("Home", "Away", "2026-06-05") == 3.0
    # Symmetric: if the away side is the rested one, the adjustment flips sign.
    assert m.margin_adjustment("Away", "Home", "2026-06-05") == -3.0


def test_rest_days_capped():
    m = RestModel(points_per_day=1.0, max_rest=4)
    m.observe("Home", "X", "2026-01-01")   # very stale
    m.observe("Away", "Y", "2026-06-04")
    # Home rest would be huge but caps at 4; away rest 1 -> +1*(4-1)=3.
    assert m.margin_adjustment("Home", "Away", "2026-06-05") == 3.0


def test_first_game_or_unknown_is_neutral():
    m = RestModel(points_per_day=1.0)
    # No prior games recorded -> no adjustment.
    assert m.margin_adjustment("A", "B", "2026-06-05") == 0.0
    m.observe("A", "B", "2026-06-01")
    # B has a prior game but C does not -> still neutral (one side unknown).
    assert m.margin_adjustment("A", "C", "2026-06-05") == 0.0


def test_unparseable_date_is_neutral():
    m = RestModel(points_per_day=1.0)
    m.observe("A", "B", "2026-06-01")
    assert m.margin_adjustment("A", "B", "not-a-date") == 0.0
