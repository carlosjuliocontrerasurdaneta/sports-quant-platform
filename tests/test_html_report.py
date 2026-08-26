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
         "game_date": "2026-06-12", "home": "A", "away": "B",
         "settled_at": "2026-06-12T03:00:00+00:00"},
        {"event_id": "e2", "league": "nba", "market": "h2h", "selection": "D",
         "line": None, "price_decimal": 2.1, "stake": 10.0, "result": "loss",
         "pnl": -10.0, "estimated_edge": 0.08, "estimated_probability": 0.52,
         "game_date": "2026-06-13", "home": "C", "away": "D",
         "settled_at": "2026-06-13T03:00:00+00:00"},
        {"event_id": "e3", "league": "nba", "market": "totals", "selection": "Over",
         "line": 220.5, "price_decimal": 1.95, "stake": 10.0, "result": "win",
         "pnl": 9.5, "estimated_edge": 0.06, "estimated_probability": 0.55,
         "game_date": "2026-06-13", "home": "E", "away": "F",
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


def _write_inputs_with_dates(tmp_path):
    """Same fixtures but the predictions CSV carries start_time: e1 today,
    e2 six days out (a soccer matchday within the 7-day event horizon)."""
    from datetime import datetime, timedelta, timezone
    pred = tmp_path / "predictions"
    bets = tmp_path / "bets"
    pred.mkdir()
    bets.mkdir()
    _candidates().to_csv(pred / "candidates_nba.csv", index=False)
    now = datetime.now(timezone.utc)
    st1 = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    st2 = (now + timedelta(days=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
    pd.DataFrame([
        {"event_id": "e1", "home": "A", "away": "B", "start_time": st1},
        {"event_id": "e2", "home": "C", "away": "D", "start_time": st2},
    ]).to_csv(pred / "predictions_nba.csv", index=False)
    _settled().to_csv(bets / "settled_nba.csv", index=False)
    return pred, bets, st1, st2


def _payload(text: str) -> dict:
    start = text.index("const DATA = ") + len("const DATA = ")
    end = text.index(";\nconst COLS", start)
    return json.loads(text[start:end])


def test_dashboard_picks_carry_local_event_date(tmp_path):
    # fecha = the event's LOCAL calendar date (a west-coast night game commences
    # after 00:00Z; grouping by the UTC date would file it under "tomorrow")
    from datetime import datetime
    pred, bets, st1, st2 = _write_inputs_with_dates(tmp_path)
    data = _payload(open(html_dashboard(pred, bets), encoding="utf-8").read())
    def local_date(st):
        return (datetime.fromisoformat(st.replace("Z", "+00:00"))
                .astimezone().date().isoformat())
    got = {p["partido"]: p["fecha"] for p in data["picks"]}
    assert got["B @ A"] == local_date(st1)
    assert got["D @ C"] == local_date(st2)
    # the generation day travels with the payload so "Hoy" is anchored to the
    # run, not to whenever the file is opened
    assert data["today"] == datetime.now().date().isoformat()
    assert any(c["key"] == "fecha" for c in data["columns"])


def test_dashboard_has_event_date_pills_defaulting_to_today(tmp_path):
    pred, bets, _, _ = _write_inputs_with_dates(tmp_path)
    text = open(html_dashboard(pred, bets), encoding="utf-8").read()
    # date pills machinery mirrors the sport pills; default view = today only
    assert 'id="dateTags"' in text and "buildDateTags()" in text
    assert "toggleDate(" in text and "activeDates" in text
    assert "DATA.today" in text


def test_dashboard_picks_without_start_time_are_safe(tmp_path):
    # legacy predictions CSV without start_time: fecha degrades to "" and the
    # dashboard still renders (the empty date is selectable, never dropped)
    pred, bets = _write_inputs(tmp_path)
    text = open(html_dashboard(pred, bets), encoding="utf-8").read()
    data = _payload(text)
    assert all(p["fecha"] == "" for p in data["picks"])
    assert "Picks del Dia" in text


def test_dashboard_has_five_tabs_and_stats_bar(tmp_path):
    pred, bets = _write_inputs(tmp_path)
    path = html_dashboard(pred, bets)
    text = open(path, encoding="utf-8").read()
    assert path.endswith(".html")
    for tab in ("Picks del Dia", "Auditoria", "Diagnostico", "Patrones",
                "Historial"):
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


def test_dashboard_embeds_every_candidate_with_its_state(tmp_path):
    """CONTRATO CAMBIADO el 2026-08-26 por decision del operador.

    Antes se llamaba `test_dashboard_embeds_only_actionable_picks` y exigia lo
    contrario: que la pestana mostrara SOLO los accionables. Ese contrato dejo
    la pestana EN BLANCO desde el 2026-08-16, cuando al levantar shadow_mode
    desaparecio el flag que mantenia visibles los picks de stake 0. El operador
    paso 53 dias creyendo que el sistema no generaba nada; generaba 63
    candidatos al dia, ninguno con dinero.

    Ahora se embeben TODOS los candidatos y cada uno lleva en `estado` la razon
    de su stake. El contador `Total accionables` del reporte markdown sigue
    contando solo los que llevarian dinero -- ver
    tests/test_picks_del_dia.py::TestNoSeTocoElContadorDeAccionables.
    """
    pred, bets = _write_inputs(tmp_path)
    path = html_dashboard(pred, bets)
    text = open(path, encoding="utf-8").read()
    start = text.index("const DATA = ") + len("const DATA = ")
    end = text.index(";\nconst COLS", start)
    data = json.loads(text[start:end])
    # el pick flageado de edge 0.75 ahora SI aparece, con su razon
    assert len(data["picks"]) == 3
    assert 0.75 in {p["estimated_edge"] for p in data["picks"]}
    flageado = next(p for p in data["picks"] if p["estimated_edge"] == 0.75)
    assert flageado["estado"] not in ("", "con stake")
    # y los accionables siguen marcados como tales
    assert any(p["estado"] == "con stake" for p in data["picks"])
    # partido se construye desde home/away
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


def test_dashboard_history_has_filters_and_tables_are_sortable(tmp_path):
    pred, bets = _write_inputs(tmp_path)
    text = open(html_dashboard(pred, bets), encoding="utf-8").read()
    # history filter controls (hLine replaced back by hMarket, 2026-07-03)
    for ctrl in ('id="hSport"', 'id="hMarket"', 'id="hCond"', 'id="hTeam"',
                 'id="hHome"', 'id="hAway"', 'id="hFrom"', 'id="hTo"',
                 'id="historyTable"'):
        assert ctrl in text
    assert 'id="hLine"' not in text
    # each history row carries the filter keys
    assert 'data-fecha="2026-06-13"' in text
    assert 'data-league="nba"' in text
    assert 'data-market=' in text
    assert 'data-home=' in text
    # condition derived per row: settled e1 picked the home side, e2 the away
    # side, and the Over pick is not a team side
    assert 'data-cond="home"' in text
    assert 'data-cond="away"' in text
    assert 'data-cond=""' in text
    # realized hit-rate card recomputed with the active filters
    assert 'id="hHit"' in text
    # generic client-side sorting wired for the server-rendered grids
    assert "makeSortable(" in text and "initSortable()" in text


def test_dashboard_history_team_lists_cascade_by_sport(tmp_path):
    pred, bets = _write_inputs(tmp_path)
    text = open(html_dashboard(pred, bets), encoding="utf-8").read()
    # the Equipo / Home / Away option lists are rebuilt from the rows of the
    # selected sport whenever it changes, keeping a still-valid selection
    assert 'id="hTeam"' in text
    assert "fillTeams" in text
    assert 'getElementById("hSport").addEventListener("input", fillTeams)' in text


def test_team_condition_uses_normalized_identity():
    # same criterion as settlement grading: accents/casing must not break the
    # home/away match; Over/Under and Draw are not team sides
    assert html_report._team_condition("Atlético Madrid", "Atletico Madrid", "Real") == "home"
    assert html_report._team_condition("real", "Atletico Madrid", "Real") == "away"
    assert html_report._team_condition("Over", "A", "B") == ""
    assert html_report._team_condition("Draw", "A", "B") == ""
    assert html_report._team_condition(None, "A", "B") == ""
    # spread-style selections append the line and must match via prefix
    assert html_report._team_condition("Yankees -1.5", "Yankees", "Red Sox") == "home"


def test_dashboard_line_without_point_renders_dash_not_nan(tmp_path):
    # KI-018: h2h rows have no point -> line is NaN after the CSV round-trip;
    # server-rendered cells must show an em dash, never the string "nan".
    pred, bets = _write_inputs(tmp_path)
    text = open(html_dashboard(pred, bets), encoding="utf-8").read()
    assert ">nan<" not in text
    assert ">—<" in text                    # h2h history row, Linea column
    assert html_report._fmt_cell(float("nan")) == "—"
    assert html_report._fmt_cell(-2.5) == "-2.5000"


def _write_diagnostics_inputs(bets):
    registry = {
        "generated_at": "2026-07-14T11:00:00+00:00",
        "params": {"window_days": 60, "min_n": 30},
        "markets": {
            "mlb|spreads": {"paused": True, "since": "2026-07-14T11:00:00+00:00",
                            "reasons": ["brier_worse_than_market",
                                        "roi_flat_below_threshold"],
                            "n": 117, "brier_model": 0.2582,
                            "brier_market": 0.2478, "roi_flat": -0.308,
                            "updated_at": "2026-07-14T11:00:00+00:00"},
            "mlb|h2h": {"paused": False, "since": None, "reasons": [],
                        "n": 190, "brier_model": 0.2401,
                        "brier_market": 0.2440, "roi_flat": 0.012,
                        "updated_at": "2026-07-14T11:00:00+00:00"},
        },
    }
    (bets / "degradation_pause.json").write_text(
        json.dumps(registry), encoding="utf-8")
    pd.DataFrame([
        {"league": "wnba", "market": "totals", "dimension": "lado",
         "segment": "under", "n": 40, "hit_rate": 0.44, "mean_est_prob": 0.59,
         "gap": -0.15, "brier_model": 0.2797, "brier_market": 0.25,
         "roi_flat": -0.19, "flags": "sobreconfianza;peor_que_mercado"},
        {"league": "mlb", "market": "h2h", "dimension": "favorito",
         "segment": "favorito", "n": 120, "hit_rate": 0.61,
         "mean_est_prob": 0.60, "gap": 0.01, "brier_model": 0.2301,
         "brier_market": 0.2340, "roi_flat": 0.02, "flags": ""},
    ]).to_csv(bets / "segment_diagnostics_latest.csv", index=False)


def test_dashboard_diagnostics_tab_renders_degradation_and_segments(tmp_path):
    pred, bets = _write_inputs(tmp_path)
    _write_diagnostics_inputs(bets)
    text = open(html_dashboard(pred, bets), encoding="utf-8").read()
    # degradation state table: paused market with reasons, active market too
    assert "PAUSADO" in text
    assert "brier_worse_than_market" in text
    assert "mlb|spreads" not in text            # key split into league/market cells
    # flagged segments table shows only rows with flags
    assert "sobreconfianza" in text
    assert 'id="segmentsTable"' in text
    assert 'id="degradationTable"' in text
    # unflagged segment row (favorito, gap 0.01) is not in the flagged table
    assert ">favorito<" not in text


def test_dashboard_diagnostics_tab_empty_is_safe(tmp_path):
    pred, bets = _write_inputs(tmp_path)
    text = open(html_dashboard(pred, bets), encoding="utf-8").read()
    assert "Diagnostico" in text
    assert "monitor de degradacion" in text     # placeholder: not run yet
    assert "diagnostico por segmentos" in text  # placeholder: no CSV yet


def test_dashboard_empty_is_safe(tmp_path):
    pred = tmp_path / "predictions"
    bets = tmp_path / "bets"
    pred.mkdir()
    bets.mkdir()
    text = open(html_dashboard(pred, bets), encoding="utf-8").read()
    assert "Sin candidatos accionables" in text
    assert "Sin apuestas liquidadas" in text
    assert "Sin historial de picks." in text


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
