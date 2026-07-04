"""Realized-ROI backtest: closing-snapshot selection, result matching, summary."""
import pandas as pd

from sqp.backtesting.roi_engine import (_match_index, _match_result, _summarize,
                                        discover_leagues_with_odds,
                                        load_closing_odds, realized_roi_backtest)
from sqp.config import RiskConfig
from sqp.domain.models import Event, EventOdds, MarketLine
from sqp.storage.odds_store import COLUMNS


def _write_odds(root, rows):
    d = root / "data" / "odds"
    d.mkdir(parents=True)
    pd.DataFrame(rows)[COLUMNS].to_csv(d / "odds_test_202606.csv", index=False)


def test_load_closing_odds_picks_last_snapshot_before_commence(tmp_path):
    commence = "2026-06-10T23:00:00Z"
    base = {"event_id": "e1", "commence_time": commence, "home": "Rays", "away": "Red Sox",
            "market": "h2h", "point": "", "bookmaker": "dk"}
    rows = [
        {**base, "captured_at": "2026-06-09T23:00:00Z", "outcome": "Rays", "price_decimal": 1.7},
        {**base, "captured_at": "2026-06-10T22:00:00Z", "outcome": "Rays", "price_decimal": 1.9},  # last pre-game
        {**base, "captured_at": "2026-06-11T01:00:00Z", "outcome": "Rays", "price_decimal": 2.5},  # post-commence, ignore
    ]
    _write_odds(tmp_path, rows)
    odds = load_closing_odds(tmp_path, "test")
    assert set(odds) == {"e1"}
    prices = [ln.price_decimal for ln in odds["e1"].lines]
    assert prices == [1.9]                     # only the last strictly-pre-commence snapshot


def test_match_result_by_name_and_date_window():
    from sqp.domain.models import Event, EventOdds, MarketLine
    eo = EventOdds(event=Event(event_id="e1", sport_key="bt", league="test",
                               home="Boston Red Sox", away="Tampa Bay Rays",
                               start_time="2026-06-10T23:00:00Z", data_label="real"),
                   lines=[MarketLine("h2h", "dk", "Boston Red Sox", 1.9, None)])
    idx = _match_index({"e1": eo})
    used = set()
    # same teams, result date one day off (UTC drift) -> still matches, once.
    r = {"home": "Boston Red Sox", "away": "Tampa Bay Rays", "date": "2026-06-11"}
    assert _match_result(r, idx, used) is eo
    assert _match_result(r, idx, used) is None   # already consumed


def test_summarize_computes_realized_roi_and_by_market():
    settled = pd.DataFrame([
        {"market": "h2h", "selection": "A", "stake": 10.0, "price_decimal": 2.0,
         "result": "win", "pnl": 10.0, "estimated_edge": 0.05, "estimated_probability": 0.55},
        {"market": "h2h", "selection": "B", "stake": 10.0, "price_decimal": 1.9,
         "result": "loss", "pnl": -10.0, "estimated_edge": 0.03, "estimated_probability": 0.54},
        {"market": "totals", "selection": "Over", "stake": 10.0, "price_decimal": 2.0,
         "result": "win", "pnl": 10.0, "estimated_edge": 0.04, "estimated_probability": 0.52},
    ])
    out = _summarize("mlb", settled, n_matched=3)
    assert out["n_bets"] == 3 and out["n_graded"] == 3
    assert out["staked"] == 30.0 and out["pnl"] == 10.0
    assert out["realized_roi"] == round(10.0 / 30.0, 4)
    markets = set(out["by_market"]["market"])
    assert markets == {"h2h", "totals"}


def test_summarize_empty_is_safe():
    out = _summarize("mlb", pd.DataFrame(), n_matched=0)
    assert out["n_bets"] == 0 and out["by_market"].empty


def test_discover_leagues_with_odds(tmp_path):
    d = tmp_path / "data" / "odds"
    d.mkdir(parents=True)
    for name in ("odds_mlb_202606.csv", "odds_mlb_202605.csv",
                 "odds_wnba_202606.csv", "odds_ligue1_202606.csv"):
        (d / name).write_text("x", encoding="utf-8")
    (d / "ignore.csv").write_text("x", encoding="utf-8")  # not an odds file
    assert discover_leagues_with_odds(tmp_path) == ["ligue1", "mlb", "wnba"]


def test_discover_leagues_with_odds_empty(tmp_path):
    assert discover_leagues_with_odds(tmp_path) == []


def _eo(eid, home, away, day):
    return EventOdds(
        event=Event(event_id=eid, sport_key="bt", league="test", home=home,
                    away=away, start_time=f"{day}T23:00:00Z", data_label="real"),
        lines=[MarketLine("h2h", "dk", home, 1.9, None),
               MarketLine("h2h", "dk", away, 2.1, None)])


def test_bet_from_date_restricts_evaluation_window():
    # n_events_matched counts games that fall in the betting window, so it
    # isolates the gate independently of whether any stake is placed.
    results = [
        {"date": "2026-06-01", "home": "A", "away": "B", "home_score": 5,
         "away_score": 3, "neutral": False, "game_id": "1"},
        {"date": "2026-06-05", "home": "A", "away": "B", "home_score": 2,
         "away_score": 4, "neutral": False, "game_id": "2"},
        {"date": "2026-06-10", "home": "A", "away": "B", "home_score": 1,
         "away_score": 0, "neutral": False, "game_id": "3"},
    ]
    odds = {"e1": _eo("e1", "A", "B", "2026-06-01"),
            "e2": _eo("e2", "A", "B", "2026-06-05"),
            "e3": _eo("e3", "A", "B", "2026-06-10")}
    risk = RiskConfig()

    full = realized_roi_backtest(results, odds, "test", "baseball", None, risk,
                                 1000.0, warmup=0)
    assert full["n_events_matched"] == 3

    windowed = realized_roi_backtest(results, odds, "test", "baseball", None, risk,
                                     1000.0, warmup=0, bet_from_date="2026-06-05")
    assert windowed["n_events_matched"] == 2  # only 06-05 and 06-10

    after_all = realized_roi_backtest(results, odds, "test", "baseball", None, risk,
                                      1000.0, warmup=0, bet_from_date="2026-07-01")
    assert after_all["n_events_matched"] == 0
