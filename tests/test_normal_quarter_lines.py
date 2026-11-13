"""Lineas asiaticas de cuarto en el modelo normal (NBA/NFL): precio == liquidacion.

Mismo contrato que AUD-001 para Poisson: la probabilidad de una linea x.25/x.75
debe ser la de la liquidacion a medias (`settle._grade_linea` sobre las dos
lineas adyacentes), no la de una linea de medio punto.
"""
import pytest
from scipy.stats import norm

from sqp.markets.settlement_math import split_asian_line
from sqp.models.distributions import normal_margin_probs, normal_total_probs
from sqp.settlement.settle import _grade_linea

MU, SIGMA = 4.0, 11.0


def _reference(market: str, sel: str, line: float, mu: float) -> float:
    """P(gana | resuelto) sumando el pmf discretizado y liquidando cada mitad."""
    win = loss = 0.0
    for score in range(-200, 400):
        p = norm.cdf(score + 0.5, mu, SIGMA) - norm.cdf(score - 0.5, mu, SIGMA)
        for half in split_asian_line(line):
            if market == "spreads" and sel == "h":
                res = _grade_linea("spreads", "h", True, score, 0, half)
            elif market == "spreads":
                # visitante: margen local `score`, linea del visitante = -half
                res = _grade_linea("spreads", "a", False, score, 0, -half)
            else:
                res = _grade_linea("totals", sel, True, 0, score, half)
            win += 0.5 * p * (res == "win")
            loss += 0.5 * p * (res == "loss")
    return win / (win + loss)


@pytest.mark.parametrize("line", [-5.25, -5.75, 5.25, 5.75, -0.25, 0.75])
def test_spread_quarter_line_matches_settlement(line):
    got = normal_margin_probs(MU, SIGMA, line)
    ref = _reference("spreads", "h", line, MU)
    assert got["home_cover"] == pytest.approx(ref, abs=1e-9)
    assert got["away_cover"] == pytest.approx(_reference("spreads", "a", line, MU), abs=1e-9)
    assert got["home_cover"] + got["away_cover"] == pytest.approx(1.0)


@pytest.mark.parametrize("line", [220.25, 220.75, 221.25, 221.75])
def test_total_quarter_line_matches_settlement(line):
    mu = 221.0
    got = normal_total_probs(mu, SIGMA, line)
    assert got["over"] == pytest.approx(_reference("totals", "Over", line, mu), abs=1e-9)
    assert got["under"] == pytest.approx(_reference("totals", "Under", line, mu), abs=1e-9)
    assert got["over"] + got["under"] == pytest.approx(1.0)


def test_quarter_line_lies_between_adjacent_half_lines():
    lo, hi = normal_total_probs(221.0, SIGMA, 220.5)["over"], normal_total_probs(221.0, SIGMA, 221.0)["over"]
    q = normal_total_probs(221.0, SIGMA, 220.75)["over"]
    assert min(lo, hi) < q < max(lo, hi)


def test_half_and_integer_lines_unchanged():
    assert normal_total_probs(221.0, SIGMA, 220.5)["over"] == pytest.approx(1 - norm.cdf(220.5, 221.0, SIGMA))
    p_over = 1 - norm.cdf(221.5, 221.0, SIGMA)
    push = norm.cdf(221.5, 221.0, SIGMA) - norm.cdf(220.5, 221.0, SIGMA)
    assert normal_total_probs(221.0, SIGMA, 221.0)["over"] == pytest.approx(p_over / (1 - push))
    assert normal_margin_probs(MU, SIGMA, -5.5)["home_cover"] == pytest.approx(1 - norm.cdf(5.5, MU, SIGMA))
