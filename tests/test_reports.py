"""Consolidated picks report and realized-ROI settlement audit."""
import pandas as pd

from sqp.audit.report import (consolidated_report, rank_candidates,
                              settlement_audit_report)


def _candidates() -> pd.DataFrame:
    return pd.DataFrame([
        {"event_id": "e1", "market": "spreads", "selection": "A", "line": -2.5,
         "price_decimal": 1.91, "estimated_probability": 0.58,
         "implied_probability_novig": 0.50, "estimated_edge": 0.10,
         "kelly_stake_pct": 0.01, "stake": 9.0, "data_label": "real", "flags": ""},
        {"event_id": "e1", "market": "h2h", "selection": "A", "line": None,
         "price_decimal": 3.5, "estimated_probability": 0.5,
         "implied_probability_novig": 0.30, "estimated_edge": 0.75,
         "kelly_stake_pct": 0.0, "stake": 0.0, "data_label": "real",
         "flags": "edge_exceeds_max_plausible"},
        {"event_id": "e2", "market": "totals", "selection": "Over", "line": 8.5,
         "price_decimal": 2.0, "estimated_probability": 0.55,
         "implied_probability_novig": 0.50, "estimated_edge": 0.10,
         "kelly_stake_pct": 0.012, "stake": 12.0, "data_label": "real", "flags": ""},
        # Bet whose stake was reduced by the daily exposure cap: still a real,
        # positive-stake bet and MUST count as actionable (regression: previously
        # the flags=="" filter hid every scaled pick, i.e. a whole league on a
        # day the cap triggers).
        {"event_id": "e3", "market": "h2h", "selection": "Scaled", "line": None,
         "price_decimal": 1.95, "estimated_probability": 0.56,
         "implied_probability_novig": 0.51, "estimated_edge": 0.09,
         "kelly_stake_pct": 0.006, "stake": 6.0, "data_label": "real",
         "flags": "daily_exposure_scaled"},
    ])


def test_rank_candidates_keeps_scaled_excludes_zero_stake():
    ranked = rank_candidates(_candidates())
    # Both unflagged picks AND the daily_exposure_scaled pick are actionable;
    # only the zero-stake (edge_exceeds_max_plausible) row is dropped.
    assert set(ranked["selection"]) == {"A", "Over", "Scaled"}
    assert (ranked["stake"] > 0).all()
    assert "daily_exposure_scaled" in set(ranked["flags"])  # scaled bet retained
    # the zero-stake flagged 0.75-edge row is gone
    assert 0.75 not in set(ranked["estimated_edge"])


def test_consolidated_report_writes_file(tmp_path):
    _candidates().to_csv(tmp_path / "candidates_nba.csv", index=False)
    pd.DataFrame([{"event_id": "e1", "home": "A", "away": "B"},
                  {"event_id": "e2", "home": "C", "away": "D"}]).to_csv(
        tmp_path / "predictions_nba.csv", index=False)
    path = consolidated_report(tmp_path, top=100)
    text = open(path, encoding="utf-8").read()
    assert "Reporte consolidado" in text
    assert "Picks accionables" in text
    assert "nba" in text


def test_consolidated_report_empty_is_safe(tmp_path):
    path = consolidated_report(tmp_path)
    assert "sin candidatos" in open(path, encoding="utf-8").read()


def test_settlement_audit_report(tmp_path):
    pd.DataFrame([
        {"league": "nba", "market": "spreads", "result": "win", "stake": 10.0,
         "pnl": 9.1, "estimated_edge": 0.10, "estimated_probability": 0.58},
        {"league": "nba", "market": "h2h", "result": "loss", "stake": 10.0,
         "pnl": -10.0, "estimated_edge": 0.08, "estimated_probability": 0.52},
        {"league": "mlb", "market": "totals", "result": "push", "stake": 10.0,
         "pnl": 0.0, "estimated_edge": 0.05, "estimated_probability": 0.51},
    ]).to_csv(tmp_path / "settled_nba.csv", index=False)
    path = settlement_audit_report(tmp_path)
    text = open(path, encoding="utf-8").read()
    assert "Auditoria de liquidacion" in text
    assert "ROI realizado" in text
    assert "Por liga" in text


def test_settlement_audit_empty_is_safe(tmp_path):
    path = settlement_audit_report(tmp_path)
    assert "sin apuestas liquidadas" in open(path, encoding="utf-8").read()
