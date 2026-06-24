"""Generic Elo engine: expectation, zero-sum updates, home advantage, name
normalization and reliability gate. Deterministic (no RNG)."""
import math

from sqp.models.elo import EloRatings


def test_unknown_team_returns_base():
    elo = EloRatings(base=1500.0)
    assert elo.get("Nobody") == 1500.0


def test_expected_home_win_symmetry_and_home_advantage():
    elo = EloRatings(home_advantage=60.0)
    # Equal ratings on a NEUTRAL court -> coin flip.
    assert elo.expected_home_win("A", "B", neutral=True) == 0.5
    # Home advantage tilts it above 0.5 on a non-neutral court.
    assert elo.expected_home_win("A", "B") > 0.5
    # Probability is bounded in (0, 1).
    p = elo.expected_home_win("A", "B")
    assert 0.0 < p < 1.0


def test_higher_rating_is_favored():
    elo = EloRatings(home_advantage=0.0)
    elo.ratings = {"Strong": 1700.0, "Weak": 1400.0}
    assert elo.expected_home_win("Strong", "Weak", neutral=True) > 0.5
    assert elo.expected_home_win("Weak", "Strong", neutral=True) < 0.5


def test_update_is_zero_sum_and_directional():
    elo = EloRatings(k=20.0, home_advantage=0.0)
    before_home, before_away = elo.get("H"), elo.get("A")
    elo.update("H", "A", home_score=3, away_score=1)  # home wins
    gain = elo.get("H") - before_home
    loss = before_away - elo.get("A")
    assert gain > 0                       # winner gains
    assert math.isclose(gain, loss)       # zero-sum: loser loses the same
    assert elo.games_played["H"] == elo.games_played["A"] == 1


def test_expected_matches_realized_after_balanced_history():
    # Two evenly-matched teams splitting results stay near the base rating.
    elo = EloRatings(k=20.0, home_advantage=0.0)
    for i in range(20):
        if i % 2 == 0:
            elo.update("X", "Y", 2, 1, neutral=True)
        else:
            elo.update("X", "Y", 1, 2, neutral=True)
    assert abs(elo.expected_home_win("X", "Y", neutral=True) - 0.5) < 0.05


def test_normalize_binds_name_variants():
    elo = EloRatings(home_advantage=0.0, normalize=lambda s: s.strip().lower())
    elo.update("Lakers", "Suns", 110, 100, neutral=True)
    # A different surface form of the same team resolves to the same rating.
    assert elo.get("  lakers ") == elo.get("Lakers")
    assert elo.get("Lakers") > 1500.0     # they won, so above base


def test_is_reliable_threshold():
    elo = EloRatings(home_advantage=0.0)
    for _ in range(9):
        elo.update("T", "U", 1, 0, neutral=True)
    assert elo.is_reliable("T", min_games=10) is False
    elo.update("T", "U", 1, 0, neutral=True)
    assert elo.is_reliable("T", min_games=10) is True
