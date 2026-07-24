"""_grade must compare selection vs home by normalized identity, not raw string.

The settlement winner match (tennis_scores_map) already keys on normalize_key,
but _grade compared `selection == home` raw. When a selection was written in a
different spelling than the home name (accents, casing), a HOME-side bet whose
player actually won was silently graded `loss` -- the asymmetric failure spotted
in the 2026-06-28 WTA Wimbledon review (home bets break, away bets don't)."""
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


def test_h2h_two_way_tie_is_push():
    # Auditoria 2026-07-24 (M-9): en h2h 2-way los books devuelven el stake en
    # un empate (NFL ~1-2/ano); gradarlo "loss" sesgaba calibracion y ROI.
    assert _grade(_row("h2h", "Buffalo Bills"), 20, 20, "Buffalo Bills") == "push"
    assert _grade(_row("h2h", "Detroit Lions"), 20, 20, "Buffalo Bills") == "push"


def test_h2h_three_way_tie_team_loses_draw_wins():
    # En 1X2 el empate SI se cotiza: la seleccion de equipo pierde, Draw gana.
    assert _grade(_row("h2h", "Arsenal"), 1, 1, "Arsenal", three_way=True) == "loss"
    assert _grade(_row("h2h", "Chelsea"), 1, 1, "Arsenal", three_way=True) == "loss"
    assert _grade(_row("h2h", "Draw"), 1, 1, "Arsenal", three_way=True) == "win"
