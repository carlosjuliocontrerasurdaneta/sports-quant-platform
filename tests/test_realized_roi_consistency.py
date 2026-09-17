"""AUD-002 (auditoria integral 2026-09-17): una sola definicion de ROI realizado.

Tras AUD-MED-002 (medias victorias/derrotas de las lineas asiaticas de cuarto)
coexistian tres definiciones: `runner.realized_roi` (medias en numerador y
denominador), `roi_engine._summarize` y el dashboard (pnl de TODAS las filas
sobre el stake de win/loss -> una `half_win` sola daba 0,0 y mezclada con una
`win` DUPLICABA el ROI) y `audit/report.py` (medias fuera de ambos lados).
"""
from pathlib import Path

import pandas as pd
import pytest

from sqp.audit.report import _segment_audit, settlement_audit_report
from sqp.backtesting.roi_engine import _summarize
from sqp.settlement.runner import realized_roi
from sqp.settlement.settle import realized_roi_parts, settle_candidates


def _half_win_row():
    row = dict(league="t", event_id="e", home="A", away="B", market="spreads",
               selection="A", line=-0.75, price_decimal=2.0, stake=20.0,
               estimated_probability=0.6, estimated_edge=0.2, data_label="real",
               generated_at="2026-09-17T00:00:00+00:00", game_date="2026-09-17")
    settled = settle_candidates(pd.DataFrame([row]), {"e": (1, 0, "A")}, True)
    assert settled["result"].iloc[0] == "half_win" and settled["pnl"].iloc[0] == 10.0
    return settled


def test_half_win_alone_has_the_same_roi_everywhere():
    s = _half_win_row()
    assert realized_roi_parts(s) == (10.0, 20.0)
    assert realized_roi(s) == pytest.approx(0.5)
    summary = _summarize("t", s, 1)
    assert summary["realized_roi"] == pytest.approx(0.5)
    assert summary["staked"] == 20.0 and summary["pnl"] == 10.0
    seg = _segment_audit(s, ["league"])
    assert seg["realized_roi"].iloc[0] == pytest.approx(0.5)
    assert seg["n"].iloc[0] == 0          # una media no es acierto ni fallo
    assert pd.isna(seg["hit_rate"].iloc[0])


def test_mixed_half_and_full_results_do_not_double_the_roi(tmp_path):
    s = _half_win_row()
    mixed = pd.concat([s, s.assign(result="win", pnl=20.0),
                       s.assign(result="push", pnl=0.0),
                       s.assign(result="void", pnl=0.0)], ignore_index=True)
    # 30 de pnl sobre 40 de stake arriesgado; push/void fuera de ambos lados.
    assert realized_roi(mixed) == pytest.approx(0.75)
    summary = _summarize("t", mixed, 4)
    assert summary["realized_roi"] == pytest.approx(0.75)
    assert summary["by_market"]["realized_roi"].iloc[0] == pytest.approx(0.75)
    seg = _segment_audit(mixed, ["league"])
    assert seg["realized_roi"].iloc[0] == pytest.approx(0.75)
    assert seg["n"].iloc[0] == 1 and seg["wins"].iloc[0] == 1
    mixed.to_csv(tmp_path / "settled_t.csv", index=False)
    report = Path(settlement_audit_report(tmp_path)).read_text(encoding="utf-8")
    assert "ROI realizado: 75.00%" in report


def test_push_and_void_only_means_no_roi():
    s = _half_win_row()
    only = pd.concat([s.assign(result="push", pnl=0.0), s.assign(result="void", pnl=0.0)],
                     ignore_index=True)
    assert realized_roi_parts(only) == (0.0, 0.0)
    assert realized_roi(only) == 0.0
    assert _summarize("t", only, 2)["realized_roi"] == 0.0
    assert _segment_audit(only, ["league"]).empty
