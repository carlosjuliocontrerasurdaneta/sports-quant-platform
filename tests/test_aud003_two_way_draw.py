"""AUD-003 (ronda audit-2026-10-15): en una liga de h2h a DOS vias (NHL y demas
ligas con ``three_way: False``) una casa europea que cotiza el 1X2 a tiempo
reglamentario (outcome "Draw") vende OTRO contrato: su Home/Away no paga en la
prorroga. Mezclarla en la mediana y de-vigear Home/Away/Draw como si fueran un
mercado daba Home+Away ~0,84 en modo dos vias.

Contrato fijado aqui:
- en ligas no three_way, la casa que cotiza Draw en h2h queda FUERA del grupo
  h2h del evento (todas sus lineas h2h), por igual en consenso, conteos,
  dispersion, precios de ejecucion y snapshot de revalidacion;
- sus totals/spreads no cambian;
- ``_novig_probs`` a dos vias exige exactamente {home, away}: si sobran claves
  devuelve {} (mercado incompleto, default-deny);
- futbol (three_way) no cambia.
"""
from __future__ import annotations

from datetime import datetime, timezone
from statistics import median

import pandas as pd
import pytest

from sqp.domain.models import Event, EventOdds, MarketLine
from sqp.pipeline.probabilities import (_consensus_counts, _consensus_lines,
                                        _consensus_spread, _execution_prices,
                                        _novig_probs)

HOME, AWAY = "Philadelphia Flyers", "Pittsburgh Penguins"


def _line(book: str, market: str, outcome: str, price: float,
          point: float | None = None) -> MarketLine:
    return MarketLine(market=market, outcome=outcome, point=point,
                      price_decimal=price, bookmaker=book)


def _eo(league: str, lines: list[MarketLine], sport_key: str = "icehockey_nhl") -> EventOdds:
    ev = Event(event_id="e1", sport_key=sport_key, league=league, home=HOME,
               away=AWAY, start_time="2026-10-20T23:00:00Z")
    return EventOdds(event=ev, lines=lines)


def _nhl_mixed() -> EventOdds:
    """Dos casas a dos vias + una casa a 1X2 reglamentario (con Draw)."""
    return _eo("nhl", [
        _line("draftkings", "h2h", HOME, 1.90),
        _line("draftkings", "h2h", AWAY, 1.95),
        _line("fanduel", "h2h", HOME, 1.86),
        _line("fanduel", "h2h", AWAY, 2.00),
        _line("eurobook", "h2h", HOME, 2.17),
        _line("eurobook", "h2h", AWAY, 2.61),
        _line("eurobook", "h2h", "Draw", 4.40),
        # Totals de la casa europea: otro mercado, NO se excluye.
        _line("draftkings", "totals", "Over", 1.91, 6.5),
        _line("draftkings", "totals", "Under", 1.91, 6.5),
        _line("eurobook", "totals", "Over", 1.95, 6.5),
        _line("eurobook", "totals", "Under", 1.87, 6.5),
    ])


# --- consenso -------------------------------------------------------------

@pytest.mark.parametrize("kwargs", [{}, {"three_way": False}])
def test_nhl_mixto_consenso_ignora_la_casa_a_tres_vias(kwargs):
    cons = _consensus_lines(_nhl_mixed(), **kwargs)
    assert ("h2h", "Draw", None) not in cons
    assert cons[("h2h", HOME, None)] == pytest.approx(median([1.90, 1.86]))
    assert cons[("h2h", AWAY, None)] == pytest.approx(median([1.95, 2.00]))
    # totals de la casa europea siguen dentro
    assert cons[("totals", "Over", 6.5)] == pytest.approx(median([1.91, 1.95]))
    assert cons[("totals", "Under", 6.5)] == pytest.approx(median([1.91, 1.87]))


def test_nhl_mixto_novig_suma_uno_con_dos_desenlaces():
    cons = _consensus_lines(_nhl_mixed())
    fair = _novig_probs(cons, "h2h", three_way=False)
    assert set(fair) == {HOME, AWAY}
    assert fair[HOME] + fair[AWAY] == pytest.approx(1.0, abs=1e-9)


def test_solo_dos_vias_sin_cambio():
    eo = _eo("nhl", [
        _line("draftkings", "h2h", HOME, 1.90),
        _line("draftkings", "h2h", AWAY, 1.95),
        _line("fanduel", "h2h", HOME, 1.86),
        _line("fanduel", "h2h", AWAY, 2.00),
        _line("betmgm", "h2h", HOME, 1.88),
        _line("betmgm", "h2h", AWAY, 1.97),
    ])
    cons = _consensus_lines(eo)
    assert cons == {("h2h", HOME, None): median([1.90, 1.86, 1.88]),
                    ("h2h", AWAY, None): median([1.95, 2.00, 1.97])}
    assert _consensus_counts(eo) == {("h2h", HOME, None): 3, ("h2h", AWAY, None): 3}
    fair = _novig_probs(cons, "h2h", three_way=False)
    assert fair[HOME] + fair[AWAY] == pytest.approx(1.0, abs=1e-9)


