"""AUD-008 (ronda audit-2026-10-18): lineas de cuarto graduadas win/loss antes
del arreglo de su liquidacion dejan de contar en el gate y en la calibracion."""
from __future__ import annotations

import pandas as pd

from sqp.risk.prediction_gate import _usable
from sqp.settlement.quarter_line_fix import (QUARTER_LINE_GRADING_FIXED_AT,
                                             pre_fix_quarter_line_mask)

ANTES = "2026-09-06T12:00:00+00:00"
DESPUES = "2026-09-20T12:00:00+00:00"


def _row(market: str, line, gen: str, result: str = "win") -> dict:
    return {"league": "laliga", "market": market, "line": line, "generated_at": gen,
            "game_date": gen[:10], "event_id": f"e-{market}-{line}-{gen}",
            "result": result, "model_probability": 0.55,
            "implied_probability_novig": 0.5, "price_decimal": 1.95}


def test_mask_selects_only_pre_fix_quarter_lines():
    df = pd.DataFrame([
        _row("totals", -0.75, ANTES),     # cuarto, antes  -> fuera
        _row("spreads", 2.25, ANTES),     # cuarto, antes  -> fuera
        _row("totals", 2.5, ANTES),       # media linea    -> dentro
        _row("totals", 2.0, ANTES),       # entera         -> dentro
        _row("h2h", None, ANTES),         # sin linea      -> dentro
        _row("totals", 2.75, DESPUES),    # cuarto, despues -> dentro
        _row("totals", 2.75, QUARTER_LINE_GRADING_FIXED_AT),   # en el corte -> dentro
        _row("totals", 2.75, "ilegible"),  # sin fecha      -> fuera (default-deny)
    ])
    assert pre_fix_quarter_line_mask(df).tolist() == [
        True, True, False, False, False, False, False, True]


def test_gate_usable_drops_a_pre_fix_quarter_line_win():
    df = pd.DataFrame([_row("totals", -0.75, ANTES), _row("totals", 2.5, ANTES)])
    out = _usable(df, "2026-01-01")
    assert out["line"].tolist() == [2.5]


def test_calibration_stream_drops_pre_fix_quarter_lines(tmp_path):
    from sqp.calibration.data import _load_graded_served

    pd.DataFrame([_row("totals", -0.75, ANTES) | {"data_label": "real"},
                  _row("totals", -0.75, DESPUES) | {"data_label": "real"}]
                 ).to_csv(tmp_path / "graded_laliga.csv", index=False)
    out = _load_graded_served(tmp_path)
    assert out["generated_at"].tolist() == [DESPUES]
