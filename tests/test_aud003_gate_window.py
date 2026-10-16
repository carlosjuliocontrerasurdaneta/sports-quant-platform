"""AUD-003 (ronda audit-2026-10-15): las filas nhl|h2h servidas antes del
arreglo llevan un ``implied_probability_novig`` deprimido por el Draw del 1X2,
asi que no pueden contar en el test de signo del gate de prediccion."""
from __future__ import annotations

import json

import pandas as pd

from sqp.risk.prediction_gate import (INVALID_BEFORE, evaluate_markets,
                                      load_prediction_gate, market_allowed,
                                      write_prediction_gate)

FIX = INVALID_BEFORE[("nhl", "h2h")]


def _rows(n: int, *, league: str, market: str, generated_at: str | None,
          prefix: str) -> pd.DataFrame:
    recs = []
    for i in range(n):
        rec = {"league": league, "market": market, "event_id": f"{prefix}-{i}",
               "model_probability": 0.6, "implied_probability_novig": 0.4,
               "price_decimal": 2.1, "result": "win" if i % 2 else "loss",
               "game_date": "2026-10-10"}
        if generated_at is not None:
            rec["generated_at"] = generated_at
        recs.append(rec)
    return pd.DataFrame(recs)


def _n(table: pd.DataFrame, league: str, market: str) -> int:
    row = table[(table["league"] == league) & (table["market"] == market)]
    return int(row["n"].iloc[0]) if len(row) else 0


def test_nhl_h2h_rows_before_the_fix_do_not_count():
    graded = pd.concat([
        _rows(10, league="nhl", market="h2h",
              generated_at="2026-10-06T15:07:40+00:00", prefix="antes"),
        _rows(4, league="nhl", market="h2h",
              generated_at="2026-10-16T15:06:31+00:00", prefix="despues"),
    ], ignore_index=True)
    assert _n(evaluate_markets(graded), "nhl", "h2h") == 4


def test_the_cutoff_instant_itself_counts():
    graded = _rows(3, league="nhl", market="h2h", generated_at=FIX, prefix="x")
    assert _n(evaluate_markets(graded), "nhl", "h2h") == 3


def test_other_segments_are_untouched():
    graded = pd.concat([
        _rows(5, league="nhl", market="totals",
              generated_at="2026-10-06T15:07:40+00:00", prefix="tot"),
        _rows(5, league="mlb", market="h2h",
              generated_at="2026-10-06T15:07:40+00:00", prefix="mlb"),
    ], ignore_index=True)
    table = evaluate_markets(graded)
    assert _n(table, "nhl", "totals") == 5
    assert _n(table, "mlb", "h2h") == 5


def test_cutoff_is_an_instant_whatever_the_offset():
    graded = pd.concat([
        _rows(2, league="nhl", market="h2h",
              generated_at="2026-10-16T09:56:02-03:00", prefix="un-segundo-antes"),
        _rows(3, league="nhl", market="h2h",
              generated_at="2026-10-16T09:56:03-03:00", prefix="en-el-corte"),
    ], ignore_index=True)
    assert _n(evaluate_markets(graded), "nhl", "h2h") == 3


def test_mixed_formats_and_corrupt_stamps_in_one_column():
    stamps = ["2026-10-17T15:07:19.123456+00:00", "2026-10-17 15:07:19Z",
              "2026-10-17T12:07:19-03:00", "no-es-una-fecha",
              "2026-10-06T15:07:40+00:00"]
    graded = _rows(len(stamps), league="nhl", market="h2h",
                   generated_at=None, prefix="mix")
    graded["generated_at"] = stamps
    # Las tres validas posteriores al corte cuentan; la corrupta y la anterior no.
    assert _n(evaluate_markets(graded), "nhl", "h2h") == 3


def _write_previous(bets_dir, markets: dict) -> None:
    (bets_dir / "prediction_gate.json").write_text(
        json.dumps({"generated_at": "2026-10-16T15:06:34+00:00",
                    "markets": markets}), encoding="utf-8")


def _pre_fix_graded() -> pd.DataFrame:
    return pd.concat([
        _rows(6, league="nhl", market="h2h",
              generated_at="2026-10-06T15:07:40+00:00", prefix="nh"),
        _rows(6, league="nhl", market="totals",
              generated_at="2026-10-06T15:07:40+00:00", prefix="nt"),
    ], ignore_index=True)


def test_segment_without_spent_test_drops_out_of_the_registry(tmp_path):
    _write_previous(tmp_path, {"nhl|h2h": {
        "n": 118, "wins": 49, "allowed": False, "latched": False,
        "latched_at": None, "entry_test_at": None,
        "reason": "muestra_insuficiente"}})
    write_prediction_gate(_pre_fix_graded(), tmp_path)
    markets = load_prediction_gate(tmp_path)
    assert "nhl|h2h" not in markets
    assert market_allowed(markets, "nhl", "h2h") is False
    assert markets["nhl|totals"]["n"] == 6


def test_segment_with_spent_test_keeps_its_state(tmp_path):
    _write_previous(tmp_path, {"nhl|h2h": {
        "n": 300, "wins": 140, "allowed": False, "latched": False,
        "latched_at": None, "entry_test_at": "2026-10-10T15:00:00+00:00",
        "reason": "p_value"}})
    write_prediction_gate(_pre_fix_graded(), tmp_path)
    entry = load_prediction_gate(tmp_path)["nhl|h2h"]
    assert entry["reason"] == "sin_evaluacion"
    assert entry["entry_test_at"] == "2026-10-10T15:00:00+00:00"
    assert entry["allowed"] is False


def test_listed_segment_without_generated_at_is_default_deny():
    graded = pd.concat([
        _rows(5, league="nhl", market="h2h", generated_at=None, prefix="nh"),
        _rows(5, league="mlb", market="h2h", generated_at=None, prefix="ml"),
    ], ignore_index=True)
    table = evaluate_markets(graded)
    assert _n(table, "nhl", "h2h") == 0
    assert _n(table, "mlb", "h2h") == 5
