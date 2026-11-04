"""AUD-019: elementos malformados se omiten (con conteo) y los creditos de una
peticion pagada se descuentan aunque el parseo falle."""
from __future__ import annotations

from sqp.pipeline import closing_capture
from sqp.providers.odds_api import OddsAPIClient


def _ev(outcomes):
    return {"id": "e1", "home_team": "A", "away_team": "B",
            "commence_time": "2026-11-04T00:00:00Z",
            "bookmakers": [{"key": "bk", "markets": [
                {"key": "h2h", "outcomes": outcomes}]}]}


def test_outcome_sin_price_no_pierde_la_liga():
    c = OddsAPIClient("k")
    raw = [_ev([{"name": "A", "price": 1.9}, {"name": "B"},
                {"name": "C", "price": "abc"}]),
           {"id": "e2"},                                   # evento sin equipos
           _ev([{"name": "A", "price": 2.0}]) | {"id": "e3"}]
    out = c._parse_events(raw, "sport", "lg")
    assert [eo.event.event_id for eo in out] == ["e1", "e3"]
    assert len(out[0].lines) == 1 and out[0].lines[0].price_decimal == 1.9
    assert c.last_parse_skipped == 3          # 2 outcomes + 1 evento


def test_payload_sano_no_omite_nada():
    c = OddsAPIClient("k")
    assert len(c._parse_events([_ev([{"name": "A", "price": 1.9}])], "s", "lg")) == 1
    assert c.last_parse_skipped == 0


class _ClientePagaYFalla:
    requests_remaining = None
    requests_last = None

    def fetch_odds(self, league_id, sport_key, markets="h2h,spreads,totals"):
        self.requests_last = 15            # la API ya cobro la peticion
        raise KeyError("price")            # y el parseo revienta


class _Ajustes:
    odds_api_key = "dummy"
    regions = "us"


def test_closing_capture_descuenta_creditos_aunque_el_parseo_falle(tmp_path, monkeypatch):
    monkeypatch.setattr(closing_capture, "ROOT", tmp_path)
    monkeypatch.setattr(closing_capture, "leagues_with_imminent_bets",
                        lambda *a, **k: {"mlb": ["ev1"]})
    monkeypatch.setattr(closing_capture, "spent_today", lambda *a, **k: 0)
    gastos = []
    monkeypatch.setattr(closing_capture, "add_spent",
                        lambda d, day, n: gastos.append(n))
    s = closing_capture.capture_closing(tmp_path, settings=_Ajustes(),
                                        client=_ClientePagaYFalla(), odds_store=object())
    assert gastos == [15]
    assert s["credits_spent"] == 15
    assert "mlb" in s["failed_leagues"]
