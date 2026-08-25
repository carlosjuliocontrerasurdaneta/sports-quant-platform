"""Paridad de banca dinamica entre los dos entrypoints diarios (KI-016).

`scripts/run_all.py` (produccion) dimensionaba sobre el balance REAL del ledger
y `scripts/run_daily.py --mode live` sobre la cifra nominal estatica. Con
inicial 1000 y balance 915,75 eso infla todos los stakes un 9,2%, y run_daily
escribe sobre los MISMOS candidates_*.csv. Ahora ambos llaman al mismo helper;
estos tests fijan que no puedan volver a separarse.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import pytest

from sqp.risk.bankroll import apply_dynamic_bankroll


@dataclass
class _S:
    bankroll: float = 1000.0
    bankroll_dynamic: bool = True


def _ledger(tmp_path, rows):
    d = tmp_path / "data" / "bets"
    d.mkdir(parents=True)
    pd.DataFrame(rows).to_csv(d / "settled_nfl.csv", index=False)
    return tmp_path


def _row(pnl, label="real"):
    return {"event_id": "e", "market": "h2h", "selection": "A",
            "price_decimal": 1.9, "stake": 10.0, "result": "loss",
            "pnl": pnl, "data_label": label,
            "settled_at": "2026-06-01T00:00:00+00:00"}


def test_live_sizes_on_the_real_balance_not_the_nominal_figure(tmp_path):
    root = _ledger(tmp_path, [_row(-84.25)])
    s = _S()
    assert apply_dynamic_bankroll(s, root, "live") == pytest.approx(915.75)
    assert s.bankroll == pytest.approx(915.75)


def test_demo_keeps_the_static_bankroll(tmp_path):
    root = _ledger(tmp_path, [_row(-84.25)])
    s = _S()
    assert apply_dynamic_bankroll(s, root, "demo") == pytest.approx(1000.0)
    assert s.bankroll == pytest.approx(1000.0)


def test_disabled_flag_is_a_no_op(tmp_path):
    root = _ledger(tmp_path, [_row(-84.25)])
    s = _S(bankroll_dynamic=False)
    assert apply_dynamic_bankroll(s, root, "live") == pytest.approx(1000.0)


def test_negative_balance_floors_at_zero(tmp_path):
    """Una banca negativa propagaba stakes NEGATIVOS al stake plano, y settle
    grada una perdida como pnl=-stake (POSITIVO), realimentando el ledger
    (auditoria 2026-07-29, B-06)."""
    root = _ledger(tmp_path, [_row(-5000.0)])
    s = _S()
    assert apply_dynamic_bankroll(s, root, "live") == 0.0


def test_demo_settled_rows_never_move_the_real_bankroll(tmp_path):
    root = _ledger(tmp_path, [_row(-84.25, label="demo_synthetic")])
    s = _S()
    assert apply_dynamic_bankroll(s, root, "live") == pytest.approx(1000.0)


def test_both_entrypoints_call_the_same_helper():
    """Candado estructural: si alguien reintroduce la logica inline en cualquiera
    de los dos scripts, este test lo señala."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for name in ("run_all.py", "run_daily.py"):
        src = (root / "scripts" / name).read_text(encoding="utf-8")
        assert "apply_dynamic_bankroll" in src, f"{name} no usa el helper compartido"
        assert "BankrollLedger(" not in src, (
            f"{name} instancia el ledger directamente: la logica volvio a "
            f"duplicarse fuera del helper")
