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
        # Shadow-mode pick: stake forced to 0 but it IS the day's pick and must
        # stay visible in reports (regression: the stake>0 filter blanked the
        # whole dashboard on 2026-07-04, the first shadow day).
        {"event_id": "e4", "market": "h2h", "selection": "Shadow", "line": None,
         "price_decimal": 2.1, "estimated_probability": 0.52,
         "implied_probability_novig": 0.48, "estimated_edge": 0.04,
         "kelly_stake_pct": 0.0, "stake": 0.0, "data_label": "real",
         "flags": "shadow_mode"},
    ])


def test_rank_candidates_keeps_scaled_excludes_zero_stake():
    ranked = rank_candidates(_candidates())
    # Unflagged picks, the daily_exposure_scaled pick AND shadow picks are all
    # visible; only the blocking zero-stake flags are dropped.
    assert set(ranked["selection"]) == {"A", "Over", "Scaled", "Shadow"}
    assert "daily_exposure_scaled" in set(ranked["flags"])  # scaled bet retained
    assert "shadow_mode" in set(ranked["flags"])            # shadow pick visible
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


def test_consolidated_report_excludes_prior_day_candidates(tmp_path, monkeypatch):
    old = _candidates().iloc[:1].copy()
    old["generated_at"] = "2026-07-09T12:00:00+00:00"
    old.to_csv(tmp_path / "candidates_nba.csv", index=False)
    # The report derives its UTC date internally. Pin its datetime source.
    class _Now:
        @classmethod
        def now(cls, tz=None):
            return pd.Timestamp("2026-07-10T12:00:00Z").to_pydatetime()
    import sqp.audit.report as report
    monkeypatch.setattr(report, "datetime", _Now)
    path = consolidated_report(tmp_path)
    texto = open(path, encoding="utf-8").read()
    # CONTRATO CAMBIADO el 2026-08-26. Antes se exigia que el reporte quedara
    # VACIO ("sin candidatos generados") cuando los candidatos no eran de hoy.
    # Ese vaciado dejaba al operador sin informacion y sin saber por que -- es
    # el mismo silencio que le hizo creer durante 53 dias que el sistema no
    # generaba nada. Ahora se MUESTRAN, con un aviso explicito de que son de
    # otro dia; lo que no se puede es presentarlos como si fueran de hoy.
    assert "ATENCION" in texto
    assert "2026-07-09" in texto
    assert "no de hoy" in texto


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
