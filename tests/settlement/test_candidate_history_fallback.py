"""Liquidacion de candidatos de equipo fuera de la ventana del feed (ronda
audit-2026-09-23).

- AUD-003 (OPENAI-003 + CLAUDE-002 b): BLOQUEADO. Un fallback contra
  data/historical/ por (local, visitante) +-1 dia se implemento y la revision
  Fable lo tumbo: en una serie MLB el pick de HOY, sin jugar, se liquidaba con
  el marcador de AYER, de forma irreversible (FABLE-001). Estos tests fijan que
  NO se gradua un candidato desde el historico mientras la identidad entre
  proveedores siga sin decidir.
- AUD-004 (CLAUDE-002 a): un pick desplazado (`superseded`) no tenia
  `start_time` -- se buscaba solo en el `predictions` vigente --, asi que nunca
  expiraba y a los 14 dias salia del escaneo sin veredicto.
- AUD-012 (CLAUDE-004): un segundo run el mismo dia pisaba la copia de archivo
  del primero al archivarse al dia siguiente.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from sqp.config import Settings
from sqp.pipeline.daily import _archive_existing
from sqp.settlement import runner
from sqp.settlement.runner import (SUPERSEDED_FLAG, fetch_and_settle,
                                   superseded_candidates)
from sqp.storage.results_store import ResultsStore

LEAGUE = "mlb"
NOW = datetime.now(timezone.utc)
GAME = NOW - timedelta(days=5)          # fuera de la ventana del feed (3 dias)
GEN = GAME - timedelta(days=1)          # el pick se publico el dia anterior
ISO = "%Y-%m-%dT%H:%M:%SZ"


def _cand(event_id, *, selection="Home Team", stake=100.0):
    return {"event_id": event_id, "league": LEAGUE, "market": "h2h",
            "selection": selection, "line": float("nan"), "price_decimal": 2.0,
            "stake": stake, "data_label": "real", "flags": "",
            "home": "Home Team", "away": "Away Team",
            "generated_at": GEN.strftime("%Y-%m-%dT%H:%M:%S+00:00")}


def _pred(event_id, start=GAME):
    return {"event_id": event_id, "home": "Home Team", "away": "Away Team",
            "start_time": start.strftime(ISO)}


def _write(root, *, current_cands, current_preds, archived_cands=(),
           archived_preds=()):
    pred_dir = root / "data" / "predictions"
    (pred_dir / "archive").mkdir(parents=True)
    pd.DataFrame(list(current_cands), columns=list(_cand("x"))).to_csv(
        pred_dir / f"candidates_{LEAGUE}.csv", index=False)
    pd.DataFrame(list(current_preds), columns=list(_pred("x"))).to_csv(
        pred_dir / f"predictions_{LEAGUE}.csv", index=False)
    day = GEN.strftime("%Y-%m-%d")
    if archived_cands:
        pd.DataFrame(list(archived_cands)).to_csv(
            pred_dir / "archive" / f"candidates_{LEAGUE}_{day}.csv", index=False)
    if archived_preds:
        pd.DataFrame(list(archived_preds)).to_csv(
            pred_dir / "archive" / f"predictions_{LEAGUE}_{day}.csv", index=False)
    return pred_dir


class _HealthyFeed:
    """Feed sano (scores_trusted) que NO lista el partido del pick: solo otro,
    reciente. Es el caso normal pasados 3 dias."""

    def fetch_scores(self, sport_key, days_from=2):   # noqa: ARG002
        return [{"id": "otro", "completed": True, "home_team": "X",
                 "away_team": "Y", "commence_time": NOW.strftime(ISO),
                 "scores": [{"name": "X", "score": "1"},
                            {"name": "Y", "score": "0"}]}]


def _history(root, *results):
    ResultsStore(root).upsert(LEAGUE, [
        {"date": GAME.strftime("%Y-%m-%d"), "home": "Home Team",
         "away": "Away Team", "game_id": gid, "home_score": hs,
         "away_score": as_, "neutral": False,
         "ingested_at": NOW.strftime(ISO)} for gid, hs, as_ in results])


def _settle(root):
    return fetch_and_settle(LEAGUE, Settings(), days_from=2, client=_HealthyFeed())


# --- AUD-003 (bloqueado) / FABLE-001 -------------------------------------------


def test_un_pick_sin_jugar_no_se_liquida_con_el_partido_anterior_de_la_serie(
        tmp_path, monkeypatch):
    """FABLE-001 (CRITICAL, reproducido): serie MLB, el juego 1 (ayer) ya esta
    en el historico y el pick es del juego 2 (hoy, sin jugar). No puede salir
    liquidado -- y menos con el marcador de otro partido."""
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    hoy = NOW + timedelta(hours=10)
    _write(tmp_path, current_cands=[_cand("g2")],
           current_preds=[_pred("g2", start=hoy)])
    ResultsStore(tmp_path).upsert(LEAGUE, [
        {"date": (hoy - timedelta(days=1)).strftime("%Y-%m-%d"),
         "home": "Home Team", "away": "Away Team", "game_id": "g1",
         "home_score": 2, "away_score": 5, "neutral": False,
         "ingested_at": NOW.strftime(ISO)}])
    assert _settle(tmp_path).empty


def test_candidato_jugado_fuera_de_ventana_no_se_gradua_desde_el_historico(
        tmp_path, monkeypatch):
    """Mientras AUD-003 siga bloqueado, el historico no liquida candidatos: fuera
    de la ventana del feed rige la politica de expiracion de siempre."""
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _write(tmp_path, current_cands=[_cand("e1")], current_preds=[_pred("e1")])
    _history(tmp_path, ("g1", 70, 80))
    settled = _settle(tmp_path)
    assert settled.iloc[0]["result"] == "void"
    assert "stale_void" in str(settled.iloc[0]["flags"])
    assert _settle(tmp_path).empty


def test_sin_resultado_historico_se_mantiene_la_expiracion(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _write(tmp_path, current_cands=[_cand("e1")], current_preds=[_pred("e1")])
    settled = _settle(tmp_path)
    assert settled.iloc[0]["result"] == "void"
    assert float(settled.iloc[0]["pnl"]) == 0.0


# --- AUD-004 ------------------------------------------------------------------


def test_desplazado_sin_marcador_expira_como_uno_vigente(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    # e2 salio de la lista: solo esta en archive/, y el `predictions` vigente
    # ya no lo describe (el partido paso).
    _write(tmp_path, current_cands=[], current_preds=[],
           archived_cands=[_cand("e2")], archived_preds=[_pred("e2")])
    settled = _settle(tmp_path)
    assert settled["event_id"].tolist() == ["e2"]
    row = settled.iloc[0]
    assert row["result"] == "void"
    assert "stale_void" in str(row["flags"])
    assert SUPERSEDED_FLAG in str(row["flags"])
    assert _settle(tmp_path).empty


# --- AUD-012 ------------------------------------------------------------------


def test_dos_generaciones_del_mismo_dia_sobreviven_en_el_archivo(tmp_path):
    pred_dir = tmp_path / "data" / "predictions"
    pred_dir.mkdir(parents=True)
    path = pred_dir / f"candidates_{LEAGUE}.csv"
    t1 = NOW - timedelta(days=1, hours=3)
    t2 = t1 + timedelta(hours=2)            # mismo dia UTC, otro run

    def generacion(eid, ts):
        row = _cand(eid)
        row["generated_at"] = ts.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        pd.DataFrame([row]).to_csv(path, index=False)

    generacion("f1", t1)
    _archive_existing(path)                 # antes del run 2
    generacion("f2", t2)
    _archive_existing(path)                 # antes del run del dia siguiente
    _archive_existing(path)                 # idempotente: misma generacion
    archivos = sorted((pred_dir / "archive").glob(f"candidates_{LEAGUE}_*.csv"))
    assert len(archivos) == 2, [a.name for a in archivos]
    ids = set(pd.concat(pd.read_csv(a) for a in archivos)["event_id"])
    assert ids == {"f1", "f2"}
    # Y la liquidacion de desplazados los ve a los dos.
    out = superseded_candidates(LEAGUE, pd.DataFrame(), pred_dir=pred_dir, now=NOW)
    assert set(out["event_id"]) == {"f1", "f2"}
