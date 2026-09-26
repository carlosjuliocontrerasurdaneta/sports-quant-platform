"""Parsing of the public NHL API payloads (`sqp.providers.nhl_api`), with
synthetic JSON only -- no network, no `data/`.
"""
from sqp.providers.nhl_api import is_final_game_state, parse_boxscore_goalies, parse_score_games



def _score_payload():
    return {
        "games": [
            {
                "id": 2024020011,
                "gameType": 2,
                "startTimeUTC": "2024-10-10T23:00:00Z",
                "homeTeam": {"name": {"default": "Bruins"}},
                "awayTeam": {"name": {"default": "Canadiens"}},
            },
            {
                # sin startTimeUTC: no debe aparecer (defecto de datos, no se adivina)
                "id": 999,
                "gameType": 2,
                "homeTeam": {"name": {"default": "Sharks"}},
                "awayTeam": {"name": {"default": "Kings"}},
            },
        ]
    }


def test_parse_score_games_extrae_fecha_utc_y_equipos():
    games = parse_score_games(_score_payload())
    assert len(games) == 1
    g = games[0]
    assert g["nhl_game_id"] == "2024020011"
    assert g["date_utc"] == "2024-10-10"
    assert g["start_time_utc"] == "2024-10-10T23:00:00Z"
    assert g["home_name"] == "Bruins"
    assert g["away_name"] == "Canadiens"
    assert g["game_type"] == 2


def _boxscore_payload():
    return {
        "gameType": 2,
        "startTimeUTC": "2024-10-10T23:00:00Z",
        "playerByGameStats": {
            "awayTeam": {
                "goalies": [
                    {
                        "playerId": 8480051,
                        "name": {"default": "C. Primeau"},
                        "starter": True,
                        "toi": "57:11",
                        "shotsAgainst": 29,
                        "saves": 23,
                        "goalsAgainst": 6,
                    },
                    {
                        # suplente que no jugo: sin tiros, starter False.
                        # Debe seguir apareciendo (no se descarta).
                        "playerId": 8478470,
                        "name": {"default": "S. Montembeault"},
                        "starter": False,
                        "toi": "00:00",
                        "shotsAgainst": 0,
                        "saves": 0,
                        "goalsAgainst": 0,
                    },
                ]
            },
            "homeTeam": {
                "goalies": [
                    {
                        "playerId": 8480280,
                        "name": {"default": "J. Swayman"},
                        "starter": True,
                        "toi": "60:00",
                        "shotsAgainst": 24,
                        "saves": 20,
                        "goalsAgainst": 4,
                    },
                    {
                        # portero sin el campo `starter`: payload malformado /
                        # temporada muy antigua -> se OMITE, no se adivina.
                        "playerId": 1111,
                        "name": {"default": "Nadie"},
                        "toi": "00:00",
                    },
                ]
            },
        },
    }


def test_parse_boxscore_goalies_titular_suplente_y_sin_tiros():
    rows = parse_boxscore_goalies(_boxscore_payload(), "2024020011")
    # 3 filas: titular visitante, suplente sin tiros visitante, titular local.
    # El portero local sin `starter` se omite.
    assert len(rows) == 3
    by_id = {r["goalie_player_id"]: r for r in rows}

    starter_away = by_id["8480051"]
    assert starter_away["starter"] is True
    assert starter_away["team_side"] == "away"
    assert starter_away["shots_against"] == 29
    assert starter_away["saves"] == 23
    assert starter_away["goals_against"] == 6
    assert starter_away["toi"] == "57:11"
    assert starter_away["nhl_game_id"] == "2024020011"

    backup_no_shots = by_id["8478470"]
    assert backup_no_shots["starter"] is False
    assert backup_no_shots["shots_against"] == 0
    assert backup_no_shots["saves"] == 0

    starter_home = by_id["8480280"]
    assert starter_home["starter"] is True
    assert starter_home["team_side"] == "home"

    assert "1111" not in by_id  # sin `starter`: omitido, no adivinado


def test_parse_boxscore_goalies_payload_vacio():
    assert parse_boxscore_goalies({"playerByGameStats": {}}, "x") == []


def test_is_final_game_state_off_y_final_son_definitivos():
    assert is_final_game_state({"gameState": "OFF"}) is True
    assert is_final_game_state({"gameState": "FINAL"}) is True


def test_is_final_game_state_live_crit_fut_pre_no_son_definitivos():
    """B2 (revision independiente de Fable, NO APTO): solo OFF/FINAL se
    tratan como terminados; un partido en juego no puede ingerirse como si
    sus estadisticas fueran definitivas."""
    for estado in ("LIVE", "CRIT", "FUT", "PRE"):
        assert is_final_game_state({"gameState": estado}) is False


def test_is_final_game_state_sin_campo_no_se_adivina_como_terminado():
    assert is_final_game_state({}) is False
