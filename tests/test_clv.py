"""CLV automatizado (sqp.audit.clv): emparejado contra cierre capturado,
matematica del CLV, segmentos y regla de salida del shadow mode."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from sqp.audit.clv import (SHADOW_EXIT_MIN_N, clv_segments, compute_clv,
                           daily_clv)
from sqp.storage.odds_store import COLUMNS

COMMENCE = "2026-07-01T23:00:00Z"


def _write_odds(root: Path, rows: list[dict], league: str = "test") -> None:
    d = root / "data" / "odds"
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows)[COLUMNS].to_csv(d / f"odds_{league}_202607.csv",
                                       index=False)


def _odds_row(**kw) -> dict:
    base = {"event_id": "e1", "commence_time": COMMENCE, "home": "A",
            "away": "B", "market": "h2h", "point": "", "bookmaker": "dk",
            "captured_at": "2026-07-01T22:00:00Z", "outcome": "A",
            "price_decimal": 1.9}
    return {**base, **kw}


def _write_settled(root: Path, rows: list[dict], league: str = "test") -> None:
    d = root / "data" / "bets"
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(d / f"settled_{league}.csv", index=False)


def _settled_row(**kw) -> dict:
    base = {"event_id": "e1", "market": "h2h", "selection": "A", "line": "",
            "price_decimal": 2.0, "result": "win", "stake": 0.0, "pnl": 0.0}
    return {**base, **kw}


def test_compute_clv_matches_h2h_and_math(tmp_path):
    _write_odds(tmp_path, [_odds_row()])
    _write_settled(tmp_path, [_settled_row()])
    df, unmatched = compute_clv(tmp_path / "data" / "bets", tmp_path)
    assert unmatched == 0 and len(df) == 1
    r = df.iloc[0]
    assert r["entry"] == 2.0 and r["close"] == 1.9
    assert abs(r["clv_pct"] - (2.0 / 1.9 - 1.0)) < 1e-12
    assert bool(r["beat_close"]) is True


def test_compute_clv_negative_when_entry_worse_than_close(tmp_path):
    _write_odds(tmp_path, [_odds_row(price_decimal=2.2)])
    _write_settled(tmp_path, [_settled_row(price_decimal=2.0, result="loss")])
    df, _ = compute_clv(tmp_path / "data" / "bets", tmp_path)
    assert df.iloc[0]["clv_pct"] < 0
    assert bool(df.iloc[0]["beat_close"]) is False


def test_equal_entry_is_neutral_not_beating_close(tmp_path):
    _write_odds(tmp_path, [_odds_row(price_decimal=2.0)])
    _write_settled(tmp_path, [_settled_row(price_decimal=2.0)])
    df, _ = compute_clv(tmp_path / "data" / "bets", tmp_path)
    assert df.iloc[0]["clv_pct"] == 0.0
    assert bool(df.iloc[0]["beat_close"]) is False


def test_compute_clv_matches_spreads_by_line(tmp_path):
    _write_odds(tmp_path, [_odds_row(market="spreads", point=-1.5),
                           _odds_row(market="spreads", point=-2.5,
                                     price_decimal=2.4)])
    _write_settled(tmp_path, [_settled_row(market="spreads", line=-1.5)])
    df, unmatched = compute_clv(tmp_path / "data" / "bets", tmp_path)
    # Must match the -1.5 close (1.9), not the -2.5 one.
    assert unmatched == 0 and df.iloc[0]["close"] == 1.9


def test_compute_clv_unmatched_when_no_closing_capture(tmp_path):
    _write_odds(tmp_path, [_odds_row(event_id="other")])
    _write_settled(tmp_path, [_settled_row()])
    df, unmatched = compute_clv(tmp_path / "data" / "bets", tmp_path)
    assert df.empty and unmatched == 1


def test_compute_clv_ignores_push_and_void(tmp_path):
    _write_odds(tmp_path, [_odds_row()])
    _write_settled(tmp_path, [_settled_row(result="push"),
                              _settled_row(result="void")])
    df, unmatched = compute_clv(tmp_path / "data" / "bets", tmp_path)
    assert df.empty and unmatched == 0


def test_clv_segments_aggregates(tmp_path):
    df = pd.DataFrame([
        {"league": "mlb", "market": "h2h", "clv_pct": 0.05, "beat_close": True},
        {"league": "mlb", "market": "h2h", "clv_pct": -0.01, "beat_close": False},
    ])
    seg = clv_segments(df, ["league"])
    assert seg.iloc[0]["n"] == 2
    assert seg.iloc[0]["median_clv_pct"] == 0.02
    assert seg.iloc[0]["beat_close_rate"] == 0.5


def test_daily_clv_writes_report_and_summary(tmp_path):
    _write_odds(tmp_path, [_odds_row()])
    _write_settled(tmp_path, [_settled_row()])
    s = daily_clv(tmp_path / "data" / "bets", tmp_path)
    assert s["n_matched"] == 1 and s["n_unmatched"] == 0
    assert s["median_clv_pct"] > 0
    assert s["shadow_clv_ok"] is False          # n < SHADOW_EXIT_MIN_N
    text = Path(s["path"]).read_text(encoding="utf-8")
    assert "CLV mediano" in text and "shadow mode" in text
    assert "probabilidades estimadas" in text   # disclaimer present


def test_daily_clv_empty_still_writes_report(tmp_path):
    (tmp_path / "data" / "bets").mkdir(parents=True)
    s = daily_clv(tmp_path / "data" / "bets", tmp_path)
    assert s["n_matched"] == 0 and s["median_clv_pct"] is None
    assert Path(s["path"]).exists()


def test_daily_clv_shadow_exit_met_with_enough_positive_median(tmp_path):
    _write_odds(tmp_path, [_odds_row()])
    _write_settled(tmp_path, [_settled_row() for _ in range(SHADOW_EXIT_MIN_N)])
    s = daily_clv(tmp_path / "data" / "bets", tmp_path)
    assert s["n_matched"] == SHADOW_EXIT_MIN_N
    assert s["shadow_clv_ok"] is True
    assert "CUMPLE la parte CLV" in Path(s["path"]).read_text(encoding="utf-8")
