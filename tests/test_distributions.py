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


# --- Lineas asiaticas de cuarto (auditoria integral 2026-09-17, AUD-001) ------
#
# La liquidacion (`settle._grade`, AUD-MED-002) reparte el stake de una linea
# +-x.25 / +-x.75 entre las dos lineas adyacentes de medio punto. El pricing
# trataba esas lineas como enteras (push siempre 0), asi que la probabilidad
# servida se desviaba 7-13 pp de la coherente con el contrato de liquidacion e
# invertia el signo del EV. El oraculo es la propia `_grade` sobre la rejilla
# de marcadores: la probabilidad de decision debe coincidir con
# win_units / (win_units + loss_units).

def _decision_prob_via_grade(lam_h, lam_a, market, sel, line, max_goals=30):
    import pandas as pd
    from sqp.markets.settlement_math import SettlementProbabilities
    from sqp.models.distributions import score_pmf
    from sqp.settlement.settle import _grade
    ph, pa = score_pmf(lam_h, max_goals), score_pmf(lam_a, max_goals)
    mass = dict.fromkeys(["win", "loss", "push", "half_win", "half_loss", "void"], 0.0)
    row = pd.Series(dict(market=market, selection=sel, line=line, away="B"))
    for i, pi in enumerate(ph):
        for j, pj in enumerate(pa):
            mass[_grade(row, i, j, "A", True)] += pi * pj
    total = sum(mass.values())
    sp = SettlementProbabilities(full_win=mass["win"] / total, half_win=mass["half_win"] / total,
                                 push=mass["push"] / total, half_loss=mass["half_loss"] / total,
                                 full_loss=mass["loss"] / total)
    return sp.decision_probability


@pytest.mark.parametrize("market,sel,line,key", [
    ("spreads", "A", -0.25, "home_cover"), ("spreads", "B", 0.25, "away_cover"),
    ("spreads", "A", -0.75, "home_cover"), ("spreads", "B", 0.75, "away_cover"),
    ("spreads", "A", 1.25, "home_cover"), ("spreads", "B", -1.25, "away_cover"),
    ("totals", "Over", 2.25, "over"), ("totals", "Under", 2.25, "under"),
    ("totals", "Over", 2.75, "over"), ("totals", "Under", 2.75, "under"),
])
def test_quarter_line_pricing_matches_settlement_contract(market, sel, line, key):
    lam_h, lam_a = 1.5, 1.0
    spread = None
    total = None
    if market == "spreads":
        spread = line if sel == "A" else -line   # el adaptador recibe la linea del LOCAL
    else:
        total = line
    got = poisson_match_probs(lam_h, lam_a, spread, total, three_way=True, max_goals=30)[key]
    expected = _decision_prob_via_grade(lam_h, lam_a, market, sel, line)
    assert got == pytest.approx(expected, abs=1e-9)


@pytest.mark.parametrize("spread,total", [(-0.5, 2.5), (-1.0, 3.0), (0.0, 2.0), (None, None)])
def test_non_quarter_lines_unchanged_by_asian_split(spread, total):
    # Lineas enteras y de medio punto: la descomposicion no se activa y el
    # resultado es el mismo que calcular las masas a mano sobre la rejilla.
    p = poisson_match_probs(1.5, 1.0, spread, total, three_way=True, max_goals=30)
    from sqp.models.distributions import score_pmf
    ph, pa = score_pmf(1.5, 30), score_pmf(1.0, 30)
    cover = push = over = tpush = mass = 0.0
    for i, pi in enumerate(ph):
        for j, pj in enumerate(pa):
            q = pi * pj
            mass += q
            if spread is not None:
                if i - j > -spread: cover += q
                elif i - j == -spread: push += q
            if total is not None:
                if i + j > total: over += q
                elif i + j == total: tpush += q
    if spread is not None:
        assert p["home_cover"] == pytest.approx((cover / mass) / (1 - push / mass), abs=1e-12)
    if total is not None:
        assert p["over"] == pytest.approx((over / mass) / (1 - tpush / mass), abs=1e-12)
    assert p["home_win"] + p["draw"] + p["away_win"] == pytest.approx(1.0, abs=1e-9)


# --- AUD-001 (ronda audit-2026-10-18): en NHL el empate reglamentario siempre
#     termina con un gol mas ------------------------------------------------------

def _over(lam, line, fix):
    return poisson_match_probs(lam / 2, lam / 2, None, line, tie_adds_goal=fix)["over"]


