"""Guard de mercado completo en _novig_probs (auditoria 2026-07-24, C-1).

Un mercado unilateral se de-vig-eaba a probabilidad implicita 1.0 (cualquier
implied unica normaliza a certeza) y un 1X2 sin la cara del empate inflaba
ambas probabilidades estimadas. Ahora devuelven {} y el pipeline marca el
candidato como incomplete_market (stake 0), igual que _spread_novig.
"""
import pytest

from sqp.pipeline.probabilities import _novig_probs


def test_one_sided_h2h_returns_empty():
    assert _novig_probs({("h2h", "Home", None): 1.91}, "h2h") == {}


def test_complete_two_way_h2h_sums_to_one():
    fair = _novig_probs({("h2h", "Home", None): 1.91,
                         ("h2h", "Away", None): 2.05}, "h2h")
    assert set(fair) == {"Home", "Away"}
    assert sum(fair.values()) == pytest.approx(1.0, abs=1e-9)


def test_three_way_missing_draw_returns_empty():
    cons = {("h2h", "A", None): 1.70, ("h2h", "B", None): 4.80}
    assert _novig_probs(cons, "h2h", three_way=True) == {}


def test_three_way_complete_sums_to_one():
    cons = {("h2h", "A", None): 2.10, ("h2h", "Draw", None): 3.40,
            ("h2h", "B", None): 3.60}
    fair = _novig_probs(cons, "h2h", three_way=True)
    assert set(fair) == {"A", "Draw", "B"}
    assert sum(fair.values()) == pytest.approx(1.0, abs=1e-9)


def test_totals_single_side_returns_empty():
    assert _novig_probs({("totals", "Over", 8.5): 1.95}, "totals", 8.5) == {}


def test_totals_complete_pair_sums_to_one():
    cons = {("totals", "Over", 8.5): 1.95, ("totals", "Under", 8.5): 1.87,
            ("totals", "Over", 9.0): 2.10}   # otra linea: no debe mezclarse
    fair = _novig_probs(cons, "totals", 8.5)
    assert set(fair) == {"Over", "Under"}
    assert sum(fair.values()) == pytest.approx(1.0, abs=1e-9)
