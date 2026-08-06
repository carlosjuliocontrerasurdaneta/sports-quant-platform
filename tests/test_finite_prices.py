"""Invariante de valor finito (auditoria 2026-08-05, F-01/F-02, causa raiz RC-1).

Toda comparacion con NaN es False, asi que los guards escritos como
`price <= 1.0`, `p >= 1` o `s <= 0` dejaban pasar los valores no finitos. El
efecto medido: un solo precio NaN anulaba las probabilidades justas del MERCADO
COMPLETO y el evento desaparecia de los picks en silencio, con el unico aviso
apuntando al sintoma equivocado ("power de-vig found no root").

Estas pruebas fijan el contrato en los cuatro puntos donde el patron aparecia.
"""
from __future__ import annotations

import logging

import pandas as pd
import pytest

from sqp.audit.clv import clv_segments
from sqp.domain.models import Event, EventOdds, MarketLine
from sqp.markets.odds import is_usable_price
from sqp.markets.vig import remove_vig_power, remove_vig_proportional
from sqp.pipeline.probabilities import (_consensus_counts, _consensus_lines,
                                        _novig_probs)
from sqp.risk.clv_gate import gate_decisions

NAN, INF = float("nan"), float("inf")


def _odds(*prices: tuple[str, float | None]) -> EventOdds:
    ev = Event(event_id="e1", sport_key="s", league="test", home="A", away="B",
               start_time="2026-07-01T23:00:00Z", data_label="real")
    lines = [MarketLine(market="h2h", bookmaker=f"bk{i}", outcome=outcome,
                        price_decimal=price, point=None)
             for i, (outcome, price) in enumerate(prices)]
    return EventOdds(event=ev, lines=lines)


# --- el predicado compartido -------------------------------------------------

@pytest.mark.parametrize("bad", [None, NAN, INF, -INF, 1.0, 0.0, -2.0])
def test_is_usable_price_rejects_non_finite_and_degenerate(bad):
    assert is_usable_price(bad) is False


@pytest.mark.parametrize("good", [1.01, 1.9, 2.0, 50.0])
def test_is_usable_price_accepts_real_quotes(good):
    assert is_usable_price(good) is True


# --- consenso y conteo de casas ----------------------------------------------

def test_consensus_drops_non_finite_price(caplog):
    caplog.set_level(logging.WARNING, logger="sqp.probabilities")
    cons = _consensus_lines(_odds(("A", NAN), ("A", 1.90), ("B", 2.10)))
    assert cons[("h2h", "A", None)] == 1.90      # el NaN no arrastra la mediana
    assert all(pd.notna(v) for v in cons.values())


def test_consensus_logs_the_discard_instead_of_losing_it_silently(caplog):
    # El defecto no era solo el NaN: era que nadie se enteraba (F-01).
    caplog.set_level(logging.WARNING, logger="sqp.probabilities")
    _consensus_lines(_odds(("A", NAN), ("A", 1.90), ("B", 2.10)))
    msgs = [r.getMessage() for r in caplog.records if r.name == "sqp.probabilities"]
    assert msgs and "no finito" in msgs[0]


def test_books_count_ignores_lines_the_consensus_discarded():
    # COR-03: _consensus_counts contaba TODA linea, incluidas las que
    # _consensus_lines habia descartado, asi que books_count inflado desactivaba
    # la penalizacion por mercado fino.
    eo = _odds(("A", NAN), ("A", 1.0), ("A", 1.90), ("B", 2.10))
    assert _consensus_counts(eo)[("h2h", "A", None)] == 1


# --- de-vig ------------------------------------------------------------------

def test_novig_returns_incomplete_market_when_a_price_is_non_finite():
    # Degrada al camino ya existente y probado (mercado incompleto -> {}),
    # en vez de propagar NaN a todo el mercado.
    assert _novig_probs({("h2h", "A", None): NAN,
                         ("h2h", "B", None): 2.10}, "h2h") == {}


@pytest.mark.parametrize("bad", [[NAN, 0.5], [INF, 0.5], [0.5, NAN]])
def test_remove_vig_rejects_non_finite_explicitly(bad):
    # Defensa en profundidad: con el consenso filtrando en origen esto no
    # deberia alcanzarse nunca; si se alcanza, tiene que ser ruidoso.
    with pytest.raises(ValueError):
        remove_vig_power(bad)
    with pytest.raises(ValueError):
        remove_vig_proportional(bad)


def test_remove_vig_power_still_works_on_normal_markets():
    out = remove_vig_power([0.55, 0.50])
    assert abs(sum(out) - 1.0) < 1e-9 and all(0.0 < p < 1.0 for p in out)


# --- CLV: n y mediana del gate ------------------------------------------------

def test_clv_segments_n_counts_only_informative_rows():
    # F-02: n usaba size, que CUENTA los NaN que median/mean saltan, asi que el
    # n>=30 del gate se satisfacia con filas que no aportan informacion.
    df = pd.DataFrame([
        {"league": "mlb", "market": "h2h", "clv_pct": 0.01, "beat_close": True},
        {"league": "mlb", "market": "h2h", "clv_pct": NAN, "beat_close": False},
        {"league": "mlb", "market": "h2h", "clv_pct": 0.03, "beat_close": True},
    ])
    seg = clv_segments(df, ["league", "market"])
    assert int(seg.iloc[0]["n"]) == 2


def test_gate_rejects_non_finite_median():
    # F-02: pandas NO ignora inf en median (a diferencia de NaN), asi que una
    # sola fila inf llevaba la mediana a inf, e inf > 0 es True: un precio
    # corrupto podia APROBAR un mercado para stake real.
    seg = pd.DataFrame([{"league": "mlb", "market": "totals",
                         "n": 30, "median_clv_pct": INF}])
    assert bool(gate_decisions(seg).iloc[0]["allowed"]) is False


def test_gate_still_approves_a_legitimate_market():
    # Premisa: el guard no puede cerrar el gate para todo el mundo.
    seg = pd.DataFrame([{"league": "mlb", "market": "totals",
                         "n": 30, "median_clv_pct": 0.01}])
    assert bool(gate_decisions(seg).iloc[0]["allowed"]) is True
