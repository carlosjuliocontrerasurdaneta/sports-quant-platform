"""Fallback de liquidación del stream servido desde el histórico (M-01,
auditoría 2026-08-02): las filas servidas más viejas que la ventana de 3 días
del feed de scores no pueden graduarse nunca desde The Odds API; el fallback
las gradúa contra data/historical/ (ResultsStore) por nombres normalizados
ORDENADOS + fecha (±1 día)."""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

import sqp.settlement.runner as runner
from sqp.storage.results_store import ResultsStore
from sqp.storage.served_store import ServedStore


def _served_row(**kw):
    base = dict(league="wnba", event_id="ev1", home="Las Vegas Aces",
                away="Chicago Sky", start_time="2026-07-20T23:00:00Z",
                game_date="2026-07-20", market="h2h",
                selection="Las Vegas Aces", line="", price_decimal=1.5,
                bookmaker="test", model_probability=0.6,
                estimated_probability=0.6, calibrated_probability=0.6,
                implied_probability_novig=0.55, estimated_edge=0.05,
                books_count=3, stake=0.0, data_label="real", flags="",
                generated_at="2026-07-20T15:00:00+00:00")
    base.update(kw)
    return base


def _result(date="2026-07-20", home="Las Vegas Aces", away="Chicago Sky",
            hs=80, as_=70, game_id="g1"):
    return {"date": date, "home": home, "away": away, "game_id": game_id,
            "home_score": hs, "away_score": as_, "neutral": False,
            "ingested_at": "2026-07-21T00:00:00Z"}


# ---------------------------------------------------------------------------
# history_scores_map: matching ordenado por nombres + fecha
# ---------------------------------------------------------------------------

def test_history_scores_map_matches_ordered_names_and_date():
    pending = pd.DataFrame([_served_row()])
    scores = runner.history_scores_map(pending, [_result()])
    assert scores == {"ev1": (80, 70, "Las Vegas Aces")}


def test_history_scores_map_normalizes_divergent_spellings():
    pending = pd.DataFrame([_served_row(home="Las Vegas Aces",
                                        away="Chicago Sky")])
    # Vendor histórico escribe distinto (mayúsculas/acentos): normaliza igual.
    scores = runner.history_scores_map(
        pending, [_result(home="LAS VEGAS ACES", away="chicago sky")])
    assert scores == {"ev1": (80, 70, "Las Vegas Aces")}


def test_history_scores_map_swapped_home_away_does_not_match():
    # El match es ORDENADO: local/visitante decide lados de h2h y spreads.
    pending = pd.DataFrame([_served_row(home="Chicago Sky",
                                        away="Las Vegas Aces")])
    assert runner.history_scores_map(pending, [_result()]) == {}


def test_history_scores_map_respects_date_tolerance():
    pending = pd.DataFrame([_served_row(game_date="2026-07-22",
                                        start_time="2026-07-22T23:00:00Z")])
    assert runner.history_scores_map(pending, [_result(date="2026-07-20")]) == {}
    scores = runner.history_scores_map(pending, [_result(date="2026-07-21")])
    assert scores["ev1"] == (80, 70, "Las Vegas Aces")


def test_history_scores_map_ambiguous_doubleheader_is_skipped():
    # Dos juegos mismo día mismos equipos (doubleheader MLB) con marcadores
    # distintos: graduar con el marcador equivocado corrompería la evidencia,
    # así que la ambigüedad NO gradúa.
    pending = pd.DataFrame([_served_row()])
    results = [_result(hs=80, as_=70, game_id="g1"),
               _result(hs=1, as_=2, game_id="g2")]
    assert runner.history_scores_map(pending, results) == {}


# ---------------------------------------------------------------------------
# Integración: fetch_and_settle gradúa desde el histórico lo que el feed no pudo
# ---------------------------------------------------------------------------

class _EmptyScoresClient:
    def fetch_scores(self, sport_key, days_from=2):
        return []  # el feed diario ya no lista el partido (>3 días)