@pytest.mark.parametrize("kwargs", [{}, {"three_way": True}])
def test_futbol_three_way_sin_cambio(kwargs):
    """Liga 1X2: el Draw ES el mercado y ninguna casa se excluye, ni siquiera
    una que (anomalamente) solo cotiza Home/Away."""
    eo = _eo("epl", [
        _line("b1", "h2h", HOME, 2.10), _line("b1", "h2h", AWAY, 3.60),
        _line("b1", "h2h", "Draw", 3.30),
        _line("b2", "h2h", HOME, 2.05), _line("b2", "h2h", AWAY, 3.70),
        _line("b2", "h2h", "Draw", 3.40),
        _line("b3", "h2h", HOME, 2.20), _line("b3", "h2h", AWAY, 3.50),
    ], sport_key="soccer_epl")
    cons = _consensus_lines(eo, **kwargs)
    assert cons[("h2h", HOME, None)] == pytest.approx(median([2.10, 2.05, 2.20]))
    assert cons[("h2h", "Draw", None)] == pytest.approx(median([3.30, 3.40]))
    assert _consensus_counts(eo, **kwargs)[("h2h", HOME, None)] == 3
    fair = _novig_probs(cons, "h2h", three_way=True)
    assert set(fair) == {HOME, AWAY, "Draw"}
    assert sum(fair.values()) == pytest.approx(1.0, abs=1e-9)


# --- no-vig a dos vias: conjunto exacto -------------------------------------

def test_novig_dos_vias_con_tres_claves_es_mercado_incompleto():
    cons = {("h2h", HOME, None): 2.0, ("h2h", AWAY, None): 2.2,
            ("h2h", "Draw", None): 4.4}
    assert _novig_probs(cons, "h2h", three_way=False) == {}


def test_novig_dos_vias_exige_los_lados_del_evento():
    cons = {("h2h", HOME, None): 1.9, ("h2h", AWAY, None): 1.95}
    ok = _novig_probs(cons, "h2h", three_way=False, outcomes=(HOME, AWAY))
    assert set(ok) == {HOME, AWAY}
    assert _novig_probs(cons, "h2h", three_way=False,
                        outcomes=(HOME, "Otro equipo")) == {}


# --- conteos, dispersion y ejecucion ---------------------------------------

def test_conteos_no_cuentan_la_casa_excluida():
    counts = _consensus_counts(_nhl_mixed())
    assert counts[("h2h", HOME, None)] == 2
    assert counts[("h2h", AWAY, None)] == 2
    assert ("h2h", "Draw", None) not in counts
    assert counts[("totals", "Over", 6.5)] == 2


def test_dispersion_no_mezcla_la_casa_excluida():
    spread = _consensus_spread(_nhl_mixed())
    from statistics import stdev
    assert spread[("h2h", HOME, None)] == pytest.approx(stdev([1 / 1.90, 1 / 1.86]))
    assert ("h2h", "Draw", None) not in spread


def test_ejecucion_no_elige_precio_de_la_casa_excluida():
    eo = _nhl_mixed()
    cons = _consensus_lines(eo)
    px = _execution_prices(eo, cons, ["eurobook", "draftkings"], max_uplift=0.5)
    assert px[("h2h", HOME, None)] == (1.90, "draftkings")
    assert px[("h2h", AWAY, None)] == (1.95, "draftkings")
    # en totals la casa europea sigue siendo elegible
    assert px[("totals", "Over", 6.5)] == (1.95, "eurobook")


# --- snapshot de revalidacion ----------------------------------------------

pytestmark_reval = pytest.mark.usefixtures("isolated_pipeline_outputs")

NOW = datetime(2026, 7, 1, 20, 0, tzinfo=timezone.utc)
START_IN_WINDOW = "2026-07-01T21:00:00Z"
FRESH_CAPTURE = "2026-07-01T19:40:00Z"


@pytestmark_reval
def test_revalidacion_nhl_ignora_la_casa_a_tres_vias(tmp_path):
    from sqp.pipeline.revalidation import revalidate_candidates
    pred_dir = tmp_path / "data" / "predictions"
    odds_dir = tmp_path / "data" / "odds"
    pred_dir.mkdir(parents=True)
    odds_dir.mkdir(parents=True)
    pd.DataFrame([{"event_id": "e1", "market": "h2h", "selection": "A", "line": "",
                   "price_decimal": 2.0, "estimated_probability": 0.55,
                   "estimated_edge": 0.10, "adjusted_edge": 0.08, "stake": 5.0,
                   "kelly_stake_pct": 0.005, "flags": "",
                   "generated_at": "2026-07-01T15:00:00Z"}]
                 ).to_csv(pred_dir / "candidates_nhl.csv", index=False)
    pd.DataFrame([{"event_id": "e1", "home": "A", "away": "B",
                   "start_time": START_IN_WINDOW}]
                 ).to_csv(pred_dir / "predictions_nhl.csv", index=False)
    base = {"event_id": "e1", "commence_time": START_IN_WINDOW, "home": "A",
            "away": "B", "market": "h2h", "point": "",
            "captured_at": FRESH_CAPTURE}
    pd.DataFrame([
        {**base, "bookmaker": "dk", "outcome": "A", "price_decimal": 1.70},
        {**base, "bookmaker": "dk", "outcome": "B", "price_decimal": 2.20},
        {**base, "bookmaker": "fd", "outcome": "A", "price_decimal": 1.80},
        {**base, "bookmaker": "fd", "outcome": "B", "price_decimal": 2.10},
        {**base, "bookmaker": "eu", "outcome": "A", "price_decimal": 2.50},
        {**base, "bookmaker": "eu", "outcome": "B", "price_decimal": 2.90},
        {**base, "bookmaker": "eu", "outcome": "Draw", "price_decimal": 4.20},
    ]).to_csv(odds_dir / "odds_nhl_202607.csv", index=False)
    revalidate_candidates(pred_dir, tmp_path, min_edge=0.02, now=NOW)
    row = pd.read_csv(pred_dir / "candidates_nhl.csv").iloc[0]
    # mediana de dk y fd (1.70, 1.80) = 1.75; con la casa europea seria 1.80
    assert float(row["reval_price"]) == pytest.approx(1.75)
