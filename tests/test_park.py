"""Ballpark run-environment factor (sqp.models.park). See ParkFactors."""
from sqp.models.park import ParkFactors


def _feed(pf, home, away, total, n=1):
    for _ in range(n):
        pf.update(home, away, total)


def test_no_op_when_bound_is_zero():
    pf = ParkFactors(prior_games=5.0, bound=0.0)
    # Hitter park: home games average far more runs than away games.
    _feed(pf, "Rockies", "Mets", 14.0, n=40)
    _feed(pf, "Padres", "Rockies", 6.0, n=40)   # Rockies away games
    assert pf.factor("Rockies") == 1.0           # bound 0 -> always neutral


def test_hitter_park_above_one_pitcher_park_below_one():
    pf = ParkFactors(prior_games=5.0, bound=0.20)
    # Rockies hitter park: high totals at home, lower on the road.
    _feed(pf, "Rockies", "OppA", 14.0, n=20)     # Rockies home
    _feed(pf, "OppB", "Rockies", 8.0, n=20)      # Rockies away
    # Padres pitcher park: low totals at home, higher on the road.
    _feed(pf, "Padres", "OppC", 6.0, n=20)       # Padres home
    _feed(pf, "OppD", "Padres", 10.0, n=20)      # Padres away
    f_rockies = pf.factor("Rockies")             # 14/8 -> >1
    f_padres = pf.factor("Padres")               # 6/10 -> <1
    assert f_rockies > 1.0 and f_padres < 1.0
    assert f_rockies <= 1.20 + 1e-9 and f_padres >= 0.80 - 1e-9   # bounded


def test_unknown_or_one_sided_team_is_neutral():
    pf = ParkFactors(prior_games=5.0, bound=0.20)
    assert pf.factor("Nobody") == 1.0
    _feed(pf, "Rays", "Yankees", 8.0, n=3)       # Rays only have HOME games so far
    assert pf.factor("Rays") == 1.0              # needs both home and away samples
    assert pf.is_known("Rays") is False


def test_low_sample_regresses_toward_neutral():
    strong = ParkFactors(prior_games=5.0, bound=0.50)
    weak = ParkFactors(prior_games=100.0, bound=0.50)
    for pf in (strong, weak):
        _feed(pf, "Rockies", "Mets", 14.0, n=10)
        _feed(pf, "Padres", "Rockies", 6.0, n=10)
    # Same data, larger prior -> factor pulled closer to 1.0.
    assert abs(weak.factor("Rockies") - 1.0) < abs(strong.factor("Rockies") - 1.0)
