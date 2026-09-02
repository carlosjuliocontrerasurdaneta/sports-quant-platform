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


def test_production_and_backtest_share_the_adjustment_chain():
    """AUD-MED-006, garantia estructural (misma logica que la de F-10): daily y
    roi_engine deben usar EL MISMO objeto funcion para la capa de ajustes."""
    from sqp.backtesting import roi_engine
    from sqp.pipeline import daily, probabilities
    assert daily.adjust_model_probability is probabilities.adjust_model_probability
    assert roi_engine.adjust_model_probability is probabilities.adjust_model_probability
    assert daily.build_adjustment_context is probabilities.build_adjustment_context
    assert roi_engine.build_adjustment_context is probabilities.build_adjustment_context


def test_adjustment_chain_is_identity_when_all_coefficients_are_zero():
    """Con la configuracion por defecto (todos los coeficientes a 0) la cadena
    devuelve p_model intacta dentro de [0.01, 0.99]; fuera, aplica el MISMO
    clamp que produccion (daily siempre acoto _p_adj; el motor ROI antiguo no)."""
    from sqp.pipeline.probabilities import (adjust_model_probability,
                                            build_adjustment_context)
    results, _ = _adjustment_scenario()
    risk = RiskConfig()   # todos los coeficientes 0.0 por defecto
    ctx = build_adjustment_context("A", "B", "2026-06-10", results[:-1], risk)
    for p in (0.01, 0.3141592653589793, 0.57, 0.99):
        assert adjust_model_probability(p, "h2h", "A", None, "A", "B",
                                        ctx, risk) == p
    assert adjust_model_probability(0.999, "h2h", "A", None, "A", "B",
                                    ctx, risk) == 0.99
    assert adjust_model_probability(0.001, "h2h", "B", None, "A", "B",
                                    ctx, risk) == 0.01


def test_adjustment_chain_wires_each_coefficient_to_its_feature():
    """Cableado coeficiente->feature en un mercado de totals: el helper debe
    reproducir la suma manual de los terminos con las primitivas de rest_form
    (el oraculo independiente de la formula que daily aplicaba inline)."""
    from sqp.features.rest_form import (off_def_p_adjustment,
                                        over_under_rate_p_adjustment,
                                        team_avg_conceded, team_avg_scored,
                                        team_avg_total, team_over_rate,
                                        totals_tendency_p_adjustment)
    from sqp.pipeline.probabilities import (adjust_model_probability,
                                            build_adjustment_context)
    results, _ = _adjustment_scenario()
    prior = results[:-1]
    risk = RiskConfig(totals_tendency_coef=0.004, off_def_totals_coef=0.003,
                      over_under_rate_coef=0.02)
    ctx = build_adjustment_context("A", "B", "2026-06-10", prior, risk)
    line, p_model = 7.5, 0.5
    expected = p_model
    expected += totals_tendency_p_adjustment(
        "totals", "Over", team_avg_total("A", prior, risk.totals_tendency_n),
        team_avg_total("B", prior, risk.totals_tendency_n), line,
        risk.totals_tendency_coef)
    expected += off_def_p_adjustment(
        "totals", "Over", "A", "B",
        team_avg_scored("A", prior, risk.off_def_n),
        team_avg_conceded("A", prior, risk.off_def_n),
        team_avg_scored("B", prior, risk.off_def_n),
        team_avg_conceded("B", prior, risk.off_def_n),
        line, risk.off_def_h2h_coef, risk.off_def_totals_coef)
    expected += over_under_rate_p_adjustment(
        "totals", "Over",
        team_over_rate("A", prior, line, risk.over_under_rate_n),
        team_over_rate("B", prior, line, risk.over_under_rate_n),
        risk.over_under_rate_coef)
    expected = max(0.01, min(0.99, expected))
    got = adjust_model_probability(p_model, "totals", "Over", line,
                                   "A", "B", ctx, risk)
    assert abs(got - expected) < 1e-12
    assert got != p_model   # el escenario tiene senal: el test discrimina


# --- F-11: el backtest no puede depender del orden de entrada ----------------

def _eo(eid, home, away, day):
    return EventOdds(
        event=Event(event_id=eid, sport_key="bt", league="test", home=home,
                    away=away, start_time=f"{day}T23:00:00Z", data_label="real"),
        lines=[MarketLine("h2h", "dk", home, 1.9, None),
               MarketLine("h2h", "dk", away, 2.1, None)])


