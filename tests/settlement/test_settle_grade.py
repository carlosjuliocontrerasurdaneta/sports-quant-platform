"""_grade must compare selection vs home by normalized identity, not raw string.

When a selection was written in a different spelling than the home name
(accents, casing), a HOME-side bet whose side actually won was silently graded
`loss` -- an asymmetric failure (home bets break, away bets don't) spotted in
the 2026-06-28 settlement review."""
import pandas as pd

from sqp.settlement.settle import _grade


def _row(market, selection, line=float("nan")):
    return pd.Series({"market": market, "selection": selection, "line": line})


def test_h2h_home_winner_graded_win_despite_accent_spelling():
    # home "Iga Swiatek" won (1-0); selection carries the accented spelling.
    row = _row("h2h", "Iga Świątek")
    assert _grade(row, 1, 0, "Iga Swiatek") == "win"


def test_h2h_home_winner_graded_win_despite_casing():
    row = _row("h2h", "naomi OSAKA")
    assert _grade(row, 1, 0, "Naomi Osaka") == "win"


def test_h2h_away_selection_grades_by_outcome():
    # away path never used the home string, so it already worked -- guard it.
    row = _row("h2h", "Harriet Dart")
    assert _grade(row, 0, 1, "Jelena Ostapenko") == "win"   # away won
    assert _grade(row, 1, 0, "Jelena Ostapenko") == "loss"  # home won


def test_distinct_players_not_merged_by_normalization():
    # Guard: normalization must not collapse two different identities.
    row = _row("h2h", "Karolina Muchova")  # away, lost; home won 1-0
    assert _grade(row, 1, 0, "Karolina Pliskova") == "loss"


def test_spreads_home_normalized_match():
    # home covers (won by 2, line -1.5) -> win, despite accented selection.
    row = _row("spreads", "Iga Świątek", line=-1.5)
    assert _grade(row, 6, 4, "Iga Swiatek") == "win"