def test_aud001_over_matches_the_nhl_history_at_its_mean_total():
    """Valores medidos sobre results_nhl.csv desde 2023-10 (n=4.658, 0 empates,
    total medio 6,158). Criterio de aceptacion: error < 2 pp en 4,5..7,5."""
    observado = {4.5: 0.781, 5.5: 0.558, 6.5: 0.444, 7.5: 0.244}
    for line, emp in observado.items():
        assert abs(_over(6.158, line, True) - emp) < 0.02, line


def test_aud001_parity_bias_is_gone():
    """Antes el error alternaba de signo con la paridad de la linea."""
    observado = {4.5: 0.781, 5.5: 0.558, 6.5: 0.444, 7.5: 0.244}
    antes = [_over(6.158, line, False) - emp for line, emp in observado.items()]
    assert [e > 0 for e in antes] == [False, True, False, True]
    assert max(abs(e) for e in antes) > 0.025


def test_aud001_expected_final_total_is_preserved():
    """Los ritmos vienen de marcadores FINALES: con el gol del empate sumado,
    el total final esperado debe seguir siendo lam_home + lam_away."""
    from sqp.models.distributions import _regulation_rates, _tie_mass_and_mean

    lh, la = _regulation_rates(3.4, 2.8, 15, None, 0.0, 0.0)
    tie, mean = _tie_mass_and_mean(lh, la, 15, None, 0.0, 0.0)
    assert mean + tie == pytest.approx(6.2, abs=1e-6)
    assert lh / la == pytest.approx(3.4 / 2.8)


def test_aud001_default_and_three_way_are_unchanged():
    base = poisson_match_probs(1.4, 1.1, -0.5, 2.5, three_way=True)
    assert base == poisson_match_probs(1.4, 1.1, -0.5, 2.5, three_way=True, tie_adds_goal=False)
    with pytest.raises(ValueError):
        poisson_match_probs(1.4, 1.1, -0.5, 2.5, three_way=True, tie_adds_goal=True)


def test_aud001_hockey_adapter_enables_it_and_baseball_does_not():
    from sqp.sports.adapters import BaseballAdapter, HockeyAdapter, SoccerAdapter

    assert HockeyAdapter.TIE_ADDS_GOAL is True
    assert BaseballAdapter.TIE_ADDS_GOAL is False
    assert SoccerAdapter.TIE_ADDS_GOAL is False


def test_aud001_tie_mass_goes_to_one_goal_margins():
    """Con el empate repartido en +-1, la cobertura de +1,5 de un equipo
    incluye toda esa masa y la de -1,5 ninguna; el h2h sigue 50/50."""
    sin = poisson_match_probs(3.0, 3.0, 1.5, None, tie_adds_goal=True)
    assert sin["home_win"] == pytest.approx(0.5)
    assert sin["home_cover"] == pytest.approx(1.0 - poisson_match_probs(
        3.0, 3.0, -1.5, None, tie_adds_goal=True)["home_cover"])


def test_aud001_low_totals_still_rescale_and_impossible_ones_warn():
    """Revision Fable: la saturacion no puede ser silenciosa. Un total bajo pero
    posible (1,1, el del harness de tuning) se resuelve; uno de 1 gol o menos
    es imposible si cada empate suma uno, y avisa sin tumbar el run."""
    import warnings

    from sqp.models.distributions import _regulation_rates, _tie_mass_and_mean

    lh, la = _regulation_rates(0.6, 0.5, 15, None, 0.0, 0.0)
    tie, mean = _tie_mass_and_mean(lh, la, 15, None, 0.0, 0.0)
    assert mean + tie == pytest.approx(1.1, abs=1e-6)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        assert _regulation_rates(0.4, 0.4, 15, None, 0.0, 0.0) == (0.4, 0.4)
    assert any("saturated" in str(x.message) for x in w)


def test_aud001_preregistered_pricing_context_restores_production():
    """`regulation_tie_without_goal` solo vale dentro del bloque, tambien ante
    una excepcion: el pipeline diario nunca debe quedarse con el pricing viejo."""
    from sqp.sports.adapters import HockeyAdapter, regulation_tie_without_goal

    with regulation_tie_without_goal():
        assert HockeyAdapter.TIE_ADDS_GOAL is False
    assert HockeyAdapter.TIE_ADDS_GOAL is True
    with pytest.raises(RuntimeError):
        with regulation_tie_without_goal():
            raise RuntimeError("x")
    assert HockeyAdapter.TIE_ADDS_GOAL is True
