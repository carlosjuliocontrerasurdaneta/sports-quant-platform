"""Picks desplazados (AUD-MED-003, auditoria integral 2026-09-13).

El ledger `settled_*` solo graduaba la ultima vista de `candidates_<liga>.csv`.
Un pick publicado el dia D para un partido de D+k que no sobrevive al refresco
de D+1 desaparecia sin veredicto: 132 de 730 unidades (evento, mercado)
listadas entre el 2026-08-16 y el 2026-09-08 nunca entraron en settled_* pese
a que el stream servido las graduo. `superseded_candidates` recupera del
archivo la ULTIMA generacion de cada identidad ausente del fichero vigente, y
`fetch_and_settle` la gradua con flag `superseded`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from sqp.config import Settings
from sqp.settlement import runner
from sqp.settlement.runner import (SUPERSEDED_FLAG, fetch_and_settle,
                                   superseded_candidates)

LEAGUE = "mlb"
NOW = datetime.now(timezone.utc)
D0 = NOW - timedelta(days=3)      # generacion antigua
D1 = NOW - timedelta(days=2)      # generacion mas reciente del pick desplazado
GAME = NOW - timedelta(hours=6)   # partido ya jugado


def _row(event_id, selection, generated, *, stake=10.0, line=float("nan"),
         label="real", market="h2h"):
    return {"event_id": event_id, "league": LEAGUE, "market": market,
            "selection": selection, "line": line, "price_decimal": 2.0,
            "stake": stake, "data_label": label, "flags": "",
            "generated_at": generated.strftime("%Y-%m-%dT%H:%M:%S+00:00")}


def _write(root, *, current, archive):
    pred_dir = root / "data" / "predictions"
    (pred_dir / "archive").mkdir(parents=True)
    pd.DataFrame(current).to_csv(pred_dir / f"candidates_{LEAGUE}.csv", index=False)
    for day, rows in archive.items():
        pd.DataFrame(rows).to_csv(
            pred_dir / "archive" / f"candidates_{LEAGUE}_{day}.csv", index=False)
    pd.DataFrame([{"event_id": e, "home": "A", "away": "B",
                   "start_time": GAME.strftime("%Y-%m-%dT%H:%M:%SZ")}
                  for e in ("e1", "e2", "e3")]).to_csv(
        pred_dir / f"predictions_{LEAGUE}.csv", index=False)
    return pred_dir


class FakeClient:
    def __init__(self, payload):
        self.payload = payload

    def fetch_scores(self, sport_key, days_from=2):
        return self.payload


def _scores():
    return [{"id": e, "completed": True, "home_team": "A", "away_team": "B",
             "commence_time": GAME.strftime("%Y-%m-%dT%H:%M:%SZ"),
             "scores": [{"name": "A", "score": "3"}, {"name": "B", "score": "1"}]}
            for e in ("e1", "e2", "e3")]


def test_superseded_es_una_fila_por_identidad_con_la_ultima_generacion(tmp_path):
    current = [_row("e1", "A", D1)]                         # sigue vigente
    archive = {
        D0.strftime("%Y-%m-%d"): [_row("e1", "A", D0), _row("e2", "B", D0, stake=4.0)],
        D1.strftime("%Y-%m-%d"): [_row("e1", "A", D1), _row("e2", "B", D1, stake=6.0),
                                  _row("e3", "A", D1, label="demo_synthetic")],
    }
    pred_dir = _write(tmp_path, current=current, archive=archive)
    out = superseded_candidates(LEAGUE, pd.DataFrame(current), pred_dir=pred_dir, now=NOW)
    # e1 esta vigente -> fuera; e3 es demo -> fuera; e2 una sola vez, la de D1.
    assert out["event_id"].tolist() == ["e2"]
    assert float(out.iloc[0]["stake"]) == 6.0
    assert out.iloc[0]["generated_at"].startswith(D1.strftime("%Y-%m-%d"))
    assert out.iloc[0]["flags"] == SUPERSEDED_FLAG


def test_fuera_del_lookback_no_se_recupera(tmp_path):
    viejo = NOW - timedelta(days=40)
    pred_dir = _write(tmp_path, current=[],
                      archive={viejo.strftime("%Y-%m-%d"): [_row("e2", "B", viejo)]})
    assert superseded_candidates(LEAGUE, pd.DataFrame(), pred_dir=pred_dir, now=NOW).empty


def test_fetch_and_settle_gradua_el_pick_desplazado_y_es_idempotente(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    current = [_row("e1", "A", D1)]
    archive = {D0.strftime("%Y-%m-%d"): [_row("e1", "A", D0), _row("e2", "B", D0)]}
    _write(tmp_path, current=current, archive=archive)
    settled = fetch_and_settle(LEAGUE, Settings(), days_from=2,
                               client=FakeClient(_scores()))
    by_id = settled.set_index("event_id")
    assert set(by_id.index) == {"e1", "e2"}
    assert by_id.loc["e1", "result"] == "win" and SUPERSEDED_FLAG not in str(by_id.loc["e1", "flags"])
    assert by_id.loc["e2", "result"] == "loss"                 # B perdio 1-3
    assert SUPERSEDED_FLAG in str(by_id.loc["e2", "flags"])
    assert float(by_id.loc["e2", "pnl"]) == -10.0
    # Segunda pasada: nada nuevo (dedup por DEDUP_KEY, generated_at incluido).
    again = fetch_and_settle(LEAGUE, Settings(), days_from=2,
                             client=FakeClient(_scores()))
    assert again.empty
    ledger = pd.read_csv(tmp_path / "data" / "bets" / f"settled_{LEAGUE}.csv")
    assert len(ledger) == 2


def test_sin_fichero_vigente_los_desplazados_se_liquidan_igual(tmp_path, monkeypatch):
    """Una liga cuyo run no produjo candidatos (fichero borrado por _finalize)
    sigue teniendo picks archivados que liquidar."""
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _write(tmp_path, current=[], archive={D0.strftime("%Y-%m-%d"): [_row("e2", "A", D0)]})
    (tmp_path / "data" / "predictions" / f"candidates_{LEAGUE}.csv").unlink()
    settled = fetch_and_settle(LEAGUE, Settings(), days_from=2,
                               client=FakeClient(_scores()))
    assert settled["event_id"].tolist() == ["e2"]
    assert settled.iloc[0]["result"] == "win"
