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


# --- AUD-014, ronda audit-2026-09-23: lineas asiaticas de cuarto -------------
#
# Con marcadores enteros, `total != 2.25` se cumple siempre: la simulacion
# trataba como binaria una apuesta que liquida a medias. Reproducido por OpenAI:
# lambda 1.5/1.0, total 2.25, seed 42 -> MC 0,4565 frente a 0,5233 analitico.

import pytest  # noqa: E402

from sqp.models.distributions import poisson_match_probs  # noqa: E402


@pytest.mark.parametrize("total_line", [2.25, 2.75, 3.25])
def test_poisson_totales_de_cuarto_coinciden_con_el_analitico(total_line):
    mc = simulate_poisson_game(1.5, 1.0, None, total_line, three_way=True,
                               n_sims=400_000, seed=42)
    exacto = poisson_match_probs(1.5, 1.0, None, total_line, three_way=True)
    # Error MC de una proporcion con n=400k: ~0,0008; 4 sigmas de margen.
    assert mc["over_estimated_probability"] == pytest.approx(exacto["over"], abs=0.004)
    assert mc["under_estimated_probability"] == pytest.approx(exacto["under"], abs=0.004)


@pytest.mark.parametrize("spread_line", [-0.25, -0.75, 0.25, 0.75])
def test_poisson_handicap_de_cuarto_coincide_con_el_analitico(spread_line):
    mc = simulate_poisson_game(1.5, 1.0, spread_line, None, three_way=True,
                               n_sims=400_000, seed=42)
    exacto = poisson_match_probs(1.5, 1.0, spread_line, None, three_way=True)
    assert mc["home_cover_estimated_probability"] == pytest.approx(
        exacto["home_cover"], abs=0.004)


@pytest.mark.parametrize("line", [2.0, 2.5])
def test_lineas_enteras_y_medias_no_cambian(line):
    """Contraprueba: la ruta de enteras/medias es la de siempre."""
    mc = simulate_poisson_game(1.5, 1.0, -line + 2.0, line, three_way=True,
                               n_sims=200_000, seed=7)
    exacto = poisson_match_probs(1.5, 1.0, -line + 2.0, line, three_way=True)
    assert mc["over_estimated_probability"] == pytest.approx(exacto["over"], abs=0.005)
