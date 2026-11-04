"""AUD-005, AUD-010 y AUD-011 (audit-2026-11-03, lote G2)."""
from __future__ import annotations

import math

import pandas as pd
import pytest

from sqp.evaluation.tipster import tipster_table
from sqp.markets.settlement_math import SettlementProbabilities
from sqp.pipeline.daily import _ev_ejecucion_no_positivo
from sqp.risk.kelly import edge, kelly_fraction_stake, stake_price
from sqp.settlement.settle import settle_candidates


# ---- AUD-005 --------------------------------------------------------------
def test_stake_price_toma_el_menor_y_tolera_ejecucion_invalida():
    assert stake_price(1.95, 2.05) == 1.95
    assert stake_price(1.95, 1.85) == 1.85
    assert stake_price(1.95, float("nan")) == 1.95
    assert stake_price(1.95, None) == 1.95
    assert stake_price(1.95, 1.0) == 1.95
    assert stake_price(1.95, float("inf")) == 1.95


def test_kelly_a_precio_de_ejecucion_menor_no_apuesta():
    assert kelly_fraction_stake(0.54, stake_price(1.95, 1.85), 1000, 0.08,
                                0.02, 0.02) == (0.0, 0.0)
    stake, _ = kelly_fraction_stake(0.54, 1.95, 1000, 0.08, 0.02, 0.02)
    assert stake == pytest.approx(4.46, abs=0.01)


def test_guarda_ev_ejecucion():
    assert _ev_ejecucion_no_positivo(5.0, 0.54, 1.85) is True
    assert _ev_ejecucion_no_positivo(5.0, 0.54, 1.95) is False
    assert _ev_ejecucion_no_positivo(0.0, 0.54, 1.85) is False
    assert _ev_ejecucion_no_positivo(5.0, 0.54, float("nan")) is False


def _cand(**kw):
    base = {"event_id": "e1", "market": "h2h", "selection": "Home", "line": None,
            "price_decimal": 1.95, "stake": 10.0, "home": "Home", "away": "Away"}
    base.update(kw)
    return pd.DataFrame([base])


SCORES = {"e1": (3, 1, "Home")}


def test_liquida_al_precio_de_ejecucion():
    out = settle_candidates(_cand(settle_price=1.85), SCORES)
    assert out.iloc[0]["result"] == "win"
    assert out.iloc[0]["pnl"] == pytest.approx(8.5)


def test_fila_sin_settle_price_liquida_como_siempre():
    assert settle_candidates(_cand(), SCORES).iloc[0]["pnl"] == pytest.approx(9.5)
    for v in (float("nan"), 1.0, 0.0):
        out = settle_candidates(_cand(settle_price=v), SCORES)
        assert out.iloc[0]["pnl"] == pytest.approx(9.5)


def test_half_win_usa_settle_price(monkeypatch):
    import sqp.settlement.settle as s
    monkeypatch.setattr(s, "_grade", lambda *a, **k: "half_win")
    out = settle_candidates(_cand(settle_price=1.85), SCORES)
    assert out.iloc[0]["pnl"] == pytest.approx(4.25)
    out = settle_candidates(_cand(), SCORES)
    assert out.iloc[0]["pnl"] == pytest.approx(4.75)


# ---- AUD-010 --------------------------------------------------------------
def _stream(**kw):
    base = {"league": "nba", "event_id": "e1", "home": "A", "away": "B",
            "start_time": "2026-11-04T01:00:00Z", "game_date": "2026-11-04",
            "market": "h2h", "selection": "A", "line": None,
            "price_decimal": 1.95, "calibrated_probability": 0.52,
            "estimated_probability": 0.52, "implied_probability_novig": 0.49,
            "books_count": 12}
    base.update(kw)
    return pd.DataFrame([base])


def test_tipster_descarta_lo_que_el_motor_de_riesgo_descarta():
    t = tipster_table(_stream(adjusted_edge=0.0035), min_edge=0.02)
    assert t.iloc[0]["tier"] == "NO BET"
    assert t.iloc[0]["ev_riesgo"] == pytest.approx(0.0035)
    assert "motor de riesgo" in t.iloc[0]["motivo"]


