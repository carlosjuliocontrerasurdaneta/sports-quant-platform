"""Paridad backtest<->produccion y determinismo (auditoria 2026-08-05, F-10/F-11).

F-10: el mapa (mercado, seleccion, punto) -> probabilidad estaba duplicado
literalmente en pipeline.daily y backtesting.roi_engine. Anadir un mercado o
cambiar un signo exigia dos ediciones coherentes; una sola producia un backtest
que evaluaba una politica DISTINTA de la desplegada, en silencio.

F-11: el emparejamiento resultado<->cuotas es codicioso con consumo, asi que el
reparto dependia del orden de entrada y el backtest no era reproducible.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from sqp.backtesting.roi_engine import realized_roi_backtest
from sqp.config import RiskConfig
from sqp.domain.models import Event, EventOdds, MarketLine
from sqp.pipeline.probabilities import build_model_map


@dataclass
class _Est:
    home_win_estimated_probability: float = 0.55
    away_win_estimated_probability: float = 0.45
    draw_estimated_probability: float | None = None
    home_cover_estimated_probability: float | None = None
    away_cover_estimated_probability: float | None = None
    over_estimated_probability: float | None = None
    under_estimated_probability: float | None = None


def _ev(home="A", away="B"):
    return Event(event_id="e1", sport_key="bt", league="test", home=home,
                 away=away, start_time="2026-06-01T23:00:00Z", data_label="real")


# --- F-10: un solo constructor del mapa --------------------------------------

def test_model_map_two_way_moneyline_only():
    mm = build_model_map(_Est(), _ev(), None, None)
    assert set(mm) == {("h2h", "A", None), ("h2h", "B", None)}


def test_model_map_includes_draw_when_the_adapter_estimates_one():
    mm = build_model_map(_Est(draw_estimated_probability=0.25), _ev(), None, None)
    assert mm[("h2h", "Draw", None)] == 0.25


def test_model_map_spreads_use_opposite_signs():
    # La convencion de signo es justo lo que la duplicacion ponia en riesgo.
    mm = build_model_map(_Est(home_cover_estimated_probability=0.6,
                              away_cover_estimated_probability=0.4),
                         _ev(), -1.5, None)
    assert mm[("spreads", "A", -1.5)] == 0.6
    assert mm[("spreads", "B", 1.5)] == 0.4


def test_model_map_totals_share_the_same_point():
    mm = build_model_map(_Est(over_estimated_probability=0.52,
                              under_estimated_probability=0.48),
                         _ev(), None, 8.5)
    assert mm[("totals", "Over", 8.5)] == 0.52
    assert mm[("totals", "Under", 8.5)] == 0.48


def test_model_map_skips_markets_without_a_line():
    # Sin punto seleccionado no hay mercado que puntuar, aunque el modelo opine.
    mm = build_model_map(_Est(home_cover_estimated_probability=0.6,
                              over_estimated_probability=0.5), _ev(), None, None)
    assert not any(k[0] in ("spreads", "totals") for k in mm)


def test_production_and_backtest_share_the_same_builder():
    # La garantia estructural: si alguien vuelve a copiar el bloque, este test
    # no lo detecta -- pero si alguien cambia el helper, ambos caminos cambian.
    from sqp.backtesting import roi_engine
    from sqp.pipeline import daily
    assert daily.build_model_map is build_model_map
    assert roi_engine.build_model_map is build_model_map


# --- F-11: el backtest no puede depender del orden de entrada ----------------

def _eo(eid, home, away, day):
    return EventOdds(
        event=Event(event_id=eid, sport_key="bt", league="test", home=home,
                    away=away, start_time=f"{day}T23:00:00Z", data_label="real"),
        lines=[MarketLine("h2h", "dk", home, 1.9, None),
               MarketLine("h2h", "dk", away, 2.1, None)])


def test_backtest_is_reproducible_under_input_reordering():
    # Serie de dias consecutivos con el MISMO par: el caso que hacia competir a
    # dos resultados por las mismas cuotas (I-4 de la auditoria 2026-07-24).
    results = [
        {"date": "2026-06-01", "home": "A", "away": "B", "home_score": 5,
         "away_score": 3, "neutral": False, "game_id": "1"},
        {"date": "2026-06-01", "home": "A", "away": "B", "home_score": 1,
         "away_score": 7, "neutral": False, "game_id": "2"},
        {"date": "2026-06-02", "home": "A", "away": "B", "home_score": 2,
         "away_score": 4, "neutral": False, "game_id": "3"},
    ]
    odds = {f"e{i}": _eo(f"e{i}", "A", "B", d) for i, d in
            enumerate(["2026-06-01", "2026-06-01", "2026-06-02"], start=1)}
    risk = RiskConfig()

    base = realized_roi_backtest(list(results), odds, "test", "baseball", None,
                                 risk, 1000.0, warmup=0)
    rng = random.Random(0)
    for _ in range(5):
        shuffled = list(results)
        rng.shuffle(shuffled)
        out = realized_roi_backtest(shuffled, odds, "test", "baseball", None,
                                    risk, 1000.0, warmup=0)
        assert out["n_events_matched"] == base["n_events_matched"]
        assert out["realized_roi"] == base["realized_roi"]
        assert out["n_bets"] == base["n_bets"]
