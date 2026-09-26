"""Barrido de integridad de nombres de equipo (2026-09-26): fija que cada
alias anadido a configs/leagues/team_aliases.yaml realmente une la grafia de
The Odds API con la grafia del historico (ResultsStore) bajo la MISMA clave
normalizada, para la liga en la que fue declarado.

Caso confirmado que origino el barrido: en NCAAF, el historico guarda
"Hawai'i Rainbow Warriors" pero The Odds API sirve "Hawaii Rainbow Warriors"
(sin apostrofo); sin el alias, normalize_key() produce claves distintas, el
adaptador ve a Hawai'i sin partidos y reliability_warning() se dispara para
cualquier evento de Hawai'i, aunque el equipo tenga historico de sobra.
"""

from functools import lru_cache

import pytest

from sqp.config import CONFIG_DIR, ROOT, load_yaml
from sqp.domain.models import Event
from sqp.sports import team_names as tn
from sqp.sports.registry import get_adapter
from sqp.storage.results_store import ResultsStore

# (liga, grafia de The Odds API, grafia canonica del historico), tal como
# quedaron en configs/leagues/team_aliases.yaml. Cada pareja fue verificada
# como el MISMO equipo/club (traduccion, sigla, apodo, articulo/prefijo,
# renombramiento oficial, o un caracter que normalize_key no pliega); los
# emparejamientos por similitud de cadena pero de entidades DISTINTAS
# (Inter Milan/AC Milan, Sparta Praga/Slavia Praga, Los Angeles
# Clippers/Lakers, New York Red Bulls/NYCFC, etc.) se descartaron a
# proposito y no aparecen aqui.
NCAAF_ALIASES = [
    ("Albany", "UAlbany Great Danes"),
    ("Citadel Bulldogs", "The Citadel Bulldogs"),
    ("Grambling State Tigers", "Grambling Tigers"),
    ("Hawaii Rainbow Warriors", "Hawai'i Rainbow Warriors"),
    ("Houston Baptist Huskies", "Houston Christian Huskies"),
    ("LIU Sharks", "Long Island University Sharks"),
    ("Nicholls State Colonels", "Nicholls Colonels"),
    ("Sam Houston State Bearkats", "Sam Houston Bearkats"),
    ("Southeastern Louisiana Lions", "SE Louisiana Lions"),
    ("Southern Mississippi Golden Eagles", "Southern Miss Golden Eagles"),
    ("Southern University Jaguars", "Southern Jaguars"),
    ("UMass Minutemen", "Massachusetts Minutemen"),
    ("William and Mary Tribe", "William & Mary Tribe"),
    ("Youngstown St Penguins", "Youngstown State Penguins"),
]