def test_tipster_fila_legada_sigue_igual_con_sufijo():
    t = tipster_table(_stream(), min_edge=0.02)
    assert t.iloc[0]["tier"] == "B"
    assert t.iloc[0]["motivo"].endswith("(pre-penalización)")
    assert math.isnan(t.iloc[0]["ev_riesgo"])


def test_tipster_usa_precio_de_ejecucion():
    t = tipster_table(_stream(calibrated_probability=0.54,
                              estimated_probability=0.54, adjusted_edge=0.053,
                              execution_price=1.85), min_edge=0.02)
    assert t.iloc[0]["ev_riesgo"] == pytest.approx(-0.0010, abs=1e-4)
    assert t.iloc[0]["tier"] == "NO BET"


def test_tipster_sin_min_edge_no_descarta():
    t = tipster_table(_stream(adjusted_edge=0.0035))
    assert t.iloc[0]["tier"] == "B"


# ---- AUD-011 --------------------------------------------------------------
def test_edge_es_ev_por_unidad_resuelta():
    sp = SettlementProbabilities(full_win=0.45, push=0.10, full_loss=0.45)
    p = sp.decision_probability
    assert p == pytest.approx(0.5)
    e = edge(p, 1.909)
    assert e == pytest.approx(-0.0455, abs=1e-4)
    assert sp.expected_value(1.909) == pytest.approx(e * 0.9, abs=1e-6)
    assert sp.expected_value(1.909) == pytest.approx(-0.04095, abs=1e-5)



def test_served_store_reconcilia_cabecera_vieja_una_sola_vez(tmp_path, monkeypatch):
    """Revision Fable de AUD-010: con una cabecera vieja (sin adjusted_edge) el
    primer guardado reconcilia y reescribe UNA vez; despues la cabecera iguala a
    COLUMNS y los guardados siguientes son append (sin reescrituras)."""
    import csv
    import pandas as pd
    import sqp.storage.served_store as ss

    store = ss.ServedStore(tmp_path)
    p = store.served_path("wnba")
    p.parent.mkdir(parents=True, exist_ok=True)
    old = [c for c in ss.COLUMNS if c != "adjusted_edge"]
    row = {c: "" for c in old}
    row.update(league="wnba", event_id="e0", market="h2h", selection="A", line="",
               generated_at="2026-11-01T12:00:00Z", start_time="2026-11-01T20:00:00Z",
               price_decimal=1.9)
    pd.DataFrame([row], columns=old).to_csv(p, index=False)
    writes = {"n": 0}
    orig = ss._atomic_write_csv

    def spy(df, path):
        writes["n"] += 1
        return orig(df, path)

    monkeypatch.setattr(ss, "_atomic_write_csv", spy)
    for i in range(1, 4):
        r = dict(row, event_id=f"e{i}", generated_at=f"2026-11-0{i + 1}T12:00:00Z",
                 adjusted_edge=0.01)
        store.append_served("wnba", [r])
    with p.open(newline="", encoding="utf-8") as fh:
        header = next(csv.reader(fh))
    assert writes["n"] == 1
    assert header == list(ss.COLUMNS) and header[-1] == "market_shrink"
    assert len(pd.read_csv(p)) == 4


def test_classify_sin_ev_riesgo_conserva_el_motivo_de_siempre():
    """Las llamadas antiguas (sin ev_riesgo) no cambian: el clasificador
    congelado del pre-registro tier A depende del motivo exacto."""
    from sqp.evaluation.tipster import classify
    assert classify(0.05, 0.03, 20, 0.55, 0.075) == ("A", "edge solido con consenso profundo")
    tier, motivo = classify(0.05, 0.03, 20, 0.55, 0.075, ev_riesgo=float("nan"))
    assert tier == "A" and motivo.endswith("(pre-penalización)")