# Reloj fijo: el partido (07-20) queda FUERA de la ventana de 3 días del feed
# pero DENTRO del corte de 7 días de pending(). Nunca depender del reloj real.
_FIXED_NOW = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)


def _freeze_served_clock(monkeypatch):
    class _Now(datetime):
        @classmethod
        def now(cls, tz=None):
            return _FIXED_NOW

    monkeypatch.setattr("sqp.storage.served_store.datetime", _Now)
    monkeypatch.setattr(runner, "datetime", _Now)


def test_fetch_and_settle_grades_expired_served_from_history(tmp_path, monkeypatch):
    from sqp.config import Settings

    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _freeze_served_clock(monkeypatch)
    store = ServedStore(tmp_path)
    store.append_served("wnba", [_served_row()])
    ResultsStore(tmp_path).upsert("wnba", [_result()])

    settled = runner.fetch_and_settle("wnba", Settings.load(),
                                      client=_EmptyScoresClient())
    assert settled.empty  # sin candidates: ningún pick real liquidado
    graded = pd.read_csv(store.graded_path("wnba"))
    assert len(graded) == 1
    assert graded.loc[0, "result"] == "win"   # moneyline del local, ganó local
    assert graded.loc[0, "pnl"] == 0.0        # fila de calibración stake-0
    assert store.pending("wnba", now=_FIXED_NOW).empty


def test_history_fallback_missing_results_file_leaves_pending_until_stale(tmp_path, monkeypatch):
    from sqp.config import Settings

    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _freeze_served_clock(monkeypatch)
    store = ServedStore(tmp_path)
    # 1 día de antigüedad respecto del reloj congelado: aún no es stale.
    store.append_served("wnba", [_served_row(
        start_time="2026-07-24T23:00:00Z", game_date="2026-07-24")])
    settled = runner.fetch_and_settle("wnba", Settings.load(),
                                      client=_EmptyScoresClient())
    assert settled.empty
    # Sigue pendiente, sin excepción y sin void prematuro.
    assert len(store.pending("wnba", now=_FIXED_NOW)) == 1


# ---------------------------------------------------------------------------
# Void de filas servidas rancias (política stale_void de candidates, 2026-07-12)
# ---------------------------------------------------------------------------

def test_void_stale_served_voids_ungradable_old_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _freeze_served_clock(monkeypatch)
    store = ServedStore(tmp_path)
    # 5 días sin resultado graduable (pospuesto o sin vendor): void.
    store.append_served("mlb", [_served_row(league="mlb")])
    n = runner._void_stale_served("mlb", now=_FIXED_NOW)
    assert n == 1
    graded = pd.read_csv(store.graded_path("mlb"))
    assert graded.loc[0, "result"] == "void"
    assert graded.loc[0, "pnl"] == 0.0
    assert "stale_void" in str(graded.loc[0, "flags"])
    assert store.pending("mlb", now=_FIXED_NOW).empty


def test_void_stale_served_keeps_fresh_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _freeze_served_clock(monkeypatch)
    store = ServedStore(tmp_path)
    store.append_served("mlb", [_served_row(
        league="mlb", start_time="2026-07-24T23:00:00Z", game_date="2026-07-24")])
    assert runner._void_stale_served("mlb", now=_FIXED_NOW) == 0
    assert len(store.pending("mlb", now=_FIXED_NOW)) == 1


def test_gradable_row_is_graded_not_voided(tmp_path, monkeypatch):
    from sqp.config import Settings

    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _freeze_served_clock(monkeypatch)
    store = ServedStore(tmp_path)
    store.append_served("wnba", [_served_row()])
    ResultsStore(tmp_path).upsert("wnba", [_result()])
    runner.fetch_and_settle("wnba", Settings.load(), client=_EmptyScoresClient())
    graded = pd.read_csv(store.graded_path("wnba"))
    # El fallback histórico gradúa ANTES de que el void toque la fila.
    assert list(graded["result"]) == ["win"]
