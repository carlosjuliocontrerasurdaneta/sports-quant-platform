"""Payload health gate: an empty scores response must never be read as
"every pending game was cancelled" (audit 2026-08-31, N-A-3).

Voiding is FINAL -- DEDUP_KEY carries no `result`, so tomorrow's real grade
collides with today's persisted `void` and gets discarded. Two ways to reach the
voiding path without an exception, so `settle_all` never flags the league: the
provider answers 200 with an empty list, or its schema changes and `_scores_map`
drops every entry per-entry. Either one used to void days of evidence at pnl 0.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from sqp.config import Settings
from sqp.settlement import runner
from sqp.settlement.runner import fetch_and_settle
from sqp.settlement.settle import STALE_VOID_DAYS

LEAGUE = "mlb"
NOW = datetime.now(timezone.utc)
OLD = (NOW - timedelta(days=STALE_VOID_DAYS + 2))
FRESH = (NOW - timedelta(hours=6))


class FakeClient:
    """Stands in for OddsAPIClient. `payload` is what /scores returns."""
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def fetch_scores(self, sport_key, days_from=2):
        self.calls += 1
        return self.payload


def _write_inputs(root):
    pred_dir = root / "data" / "predictions"
    pred_dir.mkdir(parents=True)
    # e1 commenced well past the stale window: the row voiding would destroy.
    pd.DataFrame([
        {"event_id": "e1", "league": LEAGUE, "market": "h2h", "selection": "A",
         "line": float("nan"), "price_decimal": 2.0, "stake": 10.0,
         "data_label": "real", "flags": "",
         "generated_at": f"{OLD.strftime('%Y-%m-%d')}T10:00:00+00:00"},
    ]).to_csv(pred_dir / f"candidates_{LEAGUE}.csv", index=False)
    pd.DataFrame([
        {"event_id": "e1", "home": "A", "away": "B",
         "start_time": OLD.strftime("%Y-%m-%dT%H:%M:%SZ")},
    ]).to_csv(pred_dir / f"predictions_{LEAGUE}.csv", index=False)


def _settled_rows(root):
    p = root / "data" / "bets" / f"settled_{LEAGUE}.csv"
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


def test_empty_scores_list_does_not_void_stale_candidates(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _write_inputs(tmp_path)
    client = FakeClient([])
    out = fetch_and_settle(LEAGUE, Settings(), days_from=3, client=client)
    assert client.calls == 1          # the fetch still happened
    assert out.empty                  # but nothing was graded OR voided
    assert _settled_rows(tmp_path).empty


def test_unparseable_scores_schema_does_not_void(tmp_path, monkeypatch):
    """`_scores_map`'s per-entry guard (M-10) turns a schema change into an empty
    map with no exception -- the second, subtler route into mass voiding."""
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _write_inputs(tmp_path)
    client = FakeClient([{"unexpected": "shape"}, {"also": "wrong"}])
    out = fetch_and_settle(LEAGUE, Settings(), days_from=3, client=client)
    assert out.empty
    assert _settled_rows(tmp_path).empty


def test_healthy_scores_response_still_voids_the_stale_row(tmp_path, monkeypatch):
    """The counterpart that keeps the expiry policy alive: one usable entry is
    enough to trust the payload, and the stale row voids as before. Without this
    the fix would silently disable stale voiding altogether."""
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _write_inputs(tmp_path)
    # A different, completed event: proves the feed is answering, and e1 is
    # genuinely absent from it.
    client = FakeClient([{
        "id": "other", "completed": True,
        "home_team": "C", "away_team": "D",
        "commence_time": FRESH.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scores": [{"name": "C", "score": "5"}, {"name": "D", "score": "3"}],
    }])
    out = fetch_and_settle(LEAGUE, Settings(), days_from=3, client=client)
    assert list(out["event_id"]) == ["e1"]
    row = out.iloc[0]
    assert row["result"] == "void" and row["pnl"] == 0.0
    assert "stale_void" in str(row["flags"])
