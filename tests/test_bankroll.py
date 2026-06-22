"""Bankroll ledger: balance = initial + realized PnL (real bets) + adjustments."""
import pandas as pd

from sqp.risk.bankroll import BankrollLedger


def _write_settled(bets_dir, league, rows):
    bets_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(bets_dir / f"settled_{league}.csv", index=False)


def _row(pnl, result="win", stake=10.0, data_label="real", settled_at="2026-06-01T00:00:00+00:00"):
    return {"pnl": pnl, "result": result, "stake": stake,
            "data_label": data_label, "settled_at": settled_at}


def test_empty_state_equals_initial(tmp_path):
    led = BankrollLedger(root=tmp_path, initial=1000.0)
    assert led.current_balance() == 1000.0
    assert led.realized_pnl() == 0.0


def test_balance_sums_realized_pnl_across_leagues(tmp_path):
    bets = tmp_path / "data" / "bets"
    _write_settled(bets, "mlb", [_row(9.0), _row(-10.0, result="loss")])
    _write_settled(bets, "nhl", [_row(5.0)])
    led = BankrollLedger(root=tmp_path, initial=1000.0)
    assert led.realized_pnl() == 4.0                 # 9 - 10 + 5
    assert led.current_balance() == 1004.0


def test_demo_bets_are_excluded(tmp_path):
    bets = tmp_path / "data" / "bets"
    _write_settled(bets, "mlb", [_row(9.0, data_label="real"),
                                 _row(500.0, data_label="demo_synthetic")])
    led = BankrollLedger(root=tmp_path, initial=1000.0)
    assert led.current_balance() == 1009.0           # demo PnL ignored


def test_manual_adjustments_apply(tmp_path):
    bets = tmp_path / "data" / "bets"
    _write_settled(bets, "mlb", [_row(0.0, result="push")])
    bets.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"date": "2026-06-01", "amount": 250.0, "kind": "deposit", "note": ""},
                  {"date": "2026-06-05", "amount": -100.0, "kind": "withdrawal", "note": ""}]
                 ).to_csv(bets / "bankroll_adjustments.csv", index=False)
    led = BankrollLedger(root=tmp_path, initial=1000.0)
    assert led.adjustments_total() == 150.0
    assert led.current_balance() == 1150.0


def test_summary_and_drawdown(tmp_path):
    bets = tmp_path / "data" / "bets"
    _write_settled(bets, "mlb", [
        _row(20.0, settled_at="2026-06-01"),
        _row(-50.0, result="loss", settled_at="2026-06-02"),
        _row(10.0, settled_at="2026-06-03")])
    led = BankrollLedger(root=tmp_path, initial=1000.0)
    s = led.summary()
    assert s["current_balance"] == 980.0             # 1000 + 20 - 50 + 10
    assert s["n_graded"] == 3
    assert s["total_staked"] == 30.0
    # peak 1020 after day1, trough 970 after day2 -> drawdown -50.
    assert s["max_drawdown"] == -50.0


def test_corrupt_or_empty_file_is_skipped(tmp_path):
    bets = tmp_path / "data" / "bets"
    bets.mkdir(parents=True, exist_ok=True)
    (bets / "settled_mlb.csv").write_text("", encoding="utf-8")          # empty
    _write_settled(bets, "nhl", [_row(7.0)])
    led = BankrollLedger(root=tmp_path, initial=1000.0)
    assert led.current_balance() == 1007.0
