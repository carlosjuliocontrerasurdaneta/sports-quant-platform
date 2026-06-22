"""HTML dashboard: three tabs, stats bar, and pick rows from real candidate data."""
import json

import pandas as pd

from sqp.audit import html_report, patterns
from sqp.audit.html_report import html_dashboard, open_in_browser


def _candidates() -> pd.DataFrame:
    return pd.DataFrame([
        {"event_id": "e1", "market": "spreads", "selection": "A", "line": -2.5,
         "price_decimal": 1.91, "model_probability": 0.57,
         "estimated_probability": 0.58, "implied_probability_novig": 0.50,
         "estimated_edge": 0.10, "kelly_stake_pct": 0.01, "stake": 9.0,
         "data_label": "real", "flags": ""},
        {"event_id": "e1", "market": "h2h", "selection": "A", "line": None,
         "price_decimal": 3.5, "model_probability": 0.5,
         "estimated_probability": 0.5, "implied_probability_novig": 0.30,
         "estimated_edge": 0.75, "kelly_stake_pct": 0.0, "stake": 0.0,
         "data_label": "real", "flags": "edge_exceeds_max_plausible"},
        {"event_id": "e2", "market": "totals", "selection": "Over", "line": 8.5,
         "price_decimal": 2.0, "model_probability": 0.54,
         "estimated_probability": 0.55, "implied_probability_novig": 0.50,
         "estimated_edge": 0.10, "kelly_stake_pct": 0.012, "stake": 12.0,
         "data_label": "real", "flags": ""},
    ])


def _settled() -> pd.DataFrame:
    return pd.DataFrame([
        {"event_id": "e1", "league": "nba", "market": "spreads", "selection": "A",
         "line": -2.5, "price_decimal": 1.91, "stake": 10.0, "result": "win",
         "pnl": 9.1, "estimated_edge": 0.10, "estimated_probability": 0.58,
         "settled_at": "2026-06-12T03:00:00+00:00"},
        {"event_id": "e2", "league": "nba", "market": "h2h", "selection": "B",
         "line": None, "price_decimal": 2.1, "stake": 10.0, "result": "loss",
         "pnl": -10.0, "estimated_edge": 0.08, "estimated_probability": 0.52,
         "settled_at": "2026-06-13T03:00:00+00:00"},
    ])


def _write_inputs(tmp_path):
    pred = tmp_path / "predictions"
    bets = tmp_path / "bets"
    pred.mkdir()
    bets.mkdir()
    _candidates().to_csv(pred / "candidates_nba.csv", index=False)
    pd.DataFrame([{"event_id": "e1", "home": "A", "away": "B"},
                  {"event_id": "e2", "home": "C", "away": "D"}]).to_csv(
        pred / "predictions_nba.csv", index=False)
    _settled().to_csv(bets / "settled_nba.csv", index=False)
    return pred, bets


def test_dashboard_has_four_tabs_and_stats_bar(tmp_path):
    pred, bets = _write_inputs(tmp_path)
    path = html_dashboard(pred, bets)
    text = open(path, encoding="utf-8").read()
    assert path.endswith(".html")
    for tab in ("Picks del Dia", "Auditoria", "Patrones", "Historial"):
        assert tab in text
    for stat in ("Mejor EV", "EV promedio", "Kelly promedio"):
        assert stat in text


def test_dashboard_patterns_tab_renders_history(tmp_path, monkeypatch):
    pred, bets = _write_inputs(tmp_path)
    hist = pd.DataFrame(
        [{"league": "nba", "date": "2026-01-01", "market": "spreads",
          "side": "away", "selection": "A", "line": -2.5, "price_decimal": 1.9,
          "estimated_probability": 0.55, "estimated_edge": 0.05, "stake": 1.0,
          "result": "win", "pnl": 0.9}]
        + [{"league": "nba", "date": "2026-01-02", "market": "totals",
            "side": "Over", "selection": "", "line": 8.5, "price_decimal": 2.0,
            "estimated_probability": 0.52, "estimated_edge": 0.04, "stake": 1.0,
            "result": "loss", "pnl": -1.0}])
    hist_csv = tmp_path / "pick_history.csv"
    hist.to_csv(hist_csv, index=False)
    # point the dashboard's pattern loader at the fixture history
    monkeypatch.setattr(patterns, "PICK_HISTORY_PATH", hist_csv)
    text = open(html_dashboard(pred, bets), encoding="utf-8").read()
    assert "Aciertos por tipo de mercado" in text
    assert "Lectura" in text


