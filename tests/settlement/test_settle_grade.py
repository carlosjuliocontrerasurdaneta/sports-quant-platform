"""_grade must compare selection vs home by normalized identity, not raw string.

The settlement winner match (tennis_scores_map) already keys on normalize_key,
but _grade compared `selection == home` raw. When a selection was written in a
different spelling than the home name (accents, casing), a HOME-side bet whose
player actually won was silently graded `loss` -- the asymmetric failure spotted
in the 2026-06-28 WTA Wimbledon review (home bets break, away bets don't)."""
import pandas as pd
import pytest

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


@pytest.mark.parametrize("line", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("market,selection", [
    ("totals", "Over"), ("totals", "Under"),
    ("spreads", "Iga Swiatek"), ("spreads", "Rival"),
])
def test_non_finite_line_is_void_not_a_fabricated_result(market, selection, line):
    """Una linea no finita NO puede producir un resultado.

    Antes las comparaciones con NaN caian por el `else` y FABRICABAN el
    resultado sin mirar el marcador (auditoria 2026-08-05, F-03, reproducido):
    totals/Under -> win SIEMPRE, totals/Over -> loss SIEMPRE, spreads -> loss
    SIEMPRE. Un `win` fabricado es peor que una fila perdida: entra en el ROI
    realizado y en las etiquetas de calibracion como evidencia valida.

    `void` y no `push`: push afirma que la apuesta existio y se devolvio el
    stake; void afirma que no se pudo graduar, que es lo cierto."""
    row = _row(market, selection, line=line)
    assert _grade(row, 5, 4, "Iga Swiatek") == "void"


def test_non_finite_line_is_void_regardless_of_score():
    # El defecto original era justo este: el resultado no dependia del marcador.
    for hs, as_ in [(5, 4), (4, 5), (0, 0), (12, 1)]:
        assert _grade(_row("totals", "Under"), hs, as_, "A") == "void"
        assert _grade(_row("totals", "Over"), hs, as_, "A") == "void"


def test_finite_line_still_grades_normally():
    # Premisa: el guard no puede tragarse el camino normal.
    assert _grade(_row("totals", "Under", line=8.5), 5, 4, "A") == "loss"   # total 9
    assert _grade(_row("totals", "Over", line=8.5), 5, 4, "A") == "win"
    assert _grade(_row("totals", "Over", line=9.0), 5, 4, "A") == "push"


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


# --- Seleccion que no casa con NINGUNO de los dos equipos ---------------------
#
# `sel_is_home` False significaba "es el visitante", asi que una seleccion que no
# era ninguno de los dos se graduaba con el resultado del visitante: una apuesta
# al LOCAL escrita de otra forma salia "loss" con el local ganando (reproducido
# en la auditoria del 2026-08-28, AUD-LOW-001). Un resultado fabricado entra en
# el ROI realizado y en las etiquetas de calibracion como evidencia valida.


def _row2(market, selection, line=0.0, away="New York Yankees"):
    return pd.Series({"market": market, "selection": selection, "line": line,
                      "away": away})


def test_h2h_selection_matching_neither_side_is_void():
    # Local "Boston Red Sox" gana 5-3; la seleccion no casa con ninguno.
    assert _grade(_row2("h2h", "Red Sox"), 5, 3, "Boston Red Sox") == "void"
    assert _grade(_row2("h2h", "EQUIPO INEXISTENTE"), 5, 3, "Boston Red Sox") == "void"


def test_spreads_selection_matching_neither_side_is_void():
    assert _grade(_row2("spreads", "Red Sox", -1.5), 5, 3, "Boston Red Sox") == "void"


def test_both_real_sides_still_grade_normally():
    """Premisa: el guard no puede tragarse el camino normal."""
    assert _grade(_row2("h2h", "Boston Red Sox"), 5, 3, "Boston Red Sox") == "win"
    assert _grade(_row2("h2h", "New York Yankees"), 5, 3, "Boston Red Sox") == "loss"
    assert _grade(_row2("spreads", "Boston Red Sox", -1.5), 5, 3, "Boston Red Sox") == "win"


def test_totals_is_not_side_dependent_and_is_untouched():
    """En totals la seleccion es Over/Under: no casa con ningun equipo NUNCA."""
    assert _grade(_row2("totals", "Over", 7.5), 5, 3, "Boston Red Sox") == "win"
    assert _grade(_row2("totals", "Under", 7.5), 5, 3, "Boston Red Sox") == "loss"


def test_three_way_draw_is_not_voided():
    """El empate cotizado no es ninguno de los dos equipos, y es legitimo."""
    row = pd.Series({"market": "h2h", "selection": "Draw", "line": 0.0,
                     "away": "Chelsea"})
    assert _grade(row, 1, 1, "Arsenal", three_way=True) == "win"


def test_a_row_without_away_keeps_the_previous_behaviour():
    """Sin la columna no se puede verificar la correspondencia, y no se inventa:
    un esquema legado sigue graduando como antes."""
    row = pd.Series({"market": "h2h", "selection": "Red Sox", "line": 0.0})
    assert _grade(row, 5, 3, "Boston Red Sox") == "loss"
