"""Observatorio de edge intradia: medicion pura, sin picks ni stakes.

En cada pase de captura re-evalua el edge de las probabilidades SERVIDAS a las
11:00 (stream served_*, misma probabilidad de decision del pipeline) contra el
consenso del snapshot fresco, y lo appendea a data/bets/intraday_edge_log.csv.
El dataset resultante decide con evidencia la fase ofensiva de la generacion
intradia (#4): si los edges que aparecen durante el dia tienen CLV positivo o
son seleccion adversa. Solo h2h en v1; nunca crea candidates ni toca stakes.
"""
from datetime import datetime, timezone

import pandas as pd

from sqp.config import Settings
from sqp.pipeline.intraday_scan import INTRADAY_LOG_FILENAME, log_intraday_edges

NOW = datetime(2026, 6, 26, 22, 0, tzinfo=timezone.utc)
TODAY = "2026-06-26"


def _served(eid, sel, prob, price, market="h2h", generated=f"{TODAY}T15:00:00",
            start=f"{TODAY}T23:00:00Z"):
    return {"league": "mlb", "event_id": eid, "home": "NYY", "away": "BOS",
            "start_time": start, "game_date": TODAY,
            "market": market, "selection": sel, "line": None,
            "price_decimal": price, "bookmaker": "consensus_median",
            "model_probability": prob, "estimated_probability": prob,
            "calibrated_probability": prob, "implied_probability_novig": 0.5,
            "estimated_edge": round(prob * price - 1.0, 4), "books_count": 5,
            "stake": 0.0, "data_label": "real", "flags": "served_stream",
            "generated_at": generated}


def _snap_row(eid, sel, price, captured_at):
    return {"event_id": eid, "market": "h2h", "outcome": sel, "point": None,
            "price_decimal": price, "bookmaker": "bk", "captured_at": captured_at}


def _seed(root, preds, served_rows, snap_rows, cand_rows=None,
          start_time=f"{TODAY}T23:00:00Z"):
    preds.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"event_id": "e1", "start_time": start_time}]).to_csv(
        preds / "predictions_mlb.csv", index=False)
    if cand_rows is not None:
        pd.DataFrame(cand_rows).to_csv(preds / "candidates_mlb.csv", index=False)
    cal = root / "data" / "calibration"
    cal.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(served_rows).to_csv(cal / "served_mlb.csv", index=False)
    odds = root / "data" / "odds"
    odds.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(snap_rows).to_csv(odds / "odds_mlb_202606.csv", index=False)


def _read_log(root):
    return pd.read_csv(root / "data" / "bets" / INTRADAY_LOG_FILENAME)


def test_logs_h2h_edges_against_fresh_consensus(tmp_path):
    preds = tmp_path / "preds"
    fresh = f"{TODAY}T21:45:00Z"
    _seed(tmp_path, preds,
          served_rows=[_served("e1", "NYY", 0.60, 1.90),
                       _served("e1", "BOS", 0.40, 2.10)],
          snap_rows=[_snap_row("e1", "NYY", 2.10, fresh),
                     _snap_row("e1", "BOS", 1.80, fresh)],
          cand_rows=[{"event_id": "e1", "market": "h2h", "selection": "NYY",
                      "generated_at": f"{TODAY}T15:00:00"}])
    out = log_intraday_edges(preds, tmp_path, min_edge=0.03, now=NOW)
    assert out["scanned"] == 2
    assert out["would_generate"] == 1                 # NYY: 0.60*2.10-1 = 0.26
    log = _read_log(tmp_path)
    assert len(log) == 2
    nyy = log[log["selection"] == "NYY"].iloc[0]
    assert nyy["price_now"] == 2.10
    assert abs(nyy["edge_now"] - 0.26) < 1e-9
    assert bool(nyy["would_generate"]) is True
    assert bool(nyy["is_candidate"]) is True          # ya era pick de las 11:00
    bos = log[log["selection"] == "BOS"].iloc[0]
    assert bool(bos["would_generate"]) is False       # 0.40*1.80-1 < min_edge
    assert bool(bos["is_candidate"]) is False
    assert nyy["minutes_to_start"] == 60.0


def test_stale_snapshot_produces_no_rows(tmp_path):
    preds = tmp_path / "preds"
    old = f"{TODAY}T20:00:00Z"                        # 120 min > max age 90
    _seed(tmp_path, preds,
          served_rows=[_served("e1", "NYY", 0.60, 1.90)],
          snap_rows=[_snap_row("e1", "NYY", 2.10, old)])
    out = log_intraday_edges(preds, tmp_path, min_edge=0.03, now=NOW)
    assert out["scanned"] == 0
    assert not (tmp_path / "data" / "bets" / INTRADAY_LOG_FILENAME).exists()


def test_out_of_window_yesterday_and_non_h2h_ignored(tmp_path):
    preds = tmp_path / "preds"
    fresh = f"{TODAY}T21:45:00Z"
    _seed(tmp_path, preds,
          served_rows=[
              _served("e1", "NYY", 0.60, 1.90, generated="2026-06-25T15:00:00"),
              _served("e1", "Over", 0.55, 1.95, market="totals"),
          ],
          snap_rows=[_snap_row("e1", "NYY", 2.10, fresh)],
          start_time=f"{TODAY}T23:00:00Z")
    out = log_intraday_edges(preds, tmp_path, min_edge=0.03, now=NOW)
    assert out["scanned"] == 0                        # ayer + no-h2h: nada

    # evento fuera de ventana: servido hoy pero comienza en 7 horas
    _seed(tmp_path, preds,
          served_rows=[_served("e1", "NYY", 0.60, 1.90,
                               start="2026-06-27T05:00:00Z")],
          snap_rows=[_snap_row("e1", "NYY", 2.10, fresh)],
          start_time="2026-06-27T05:00:00Z")
    out = log_intraday_edges(preds, tmp_path, min_edge=0.03, now=NOW)
    assert out["scanned"] == 0


def test_settings_flag_defaults_off_env_wins(monkeypatch):
    monkeypatch.delenv("INTRADAY_SCAN_ENABLED", raising=False)
    assert Settings().intraday_scan_enabled is False  # tests/demo: apagado
    monkeypatch.setenv("INTRADAY_SCAN_ENABLED", "1")
    assert Settings().intraday_scan_enabled is True
