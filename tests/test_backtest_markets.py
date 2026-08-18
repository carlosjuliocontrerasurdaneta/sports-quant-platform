"""Arnés walk-forward para spreads y totals.

Hasta el 2026-08-18 `walk_forward_backtest` solo recogía
`home_win_estimated_probability`, así que ni el backtest ni `tune_ratings.py`
evaluaban jamás esos dos mercados. La prueba de que el hueco era real: el arreglo
del `home_scoring_bonus` alteró lambda en TRES familias de producción y no rompió
ni uno de los 1086 tests.

Los desenlaces salen del marcador, así que este arnés no necesita histórico de
cuotas: se evalúa contra líneas fijas de referencia.
"""
import pytest
from sqp.backtesting.engine import walk_forward_backtest


def _hockey_rows(n: int = 240) -> list[dict]:
    """Marcadores variados y deterministas.

    Los dos marcadores usan módulos coprimos (5 y 7) a propósito: con el mismo
    módulo solo salen cinco totales distintos y la línea entera nunca produce
    empujes, así que el test que los cubre no probaría nada.
    """
    pairs = (("A", "B"), ("C", "D"), ("A", "C"), ("B", "D"))
    rows = []
    for i in range(n):
        h, a = pairs[i % 4]
        rows.append({"date": f"2026-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
                     "home": h, "away": a,
                     "home_score": 1 + (i % 5), "away_score": (i % 7) % 5})
    return rows


def test_default_call_reports_no_market_breakdown():
    """Sin líneas, el arnés se comporta EXACTAMENTE como antes: los cinco
    scripts que ya lo llaman no pueden cambiar de resultado."""
    out = walk_forward_backtest(_hockey_rows(), "nhl", "hockey", warmup=60)
    assert out["markets"] == {}
    assert out["n_games_evaluated"] > 0
    assert out["brier_score"] == pytest.approx(out["brier_score"])  # finito


def test_totals_outcome_matches_the_scoreboard():
    """La tasa observada de Over la fija el marcador, no el modelo."""
    rows = _hockey_rows()
    out = walk_forward_backtest(rows, "nhl", "hockey", warmup=60, total_lines=(5.5,))
    m = out["markets"]["totals@5.5"]
    evaluated = rows[60:]
    expected = sum(1 for r in evaluated
                   if r["home_score"] + r["away_score"] > 5.5) / len(evaluated)
    assert m["n"] == len(evaluated)
    assert m["observed_rate"] == pytest.approx(expected)


def test_spread_outcome_uses_the_home_margin():
    """A hándicap -1.5 el local cubre si gana por 2 o más."""
    rows = _hockey_rows()
    out = walk_forward_backtest(rows, "nhl", "hockey", warmup=60, spread_lines=(-1.5,))
    m = out["markets"]["spreads@-1.5"]
    evaluated = rows[60:]
    expected = sum(1 for r in evaluated
                   if r["home_score"] - r["away_score"] >= 2) / len(evaluated)
    assert m["observed_rate"] == pytest.approx(expected)


def test_integer_lines_exclude_pushes():
    """En línea entera el empate contra la línea no es ni acierto ni fallo:
    se excluye, igual que los empates en las métricas binarias del moneyline."""
    rows = _hockey_rows()
    out = walk_forward_backtest(rows, "nhl", "hockey", warmup=60, total_lines=(6.0,))
    evaluated = rows[60:]
    pushes = sum(1 for r in evaluated if r["home_score"] + r["away_score"] == 6)
    assert pushes > 0, "el fixture debe contener empujes para que el test pruebe algo"
    assert out["markets"]["totals@6.0"]["n"] == len(evaluated) - pushes


def test_harness_would_catch_a_total_inflating_parameter():
    """El test que justifica el arnés entero.

    `home_scoring_bonus` inflaba el total de cada partido (bug del 2026-08-18) y
    NINGÚN test lo detectaba. El sesgo medido —probabilidad media estimada menos
    tasa observada— tiene que responder a ese parámetro, o el arnés no sirve
    para lo que se construyó.
    """
    rows = _hockey_rows()
    lo = walk_forward_backtest(rows, "nhl", "hockey", {"home_scoring_bonus": 0.0},
                               warmup=60, total_lines=(5.5,))
    hi = walk_forward_backtest(rows, "nhl", "hockey", {"home_scoring_bonus": 1.0},
                               warmup=60, total_lines=(5.5,))
    assert (hi["markets"]["totals@5.5"]["bias"]
            > lo["markets"]["totals@5.5"]["bias"] + 0.01)


def test_bias_is_mean_estimate_minus_observed_rate():
    out = walk_forward_backtest(_hockey_rows(), "nhl", "hockey", warmup=60,
                                total_lines=(5.5,), spread_lines=(-1.5,))
    for m in out["markets"].values():
        assert m["bias"] == pytest.approx(m["mean_probability"] - m["observed_rate"])
        assert 0.0 <= m["brier"] <= 1.0
