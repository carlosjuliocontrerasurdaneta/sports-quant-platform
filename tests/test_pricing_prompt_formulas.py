"""Check source-specification formulas against independently settled outcomes."""
from math import comb
from pathlib import Path
import re

import pytest

from sqp.markets.settlement_math import SettlementProbabilities


PROMPTS = Path(__file__).resolve().parents[1] / "docs/prompts"


def document(sport):
    return (PROMPTS / f"prompt-{sport}-pricing-v3.md").read_text(encoding="utf-8")


def evaluate(sport, variable, **values):
    expression = re.search(rf"^\s*{variable} = (.+)$", document(sport), re.M)[1]
    expression = expression.split(" si ")[0].split(" (+")[0]
    expression = expression.replace("×", "*").replace("−", "-")
    return eval(expression, {"__builtins__": {}}, values)


@pytest.mark.parametrize("sport", ["basket", "football", "nhl", "tenis"])
@pytest.mark.parametrize("win,push,loss,price", [
    (.48, .10, .42, 2.0), (.55, 0, .45, 1.9),
    (0, 1, 0, 2.0), (.4, .2, .4, 2.0), (.2, .1, .7, 3.0),
])
def test_ev_matches_settlement(sport, win, push, loss, price):
    expected = SettlementProbabilities(full_win=win, push=push, full_loss=loss)
    assert evaluate(sport, "EV_por_unidad", p_win=win, p_loss=loss,
                    decimal=price) == pytest.approx(expected.expected_value(price))


@pytest.mark.parametrize("margin,expected", [(-10, -9), (10, 9), (0, 0)])
def test_weather_preserves_favorite(margin, expected):
    assert evaluate("football", "Margin_ajustado", Margin=margin) == expected


@pytest.mark.parametrize("h", [-2, -1, 0, 1, 2])
@pytest.mark.parametrize("difference", [-1, 0, 1])
def test_asian_handicap_settlement(h, difference):
    # Exactly at the covering margin is a refund; one goal either side resolves it.
    margin = -h + difference
    assert evaluate("soccer", "margen_ajustado", margen=margin, h=h) == difference
    assert "push si = 0" in document("soccer")


@pytest.mark.parametrize("tie", [0, .23, 1])
def test_nhl_expected_total_matches_explicit_score_outcomes(tie):
    # Independent weighted outcomes: non-tie total 6, resolved-tie total 7.
    expected = (1 - tie) * 6 + tie * 7 + .2
    intermediate = evaluate("nhl", "Total_con_EN", Total=6, EN_total=.2)
    overtime = evaluate("nhl", "OT_total", P_reg_empate=tie)
    assert evaluate("nhl", "Total_reportado", Total_con_EN=intermediate,
                    OT_total=overtime) == pytest.approx(expected)


def test_tennis_conversion_table_matches_binomial_match_probability():
    text = document("tenis")
    bo3 = [float(x) / 100 for x in re.search(r"P_bo3:([^\n]+)", text)[1].split('%')
           if x.strip()]
    bo5 = [float(x) for x in re.search(r"P_bo5:([^\n]+)", text)[1].split()]
    assert len(bo3) == len(bo5) == 9
    for target, reported in zip(bo3, bo5, strict=True):
        lo, hi = 0., 1.
        for _ in range(80):
            p = (lo + hi) / 2
            win_bo3 = sum(comb(3, k) * p**k * (1-p)**(3-k) for k in (2, 3))
            if win_bo3 < target:
                lo = p
            else:
                hi = p
        p = (lo + hi) / 2
        win_bo5 = sum(comb(5, k) * p**k * (1-p)**(5-k) for k in (3, 4, 5))
        assert reported == round(100 * win_bo5, 1)
