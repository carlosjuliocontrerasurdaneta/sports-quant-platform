import pytest
from sqp.models.distributions import normal_margin_probs, poisson_match_probs
from sqp.simulation.monte_carlo import simulate_normal_game, simulate_poisson_game

def test_normal_margin_probs_bounded_and_monotone():
    p1 = normal_margin_probs(3.0, 12.0, -3.5)
    p2 = normal_margin_probs(8.0, 12.0, -3.5)
    assert 0 < p1["home_win"] < 1
    assert p2["home_win"] > p1["home_win"]
    assert p1["home_cover"] + p1["away_cover"] == pytest.approx(1.0)

def test_poisson_three_way_sums_to_one():
    p = poisson_match_probs(1.6, 1.1, None, 2.5, three_way=True)
    assert p["home_win"] + p["draw"] + p["away_win"] == pytest.approx(1.0, abs=1e-6)
    assert p["over"] + p["under"] == pytest.approx(1.0)

def test_mc_agrees_with_analytic_poisson():
    a = poisson_match_probs(3.2, 2.9, None, 6.5)
    m = simulate_poisson_game(3.2, 2.9, None, 6.5, n_sims=200000, seed=1)
    assert m["home_win_estimated_probability"] == pytest.approx(a["home_win"], abs=0.01)
    assert m["over_estimated_probability"] == pytest.approx(a["over"], abs=0.01)

def test_mc_normal_probabilities_bounded():
    m = simulate_normal_game(112, 108, 11, -3.5, 220.5, n_sims=50000)
    for v in m.values():
        assert 0.0 <= v <= 1.0
