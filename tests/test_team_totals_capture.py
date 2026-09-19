"""Fase 1 del pre-registro de derivados (2026-08-24): captura de team_totals.

Ancla las propiedades que el pre-registro exige y que un cambio descuidado
rompería sin que ningún otro test lo viera: la probabilidad del motor va
sellada por (equipo, lado, línea) con Over+Under = 1; solo líneas medias; el
tope de créditos corta ANTES de la llamada; solo eventos no comenzados; la
liquidación por carreras reales; y el devig por par Over/Under de cada casa.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from sqp.domain.models import Event, EventOdds, MarketLine
from sqp.pipeline import team_totals_capture as tt
from sqp.providers.odds_api import OddsAPIClient


def _eo(lines, event_id="ev1", start="2026-09-20T23:10:00Z"):
    ev = Event(event_id=event_id, sport_key="baseball_mlb", league="mlb",
               home="Home Nine", away="Away Nine", start_time=start)
    return EventOdds(event=ev, lines=lines)


def _tt(bookmaker, team, side, point, price):
    return MarketLine("team_totals", bookmaker, side, price, point, description=team)


def test_team_total_rows_sella_probabilidad_por_lado_y_solo_lineas_medias():
    eo = _eo([_tt("bk", "Home Nine", "Over", 4.5, 1.9), _tt("bk", "Home Nine", "Under", 4.5, 1.9),
              _tt("bk", "Away Nine", "Over", 4.0, 1.9),  # linea entera: push posible, se descarta
              MarketLine("totals", "bk", "Over", 1.9, 8.5)])  # otro mercado
    rows = tt.team_total_rows(eo, 4.8, 3.9, max_score=15, dispersion_k=None,
                              captured_at="2026-09-20T15:00:00+00:00")
    assert [(r["team"], r["side"], r["point"]) for r in rows] == [
        ("Home Nine", "over", 4.5), ("Home Nine", "under", 4.5)]
    assert rows[0]["model_probability"] + rows[1]["model_probability"] == pytest.approx(1.0)
    assert rows[0]["model_probability"] == pytest.approx(tt.tail_over(4.8, 4.5, 15, None))
    assert 0.0 < rows[0]["model_probability"] < 1.0


def test_parse_events_conserva_la_descripcion_del_equipo():
    client = OddsAPIClient.__new__(OddsAPIClient)  # _parse_events no usa estado
    raw = [{"id": "e1", "home_team": "H", "away_team": "A", "commence_time": "2026-09-20T23:10:00Z",
            "bookmakers": [{"key": "bk", "markets": [{"key": "team_totals", "outcomes": [
                {"name": "Over", "description": "H", "price": 1.9, "point": 4.5}]}]}]}]
    out = client._parse_events(raw, "baseball_mlb", "mlb")
    assert out[0].lines[0].description == "H" and out[0].lines[0].outcome == "Over"


class _Adapter:
    params = {"max_score": 15, "dispersion_k": None}

    def normalize(self, s):
        return (s or "").lower()

    def _rates(self, event):
        return 4.5, 4.0


class _Client:
    def __init__(self, events, cost=2, remaining=5000):
        self._events, self.cost = events, cost
        self.requests_remaining, self.requests_last = remaining, 0
        self.fetched: list[str] = []

    def list_events(self, sport_key):
        return self._events

    def fetch_event_odds(self, league_id, sport_key, event_id, markets):
        assert markets == "team_totals"
        self.fetched.append(event_id)
        self.requests_last = self.cost
        ev = next(e for e in self._events if e["id"] == event_id)
        return [_eo([_tt("bk", ev["home_team"], "Over", 4.5, 1.9),
                     _tt("bk", ev["home_team"], "Under", 4.5, 1.9)],
                    event_id=event_id, start=ev["commence_time"])]


@pytest.fixture
def entorno(monkeypatch, tmp_path):
    monkeypatch.setattr(tt, "_fit_adapter", lambda league, root: (_Adapter(), {"sport_key": "baseball_mlb"}))
    import sqp.pipeline.daily as daily
    monkeypatch.setattr(daily, "_attach_probable_pitchers", lambda *a, **k: None)
    return tmp_path


def _events(n, start="2026-09-20T23:10:00Z"):
    return [{"id": f"ev{i}", "home_team": f"H{i}", "away_team": f"A{i}", "commence_time": start}
            for i in range(n)]


def test_captura_respeta_el_tope_diario_antes_de_llamar(entorno):
    now = datetime(2026, 9, 20, 15, tzinfo=timezone.utc)
    client = _Client(_events(30), cost=2)
    s = tt.capture_team_totals(object(), league="mlb", client=client, root=entorno, now=now)
    # El guard corta cuando lo gastado YA alcanza el tope: 22 llamadas suman 44
    # (< 45), la 23a entra y deja 46, y ahi se para. Nunca mas de una llamada
    # por encima del tope, y el coste real lo dice el header, no el codigo.
    assert s["credits_spent"] == 46 and len(client.fetched) == 23
    assert s["stop"] and "tope" in s["stop"] and len(s["skipped"]) == 7
    assert tt.spent_today(entorno / "data" / "odds", "2026-09-20", tt.CREDITS_PREFIX) == 46
    # Una segunda pasada el mismo dia no gasta nada.
    s2 = tt.capture_team_totals(object(), league="mlb", client=_Client(_events(3)), root=entorno, now=now)
    assert s2["credits_spent"] == 0 and "agotado" in s2["stop"]


def test_captura_excluye_eventos_comenzados_y_fuera_de_horizonte(entorno):
    now = datetime(2026, 9, 20, 15, tzinfo=timezone.utc)
    events = (_events(1, "2026-09-20T14:00:00Z")  # ya comenzo
              + [{"id": "ok", "home_team": "H", "away_team": "A", "commence_time": "2026-09-20T23:10:00Z"}]
              + [{"id": "far", "home_team": "H", "away_team": "A", "commence_time": "2026-09-23T23:10:00Z"}])
    client = _Client(events)
    s = tt.capture_team_totals(object(), league="mlb", client=client, root=entorno, now=now)
    assert client.fetched == ["ok"] and s["events"] == 1 and s["rows"] == 2
    df = tt.load_captures(entorno, "mlb")
    assert list(df.columns) == tt.COLUMNS
    assert (pd.to_datetime(df["captured_at"]) < pd.to_datetime(df["commence_time"])).all()


def _cap(side, price, p, commence="2026-09-21T02:10:00Z", event_id="e"):
    return dict(captured_at="c", event_id=event_id, commence_time=commence, home="H", away="A",
                team="H", side=side, point=4.5, price_decimal=price, bookmaker="bk",
                model_probability=p, home_pitcher=None, away_pitcher=None)


def test_grade_y_consenso_liquidan_por_carreras_y_quitan_el_vig():
    caps = pd.DataFrame([_cap("over", 2.0, 0.55), _cap("under", 1.8, 0.45)])
    # Nocturno de la costa oeste: fecha UTC 09-21, fecha oficial (ET) 09-20. La
    # serie sigue el 09-21: la clave UTC habria graduado con el partido siguiente.
    results = [{"date": "2026-09-20", "home": "H", "away": "A", "home_score": 5, "away_score": 1},
               {"date": "2026-09-21", "home": "H", "away": "A", "home_score": 0, "away_score": 9}]
    g = tt.grade_captures(caps, results)
    assert list(g["result"]) == ["win", "loss"] and list(g["team_runs"]) == [5.0, 5.0]
    c = tt.consensus_novig(g)
    over = c[c["side"] == "over"].iloc[0]
    assert over["implied_probability_novig"] == pytest.approx((1 / 2.0) / (1 / 2.0 + 1 / 1.8))
    assert c["implied_probability_novig"].sum() == pytest.approx(1.0)


def test_grade_no_gradua_un_doubleheader_ni_sin_resultado():
    caps = pd.DataFrame([_cap("over", 2.0, 0.55, commence="2026-09-20T17:10:00Z", event_id="g1"),
                         _cap("over", 2.0, 0.55, commence="2026-09-20T23:10:00Z", event_id="g2"),
                         _cap("over", 2.0, 0.55, commence="2026-09-25T23:10:00Z", event_id="fut")])
    results = [{"date": "2026-09-20", "home": "H", "away": "A", "home_score": 5, "away_score": 1},
               {"date": "2026-09-20", "home": "H", "away": "A", "home_score": 2, "away_score": 3}]
    g = tt.grade_captures(caps, results)
    # Dos partidos con la misma clave y el evento no dice cual es: ninguno se
    # gradua, antes que asignar el resultado del otro partido.
    assert g["team_runs"].isna().all() and g["result"].isna().all()


def test_captura_salta_el_evento_que_comienza_durante_el_bucle(entorno):
    t0 = datetime(2026, 9, 20, 15, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 20, 15, 0, 5, tzinfo=timezone.utc)
    late = datetime(2026, 9, 20, 23, 30, tzinfo=timezone.utc)
    # Reloj: arranque, antes/despues de la peticion de `a`, antes de la de `b`.
    ticks = iter([t0, t0, t1, late])
    events = [{"id": "a", "home_team": "H", "away_team": "A", "commence_time": "2026-09-20T22:00:00Z"},
              {"id": "b", "home_team": "H2", "away_team": "A2", "commence_time": "2026-09-20T23:10:00Z"}]
    client = _Client(events)
    s = tt.capture_team_totals(object(), league="mlb", client=client, root=entorno,
                               clock=lambda: next(ticks))
    # `a` se pide a las 15:00; al llegar a `b` el reloj marca 23:30 y ya comenzo.
    assert client.fetched == ["a"] and s["skipped"] == ["b"] and s["events"] == 1
    df = tt.load_captures(entorno, "mlb")
    assert (pd.to_datetime(df["captured_at"]) < pd.to_datetime(df["commence_time"])).all()
    # `captured_at` es la hora de LLEGADA de la respuesta, no la de la peticion.
    assert df["captured_at"].unique().tolist() == [t1.isoformat(timespec="seconds")]


def test_captura_descarta_la_respuesta_que_llega_tras_el_comienzo(entorno):
    t0 = datetime(2026, 9, 20, 21, 59, tzinfo=timezone.utc)
    after = datetime(2026, 9, 20, 22, 0, 30, tzinfo=timezone.utc)
    ticks = iter([t0, t0, after])  # arranque, antes de pedir, al llegar la respuesta
    events = [{"id": "a", "home_team": "H", "away_team": "A", "commence_time": "2026-09-20T22:00:00Z"}]
    client = _Client(events, cost=2)
    s = tt.capture_team_totals(object(), league="mlb", client=client, root=entorno,
                               clock=lambda: next(ticks))
    # Se pidio antes del comienzo pero la respuesta llego despues: no se
    # persiste (podria ser el libro en vivo) y el credito gastado se cuenta.
    assert client.fetched == ["a"] and s["skipped"] == ["a"] and s["events"] == 0
    assert s["credits_spent"] == 2 and tt.load_captures(entorno, "mlb").empty


def test_captura_no_vuelve_a_persistir_una_respuesta_cacheada(entorno):
    now = datetime(2026, 9, 20, 15, tzinfo=timezone.utc)
    client = _Client(_events(1))
    client.last_response_cached = True
    s = tt.capture_team_totals(object(), league="mlb", client=client, root=entorno, now=now)
    assert s["events"] == 0 and s["rows"] == 0 and tt.load_captures(entorno, "mlb").empty


def test_consenso_conserva_una_captura_por_seleccion_la_primera():
    caps = pd.DataFrame([_cap("over", 2.0, 0.55), _cap("under", 1.8, 0.45)])
    later = caps.copy()
    later["captured_at"], later["price_decimal"] = "d", 1.5
    g = tt.grade_captures(pd.concat([later, caps], ignore_index=True), [])
    c = tt.consensus_novig(g)
    assert len(c) == 2 and set(c["captured_at"]) == {"c"}
    assert c.loc[c["side"] == "over", "price_median"].item() == 2.0
