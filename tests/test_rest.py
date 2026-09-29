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


def test_same_day_observed_game_does_not_zero_out_a_later_same_day_game():
    """KI-070: at generation time `results` can already contain a game the
    SAME UTC day as the one being estimated (e.g. a 02:00Z West Coast game
    observed before a 23:30Z game later that day). Naively using "the last
    observed date" would then compute rest=0 for the later game -- a value
    the walk-forward engine never produces (it defers a day's `observe`
    calls until the whole day is done, so it always estimates from the
    PREVIOUS day's state). `rest_days`/`margin_adjustment` must skip a
    stored date equal to `game_date` and use the true previous date."""
    m = RestModel(points_per_day=1.0, max_rest=4)
    m.observe("A", "X", "2026-06-01")   # A's true previous game
    m.observe("B", "Y", "2026-06-04")   # B's true previous game
    # An earlier game THE SAME DAY as the one being estimated is observed
    # first, as production would with a same-UTC-day earlier tipoff.
    m.observe("A", "Z", "2026-06-05")
    # Now estimate a LATER game that same day (2026-06-05): A's rest must
    # come from 2026-06-01 (4 days, capped), not from the just-observed
    # 2026-06-05 entry (which would give 0).
    assert m.rest_days("A", "2026-06-05") == 4
    assert m.margin_adjustment("A", "B", "2026-06-05") == 3.0  # 1.0*(4-1)


def test_keeps_only_the_last_two_distinct_dates_per_team():
    """Storage stays bounded (two distinct dates per team) even across many
    games; only the two most recent distinct dates matter for `rest_days`."""
    m = RestModel(points_per_day=1.0, max_rest=10)
    for day in ("2026-06-01", "2026-06-02", "2026-06-03", "2026-06-10"):
        m.observe("A", "X", day)
    assert m._dates["A"] == ["2026-06-03", "2026-06-10"]
    assert m.rest_days("A", "2026-06-15") == 5
