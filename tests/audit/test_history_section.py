import pandas as pd
from sqp.audit.html_report import _history_section


def test_history_section_hides_past_open_and_emits_cards(tmp_path):
    bets = tmp_path / "bets"; bets.mkdir()
    preds = tmp_path / "pred"; preds.mkdir()
    pd.DataFrame([{"event_id": "e1", "market": "h2h", "selection": "NYY", "line": 0.0,
                   "price_decimal": 1.9, "stake": 10.0, "result": "win", "pnl": 9.0,
                   "generated_at": "2026-06-24T09:00:00Z", "home": "NYY", "away": "BOS",
                   "game_date": "2026-06-24"}]).to_csv(bets / "settled_mlb.csv", index=False)
    # an open candidate whose game is in the PAST -> must be hidden
    pd.DataFrame([{"event_id": "e2", "market": "totals", "selection": "Over", "line": 8.5,
                   "price_decimal": 2.0, "stake": 5.0,
                   "estimated_edge": 0.05}]).to_csv(preds / "candidates_mlb.csv", index=False)
    pd.DataFrame([{"event_id": "e2", "home": "LAD", "away": "SF",
                   "start_time": "2026-06-20T20:00:00Z"}]).to_csv(preds / "predictions_mlb.csv", index=False)
    html = _history_section(preds, bets, today="2026-06-26")
    assert "NYY" in html and "BOS" in html         # closed row shown
    assert "LAD" not in html                         # past-open row hidden
    assert 'id="hWins"' in html or "Wins" in html    # totals cards present
    assert "Picks cerrados" in html
