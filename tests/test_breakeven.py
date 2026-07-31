"""Punto de equilibrio por cuota (decision 2026-07-31).

El hit rate solo significa algo comparado con lo que la CUOTA exige. A 2.50
basta 40%; a 1.07 hace falta 93.5%. Juzgar los picks contra un umbral fijo fue
lo que llevo al modo accuracy a subir el hit rate perdiendo dinero.
"""
from __future__ import annotations

import pandas as pd
import pytest

from sqp.audit.report import _segment_audit, breakeven_probability


# --- Punto de equilibrio por pick ---------------------------------------------

@pytest.mark.parametrize("price,expected", [
    (2.50, 0.40),   # underdog: basta acertar 40%
    (2.00, 0.50),
    (1.50, 0.6667),
    (1.07, 0.9346),  # favorito extremo del modo accuracy
])
def test_breakeven_is_the_inverse_of_the_price(price, expected):
    assert breakeven_probability(price) == pytest.approx(expected, abs=1e-4)


def test_breakeven_is_none_for_degenerate_prices():
    """Una cuota <= 1.0 no paga nada: no tiene punto de equilibrio."""
    assert breakeven_probability(1.0) is None
    assert breakeven_probability(0.0) is None
    assert breakeven_probability(None) is None


# --- Agregado en el reporte por segmento --------------------------------------

def _settled(rows: list[tuple[str, float]]) -> pd.DataFrame:
    """rows = [(result, price_decimal), ...] con stake plano de 10."""
    return pd.DataFrame([
        {"league": "mlb", "market": "h2h", "result": r, "price_decimal": p,
         "stake": 10.0, "pnl": (10.0 * (p - 1) if r == "win" else -10.0),
         "estimated_edge": 0.05, "estimated_probability": 0.5}
        for r, p in rows])


def test_segment_audit_reports_the_required_hit_rate():
    # 4 picks a cuota 2.00 -> se necesita 50%
    df = _settled([("win", 2.0), ("loss", 2.0), ("win", 2.0), ("loss", 2.0)])
    out = _segment_audit(df, ["league"])
    assert out["breakeven_hit_rate"].iloc[0] == pytest.approx(0.50)
    assert out["hit_rate"].iloc[0] == pytest.approx(0.50)


def test_gap_is_positive_when_beating_the_breakeven():
    """45% a cuota 2.50 (necesita 40%) es rentable aunque falle la mayoria."""
    rows = [("win", 2.5)] * 45 + [("loss", 2.5)] * 55
    out = _segment_audit(_settled(rows), ["league"])
    assert out["hit_rate"].iloc[0] == pytest.approx(0.45)
    assert out["breakeven_hit_rate"].iloc[0] == pytest.approx(0.40)
    assert out["hit_rate_vs_breakeven"].iloc[0] > 0
    assert out["realized_roi"].iloc[0] > 0  # coherencia con el ROI real


def test_gap_is_negative_when_hit_rate_looks_great_but_loses_money():
    """88% a cuota 1.07 (necesita 93.5%) pierde dinero. Es el caso que motivo
    revertir el modo accuracy."""
    rows = [("win", 1.07)] * 88 + [("loss", 1.07)] * 12
    out = _segment_audit(_settled(rows), ["league"])
    assert out["hit_rate"].iloc[0] == pytest.approx(0.88)
    assert out["breakeven_hit_rate"].iloc[0] == pytest.approx(0.9346, abs=1e-4)
    assert out["hit_rate_vs_breakeven"].iloc[0] < 0
    assert out["realized_roi"].iloc[0] < 0


def test_gap_sign_agrees_with_roi_when_the_odds_are_homogeneous():
    """Con cuotas iguales, gap y ROI coinciden en signo EXACTAMENTE."""
    rows = [("win", 2.0)] * 55 + [("loss", 2.0)] * 45   # 55% donde se pide 50%
    out = _segment_audit(_settled(rows), ["league"])
    assert out["hit_rate_vs_breakeven"].iloc[0] > 0
    assert out["realized_roi"].iloc[0] > 0


def test_gap_and_roi_can_diverge_with_heterogeneous_odds():
    """LIMITACION CONOCIDA, verificada en datos reales (totals: gap -2.0% con
    ROI +4.7%): `mean(1/precio)` es el equilibrio exacto solo si los aciertos se
    reparten uniformemente entre cuotas. Si caen en las cuotas largas, se gana
    dinero acertando menos de lo que el promedio exigia.

    El gap es una lectura interpretable; el ROI realizado es la cifra
    autoritativa. Este test fija esa divergencia como comportamiento esperado
    para que nadie la 'corrija' asumiendo que es un bug."""
    # Todos los aciertos en la cuota larga, todos los fallos en la corta.
    rows = [("win", 4.0)] * 30 + [("loss", 1.4)] * 70
    out = _segment_audit(_settled(rows), ["league"])
    gap = out["hit_rate_vs_breakeven"].iloc[0]
    roi = out["realized_roi"].iloc[0]
    assert gap < 0, "acerto 30% donde el promedio pedia mas"
    assert roi > 0, "y aun asi gano dinero, por acertar en las cuotas largas"


def test_segment_audit_without_price_column_still_works():
    """Historico antiguo sin price_decimal: no debe reventar el reporte."""
    df = _settled([("win", 2.0), ("loss", 2.0)]).drop(columns=["price_decimal"])
    out = _segment_audit(df, ["league"])
    assert not out.empty
    assert "hit_rate" in out.columns
