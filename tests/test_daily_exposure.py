"""Daily exposure cap (H1).

Per-bet Kelly caps bound a single stake, but a day with many signals can still
commit more than `max_daily_exposure_pct` of the bankroll. `_apply_daily_exposure_cap`
is the only place that bankroll-level limit is enforced.
"""

import pandas as pd

from sqp.domain.models import BetCandidate
from sqp.pipeline.daily import _apply_daily_exposure_cap, apply_global_exposure_cap


def _cand(stake: float, pct: float = 0.02, flags: str = "") -> BetCandidate:
    return BetCandidate(
        event_id="e", league="mlb", market="h2h", selection="Home", line=None,
        price_decimal=2.0, bookmaker="consensus_median",
        estimated_probability=0.55, implied_probability_novig=0.5,
        estimated_edge=0.05, kelly_stake_pct=pct, stake=stake,
        data_label="real", model_probability=0.55, flags=flags)


def test_no_scaling_when_under_cap():
    cands = [_cand(10.0), _cand(20.0)]  # 30 total, cap = 1000*0.10 = 100
    factor = _apply_daily_exposure_cap(cands, bankroll=1000.0, cap_pct=0.10)
    assert factor == 1.0
    assert [c.stake for c in cands] == [10.0, 20.0]
    assert all(c.flags == "" for c in cands)


def test_scaling_when_over_cap():
    cands = [_cand(80.0, pct=0.08), _cand(80.0, pct=0.08)]  # 160 total, cap = 100
    factor = _apply_daily_exposure_cap(cands, bankroll=1000.0, cap_pct=0.10)
    assert factor == 100.0 / 160.0
    total = sum(c.stake for c in cands)
    assert abs(total - 100.0) < 0.05  # respects the cap (within rounding)
    for c in cands:
        assert abs(c.stake - 50.0) < 0.01
        assert abs(c.kelly_stake_pct - 0.05) < 1e-9
        assert "daily_exposure_scaled" in c.flags


def test_zero_stake_rows_are_untouched_and_excluded():
    # Paused / implausible-edge rows carry stake 0 and must not be scaled nor
    # counted toward the day's exposure.
    paused = _cand(0.0, pct=0.0, flags="market_paused")
    live = _cand(160.0, pct=0.16)  # alone exceeds the 100 cap
    factor = _apply_daily_exposure_cap([paused, live], bankroll=1000.0, cap_pct=0.10)
    assert factor == 100.0 / 160.0
    assert paused.stake == 0.0
    assert paused.flags == "market_paused"  # unchanged
    assert "daily_exposure_scaled" in live.flags


def test_cap_disabled_when_pct_non_positive():
    cands = [_cand(500.0)]
    assert _apply_daily_exposure_cap(cands, bankroll=1000.0, cap_pct=0.0) == 1.0
    assert cands[0].stake == 500.0


# --- Global (cross-league) exposure cap -------------------------------------

def _write_cands(path, rows):
    """rows: list of (selection, stake, kelly_pct, flags)."""
    pd.DataFrame([{"event_id": "e", "market": "h2h", "selection": s, "line": None,
                   "price_decimal": 2.0, "stake": st, "kelly_stake_pct": k,
                   "flags": fl} for s, st, k, fl in rows]).to_csv(path, index=False)


def test_global_cap_no_scaling_when_under(tmp_path):
    # Two leagues, 30 + 40 = 70 total, cap = 1000*0.10 = 100 -> no scaling.
    _write_cands(tmp_path / "candidates_mlb.csv", [("A", 30.0, 0.03, "")])
    _write_cands(tmp_path / "candidates_nba.csv", [("B", 40.0, 0.04, "")])
    factor = apply_global_exposure_cap(tmp_path, bankroll=1000.0, cap_pct=0.10)
    assert factor == 1.0
    mlb = pd.read_csv(tmp_path / "candidates_mlb.csv")
    assert mlb["stake"].iloc[0] == 30.0
    assert mlb["flags"].fillna("").iloc[0] == ""


def test_global_cap_scales_across_leagues(tmp_path):
    # Each league alone (60) is under a 10% per-league cap, but combined 120 > 100.
    _write_cands(tmp_path / "candidates_mlb.csv", [("A", 60.0, 0.06, "")])
    _write_cands(tmp_path / "candidates_nba.csv", [("B", 60.0, 0.06, "")])
    factor = apply_global_exposure_cap(tmp_path, bankroll=1000.0, cap_pct=0.10)
    assert abs(factor - 100.0 / 120.0) < 1e-9
    total = sum(pd.read_csv(tmp_path / f"candidates_{lg}.csv")["stake"].sum()
                for lg in ("mlb", "nba"))
    assert abs(total - 100.0) < 0.05
    mlb = pd.read_csv(tmp_path / "candidates_mlb.csv")
    assert abs(mlb["stake"].iloc[0] - 50.0) < 0.01
    assert abs(mlb["kelly_stake_pct"].iloc[0] - 0.05) < 1e-9
    assert "global_exposure_scaled" in mlb["flags"].iloc[0]


def test_global_cap_excludes_zero_stake_and_preserves_flags(tmp_path):
    # Paused (stake 0) rows are not counted and keep their flag; a scaled row
    # appends to any existing flag rather than overwriting it.
    _write_cands(tmp_path / "candidates_mlb.csv",
                 [("paused", 0.0, 0.0, "market_paused"),
                  ("live", 160.0, 0.16, "daily_exposure_scaled")])
    factor = apply_global_exposure_cap(tmp_path, bankroll=1000.0, cap_pct=0.10)
    assert abs(factor - 100.0 / 160.0) < 1e-9
    df = pd.read_csv(tmp_path / "candidates_mlb.csv")
    paused = df[df["selection"] == "paused"].iloc[0]
    live = df[df["selection"] == "live"].iloc[0]
    assert paused["stake"] == 0.0
    assert paused["flags"] == "market_paused"
    assert "daily_exposure_scaled" in live["flags"]
    assert "global_exposure_scaled" in live["flags"]


def test_global_cap_disabled_when_pct_non_positive(tmp_path):
    _write_cands(tmp_path / "candidates_mlb.csv", [("A", 500.0, 0.5, "")])
    assert apply_global_exposure_cap(tmp_path, bankroll=1000.0, cap_pct=0.0) == 1.0
    assert pd.read_csv(tmp_path / "candidates_mlb.csv")["stake"].iloc[0] == 500.0
