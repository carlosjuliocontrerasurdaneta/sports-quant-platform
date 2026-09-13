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
    staked = out.loc[out["result"].isin(["win", "loss"]), "stake"].sum()
    roi = float(out["pnl"].sum() / staked) if staked else 0.0
    assert roi == pytest.approx(0.0)


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
    staked = out.loc[out["result"].isin(["win", "loss"]), "stake"].sum()
    roi = float(out["pnl"].sum() / staked) if staked else 0.0
    assert roi == pytest.approx(1.0)


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


# --- lineas asiaticas de cuarto (AUD-MED-002, auditoria integral 2026-09-13) ---
# El stake se reparte a medias entre las dos lineas de medio punto adyacentes.
# Graduarlas como enteras fabricaba resultados: reproducido sobre el ledger
# (chile, Universidad de Chile -0.75, margen +1, graduado `win` siendo medio).

@pytest.mark.parametrize("line,hs,as_,esperado", [
    (-0.75, 1, 0, "half_win"),    # -1 push, -0.5 win
    (-0.75, 2, 0, "win"),
    (-0.75, 0, 0, "loss"),
    (-0.25, 0, 0, "half_loss"),   # -0.5 loss, 0 push
    (-0.25, 1, 0, "win"),
    (-1.25, 1, 0, "half_loss"),   # -1.5 loss, -1 push
    (-1.5, 2, 0, "win"),          # media linea: sin cambio
    (-1.0, 1, 0, "push"),         # entera: sin cambio
])
def test_grade_spreads_local_linea_de_cuarto(line, hs, as_, esperado):
    row = pd.Series({"market": "spreads", "selection": "Home", "line": line,
                     "away": "Away"})
    assert _grade(row, hs, as_, "Home") == esperado


@pytest.mark.parametrize("line,hs,as_,esperado", [
    (0.25, 0, 0, "half_win"),     # visitante +0.25 con empate: 0 push, +0.5 win
    (0.75, 1, 0, "half_loss"),    # visitante +0.75 pierde por 1: +0.5 loss, +1 push
])
def test_grade_spreads_visitante_linea_de_cuarto(line, hs, as_, esperado):
    row = pd.Series({"market": "spreads", "selection": "Away", "line": line,
                     "away": "Away"})
    assert _grade(row, hs, as_, "Home") == esperado


@pytest.mark.parametrize("sel,line,hs,as_,esperado", [
    ("Over", 2.25, 1, 1, "half_loss"),   # 2.0 push, 2.5 loss
    ("Over", 2.25, 2, 1, "win"),
    ("Under", 2.75, 2, 1, "half_loss"),  # total 3: 2.5 loss, 3.0 push
    ("Under", 2.75, 1, 1, "win"),
    ("Over", 2.5, 2, 1, "win"),          # media linea: sin cambio
])
def test_grade_totals_linea_de_cuarto(sel, line, hs, as_, esperado):
    row = pd.Series({"market": "totals", "selection": sel, "line": line})
    assert _grade(row, hs, as_, "Home") == esperado


def test_pnl_de_medias_es_la_mitad_del_stake():
    cands = pd.DataFrame([
        {"event_id": "e1", "market": "spreads", "selection": "Home", "line": -0.75,
         "stake": 10.0, "price_decimal": 2.0, "away": "Away"},
        {"event_id": "e1", "market": "spreads", "selection": "Home", "line": -1.25,
         "stake": 10.0, "price_decimal": 2.0, "away": "Away"},
    ])
    out = settle_candidates(cands, {"e1": (1, 0, "Home")})
    assert out["result"].tolist() == ["half_win", "half_loss"]
    assert out["pnl"].tolist() == [5.0, -5.0]


def test_realized_roi_cuenta_el_stake_de_las_medias():
    from sqp.settlement.runner import realized_roi
    settled = pd.DataFrame([
        {"result": "half_win", "stake": 10.0, "pnl": 5.0},
        {"result": "loss", "stake": 10.0, "pnl": -10.0},
        {"result": "push", "stake": 10.0, "pnl": 0.0},
    ])
    # (5 - 10) / (10 + 10): el push no entra, la media si
    assert realized_roi(settled) == pytest.approx(-0.25)
