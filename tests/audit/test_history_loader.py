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
    local_date = datetime.fromisoformat("2026-06-26T20:00:00+00:00").astimezone().date().isoformat()
    assert open_row["home"] == "LAD" and open_row["fecha"] == local_date and open_row["result"] == ""


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


def test_history_carries_tipster_tier_and_promised_prob(tmp_path):
    """El Historial filtra por tier A/B/C/NO BET: cada fila lleva el tier de
    `tipster_table` (la misma funcion de "Todos los Picks") y la probabilidad
    de decision, para comparar acierto observado con prometido."""
    bets = tmp_path / "bets"; bets.mkdir()
    preds = tmp_path / "pred"; preds.mkdir()
    base = {"market": "h2h", "line": None, "stake": 0.0, "pnl": 0.0,
            "generated_at": "2026-06-24T09:00:00Z", "home": "NYY", "away": "BOS",
            "game_date": "2026-06-24", "selection": "NYY"}
    _write_settled(bets, [
        # A: 25 casas, edge 0,05 pp, prob 0,60, EV 0,6*1,75-1 = 0,05
        {**base, "event_id": "a", "price_decimal": 1.75, "result": "win",
         "calibrated_probability": 0.60, "estimated_probability": 0.58,
         "implied_probability_novig": 0.55, "books_count": 25},
        # NO BET: EV negativo
        {**base, "event_id": "n", "price_decimal": 1.50, "result": "loss",
         "estimated_probability": 0.55, "implied_probability_novig": 0.64,
         "books_count": 25},
        # Sin probabilidad: no clasificable -> tier vacio, la fila se conserva
        {**base, "event_id": "x", "price_decimal": 2.0, "result": "loss",
         "books_count": 25},
    ])
    h = load_history(preds, bets, max_plausible_ev=0.075).set_index(
        pd.Series(["a", "n", "x"]))
    assert h.loc["a", "tier"] == "A"
    assert h.loc["a", "prob"] == 0.60          # calibrada, no la cruda
    assert h.loc["n", "tier"] == "NO BET"
    assert h.loc["x", "tier"] == ""
    assert len(h) == 3


def test_history_survives_tier_failure(tmp_path, monkeypatch):
    """El tier es best-effort: si la clasificacion falla, el historial sale
    entero con el tier vacio, en vez de tumbar el dashboard."""
    import sqp.evaluation.tipster as tipster

    def _falla(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(tipster, "tipster_table", _falla)
    bets = tmp_path / "bets"; bets.mkdir()
    preds = tmp_path / "pred"; preds.mkdir()
    _write_settled(bets, [{"event_id": "e1", "market": "h2h", "selection": "NYY",
                           "price_decimal": 1.9, "result": "win",
                           "estimated_probability": 0.6, "books_count": 25,
                           "home": "NYY", "away": "BOS", "game_date": "2026-06-24"}])
    h = load_history(preds, bets)
    assert len(h) == 1 and h.iloc[0]["tier"] == "" and h.iloc[0]["result"] == "win"


def test_history_collapses_repeated_pick_but_keeps_staked_bets(tmp_path):
    """Un pick servido en dos runs cuenta UNA vez (la fila del momento de
    decidir); una fila con stake > 0 nunca se descarta."""
    bets = tmp_path / "bets"; bets.mkdir()
    preds = tmp_path / "pred"; preds.mkdir()
    base = {"market": "h2h", "line": None, "home": "NYY", "away": "BOS",
            "game_date": "2026-06-24", "result": "win", "pnl": 0.0,
            "estimated_probability": 0.6, "books_count": 25}
    _write_settled(bets, [
        # Repetido a stake 0: se queda el primero servido (cuota 1.80)
        {**base, "event_id": "r", "selection": "NYY", "price_decimal": 1.85,
         "stake": 0.0, "generated_at": "2026-06-23T15:00:00+00:00"},
        {**base, "event_id": "r", "selection": "NYY", "price_decimal": 1.80,
         "stake": 0.0, "generated_at": "2026-06-22T15:00:00+00:00"},
        # Dos apuestas reales del mismo pick: se quedan las dos
        {**base, "event_id": "s", "selection": "NYY", "price_decimal": 1.9,
         "stake": 10.0, "pnl": 9.0, "generated_at": "2026-06-22T15:00:00+00:00"},
        {**base, "event_id": "s", "selection": "NYY", "price_decimal": 1.9,
         "stake": 5.0, "pnl": 4.5, "generated_at": "2026-06-23T15:00:00+00:00"},
        # Stake 0 de un pick que ya tiene apuesta real: sobra
        {**base, "event_id": "s", "selection": "NYY", "price_decimal": 1.9,
         "stake": 0.0, "generated_at": "2026-06-21T15:00:00+00:00"},
        # Otro lado del mismo evento: pick distinto, se queda
        {**base, "event_id": "r", "selection": "BOS", "price_decimal": 2.1,
         "stake": 0.0, "result": "loss", "generated_at": "2026-06-22T15:00:00+00:00"},
    ])
    h = load_history(preds, bets, max_plausible_ev=0.075)
    assert len(h) == 4
    r = h[(h["selection"] == "NYY") & (h["stake"] == 0.0)]
    assert len(r) == 1 and r.iloc[0]["price_decimal"] == 1.80
    assert sorted(h.loc[h["stake"] > 0, "stake"]) == [5.0, 10.0]
    assert h["pnl"].sum() == 13.5


def test_unique_settled_picks_edge_cases():
    """Casos limite de la revision Fable (2026-10-02): identidad incompleta no
    se colapsa, -0.0 y 0.0 son la misma linea, y un sello ilegible nunca se
    elige como el momento de decidir."""
    from sqp.audit.report import _unique_settled_picks
    base = {"market": "spreads", "selection": "A", "stake": 0.0}
    sin_id = pd.DataFrame([{**base, "event_id": None, "line": 1.5,
                            "generated_at": "2026-06-22T15:00:00+00:00"},
                           {**base, "event_id": None, "line": 1.5,
                            "generated_at": "2026-06-23T15:00:00+00:00"}])
    assert len(_unique_settled_picks(sin_id)) == 2
    cero = pd.DataFrame([{**base, "event_id": "e", "line": -0.0,
                          "generated_at": "2026-06-22T15:00:00+00:00"},
                         {**base, "event_id": "e", "line": 0.0,
                          "generated_at": "2026-06-23T15:00:00+00:00"}])
    assert len(_unique_settled_picks(cero)) == 1
    sello = pd.DataFrame([{**base, "event_id": "e", "line": 1.5,
                           "generated_at": "ilegible", "price_decimal": 9.0},
                          {**base, "event_id": "e", "line": 1.5,
                           "generated_at": "2026-06-23T15:00:00+00:00",
                           "price_decimal": 1.9}])
    out = _unique_settled_picks(sello)
    assert len(out) == 1 and out.iloc[0]["price_decimal"] == 1.9
