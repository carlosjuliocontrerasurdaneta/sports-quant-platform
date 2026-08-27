from datetime import datetime

import pandas as pd
from sqp.audit.report import load_history, visible_history


def _write_settled(d, rows):
    pd.DataFrame(rows).to_csv(d / "settled_mlb.csv", index=False)


def _write_candidates(d, cand_rows, pred_rows):
    pd.DataFrame(cand_rows).to_csv(d / "candidates_mlb.csv", index=False)
    pd.DataFrame(pred_rows).to_csv(d / "predictions_mlb.csv", index=False)


def test_load_history_unions_closed_and_open(tmp_path):
    bets = tmp_path / "bets"; bets.mkdir()
    preds = tmp_path / "pred"; preds.mkdir()
    _write_settled(bets, [{"event_id": "e1", "market": "h2h", "selection": "NYY",
                           "line": 0.0, "price_decimal": 1.9, "stake": 10.0,
                           "result": "win", "pnl": 9.0, "generated_at": "2026-06-24T09:00:00Z",
                           "home": "NYY", "away": "BOS", "game_date": "2026-06-24"}])
    _write_candidates(preds,
        [{"event_id": "e2", "market": "totals", "selection": "Over", "line": 8.5,
          "price_decimal": 2.0, "stake": 5.0, "estimated_edge": 0.05}],
        [{"event_id": "e2", "home": "LAD", "away": "SF", "start_time": "2026-06-26T20:00:00Z"}])
    h = load_history(preds, bets)
    assert set(h["is_closed"]) == {True, False}
    closed = h[h["is_closed"]].iloc[0]
    assert closed["home"] == "NYY" and closed["fecha"] == "2026-06-24" and closed["result"] == "win"
    open_row = h[~h["is_closed"]].iloc[0]
    assert open_row["home"] == "LAD" and open_row["fecha"] == "2026-06-26" and open_row["result"] == ""


def test_open_picks_without_stake_still_appear(tmp_path):
    """Un gate quita el STAKE, nunca la fila. Con los 32 mercados bloqueados
    todos los candidatos van a stake 0, y filtrar por stake>0 dejaba el
    historial sin un solo pick abierto (64 candidatos -> 0 filas, 2026-08-27)."""
    bets = tmp_path / "bets"; bets.mkdir()
    preds = tmp_path / "pred"; preds.mkdir()
    _write_candidates(preds,
        [{"event_id": "e2", "market": "h2h", "selection": "LAD", "line": 0.0,
          "price_decimal": 2.0, "stake": 0.0, "estimated_edge": 0.05,
          "flags": "prediction_gate"}],
        [{"event_id": "e2", "home": "LAD", "away": "SF",
          "start_time": "2026-06-26T20:00:00Z"}])
    h = load_history(preds, bets)
    assert len(h) == 1
    assert h.iloc[0]["estado"] == "prediction_gate"


def test_open_pick_date_is_local_not_utc(tmp_path):
    """La fecha del partido es la LOCAL: un nocturno en EEUU empieza despues de
    las 00:00Z y en crudo aparecia como del dia siguiente."""
    bets = tmp_path / "bets"; bets.mkdir()
    preds = tmp_path / "pred"; preds.mkdir()
    start = "2026-06-27T02:00:00Z"
    _write_candidates(preds,
        [{"event_id": "e2", "market": "h2h", "selection": "LAD", "line": 0.0,
          "price_decimal": 2.0, "stake": 0.0, "estimated_edge": 0.05}],
        [{"event_id": "e2", "home": "LAD", "away": "SF", "start_time": start}])
    esperado = (datetime.fromisoformat(start.replace("Z", "+00:00"))
                .astimezone().date().isoformat())
    assert load_history(preds, bets).iloc[0]["fecha"] == esperado


def test_visible_history_hides_past_unclosed():
    df = pd.DataFrame([
        {"fecha": "2026-06-24", "is_closed": True, "result": "win"},   # closed past -> show
        {"fecha": "2026-06-20", "is_closed": False, "result": ""},     # open past -> HIDE
        {"fecha": "2026-06-26", "is_closed": False, "result": ""},     # open today -> show
    ])
    out = visible_history(df, today="2026-06-26")
    assert len(out) == 2
    assert "2026-06-20" not in set(out["fecha"])
