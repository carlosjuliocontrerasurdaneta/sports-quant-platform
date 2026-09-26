"""Parsing of ESPN's NHL scoreboard `probables` field
(`sqp.providers.espn_goalies`), with synthetic JSON only.
"""
from sqp.providers.espn_goalies import parse_active_sides, parse_goalie_probables



def _scoreboard_payload():
    return {
        "events": [
            {
                "id": "401879457",
                "date": "2026-09-26T19:00Z",
                "status": {"type": {"completed": False}},
                "competitions": [{
                    "competitors": [
                        {
                            "homeAway": "home",
                            "team": {"displayName": "Buffalo Sabres"},
                            "probables": [{
                                "name": "probableStartingGoalie",
                                "athlete": {"id": "4233889",
                                            "fullName": "Ukko-Pekka Luukkonen"},
                                "status": {"name": "Confirmed", "type": "confirmed"},
                            }],
                        },
                        {
                            "homeAway": "away",
                            "team": {"displayName": "Vancouver Canucks"},
                            "probables": [{
                                "name": "probableStartingGoalie",
                                "athlete": {"id": "4576894", "fullName": "Arturs Silovs"},
                                "status": {"name": "Expected", "type": "expected"},
                            }],
                        },
                    ]
                }],
            },
            {
                # partido ya jugado: debe conservar completed=True para que el
                # LLAMADOR (no este parser) decida excluirlo.
                "id": "999",
                "date": "2026-09-25T23:00Z",
                "status": {"type": {"completed": True}},
                "competitions": [{
                    "competitors": [
                        {"homeAway": "home", "team": {"displayName": "X"}, "probables": []},
                        {"homeAway": "away", "team": {"displayName": "Y"}, "probables": []},
                    ]
                }],
            },
        ]
    }


def test_parse_goalie_probables_extrae_confirmed_y_expected():
    rows = parse_goalie_probables(_scoreboard_payload())
    assert len(rows) == 2
    by_side = {r["team_side"]: r for r in rows}

    home = by_side["home"]
    assert home["event_id"] == "401879457"
    assert home["team"] == "Buffalo Sabres"
    assert home["goalie_espn_id"] == "4233889"
    assert home["goalie_name"] == "Ukko-Pekka Luukkonen"
    assert home["status"] == "Confirmed"
    assert home["status_type"] == "confirmed"
    assert home["completed"] is False
    assert home["commence_time"] == "2026-09-26T19:00Z"

    away = by_side["away"]
    assert away["status"] == "Expected"  # no "Probable": verificado contra la API real


def test_parse_goalie_probables_ignora_otros_tipos_de_probable():
    payload = {
        "events": [{
            "id": "1", "date": "2026-09-26T19:00Z",
            "status": {"type": {"completed": False}},
            "competitions": [{"competitors": [{
                "homeAway": "home", "team": {"displayName": "X"},
                "probables": [{"name": "probableStartingPitcher",  # otro deporte/campo
                               "athlete": {"id": "1", "fullName": "Nadie"},
                               "status": {"name": "Confirmed"}}],
            }]}],
        }]
    }
    assert parse_goalie_probables(payload) == []


def test_parse_goalie_probables_payload_vacio():
    assert parse_goalie_probables({}) == []


def test_parse_active_sides_incluye_lados_sin_probable():
    """`parse_active_sides` -- a diferencia de `parse_goalie_probables` --
    devuelve TODOS los lados del scoreboard, tengan o no un probable, para que
    el llamador pueda detectar cuando uno deja de publicarse."""
    rows = parse_active_sides(_scoreboard_payload())
    assert len(rows) == 4  # 2 lados del partido futuro + 2 del ya jugado
    by_event = {(r["event_id"], r["team_side"]): r for r in rows}
    futuro_home = by_event[("401879457", "home")]
    assert futuro_home["team"] == "Buffalo Sabres"
    assert futuro_home["completed"] is False
    jugado_home = by_event[("999", "home")]
    assert jugado_home["completed"] is True


def test_parse_active_sides_payload_vacio():
    assert parse_active_sides({}) == []
