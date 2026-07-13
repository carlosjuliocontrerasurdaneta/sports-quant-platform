"""Void por expiracion: un partido cancelado (sin score) no puede dejar su
pick abierto para siempre — pasados STALE_VOID_DAYS se liquida como void."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from sqp.settlement.settle import STALE_VOID_DAYS, void_stale_candidates

NOW = datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc)
OLD = (NOW - timedelta(days=STALE_VOID_DAYS + 1)).isoformat()
RECENT = (NOW - timedelta(hours=6)).isoformat()


def _cand(**kw) -> dict:
    base = {"event_id": "e1", "market": "h2h", "selection": "A", "line": "",
            "price_decimal": 2.0, "stake": 1.0, "flags": ""}
    return {**base, **kw}


def test_stale_unscored_candidate_is_voided_with_flag():
    cands = pd.DataFrame([_cand()])
    out = void_stale_candidates(cands, {}, {"e1": OLD}, now=NOW)
    assert len(out) == 1
    r = out.iloc[0]
    assert r["result"] == "void" and r["pnl"] == 0.0
    assert r["flags"] == "stale_void"
    assert r["settled_at"] == NOW.isoformat()


def test_existing_flags_are_preserved():
    cands = pd.DataFrame([_cand(flags="shadow_mode")])
    out = void_stale_candidates(cands, {}, {"e1": OLD}, now=NOW)
    assert out.iloc[0]["flags"] == "shadow_mode;stale_void"


def test_nan_flags_do_not_leak_into_flag_string():
    cands = pd.DataFrame([_cand(flags=float("nan"))])
    out = void_stale_candidates(cands, {}, {"e1": OLD}, now=NOW)
    assert out.iloc[0]["flags"] == "stale_void"


def test_scored_candidate_is_never_voided():
    cands = pd.DataFrame([_cand()])
    out = void_stale_candidates(cands, {"e1": (3, 1, "A")}, {"e1": OLD}, now=NOW)
    assert out.empty


def test_recent_unscored_candidate_stays_open():
    cands = pd.DataFrame([_cand()])
    out = void_stale_candidates(cands, {}, {"e1": RECENT}, now=NOW)
    assert out.empty


def test_unknown_or_bad_start_time_stays_open():
    cands = pd.DataFrame([_cand(event_id="e1"), _cand(event_id="e2")])
    out = void_stale_candidates(cands, {}, {"e2": "not-a-date"}, now=NOW)
    assert out.empty  # e1 sin start_time, e2 ilegible: nunca adivinar


def test_z_suffix_start_time_is_parsed():
    old_z = OLD.replace("+00:00", "Z") if "+00:00" in OLD else OLD
    cands = pd.DataFrame([_cand()])
    out = void_stale_candidates(cands, {}, {"e1": old_z}, now=NOW)
    assert len(out) == 1
