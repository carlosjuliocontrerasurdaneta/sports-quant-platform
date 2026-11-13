"""Fiabilidad baja: el gate quita el STAKE, nunca la fila (defecto c, 2026-11-13).

Un evento con un equipo de < 10 partidos queda en `candidates` con stake 0 y el
flag `low_reliability`; NO entra al stream servido (protege las poblaciones de
pre-registros, gate y calibrador) y el cargador del calibrador lo excluye. Un
evento ya empezado se sigue descartando (precio in-play)."""
from __future__ import annotations

import dataclasses

import pandas as pd

from sqp.calibration.data import load_settled_training_history
from sqp.config import Settings
from sqp.pipeline import daily
from sqp.providers.synthetic import SyntheticProvider

LEAGUE = "nba"
WEAK_EVENT = "demo-nba-1"   # el evento demo con candidatos con el seed fijo (7)


class _FakeClient:
    last_response_cached = True

    def __init__(self, events):
        self._events = events

    def is_sport_active(self, sport_key):      # noqa: ARG002
        return True

    def fetch_odds(self, *a, **k):             # noqa: ARG002
        return self._events

    def fetch_scores(self, *a, **k):           # noqa: ARG002
        return []


def _arrange(tmp_path, monkeypatch, *, started: bool = False):
    sp = SyntheticProvider("basketball")
    kept = sp.fetch_results(LEAGUE)
    events = sp.fetch_odds(LEAGUE, three_way=False)
    if started:
        events = [dataclasses.replace(
            eo, event=dataclasses.replace(eo.event,
                                          start_time="2020-01-01T00:00:00+00:00"))
            if eo.event.event_id == "demo-nba-1" else eo for eo in events]
    # Un equipo con < 10 partidos hace que el adaptador devuelva el aviso real
    # ("Low-sample ratings ... <10 games"); se fuerza SOLO para este evento para
    # que el caso sea determinista (recortar el historial mueve los ratings y
    # con ellos que evento tiene candidatos).
    real_get = daily.get_adapter

    def _get(*a, **k):
        ad = real_get(*a, **k)
        orig = ad.reliability_warning
        ad.reliability_warning = lambda ev, *x, **y: (
            "Low-sample ratings for: Demo BK Team C (<10 games). Estimates unreliable."
            if ev.event_id == WEAK_EVENT else orig(ev, *x, **y))
        return ad

    monkeypatch.setattr(daily, "get_adapter", _get)
    monkeypatch.setattr(daily, "ROOT", tmp_path)
    monkeypatch.setattr(daily, "OddsAPIClient", lambda *a, **k: _FakeClient(events))
    monkeypatch.setattr(daily, "_fetch_recent_scores", lambda *a, **k: [])

    class _RS:
        def __init__(self, root):
            pass

        def load(self, league):                # noqa: ARG002
            return kept

    monkeypatch.setattr(daily, "ResultsStore", _RS)
    (tmp_path / "data" / "bets").mkdir(parents=True)


def _settings(**over):
    s = Settings.load()
    s.pick_mode = "edge"
    s.shadow_mode = False
    s.clv_gate_enabled = False
    s.prediction_gate_enabled = False
    s.risk.max_plausible_edge = 10.0
    for k, v in over.items():
        setattr(s, k, v)
    return s


def _cands(root) -> pd.DataFrame:
    p = root / "data" / "predictions" / f"candidates_{LEAGUE}.csv"
    df = pd.read_csv(p) if p.exists() else pd.DataFrame()
    if not df.empty:
        df["flags"] = df["flags"].fillna("").astype(str)
    return df


def _served(root) -> pd.DataFrame:
    p = root / "data" / "calibration" / f"served_{LEAGUE}.csv"
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


def test_unreliable_event_kept_with_zero_stake_and_not_served(tmp_path, monkeypatch):
    _arrange(tmp_path, monkeypatch)
    daily.run_league(LEAGUE, _settings(), mode="live")
    c = _cands(tmp_path)
    weak = c[c["event_id"] == "demo-nba-1"]
    assert not weak.empty, "la fila con reliability_warning se descarto"
    assert (weak["stake"] == 0).all()
    assert weak["flags"].str.contains("low_reliability").all()
    s = _served(tmp_path)
    assert not s.empty
    assert "demo-nba-1" not in set(s["event_id"])
    # contraprueba: eventos fiables conservan su stake y no llevan el flag
    ok = c[c["event_id"] != "demo-nba-1"]
    assert (ok["stake"] > 0).any()
    assert not ok["flags"].str.contains("low_reliability").any()
    # invariante global
    assert (c.loc[c["flags"].str.contains("low_reliability"), "stake"] == 0).all()


