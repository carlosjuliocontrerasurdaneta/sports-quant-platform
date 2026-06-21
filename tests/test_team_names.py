"""Cross-vendor team-name normalization: deterministic key, alias map, and the
Elo identity binding that lets ratings from one vendor apply to another's names.
"""
from sqp.models.elo import EloRatings
from sqp.pipeline.daily import _merge_results
from sqp.sports.team_names import TeamNormalizer, normalize_key


def test_normalize_key_strips_accents_case_and_punctuation():
    assert normalize_key("Club América") == "club america"
    assert normalize_key("St. Louis Blues") == "st louis blues"
    assert normalize_key("  Manchester   City ") == "manchester city"
    assert normalize_key("Nott'm Forest") == "nott m forest"
    assert normalize_key(None) == ""
    assert normalize_key("") == ""


def test_normalize_key_does_not_merge_distinct_teams():
    assert normalize_key("Manchester City") != normalize_key("Manchester United")


def test_alias_map_binds_variants_to_one_key():
    # Aliases are keyed by normalized variant -> normalized canonical.
    norm = TeamNormalizer("epl", {"man city": "manchester city"})
    assert norm("Man City") == norm("Manchester City") == "manchester city"
    # Spelling-only differences bind without any alias entry.
    assert norm("MÁNCHESTER city") == "manchester city"
    # Unknown team falls back to its own deterministic key.
    assert norm("Aston Villa") == "aston villa"


def test_empty_normalizer_is_identity_key():
    norm = TeamNormalizer("nba", {})
    assert norm("Los Angeles Lakers") == "los angeles lakers"


def test_elo_binds_ratings_across_vendor_spellings():
    # Ratings built under one spelling must apply to another spelling of the
    # same team (e.g. ESPN results vs The Odds API events).
    aliases = {"la dodgers": "los angeles dodgers"}
    norm = TeamNormalizer("mlb", aliases)
    elo = EloRatings(k=20.0, home_advantage=0.0, normalize=norm)
    elo.update("Los Angeles Dodgers", "San Francisco Giants", 5, 1)

    # Alias spelling resolves to the same rating and game count.
    assert elo.get("LA Dodgers") == elo.get("Los Angeles Dodgers")
    assert elo.get("LA Dodgers") > elo.base  # winner gained rating
    # A second game under the alias spelling increments the SAME identity.
    elo.update("LA Dodgers", "San Diego Padres", 3, 2)
    assert elo.is_reliable("Los Angeles Dodgers", min_games=2)


def test_elo_without_normalizer_keeps_raw_keys():
    elo = EloRatings(k=20.0)
    elo.update("A", "B", 3, 1)
    assert elo.games_played.get("A") == 1
    assert elo.get("C") == elo.base  # unknown team -> base


def test_merge_results_dedups_same_game_across_vendor_spellings():
    # History (ESPN-style) and recent (Odds-API-style) spell the same game
    # differently; with a normalizer the recent duplicate is dropped instead of
    # double-counting the game into the ratings.
    norm = TeamNormalizer("mlb", {"la dodgers": "los angeles dodgers",
                                  "sf giants": "san francisco giants"})
    history = [{"date": "2026-06-19", "home": "Los Angeles Dodgers",
                "away": "San Francisco Giants", "home_score": 5, "away_score": 1,
                "game_id": "espn-1"}]
    recent = [{"date": "2026-06-19T23:00:00Z", "home": "LA Dodgers",
               "away": "SF Giants", "home_score": 5, "away_score": 1,
               "game_id": "odds-1"}]
    merged = _merge_results(history, recent, norm)
    assert len(merged) == 1
    assert merged[0]["game_id"] == "espn-1"  # history wins
    # Without the normalizer the two spellings look like two distinct games.
    assert len(_merge_results(history, recent)) == 2