def test_dashboard_patterns_tab_empty_is_safe(tmp_path, monkeypatch):
    pred, bets = _write_inputs(tmp_path)
    monkeypatch.setattr(patterns, "PICK_HISTORY_PATH",
                        tmp_path / "absent.csv")
    text = open(html_dashboard(pred, bets), encoding="utf-8").read()
    assert "Sin historial consolidado" in text


def test_dashboard_embeds_only_actionable_picks(tmp_path):
    pred, bets = _write_inputs(tmp_path)
    path = html_dashboard(pred, bets)
    text = open(path, encoding="utf-8").read()
    start = text.index("const DATA = ") + len("const DATA = ")
    end = text.index(";\nconst COLS", start)
    data = json.loads(text[start:end])
    # the flagged 0.75-edge pick is excluded; only the two actionable picks remain
    assert len(data["picks"]) == 2
    assert all(p["league"] == "nba" for p in data["picks"])
    assert 0.75 not in {p["estimated_edge"] for p in data["picks"]}
    # partido is built from home/away
    assert any(" @ " in p["partido"] for p in data["picks"])


def test_dashboard_has_per_sport_toggle_tags(tmp_path):
    pred, bets = _write_inputs(tmp_path)
    text = open(html_dashboard(pred, bets), encoding="utf-8").read()
    # The tag pills are rendered client-side from DATA.picks (like project 2), so
    # assert the machinery + container are present and the old dropdown is gone.
    assert 'id="sportTags"' in text and "buildSportTags()" in text
    assert "toggleSport(" in text and "activeSports" in text
    assert 'id="fSport"' not in text                        # dropdown replaced by tags
    # the league each tag is built from is embedded in the picks payload
    assert '"league": "nba"' in text or '"league":"nba"' in text


def test_dashboard_audit_and_history_render(tmp_path):
    pred, bets = _write_inputs(tmp_path)
    text = open(html_dashboard(pred, bets), encoding="utf-8").read()
    assert "ROI realizado" in text          # audit segment
    assert "2026-06-13" in text             # history row (most recent first)


def test_dashboard_empty_is_safe(tmp_path):
    pred = tmp_path / "predictions"
    bets = tmp_path / "bets"
    pred.mkdir()
    bets.mkdir()
    text = open(html_dashboard(pred, bets), encoding="utf-8").read()
    assert "Sin candidatos accionables" in text
    assert "Sin apuestas liquidadas" in text


def test_dashboard_writes_stable_latest_copy(tmp_path):
    pred, bets = _write_inputs(tmp_path)
    dated = html_dashboard(pred, bets)
    latest = pred / "report_latest.html"
    assert latest.exists()
    # the stable bookmark holds exactly the same page as the dated file
    assert latest.read_text(encoding="utf-8") == open(dated, encoding="utf-8").read()


def test_dashboard_can_skip_latest_copy(tmp_path):
    pred, bets = _write_inputs(tmp_path)
    html_dashboard(pred, bets, make_latest=False)
    assert not (pred / "report_latest.html").exists()


def test_open_in_browser_is_best_effort(monkeypatch, tmp_path):
    target = tmp_path / "report_latest.html"
    target.write_text("<html></html>", encoding="utf-8")
    opened: list[str] = []
    monkeypatch.setattr(html_report.webbrowser, "open",
                        lambda uri: opened.append(uri) or True)
    assert open_in_browser(target) is True
    assert opened and opened[0].startswith("file:")

    # a failing platform must be swallowed, not raised
    def boom(uri):
        raise RuntimeError("no browser")
    monkeypatch.setattr(html_report.webbrowser, "open", boom)
    assert open_in_browser(target) is False
