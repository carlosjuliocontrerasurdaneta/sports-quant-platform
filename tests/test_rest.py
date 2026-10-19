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


# --- AUD-002 (ronda audit-2026-10-18): partidos programados antes del evento ---

def test_aud002_scheduled_game_before_the_event_counts_as_last_game():
    """Evento a D+3 con otro partido del mismo equipo a D+2: el descanso es 1,
    no los dias desde el ultimo partido JUGADO (topado en 4)."""
    m = RestModel(points_per_day=1.0, max_rest=4)
    m.observe("PHI", "X", "2026-10-17")
    m.observe("CLE", "Y", "2026-10-17")
    assert m.rest_days("PHI", "2026-10-22") == 4
    m.schedule("PHI", "Z", "2026-10-21")
    assert m.rest_days("PHI", "2026-10-22") == 1
    assert m.rest_days("CLE", "2026-10-22") == 4
    assert m.margin_adjustment("PHI", "CLE", "2026-10-22") == -3.0


def test_aud002_scheduled_same_day_or_later_games_do_not_count():
    m = RestModel(points_per_day=1.0)
    m.observe("A", "B", "2026-10-17")
    m.schedule("A", "C", "2026-10-22")   # el propio dia del evento
    m.schedule("A", "D", "2026-10-24")   # despues
    assert m.rest_days("A", "2026-10-22") == 4


def test_aud002_schedule_alone_does_not_invent_a_rest_history():
    m = RestModel(points_per_day=1.0)
    m.schedule("A", "B", "2026-10-20")
    assert m.rest_days("A", "2026-10-22") is None


def test_aud002_matches_the_walk_forward_state_of_the_previous_day():
    """Paridad: con el calendario, el valor servido a D+3 es el que el
    walk-forward calcula tras observar el partido de D+2."""
    servido = RestModel(points_per_day=1.0)
    servido.observe("A", "B", "2026-10-17")
    servido.schedule("A", "C", "2026-10-21")
    walk = RestModel(points_per_day=1.0)
    walk.observe("A", "B", "2026-10-17")
    walk.observe("A", "C", "2026-10-21")
    assert servido.rest_days("A", "2026-10-22") == walk.rest_days("A", "2026-10-22") == 1