OTHER_LEAGUE_ALIASES = [
    ("brasileirao", "Atletico Mineiro", "Atlético-MG"),
    ("brasileirao", "Atletico Paranaense", "Athletico-PR"),
    ("brasileirao", "Bragantino-SP", "Red Bull Bragantino"),
    ("bundesliga", "1. FC Köln", "FC Cologne"),
    ("bundesliga", "Augsburg", "FC Augsburg"),
    ("bundesliga", "Elversberg", "SV Elversberg"),
    ("bundesliga", "FC Schalke 04", "Schalke 04"),
    ("bundesliga", "FSV Mainz 05", "Mainz"),
    ("bundesliga", "Hamburger SV", "Hamburg SV"),
    ("bundesliga", "SC Paderborn", "SC Paderborn 07"),
    ("bundesliga", "Union Berlin", "1. FC Union Berlin"),
    ("chile", "Everton de Viña del Mar", "Everton CD"),
    ("chile", "Universidad Católica (CHI)", "Universidad Católica"),
    ("epl", "Bournemouth", "AFC Bournemouth"),
    ("epl", "Brighton and Hove Albion", "Brighton & Hove Albion"),
    ("laliga", "Athletic Bilbao", "Athletic Club"),
    ("laliga", "CA Osasuna", "Osasuna"),
    ("laliga", "Deportivo La Coruña", "Deportivo"),
    ("laliga", "Elche CF", "Elche"),
    ("laliga", "Real Racing Club de Santander", "Racing Santander"),
    ("ligamx", "Atlante FC", "Atlante"),
    ("ligamx", "Atlético San Luis", "Atlético de San Luis"),
    ("ligamx", "Pumas", "Pumas UNAM"),
    ("ligamx", "Santos Laguna", "Santos"),
    ("ligamx", "Tigres", "Tigres UANL"),
    ("ligue1", "Auxerre", "AJ Auxerre"),
    ("ligue1", "Le Havre", "Le Havre AC"),
    ("ligue1", "Le Mans FC", "Le Mans"),
    ("ligue1", "RC Lens", "Lens"),
    ("ligue1", "Rennes", "Stade Rennais"),
    ("mls", "Chicago Fire", "Chicago Fire FC"),
    ("mls", "Columbus Crew SC", "Columbus Crew"),
    ("mls", "Houston Dynamo", "Houston Dynamo FC"),
    ("mls", "Los Angeles FC", "LAFC"),
    ("mls", "New York Red Bulls", "Red Bull New York"),
    ("mls", "Vancouver Whitecaps FC", "Vancouver Whitecaps"),
    ("nba", "Los Angeles Clippers", "LA Clippers"),
    ("seriea", "Atalanta BC", "Atalanta"),
    ("seriea", "Inter Milan", "Internazionale"),
    ("ucl", "Bodø/Glimt", "Bodo/Glimt"),
    ("ucl", "Feyenoord", "Feyenoord Rotterdam"),
    ("ucl", "Inter Milan", "Internazionale"),
    ("ucl", "LASK", "LASK Linz"),
    ("ucl", "Porto", "FC Porto"),
    ("ucl", "RC Lens", "Lens"),
    ("ucl", "Slavia Praha", "Slavia Prague"),
    ("ucl", "Sporting Lisbon", "Sporting CP"),
    ("ucl", "ŠK Slovan Bratislava", "Slovan Bratislava"),
    ("uwcl", "AS Roma", "Roma"),
    ("uwcl", "Ajax", "Ajax Amsterdam"),
    ("uwcl", "Austria Wien", "Austria Vienna"),
    ("uwcl", "Leuven", "OH Leuven"),
    ("uwcl", "Lyon", "OL Lyonnes"),
    ("uwcl", "SKN St. Pölten", "St. Pölten"),
    ("uwcl", "Servette FC", "Servette"),
]

ALL_LEAGUE_ALIASES = [("ncaaf", odds_name, hist_name) for odds_name, hist_name in NCAAF_ALIASES] \
    + OTHER_LEAGUE_ALIASES


@lru_cache(maxsize=None)
def _league_has_history(league: str) -> bool:
    """True si hay al menos una fila de historico para la liga.

    data/historical/ esta en .gitignore, asi que un checkout de CI no lo
    trae: ResultsStore.path(league) no existe y ResultsStore.load(league)
    devuelve [] (ver src/sqp/storage/results_store.py, load()). Se comprueba
    via load() (no solo via path().exists()) porque asi el mismo chequeo
    responde igual bajo un plugin de pruebas que simule "sin datos"
    monkeypatcheando ResultsStore.load."""
    return bool(ResultsStore(ROOT).load(league))


def _skip_without_history(league: str) -> pytest.MarkDecorator:
    return pytest.mark.skipif(
        not _league_has_history(league),
        reason=f"[{league}] sin data/historical/results_{league}.csv "
               "(gitignored; no disponible en un checkout de CI)",
    )


# Los 69 casos de test_alias_canonical_name_has_real_history necesitan datos
# reales de ResultsStore; en un checkout de CI sin data/historical/ se saltan
# en vez de fallar por fixtures ausentes.
HISTORY_DEPENDENT_PARAMS = [
    pytest.param(league, odds_name, history_name, marks=_skip_without_history(league))
    for league, odds_name, history_name in ALL_LEAGUE_ALIASES
]


@pytest.fixture(autouse=True)
def _fresh_alias_cache():
    # La cache de _league_aliases vive por proceso; forzar una relectura del
    # yaml real en disco para no depender del orden de ejecucion de los tests.
    tn._league_aliases.cache_clear()
    yield
    tn._league_aliases.cache_clear()


def test_hawaii_odds_and_history_spellings_share_one_key_in_ncaaf():
    norm = tn.get_team_normalizer("ncaaf")
    assert norm("Hawaii Rainbow Warriors") == norm("Hawai'i Rainbow Warriors")
    # Y sin alias las dos grafias NO deberian colisionar por casualidad:
    # normalize_key por si solo las deja distintas (confirma que hace falta
    # el alias, no que ya "auto-matcheaban").
    bare = tn.normalize_key
    assert bare("Hawaii Rainbow Warriors") != bare("Hawai'i Rainbow Warriors")


