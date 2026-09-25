"""Tennis vertical: ESPN results parser + name/date settlement matching."""
import pandas as pd

from sqp.providers.espn_tennis import parse_tennis_scoreboard, tour_from_league
from sqp.settlement.runner import tennis_scores_map


def _payload():
    return {"events": [{"name": "Test Open", "groupings": [{"competitions": [
        # completed singles
        {"id": "1", "date": "2026-06-15T08:00Z", "status": {"type": {"completed": True}},
         "competitors": [{"winner": True, "athlete": {"displayName": "Iga Swiatek"}},
                         {"winner": False, "athlete": {"displayName": "Coco Gauff"}}]},
        # not completed -> skip
        {"id": "2", "date": "2026-06-15T10:00Z", "status": {"type": {"completed": False}},
         "competitors": [{"winner": False, "athlete": {"displayName": "A B"}},
                         {"winner": False, "athlete": {"displayName": "C D"}}]},
        # doubles (no athlete) -> skip
        {"id": "3", "date": "2026-06-15T12:00Z", "status": {"type": {"completed": True}},
         "competitors": [{"winner": True, "team": {"displayName": "X/Y"}},
                         {"winner": False, "team": {"displayName": "Z/W"}}]},
        # older match (for the `since` filter), winner is the second competitor
        {"id": "4", "date": "2026-06-01T08:00Z", "status": {"type": {"completed": True}},
         "competitors": [{"winner": False, "athlete": {"displayName": "P Q"}},
                         {"winner": True, "athlete": {"displayName": "R S"}}]},
    ]}]}]}


def test_tour_from_league():
    assert tour_from_league("tennis_wta_german_open") == "wta"
    assert tour_from_league("tennis_atp_wimbledon") == "atp"
    assert tour_from_league("atp") == "atp"
    assert tour_from_league("nba") is None


def test_parse_keeps_completed_singles_only():
    rows = parse_tennis_scoreboard(_payload())
    ids = {r["game_id"] for r in rows}
    assert ids == {"1", "4"}  # not the incomplete (2) nor the doubles (3)
    m1 = next(r for r in rows if r["game_id"] == "1")
    assert m1 == {"date": "2026-06-15", "home": "Iga Swiatek", "away": "Coco Gauff",
                  "home_score": 1, "away_score": 0, "neutral": True,
                  "game_id": "1", "winner": "Iga Swiatek"}
    m4 = next(r for r in rows if r["game_id"] == "4")
    assert m4["home"] == "R S" and m4["winner"] == "R S"  # winner oriented as home


def test_parse_since_filters_older_matches():
    rows = parse_tennis_scoreboard(_payload(), since="2026-06-10")
    assert {r["game_id"] for r in rows} == {"1"}


def test_tennis_scores_map_matches_by_name_and_date():
    preds = pd.DataFrame([
        {"event_id": "e1", "home": "Iga Swiatek", "away": "Coco Gauff",
         "start_time": "2026-06-15T09:00:00Z"},
        {"event_id": "e2", "home": "Carlos Alcaraz", "away": "Jannik Sinner",
         "start_time": "2026-06-15T11:00:00Z"},
        {"event_id": "e3", "home": "Nadie Uno", "away": "Nadie Dos",
         "start_time": "2026-06-15T11:00:00Z"},
    ])
    results = [
        {"home": "Iga Swiatek", "away": "Coco Gauff", "date": "2026-06-15", "winner": "Iga Swiatek"},
        # order swapped + date off by one day (within tolerance); accents differ
        {"home": "Jannik Sinner", "away": "Carlos Alcaráz", "date": "2026-06-16", "winner": "Jannik Sinner"},
    ]
    scores = tennis_scores_map(preds, results)
    assert scores["e1"] == (1, 0, "Iga Swiatek")   # home player won
    assert scores["e2"] == (0, 1, "Carlos Alcaraz")  # away player (Sinner) won
    assert "e3" not in scores  # no result available -> unsettled


def test_una_ventana_corta_consulta_tambien_su_ultimo_dia():
    """2026-09-25: con --days 3 solo se consultaba el primer dia de la ventana y
    un torneo ATP que empezaba despues no llegaba al historico."""
    from datetime import date
    from sqp.providers.espn_tennis import query_days
    assert query_days(date(2026, 9, 21), date(2026, 9, 26)) == [
        date(2026, 9, 21), date(2026, 9, 26)]
    # Si el paso semanal ya cae en el ultimo dia, no se repite.
    assert query_days(date(2026, 9, 1), date(2026, 9, 15)) == [
        date(2026, 9, 1), date(2026, 9, 8), date(2026, 9, 15)]
    assert query_days(date(2026, 9, 1), date(2026, 9, 17))[-1] == date(2026, 9, 17)
    assert query_days(date(2026, 9, 5), date(2026, 9, 5)) == [date(2026, 9, 5)]


def test_el_backfill_diario_ve_un_torneo_que_empieza_dentro_de_la_ventana(monkeypatch):
    from sqp.providers import espn_tennis
    from sqp.providers.date_window import fetch_window
    start, end = fetch_window(3)
    pedidas: list[str] = []
    torneo = [{"date": f"{end:%Y-%m-%d}", "home": "A", "away": "B", "home_score": 1,
               "away_score": 0, "neutral": True, "game_id": "g1", "winner": "A"}]

    def fake_fetch(self, tour, dates, since):
        pedidas.append(dates)
        return torneo if dates == f"{end:%Y%m%d}" else []

    monkeypatch.setattr(espn_tennis.ESPNTennisResultsProvider, "_fetch", fake_fetch)
    rows = espn_tennis.ESPNTennisResultsProvider().fetch_results("atp", days_back=3)
    assert pedidas == [f"{start:%Y%m%d}", f"{end:%Y%m%d}"]
    assert len(rows) == 1