def test_started_event_is_still_dropped(tmp_path, monkeypatch):
    _arrange(tmp_path, monkeypatch, started=True)
    daily.run_league(LEAGUE, _settings(), mode="live")
    assert "demo-nba-1" not in set(_cands(tmp_path).get("event_id", []))
    assert "demo-nba-1" not in set(_served(tmp_path).get("event_id", []))


def test_accuracy_mode_unreliable_has_zero_stake(tmp_path, monkeypatch):
    _arrange(tmp_path, monkeypatch)
    monkeypatch.setattr(daily, "_ev_ejecucion_no_positivo", lambda *a, **k: False)
    daily.run_league(LEAGUE, _settings(pick_mode="accuracy",
                                       accuracy_threshold=0.51), mode="live")
    c = _cands(tmp_path)
    weak = c[c["event_id"] == "demo-nba-1"]
    assert not weak.empty
    assert (weak["stake"] == 0).all()
    assert weak["flags"].str.contains("low_reliability").all()
    assert (c[~c["flags"].str.contains("low_reliability")]["stake"] > 0).any()


def test_zero_stake_flag_low_reliability_kwarg():
    f = daily._zero_stake_flag(False, False, False, low_reliability=True)
    assert f == "low_reliability"
    assert daily._zero_stake_flag(True, False, False,
                                  low_reliability=True) == "market_paused;low_reliability"
    assert daily._zero_stake_flag(False, False, False) is None


def test_calibration_loader_excludes_low_reliability(tmp_path):
    rows = []
    for i, fl in enumerate(["", "low_reliability", "market_paused;low_reliability"]):
        rows.append({"league": "nba", "event_id": f"e{i}", "market": "h2h",
                     "selection": "Home", "line": "", "game_date": "2026-10-01",
                     "generated_at": "2026-10-01T10:00:00+00:00",
                     "model_probability": 0.6, "result": "win", "flags": fl,
                     "stake": 0.0, "data_label": "real"})
    pd.DataFrame(rows).to_csv(tmp_path / "settled_nba.csv", index=False)
    df = load_settled_training_history(tmp_path)
    assert list(df["event_id"]) == ["e0"]


# ---- consumidores aguas abajo: las filas low_reliability no son picks colocados --
def _settled_rows(n, flags, result="loss"):
    return pd.DataFrame([{
        "league": "mlb", "market": "totals", "result": result,
        "estimated_probability": 0.7, "implied_probability_novig": 0.5,
        "price_decimal": 2.0, "game_date": "2026-07-10", "stake": 0.0,
        "pnl": 0.0, "flags": flags, "selection": "Over", "event_id": "e"}] * n)


def test_degradation_metrics_ignores_low_reliability_rows():
    from datetime import date
    from sqp.risk.degradation import degradation_metrics
    df = pd.concat([_settled_rows(5, "", "win"),
                    _settled_rows(30, "low_reliability;uncalibrated", "loss")],
                   ignore_index=True)
    m = degradation_metrics(df, window_days=30, today=date(2026, 7, 13))
    assert int(m["n"].iloc[0]) == 5


def test_rank_candidates_and_consolidated_hide_low_reliability():
    from sqp.audit.report import rank_candidates
    d = pd.DataFrame({
        "stake": [0.0, 10.0, 0.0], "estimated_edge": [0.1, 0.2, 0.3],
        "flags": ["low_reliability", "uncalibrated", "shadow_mode;low_reliability"]})
    assert list(rank_candidates(d)["estimated_edge"]) == [0.2]


def test_settlement_and_history_drop_low_reliability(tmp_path):
    from sqp.audit.report import drop_low_reliability, load_history
    bets = tmp_path / "bets"
    bets.mkdir()
    pred = tmp_path / "pred"
    pred.mkdir()
    df = _settled_rows(2, "low_reliability", "win")
    pd.concat([df, _settled_rows(1, "", "win").assign(event_id="ok")]).to_csv(
        bets / "settled_mlb.csv", index=False)
    assert len(drop_low_reliability(pd.read_csv(bets / "settled_mlb.csv"))) == 1
    h = load_history(pred, bets)
    assert "e" not in set(h.get("event_id", []))


def test_closing_capture_skips_low_reliability_events(tmp_path):
    from datetime import datetime, timedelta, timezone
    from sqp.pipeline.closing_capture import leagues_with_imminent_bets
    now = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)
    st = (now + timedelta(minutes=30)).isoformat()
    pd.DataFrame({"event_id": ["a", "b"], "flags": ["low_reliability", ""],
                  "stake": [0.0, 5.0]}).to_csv(tmp_path / "candidates_nba.csv",
                                               index=False)
    pd.DataFrame({"event_id": ["a", "b"], "start_time": [st, st]}).to_csv(
        tmp_path / "predictions_nba.csv", index=False)
    assert leagues_with_imminent_bets(tmp_path, now) == {"nba": ["b"]}
