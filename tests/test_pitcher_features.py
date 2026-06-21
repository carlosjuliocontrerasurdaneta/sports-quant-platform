"""Starting pitcher features: ratings, lambda adjustment, flags, starter store."""
from sqp.domain.models import Event
from sqp.models.starters import StarterRatings
from sqp.sports.registry import get_adapter
from sqp.storage.starters import StartersStore


def _ev(home_pitcher=None, away_pitcher=None) -> Event:
    return Event(event_id="x", sport_key="bt", league="mlb", home="A", away="B",
                 start_time="2026-06-12", home_pitcher=home_pitcher,
                 away_pitcher=away_pitcher)


def test_starter_ratings_regression_and_bounds():
    sr = StarterRatings(prior_starts=5.0, min_starts=3, bound=0.35)
    for _ in range(20):
        sr.update("Ace", 1.0)      # elite run suppressor
        sr.update("Batting Practice", 9.0)
        sr.update("Average Arm", 5.0)
    assert sr.factor("Ace") == 0.65          # clamped at the -35% bound
    assert sr.factor("Batting Practice") == 1.35  # clamped at +35%
    assert abs(sr.factor("Average Arm") - 1.0) < 0.05
    assert sr.factor(None) == 1.0
    assert sr.factor("Two Starts Only") == 1.0  # below min_starts -> neutral
    assert not sr.is_known("Two Starts Only")


def test_baseball_adapter_pitcher_shifts_probability():
    adapter = get_adapter("mlb", "baseball")
    rows = []
    for i in range(10):
        rows.append({"date": f"2026-05-{i+1:02d}", "home": "A", "away": "C",
                     "home_score": 4, "away_score": 1, "home_starter": "Ace",
                     "away_starter": "Filler One"})
        rows.append({"date": f"2026-05-{i+1:02d}", "home": "B", "away": "D",
                     "home_score": 4, "away_score": 8, "home_starter": "Batting Practice",
                     "away_starter": "Filler Two"})
    adapter.fit_results(rows)
    no_pitchers = adapter.estimate(_ev(), None, None)
    ace_home = adapter.estimate(_ev(home_pitcher="Ace"), None, None)
    bp_home = adapter.estimate(_ev(home_pitcher="Batting Practice"), None, None)
    assert ace_home.home_win_estimated_probability > no_pitchers.home_win_estimated_probability
    assert bp_home.home_win_estimated_probability < no_pitchers.home_win_estimated_probability


def test_baseball_reliability_flags_unknown_starter():
    adapter = get_adapter("mlb", "baseball")
    warn = adapter.reliability_warning(_ev())
    assert warn is not None and "Starter unknown" in warn
    # Basketball has no starter concept: no such flag
    nba = get_adapter("nba", "basketball")
    nba_warn = nba.reliability_warning(Event(event_id="y", sport_key="bt", league="nba",
                                             home="A", away="B", start_time="t"))
    assert nba_warn is None or "Starter" not in nba_warn


def test_starters_store_save_attach_and_refresh(tmp_path):
    store = StartersStore(tmp_path)
    assert store.save("mlb", [{"game_id": "1", "date": "2026-06-01",
                               "home_starter": "Old Name", "away_starter": "B P"}]) == 1
    # Re-ingestion replaces the announcement (newest wins, unlike results)
    store.save("mlb", [{"game_id": "1", "date": "2026-06-01",
                        "home_starter": "Ace", "away_starter": "B P"},
                       {"game_id": "2", "date": "2026-06-02",
                        "home_starter": None, "away_starter": "C D"}])
    results = [{"game_id": "1", "date": "2026-06-01", "home": "A", "away": "B",
                "home_score": 1, "away_score": 0},
               {"game_id": "2", "date": "2026-06-02", "home": "C", "away": "D",
                "home_score": 2, "away_score": 3},
               {"game_id": "999", "date": "2026-06-03", "home": "E", "away": "F",
                "home_score": 4, "away_score": 5}]
    attached = store.attach("mlb", results)
    assert attached == 1  # only game 1 has both starters
    assert results[0]["home_starter"] == "Ace"
    assert results[1]["home_starter"] is None  # missing announcement stays None
    assert "home_starter" not in results[2]  # no map row: untouched