def _adjustment_scenario(extra_same_day: bool = False):
    """Historial sintetico con senal de racha: A llega +3, B llega -3.

    `extra_same_day` anade una victoria de A EL MISMO DIA del partido apostado
    (doble jornada). Esa fila puede alimentar el Elo walk-forward (orden de la
    lista), pero JAMAS las features de ajuste: en produccion las features solo
    ven partidos liquidados de dias ANTERIORES."""
    results = [
        {"date": "2026-06-01", "home": "A", "away": "CC", "home_score": 5,
         "away_score": 2, "neutral": False, "game_id": "a1"},
        {"date": "2026-06-01", "home": "DD", "away": "B", "home_score": 6,
         "away_score": 1, "neutral": False, "game_id": "b1"},
        {"date": "2026-06-02", "home": "A", "away": "CC", "home_score": 4,
         "away_score": 1, "neutral": False, "game_id": "a2"},
        {"date": "2026-06-02", "home": "DD", "away": "B", "home_score": 3,
         "away_score": 0, "neutral": False, "game_id": "b2"},
        {"date": "2026-06-03", "home": "A", "away": "CC", "home_score": 7,
         "away_score": 3, "neutral": False, "game_id": "a3"},
        {"date": "2026-06-03", "home": "DD", "away": "B", "home_score": 5,
         "away_score": 4, "neutral": False, "game_id": "b3"},
    ]
    if extra_same_day:
        # Ordena ANTES del partido apostado (("A","AZ") < ("A","B")): el Elo
        # walk-forward la observa, las features de ajuste no deben verla.
        results.append({"date": "2026-06-10", "home": "A", "away": "AZ",
                        "home_score": 9, "away_score": 0, "neutral": False,
                        "game_id": "same_day"})
    results.append({"date": "2026-06-10", "home": "A", "away": "B",
                    "home_score": 5, "away_score": 3, "neutral": False,
                    "game_id": "bet"})
    odds = {"e1": EventOdds(
        event=Event(event_id="e1", sport_key="bt", league="test", home="A",
                    away="B", start_time="2026-06-10T23:00:00Z", data_label="real"),
        lines=[MarketLine("h2h", "dk", "A", 2.05, None),
               MarketLine("h2h", "dk", "B", 1.95, None)])}
    return results, odds


def _expected_home_probability(results, streak_coef: float,
                               expected_streak_diff: float) -> float:
    """Oraculo independiente de la cadena de produccion (daily.py):
    p_decision = clamp(p_model + ajustes) con shrink=0 y sin calibrador.
    Replica el Elo walk-forward observando los partidos previos al apostado en
    el MISMO orden que el motor, y aplica la formula documentada del ajuste de
    racha (configs/default.yaml, rest_form.streak_p_adjustment)."""
    from sqp.sports.registry import get_adapter
    adapter = get_adapter("test", "baseball", None)
    ordered = sorted(results, key=lambda r: (str(r.get("date", "")),
                                             str(r.get("home", "")),
                                             str(r.get("away", "")),
                                             str(r.get("game_id", "")),
                                             str(r.get("home_score", "")),
                                             str(r.get("away_score", ""))))
    prior = ordered[:-1]           # todo menos el partido apostado (es el ultimo)
    for r in prior:
        adapter.observe(r)
    ev = Event(event_id="e1", sport_key="bt", league="test", home="A", away="B",
               start_time="2026-06-10T23:00:00Z", data_label="real",
               home_pitcher=None, away_pitcher=None)
    est = adapter.estimate(ev, None, None)
    p_model = est.home_win_estimated_probability
    adj = expected_streak_diff * streak_coef
    return max(0.01, min(0.99, p_model + adj))


def _backtest_home_probability(results, odds, risk) -> float:
    out = realized_roi_backtest(list(results), dict(odds), "test", "baseball",
                                None, risk, 1000.0, warmup=0)
    settled = out["settled"]
    row = settled[settled["selection"] == "A"]
    assert len(row) == 1, "el lado A debe llevar stake en este escenario"
    return float(row["estimated_probability"].iloc[0])


def test_roi_backtest_applies_the_production_adjustment_chain():
    """AUD-MED-006: con un coeficiente NO nulo (streak_coef=0.01, el valor que
    corrio en produccion del 2026-08-23 al 2026-09-01), el backtest debe
    aplicar la MISMA cadena de ajustes que daily antes del shrink. El motor
    antiguo usaba p_model crudo y este test fallaba."""
    results, odds = _adjustment_scenario()
    risk = RiskConfig(min_edge=0.0, market_shrink=0.0, max_plausible_edge=1.0,
                      streak_coef=0.01)
    # A en +3, B en -3 -> diff +6 -> ajuste +0.06 para el lado A.
    expected = _expected_home_probability(results, 0.01, expected_streak_diff=6.0)
    got = _backtest_home_probability(results, odds, risk)
    assert got == round(expected, 4)


def test_roi_backtest_adjustments_ignore_same_day_games():
    """Correccion temporal: las features de ajuste solo pueden usar partidos de
    fechas ESTRICTAMENTE anteriores. Una victoria de A el mismo dia (doble
    jornada) no puede subir la racha de +3 a +4."""
    results, odds = _adjustment_scenario(extra_same_day=True)
    risk = RiskConfig(min_edge=0.0, market_shrink=0.0, max_plausible_edge=1.0,
                      streak_coef=0.01)
    # El Elo walk-forward SI observa la fila del mismo dia (orden de la lista,
    # comportamiento preexistente del motor); las features NO: diff sigue +6.
    expected = _expected_home_probability(results, 0.01, expected_streak_diff=6.0)
    got = _backtest_home_probability(results, odds, risk)
    assert got == round(expected, 4)


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
