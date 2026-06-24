"""Monte Carlo engines: estimated-probability outputs, complementarity, and a
cross-check against the analytical normal margin (the audit use case). Seeded,
so assertions are stable."""
import math

from scipy.stats import norm

from sqp.simulation.monte_carlo import simulate_normal_game, simulate_poisson_game


def test_normal_outcome_probs_complementary_and_bounded():
    out = simulate_normal_game(mu_home=2.0, mu_away=0.0, sigma_team=11.0,
                               spread_line=-2.5, total_line=210.0)
    for v in out.values():
        assert 0.0 <= v <= 1.0
    # No ties in a continuous model -> the two sides partition the mass.
    assert math.isclose(out["home_win_estimated_probability"]
                        + out["away_win_estimated_probability"], 1.0, abs_tol=1e-6)
    assert math.isclose(out["home_cover_estimated_probability"]
                        + out["away_cover_estimated_probability"], 1.0, abs_tol=1e-6)
    assert math.isclose(out["over_estimated_probability"]
                        + out["under_estimated_probability"], 1.0, abs_tol=1e-6)


def test_normal_home_win_matches_analytical():
    # margin ~ Normal(mu_home - mu_away, sigma*sqrt(2)); P(margin>0) = Phi(d/s).
    mu_h, mu_a, sigma = 3.0, 0.0, 11.0
    out = simulate_normal_game(mu_h, mu_a, sigma, None, None, n_sims=60000, seed=7)
    analytical = float(norm.cdf((mu_h - mu_a) / (sigma * math.sqrt(2))))
    assert abs(out["home_win_estimated_probability"] - analytical) < 0.02


def test_normal_stronger_home_has_higher_win_prob():
    weak = simulate_normal_game(1.0, 0.0, 11.0, None, None)
    strong = simulate_normal_game(6.0, 0.0, 11.0, None, None)
    assert strong["home_win_estimated_probability"] > weak["home_win_estimated_probability"]


def test_poisson_three_way_sums_to_one():
    out = simulate_poisson_game(1.5, 1.2, spread_line=None, total_line=None,
                                three_way=True)
    s = (out["home_win_estimated_probability"] + out["draw_estimated_probability"]
         + out["away_win_estimated_probability"])
    assert math.isclose(s, 1.0, abs_tol=1e-6)


def test_poisson_two_way_splits_draws():
    # Without a three-way market, draw mass is split 50/50 into the two sides.
    out = simulate_poisson_game(1.3, 1.3, spread_line=None, total_line=None,
                                three_way=False)
    assert math.isclose(out["home_win_estimated_probability"]
                        + out["away_win_estimated_probability"], 1.0, abs_tol=1e-6)
    # Symmetric lambdas -> near coin flip.
    assert abs(out["home_win_estimated_probability"] - 0.5) < 0.03


def test_poisson_totals_complementary():
    out = simulate_poisson_game(1.8, 1.6, spread_line=-0.5, total_line=3.5)
    assert math.isclose(out["over_estimated_probability"]
                        + out["under_estimated_probability"], 1.0, abs_tol=1e-9)
    assert math.isclose(out["home_cover_estimated_probability"]
                        + out["away_cover_estimated_probability"], 1.0, abs_tol=1e-9)
