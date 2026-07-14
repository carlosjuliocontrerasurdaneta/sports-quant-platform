"""CLV condicionado al movimiento de linea previo al pick (clv_movement):
consenso por snapshot, direccion del movimiento, join con el CLV y segmentos.
Analisis retrospectivo del filtro de confirmacion (2026-07-14)."""
from __future__ import annotations

import pandas as pd

from sqp.audit.clv import compute_clv
from sqp.audit.clv_movement import (clv_by_movement, movement_direction,
                                    movement_segments, pre_pick_movement)
from sqp.storage.odds_store import COLUMNS

COMMENCE = "2026-07-01T23:00:00Z"
PICKED_AT = "2026-07-01T11:05:00Z"


def _write_odds(root, rows, league="test"):
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


def _write_settled(root, rows, league="test"):
    d = root / "data" / "bets"
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(d / f"settled_{league}.csv", index=False)


def _settled_row(**kw) -> dict:
    base = {"event_id": "e1", "market": "h2h", "selection": "A", "line": "",
            "price_decimal": 2.0, "result": "win", "stake": 0.0, "pnl": 0.0}
    return {**base, **kw}


def _snapshots() -> list[dict]:
    """Dos snapshots pre-pick (madrugada y manana) + cierre fresco 22:00.

    Consenso h2h de "A": 2.20 -> 2.00 (prob implicita 45.5% -> 50.0%, +4.5pp
    hacia nosotros); el cierre 1.90 esta a 60 min del comienzo (fresco)."""
    return [
        # ref: 03:00, dos books (mediana 2.20)
        _odds_row(captured_at="2026-07-01T03:00:00Z", price_decimal=2.1),
        _odds_row(captured_at="2026-07-01T03:00:00Z", bookmaker="fd",
                  price_decimal=2.3),
        # pick-time: 11:00 (ultimo <= generated_at), mediana 2.00
        _odds_row(captured_at="2026-07-01T11:00:00Z", price_decimal=2.0),
        # post-pick (no debe usarse para el movimiento): cierre fresco
        _odds_row(captured_at="2026-07-01T22:00:00Z", price_decimal=1.9),
    ]


def test_movement_direction_thresholds():
    assert movement_direction(2.0) == "hacia"
    assert movement_direction(-2.0) == "contra"
    assert movement_direction(0.3) == "plano"
    assert movement_direction(-0.3) == "plano"
    assert movement_direction(0.6, flat_pp=1.0) == "plano"


def test_pre_pick_movement_uses_consensus_and_ignores_post_pick(tmp_path):
    odds = pd.DataFrame(_snapshots())
    m = pre_pick_movement(odds, market="h2h", selection="A", point=None,
                          picked_at=PICKED_AT)
    assert m is not None
    # (1/2.0 - 1/2.2) * 100 = +4.545pp hacia nosotros; el cierre 22:00 queda fuera
    assert abs(m["movement_pp"] - (100.0 / 2.0 - 100.0 / 2.2)) < 1e-9
    assert m["n_snapshots"] == 2
    assert abs(m["lookback_h"] - 8.0) < 1e-9


def test_pre_pick_movement_requires_two_distinct_snapshots(tmp_path):
    odds = pd.DataFrame([_odds_row(captured_at="2026-07-01T11:00:00Z")])
    assert pre_pick_movement(odds, market="h2h", selection="A", point=None,
                             picked_at=PICKED_AT) is None


def test_compute_clv_carries_join_keys(tmp_path):
    _write_odds(tmp_path, [_odds_row()])
    _write_settled(tmp_path, [_settled_row(generated_at=PICKED_AT)])
    df, _ = compute_clv(tmp_path / "data" / "bets", tmp_path)
    assert {"event_id", "line", "generated_at"} <= set(df.columns)
    assert df.iloc[0]["event_id"] == "e1"
    assert df.iloc[0]["generated_at"] == PICKED_AT


def test_clv_by_movement_joins_and_classifies(tmp_path):
    _write_odds(tmp_path, _snapshots())
    _write_settled(tmp_path, [_settled_row(generated_at=PICKED_AT)])
    df, coverage = clv_by_movement(tmp_path / "data" / "bets", tmp_path)
    assert coverage["n_matched_close"] == 1
    assert coverage["n_with_movement"] == 1
    r = df.iloc[0]
    assert r["direction"] == "hacia"
    assert r["movement_pp"] > 4.0
    assert "clv_pct" in df.columns
    # pick sin generated_at o sin 2 snapshots pre-pick queda excluido, no roto
    _write_settled(tmp_path, [_settled_row(generated_at=PICKED_AT),
                              _settled_row(event_id="e9")])
    df2, cov2 = clv_by_movement(tmp_path / "data" / "bets", tmp_path)
    assert cov2["n_with_movement"] == 1


def test_movement_segments_aggregates_by_direction():
    df = pd.DataFrame([
        {"direction": "hacia", "clv_pct": 0.04, "beat_close": True,
         "result": "win", "entry": 2.0},
        {"direction": "hacia", "clv_pct": 0.02, "beat_close": True,
         "result": "loss", "entry": 2.0},
        {"direction": "contra", "clv_pct": -0.03, "beat_close": False,
         "result": "loss", "entry": 1.8},
    ])
    seg = movement_segments(df).set_index("direction")
    assert seg.loc["hacia", "n"] == 2
    assert seg.loc["hacia", "median_clv_pct"] == 0.03
    assert seg.loc["contra", "beat_close_rate"] == 0.0
    # roi_flat: hacia = (+1.0 - 1.0)/2 = 0.0 ; contra = -1.0
    assert abs(seg.loc["hacia", "roi_flat"] - 0.0) < 1e-9
    assert abs(seg.loc["contra", "roi_flat"] + 1.0) < 1e-9
