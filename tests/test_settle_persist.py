"""Regression: _persist_settled must reconcile columns across schema versions.

A settled_*.csv written by an older BetCandidate schema (before
calibrated_probability existed) must not misalign when newer rows -- which carry
the extra column -- are persisted. The old failure was a blind mode='a' append
that wrote the new column order under the old header (audit 2026-06, I-1)."""
import pandas as pd

import sqp.settlement.runner as runner


def _persist(tmp_path, df):
    return runner._persist_settled("nfl", df)


def test_persist_reconciles_added_column_without_misalignment(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    out = tmp_path / "data" / "bets" / "settled_nfl.csv"
    out.parent.mkdir(parents=True)
    # Prior file from the OLD schema: no calibrated_probability column.
    out.write_text(
        "event_id,market,selection,line,price_decimal,stake,model_probability,"
        "flags,generated_at,result,pnl,settled_at\n"
        "e1,h2h,A,,1.9,10.0,0.55,,2026-06-01T00:00:00+00:00,win,9.0,"
        "2026-06-01T03:00:00+00:00\n",
        encoding="utf-8")

    # New row from the CURRENT schema: calibrated_probability sits between
    # model_probability and flags.
    new = pd.DataFrame([{
        "event_id": "e2", "market": "h2h", "selection": "B", "line": float("nan"),
        "price_decimal": 2.1, "stake": 12.0, "model_probability": 0.48,
        "calibrated_probability": 0.50, "flags": "",
        "generated_at": "2026-06-02T00:00:00+00:00", "result": "loss",
        "pnl": -12.0, "settled_at": "2026-06-02T03:00:00+00:00"}])

    _persist(tmp_path, new)
    back = pd.read_csv(out)

    # Both rows present, union of columns, no shift.
    assert "calibrated_probability" in back.columns
    r1 = back[back.event_id == "e1"].iloc[0]
    r2 = back[back.event_id == "e2"].iloc[0]
    # Old row's values stay under their own columns (not shifted by the new field).
    assert r1["result"] == "win" and float(r1["pnl"]) == 9.0
    assert float(r1["price_decimal"]) == 1.9
    assert pd.isna(r1["calibrated_probability"])      # absent in the old schema
    # New row keeps its calibrated probability and grade.
    assert r2["result"] == "loss" and float(r2["calibrated_probability"]) == 0.50


def test_persist_is_idempotent_on_repeat(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    row = {"event_id": "e9", "market": "totals", "selection": "Over", "line": 7.5,
           "price_decimal": 1.95, "stake": 5.0,
           "generated_at": "2026-06-03T00:00:00+00:00", "result": "win",
           "pnl": 4.75, "settled_at": "2026-06-03T03:00:00+00:00"}
    df = pd.DataFrame([row])
    first = _persist(tmp_path, df.copy())
    second = _persist(tmp_path, df.copy())
    assert len(first) == 1 and second.empty          # already settled -> deduped
    back = pd.read_csv(tmp_path / "data" / "bets" / "settled_nfl.csv")
    assert len(back) == 1                             # not double-written
