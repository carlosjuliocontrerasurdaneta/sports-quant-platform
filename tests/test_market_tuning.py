"""Tuner de parámetros por su efecto en spreads y totals.

`tune_home_advantage` y `tune_dc_rho` puntúan log-loss del MONEYLINE, así que
ningún parámetro podía seleccionarse por lo que le hace al hándicap o al total.
Ese hueco dejó tres decisiones sin poder cerrarse (NHL `scoring_half_life_days`,
`home_scoring_bonus` de fútbol, y el arreglo del bonus a suma cero).

Reutiliza el gate rolling-origin existente: aquí solo cambia de qué serie de
pérdida se alimenta.
"""
import pytest
from sqp.backtesting.engine import walk_forward_backtest
from sqp.backtesting.tuning import tune_market_param


def _low_scoring_hockey(n: int = 400) -> list[dict]:
    """Partidos de total bajo y determinista: con línea 2.5 el Over nunca ocurre,
    así que un parámetro que infle el total solo puede empeorar."""
    pairs = (("A", "B"), ("C", "D"), ("A", "C"), ("B", "D"))
    rows = []
    for i in range(n):
        h, a = pairs[i % 4]
        rows.append({"date": f"2026-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
                     "home": h, "away": a,
                     "home_score": i % 2, "away_score": (i + 1) % 2})
    return rows


def test_harness_exposes_per_game_series_for_markets():
    """El tuner necesita la serie por partido, no solo el agregado: sin ella no
    se puede alimentar `rolling_origin_improvement`."""
    out = walk_forward_backtest(_low_scoring_hockey(), "nhl", "hockey", warmup=60,
                                total_lines=(2.5,))
    m = out["markets"]["totals@2.5"]
    assert len(m["probs"]) == m["n"]
    assert len(m["outcomes"]) == m["n"]
    assert set(m["outcomes"]) <= {0.0, 1.0}


def test_tuner_prefers_the_value_that_does_not_inflate_the_total():
    res = tune_market_param(_low_scoring_hockey(), "nhl", "hockey",
                            param="home_scoring_bonus", grid=(0.0, 0.5, 1.0),
                            market="totals", line=2.5, default_value=1.0,
                            warmup=60, min_eval=10, margin=0.0)
    assert res["best_value"] == 0.0
    assert res["accepted"] is True
    assert res["recommended_value"] == 0.0
    assert res["improvement"] > 0


def test_tuner_refuses_a_thin_sample():
    res = tune_market_param(_low_scoring_hockey(), "nhl", "hockey",
                            param="home_scoring_bonus", grid=(0.0, 1.0),
                            market="totals", line=2.5, default_value=1.0,
                            warmup=60, min_eval=10_000, margin=0.0)
    assert res["accepted"] is False
    assert "insufficient sample" in res["reason"]
    assert res["recommended_value"] == 1.0, "al rechazar debe devolver el default"


def test_tuner_refuses_an_improvement_below_the_margin():
    res = tune_market_param(_low_scoring_hockey(), "nhl", "hockey",
                            param="home_scoring_bonus", grid=(0.0, 1.0),
                            market="totals", line=2.5, default_value=1.0,
                            warmup=60, min_eval=10, margin=99.0)
    assert res["accepted"] is False
    assert res["recommended_value"] == 1.0


def test_tuner_reports_the_raw_argmin_even_when_it_rejects():
    """Misma disciplina que los tuners existentes: el argmin crudo SIEMPRE se
    informa, para que un rechazo sea auditable y no invisible."""
    res = tune_market_param(_low_scoring_hockey(), "nhl", "hockey",
                            param="home_scoring_bonus", grid=(0.0, 1.0),
                            market="totals", line=2.5, default_value=1.0,
                            warmup=60, min_eval=10_000, margin=0.0)
    assert res["best_value"] == 0.0
    assert res["accepted"] is False


def test_tuner_applies_the_margin_to_the_holdout_when_enabled():
    res = tune_market_param(_low_scoring_hockey(), "nhl", "hockey",
                            param="home_scoring_bonus", grid=(0.0, 0.5, 1.0),
                            market="totals", line=2.5, default_value=1.0,
                            warmup=60, min_eval=10, margin=0.0, n_splits=4)
    assert res["oos_improvement"] is not None
    assert "rolling-origin" in res["reason"]


def test_spreads_market_is_tunable_too():
    res = tune_market_param(_low_scoring_hockey(), "nhl", "hockey",
                            param="home_scoring_bonus", grid=(0.0, 1.0),
                            market="spreads", line=-1.5, default_value=0.0,
                            warmup=60, min_eval=10, margin=0.0)
    assert res["market_key"] == "spreads@-1.5"
    assert res["n_eval"] > 0


def test_unknown_market_fails_loudly():
    with pytest.raises(ValueError):
        tune_market_param(_low_scoring_hockey(), "nhl", "hockey",
                          param="home_scoring_bonus", grid=(0.0,),
                          market="moneyline", line=0.0, default_value=0.0)
