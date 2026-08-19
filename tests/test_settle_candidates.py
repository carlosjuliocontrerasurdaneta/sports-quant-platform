"""settle_candidates: grading de candidatos y cálculo de realized_roi.

Cubre los gaps identificados en la auditoría 2026-08-19 (T1, T6):
- pnl por resultado (win/loss/push/void)
- realized_roi con staked==0 -> 0.0 sin dividir por cero
- event_id sin score saltado
- spreads push (adj==0)
- _parse_start naive->UTC, aware preservada, Z suffix, inválida->None
"""
from __future__ import annotations

from datetime import timezone

import pandas as pd
import pytest

from sqp.settlement.settle import _grade, _parse_start, settle_candidates


def _cands(**override):
    base = {
        "event_id": "e1",
        "market": "h2h",
        "selection": "Home",
        "line": float("nan"),
        "stake": 10.0,
        "price_decimal": 2.0,
    }
    base.update(override)
    return pd.DataFrame([base])


def _row(market, selection, line=float("nan")):
    return pd.Series({"market": market, "selection": selection, "line": line})


SCORES = {"e1": (2, 0, "Home")}


# --- pnl por resultado --------------------------------------------------------

def test_win_pnl():
    out = settle_candidates(_cands(), SCORES)
    row = out.iloc[0]
    assert row["result"] == "win"
    assert row["pnl"] == pytest.approx(10.0)  # stake * (price-1)


def test_loss_pnl():
    out = settle_candidates(_cands(selection="Away"), SCORES)
    row = out.iloc[0]
    assert row["result"] == "loss"
    assert row["pnl"] == pytest.approx(-10.0)


def test_push_pnl_is_zero():
    tie_scores = {"e1": (1, 1, "Home")}
    out = settle_candidates(_cands(), tie_scores)
    row = out.iloc[0]
    assert row["result"] == "push"
    assert row["pnl"] == pytest.approx(0.0)


def test_void_pnl_is_zero():
    out = settle_candidates(_cands(market="totals", selection="Over"), SCORES)
    row = out.iloc[0]
    assert row["result"] == "void"
    assert row["pnl"] == pytest.approx(0.0)


# --- event_id sin score saltado -----------------------------------------------

def test_event_without_score_is_skipped():
    out = settle_candidates(_cands(event_id="not_in_scores"), SCORES)
    assert out.empty


# --- realized_roi con staked == 0 (push + void) --------------------------------

def test_realized_roi_zero_staked_is_zero_not_nan():
    tie_scores = {"e1": (1, 1, "Home")}
    out = settle_candidates(_cands(), tie_scores)
    assert out.attrs.get("realized_roi") == pytest.approx(0.0)


def test_realized_roi_computed_correctly():
    cands = pd.DataFrame([
        {"event_id": "e1", "market": "h2h", "selection": "Home",
         "line": float("nan"), "stake": 10.0, "price_decimal": 2.0},
        {"event_id": "e2", "market": "h2h", "selection": "Away",
         "line": float("nan"), "stake": 10.0, "price_decimal": 2.0},
    ])
    scores = {"e1": (2, 0, "Home"), "e2": (0, 2, "Home")}
    out = settle_candidates(cands, scores)
    # e1: Home wins (2-0) -> win +10; e2: Away wins (0-2) -> win +10
    assert out.attrs["realized_roi"] == pytest.approx(1.0)


# --- spreads push (adj == 0) --------------------------------------------------

def test_spreads_push_when_adjusted_margin_is_zero():
    # Home gana por 3, línea -3 -> adj = 3 + (-3) = 0 -> push
    assert _grade(_row("spreads", "Home", line=-3.0), 3, 0, "Home") == "push"


def test_spreads_home_covers_is_win():
    # Home gana por 4, línea -3 -> adj = 4 - 3 = 1 > 0 -> win
    assert _grade(_row("spreads", "Home", line=-3.0), 4, 0, "Home") == "win"


def test_spreads_home_fails_to_cover_is_loss():
    # Home gana por 2, línea -3 -> adj = 2 - 3 = -1 < 0 -> loss
    assert _grade(_row("spreads", "Home", line=-3.0), 2, 0, "Home") == "loss"


# --- _parse_start: naive vs aware ---------------------------------------------

def test_parse_start_naive_string_gets_utc_timezone():
    dt = _parse_start("2026-08-19T12:00:00")
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt.tzinfo == timezone.utc


def test_parse_start_aware_string_preserves_timezone():
    dt = _parse_start("2026-08-19T12:00:00+00:00")
    assert dt is not None
    assert dt.tzinfo is not None


def test_parse_start_z_suffix_is_parsed():
    dt = _parse_start("2026-08-19T12:00:00Z")
    assert dt is not None
    assert dt.tzinfo is not None


def test_parse_start_invalid_string_returns_none():
    assert _parse_start("not-a-date") is None


def test_parse_start_none_returns_none():
    assert _parse_start(None) is None
