"""En `totals` la seleccion es literalmente "Over" o "Under", asi que una fila
sin el partido (`mlb | totals | Over | 8.5`) no dice de QUE encuentro habla
(operador, 2026-08-26). Las cuatro vistas de picks deben nombrarlo, y con el
MISMO formato: "Picks del Dia" ya lo hacia y las otras tres no.
"""
from __future__ import annotations

import pandas as pd
import pytest

from sqp.evaluation.labels import match_label
from sqp.evaluation.tipster import tipster_table


@pytest.fixture
def served() -> pd.DataFrame:
    """Dos caras de un totals: sin el partido son indistinguibles del resto."""
    return pd.DataFrame({
        "league": ["mlb", "mlb"],
        "event_id": ["evt-1", "evt-1"],
        "home": ["New York Yankees", "New York Yankees"],
        "away": ["Boston Red Sox", "Boston Red Sox"],
        "game_date": ["2026-08-26", "2026-08-26"],
        "start_time": ["2026-08-26T23:05:00Z", "2026-08-26T23:05:00Z"],
        "market": ["totals", "totals"],
        "selection": ["Over", "Under"],
        "line": [8.5, 8.5],
        "price_decimal": [1.90, 1.90],
        "estimated_probability": [0.55, 0.45],
        "implied_probability_novig": [0.51, 0.49],
        "books_count": [30, 30],
        "stake": [0.0, 0.0],
        "flags": ["", ""],
    })


class TestMatchLabel:
    def test_formato_visitante_arroba_local(self, served):
        assert match_label(served).tolist() == ["Boston Red Sox @ New York Yankees"] * 2

    def test_sin_home_away_cae_a_event_id(self, served):
        """Un identificador feo identifica el partido; una celda vacia no."""
        d = served.drop(columns=["home", "away"])
        assert match_label(d).tolist() == ["evt-1", "evt-1"]

    def test_sin_home_away_ni_event_id_no_revienta(self, served):
        d = served.drop(columns=["home", "away", "event_id"])
        assert match_label(d).tolist() == ["", ""]

    def test_nulos_no_producen_la_cadena_nan(self, served):
        served.loc[0, "away"] = None
        assert "nan" not in match_label(served).iloc[0]


class TestLasVistasNombranElPartido:
    def test_tabla_del_tipster(self, served):
        t = tipster_table(served)
        assert "partido" in t.columns
        assert set(t["partido"]) == {"Boston Red Sox @ New York Yankees"}

    def test_dashboard_todos_los_picks(self, tmp_path, served, monkeypatch):
        from sqp.audit import html_report

        served.assign(generated_at="2026-08-26T12:00:00Z").to_csv(
            tmp_path / "served_mlb.csv", index=False)
        recs = html_report._todos_records(cal_dir=tmp_path)

        assert recs, "la vista no devolvio filas"
        assert all(r["partido"] == "Boston Red Sox @ New York Yankees" for r in recs)

    def test_la_columna_esta_declarada_en_la_tabla_html(self):
        """Que el dato exista no basta: si no esta en T_COLS no se pinta."""
        import inspect

        from sqp.audit import html_report

        assert '["partido","Partido","txt"]' in inspect.getsource(html_report)
        assert ("partido", "Partido", "txt") in html_report._PICK_COLUMNS

    def test_daily_picks_md(self, tmp_path, served):
        import sys
        sys.path.insert(0, "scripts")
        import daily_picks

        assert "partido" in daily_picks.COLS
        out = daily_picks.rank_picks(served)
        assert not out.empty, "rank_picks no devolvio filas"
        assert set(out["partido"]) == {"Boston Red Sox @ New York Yankees"}