@pytest.mark.parametrize("league,odds_name,history_name", ALL_LEAGUE_ALIASES)
def test_alias_binds_odds_spelling_to_history_spelling(league, odds_name, history_name):
    norm = tn.get_team_normalizer(league)
    assert norm(odds_name) == norm(history_name), (
        f"[{league}] {odds_name!r} no normaliza a la misma clave que "
        f"{history_name!r}: revisar configs/leagues/team_aliases.yaml"
    )


@pytest.mark.parametrize("league,odds_name,history_name", HISTORY_DEPENDENT_PARAMS)
def test_alias_canonical_name_has_real_history(league, odds_name, history_name):
    """El lado canonico de cada alias debe existir de verdad en el historico
    (si no, el alias apuntaria a un fantasma y no arreglaria nada); y la
    grafia de The Odds API NO debe tener historico propio bajo su clave
    LITERAL (sin pasar por el alias), o el alias estaria fusionando dos
    identidades realmente distintas en vez de unir dos grafias del mismo
    equipo. Se usa normalize_key() puro (sin get_team_normalizer) para no
    depender del propio alias que se esta verificando."""
    results = ResultsStore(ROOT).load(league)

    canonical_key = tn.normalize_key(history_name)
    canonical_games = sum(
        1 for r in results
        if tn.normalize_key(r["home"]) == canonical_key or tn.normalize_key(r["away"]) == canonical_key
    )
    assert canonical_games > 0, (
        f"[{league}] {history_name!r} no tiene NINGUN partido en el historico; "
        "no deberia estar como lado canonico de un alias"
    )

    odds_key = tn.normalize_key(odds_name)
    odds_games = sum(
        1 for r in results
        if tn.normalize_key(r["home"]) == odds_key or tn.normalize_key(r["away"]) == odds_key
    )
    assert odds_games == 0, (
        f"[{league}] {odds_name!r} SI tiene historico propio bajo su grafia "
        f"literal ({odds_games} partidos); el alias hacia {history_name!r} "
        "fusionaria dos identidades distintas, no dos grafias del mismo equipo"
    )


def test_venues_keys_are_fixed_points_of_the_team_normalizer():
    """configs/venues.yaml se indexa por get_team_normalizer(liga)(equipo)
    (ver el comentario del propio yaml y sqp/pipeline/daily.py, linea con
    `load_yaml(CONFIG_DIR / "venues.yaml")`). Si un alias nuevo cambia la
    clave canonica de un equipo y venues.yaml no se actualiza, esa clave
    queda huerfana en silencio (el feature de tiempo simplemente no
    encuentra coordenadas, sin ninguna excepcion). No depende de data/."""
    venues = load_yaml(CONFIG_DIR / "venues.yaml")
    for league, teams in venues.items():
        norm = tn.get_team_normalizer(league)
        for key in teams:
            assert norm(key) == key, (
                f"[{league}] la clave {key!r} de configs/venues.yaml ya no es "
                f"un punto fijo del normalizador (normaliza a {norm(key)!r}); "
                "un alias de team_aliases.yaml la dejo huerfana: actualiza la "
                "clave en venues.yaml"
            )


@pytest.mark.skipif(
    not _league_has_history("ncaaf"),
    reason="[ncaaf] sin data/historical/results_ncaaf.csv "
           "(gitignored; no disponible en un checkout de CI)",
)
def test_hawaii_vs_wyoming_no_longer_triggers_reliability_warning():
    """Reproduccion end-to-end del fallo confirmado: un evento de The Odds
    API para NCAAF con la grafia 'Hawaii Rainbow Warriors' (sin apostrofo)
    dejaba de ver el historico de Hawai'i y marcaba reliability_warning por
    bajo numero de partidos, aunque el equipo tenga historico de sobra."""
    adapter = get_adapter("ncaaf", "football")
    history = ResultsStore(ROOT).load("ncaaf")
    adapter.fit_results(history)
    event = Event(event_id="test-hawaii-wyoming", sport_key="americanfootball_ncaaf",
                  league="ncaaf", home="Hawaii Rainbow Warriors", away="Wyoming Cowboys",
                  start_time="2026-10-01T00:00:00Z")
    assert adapter.reliability_warning(event, min_games=10) is None
