"""Paridad backtest <-> produccion (defecto a, 2026-11-13).

El backtest decide con la MISMA funcion que `daily` (`_decision_probability`,
calibracion apagada), pasa `three_way`/`outcomes` al no-vig, no apuesta en
eventos con `reliability_warning` (stake 0 en produccion) y publica en `parity`
lo que NO replica."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from sqp.backtesting import roi_engine
from sqp.backtesting.roi_engine import realized_roi_backtest
from sqp.config import RiskConfig
from sqp.domain.models import Event, EventOdds, MarketLine
from sqp.providers.synthetic import SyntheticProvider

# Golden calculado con roi_engine de HEAD (mezcla en linea) el 2026-11-13.
GOLDEN = {"n_events_matched": 132, "n_bets": 59, "staked": 883.17,
          "pnl": 13.63, "realized_roi": 0.0154}


def _fixture(n_per_day: int = 4):
    sp = SyntheticProvider("basketball")
    raw = sp.fetch_results("nba")
    results, odds = [], {}
    rng = np.random.default_rng(11)
    for i, r in enumerate(raw):
        day = (date(2026, 1, 1) + timedelta(days=i // n_per_day)).isoformat()
        row = {**r, "date": day, "home": str(r["home"]), "away": str(r["away"]),
               "game_id": str(i)}
        results.append(row)
        ph = float(np.clip(rng.normal(0.55, 0.12), 0.25, 0.8))
        over = 1.04 + float(rng.uniform(0.0, 0.10))
        odds[f"g{i}"] = EventOdds(
            event=Event(event_id=f"g{i}", sport_key="bt", league="nba",
                        home=row["home"], away=row["away"],
                        start_time=f"{day}T23:00:00Z", data_label="real"),
            lines=[MarketLine("h2h", "dk", row["home"], round(over / ph, 3), None),
                   MarketLine("h2h", "dk", row["away"], round(over / (1 - ph), 3), None)])
    return results, odds


def _run(warmup=60, risk=None):
    results, odds = _fixture()
    return realized_roi_backtest(results, odds, "nba", "basketball", None,
                                 risk or RiskConfig(), 1000.0, warmup=warmup)


def test_golden_with_reliable_teams_matches_head_numbers():
    out = _run()
    assert out["n_skipped_unreliable"] == 0
    for k, v in GOLDEN.items():
        assert out[k] == pytest.approx(v), k


def test_output_carries_parity_flags():
    out = _run()
    assert out["parity"] == {"calibration": False, "execution_price": False,
                             "paused_markets": False, "prediction_gate": False}


def test_backtest_uses_decision_probability_with_calibration_off(monkeypatch):
    seen = []
    real = roi_engine._decision_probability

    def spy(p, fair, shrink, league, market, settings):
        seen.append((league, market, settings.calibration_enabled))
        return real(p, fair, shrink, league, market, settings)

    monkeypatch.setattr(roi_engine, "_decision_probability", spy)
    _run()
    assert seen, "el backtest no paso por _decision_probability"
    assert all(en is False for _l, _m, en in seen)


def test_small_warmup_places_no_bets_on_unreliable_events():
    out = _run(warmup=2)
    assert out["n_skipped_unreliable"] > 0
    # Ninguna apuesta en un evento cuyos equipos tenian < 10 partidos previos:
    # con warmup=2 las primeras jornadas son todas poco fiables.
    settled = out["settled"]
    first_ids = {f"g{i}" for i in range(2, 12)}
    if not settled.empty:
        assert not set(settled["event_id"]) & first_ids
