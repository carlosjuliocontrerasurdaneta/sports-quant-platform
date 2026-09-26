"""Matching NHL-API team identities to the ESPN results history, including
the renamed/relocated franchises the pre-registro flags by name (Phoenix/
Arizona/Utah, Atlanta Thrashers, Mighty Ducks of Anaheim, Montreal accent).
"""
from sqp.sports.nhl_goalie_matching import build_results_index, match_espn_game


def _results():
    return [
        # Dos eras de la MISMA franquicia con el MISMO nombre corto ("Coyotes")
        # en la API de la NHL, pero grafias ESPN distintas segun la fecha.
        {"date": "2013-01-20", "home": "Phoenix Coyotes", "away": "Chicago Blackhawks",
         "game_id": "E-2013"},
        {"date": "2021-01-20", "home": "Arizona Coyotes", "away": "Chicago Blackhawks",
         "game_id": "E-2021"},
        # Mighty Ducks: la API de la NHL ya decia "Ducks" en 2005-06, ESPN
        # todavia decia "Anaheim Mighty Ducks" esa temporada.
        {"date": "2005-10-08", "home": "Nashville Predators", "away": "Anaheim Mighty Ducks",
         "game_id": "E-DUCKS-2005"},
        {"date": "2015-10-08", "home": "Nashville Predators", "away": "Anaheim Ducks",
         "game_id": "E-DUCKS-2015"},
        # Atlanta Thrashers
        {"date": "2005-10-08", "home": "Atlanta Thrashers", "away": "Washington Capitals",
         "game_id": "E-ATL"},
        # Montreal con tilde en el historico
        {"date": "2005-10-08", "home": "Toronto Maple Leafs", "away": "Montréal Canadiens",
         "game_id": "E-MTL"},
        # Utah: nombre completo identico en ambas fuentes
        {"date": "2024-10-12", "home": "New York Rangers", "away": "Utah Hockey Club",
         "game_id": "E-UTAH-2024"},
        {"date": "2025-10-12", "home": "New York Rangers", "away": "Utah Mammoth",
         "game_id": "E-UTAH-2025"},
    ]


def test_coyotes_se_desambigua_por_fecha_no_por_alias_estatico():
    idx = build_results_index(_results())
    m2013 = match_espn_game("2013-01-20", "Coyotes", "Blackhawks", idx)
    m2021 = match_espn_game("2021-01-20", "Coyotes", "Blackhawks", idx)
    assert m2013["espn_game_id"] == "E-2013"
    assert m2013["home_espn"] == "Phoenix Coyotes"
    assert m2021["espn_game_id"] == "E-2021"
    assert m2021["home_espn"] == "Arizona Coyotes"


def test_mighty_ducks_de_anaheim_2005_y_ducks_2015():
    idx = build_results_index(_results())
    m2005 = match_espn_game("2005-10-08", "Predators", "Ducks", idx)
    assert m2005["espn_game_id"] == "E-DUCKS-2005"
    m2015 = match_espn_game("2015-10-08", "Predators", "Ducks", idx)
    assert m2015["espn_game_id"] == "E-DUCKS-2015"


def test_atlanta_thrashers():
    idx = build_results_index(_results())
    m = match_espn_game("2005-10-08", "Thrashers", "Capitals", idx)
    assert m["espn_game_id"] == "E-ATL"


def test_montreal_con_tilde_en_el_historico_normaliza_igual():
    idx = build_results_index(_results())
    m = match_espn_game("2005-10-08", "Maple Leafs", "Canadiens", idx)
    assert m["espn_game_id"] == "E-MTL"
    assert m["away_espn"] == "Montréal Canadiens"


def test_utah_hockey_club_y_utah_mammoth():
    idx = build_results_index(_results())
    m2024 = match_espn_game("2024-10-12", "Rangers", "Utah Hockey Club", idx)
    assert m2024["espn_game_id"] == "E-UTAH-2024"
    m2025 = match_espn_game("2025-10-12", "Rangers", "Mammoth", idx)
    assert m2025["espn_game_id"] == "E-UTAH-2025"


def test_sin_candidato_en_esa_fecha_no_empareja():
    idx = build_results_index(_results())
    assert match_espn_game("1999-01-01", "Coyotes", "Blackhawks", idx) is None


def test_ambiguo_no_empareja_a_ciegas():
    # Dos filas de la misma fecha con el MISMO local y un visitante que sufija
    # igual en ambas (construido a proposito para forzar la ambiguedad; no
    # corresponde a franquicias reales): ninguna se elige.
    idx = build_results_index([
        {"date": "2030-01-01", "home": "Nashville Predators", "away": "Anaheim Ducks",
         "game_id": "A"},
        {"date": "2030-01-01", "home": "Nashville Predators", "away": "San Jose Ducks",
         "game_id": "B"},
    ])
    assert match_espn_game("2030-01-01", "Predators", "Ducks", idx) is None
