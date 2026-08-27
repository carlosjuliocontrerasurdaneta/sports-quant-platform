"""En `totals` la seleccion es literalmente "Over" o "Under", asi que una fila
sin el partido (`mlb | totals | Over | 8.5`) no dice de QUE encuentro habla
(operador, 2026-08-26). Las cuatro vistas de picks deben nombrarlo, y con el
MISMO formato: "Picks del Dia" ya lo hacia y las otras tres no.
"""
from __future__ import annotations

import pandas as pd
import pytest

from sqp.evaluation.labels import game_date_local, match_label
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


class TestGameDateLocal:
    """`game_date` la escribe el proveedor en UTC. Un WNBA a las 22:00 hora
    local (UTC-4) empieza a las 02:00Z del dia SIGUIENTE, asi que leer esa
    columna en crudo corre el partido un dia."""

    @pytest.fixture
    def nocturno(self) -> pd.DataFrame:
        """Partido de las 22:00 locales: en UTC ya es el dia siguiente."""
        import datetime as _dt

        tz = _dt.datetime.now(_dt.timezone.utc).astimezone().tzinfo
        local = _dt.datetime(2026, 8, 27, 22, 0, tzinfo=tz)
        utc = local.astimezone(_dt.timezone.utc)
        return pd.DataFrame({
            "start_time": [utc.strftime("%Y-%m-%dT%H:%M:%SZ")],
            "game_date": [utc.date().isoformat()],
            "esperado_local": [local.date().isoformat()],
        })

    def test_usa_start_time_y_no_la_columna_game_date(self, nocturno):
        assert (game_date_local(nocturno).iloc[0]
                == nocturno["esperado_local"].iloc[0])

    def test_sin_start_time_cae_a_game_date(self, nocturno):
        d = nocturno.drop(columns=["start_time"])
        assert game_date_local(d).iloc[0] == nocturno["game_date"].iloc[0]

    def test_start_time_ilegible_cae_a_game_date(self, nocturno):
        d = nocturno.assign(start_time=["no-es-una-fecha"])
        assert game_date_local(d).iloc[0] == nocturno["game_date"].iloc[0]

    def test_sin_ninguna_de_las_dos_no_revienta(self, nocturno):
        d = nocturno.drop(columns=["start_time", "game_date"])
        assert game_date_local(d).tolist() == [""]

    def test_el_tipster_no_depende_de_que_el_llamador_convierta(self, nocturno):
        """La regresion concreta: `tipster_table` leia `game_date` en crudo y
        solo salia bien porque `tipster_report.py` se la sobrescribia antes."""
        d = nocturno.assign(
            league="wnba", market="totals", selection="Over", line=167.5,
            price_decimal=1.89, estimated_probability=0.535,
            implied_probability_novig=0.5028, books_count=30,
            home="Phoenix Mercury", away="Washington Mystics", event_id="e1")
        t = tipster_table(d)
        assert t["fecha"].iloc[0] == nocturno["esperado_local"].iloc[0]
        assert t["fecha"].iloc[0] != nocturno["game_date"].iloc[0]


class TestTierNoSeCruzaEntrePartidos:
    """El dashboard reasociaba los tiers por (liga, mercado, seleccion, cuota).
    Esa tupla NO identifica una fila: "wnba | totals | Over | 1.87" describe
    varios partidos, asi que unas filas heredaban el tier de otras. El
    2026-08-27, 541 filas producian 512 claves y 4 tenian tiers en conflicto.
    """

    @pytest.fixture
    def colision(self) -> pd.DataFrame:
        """Dos partidos DISTINTOS con la misma (liga, mercado, seleccion,
        cuota) y clasificacion opuesta: uno con EV positivo y consenso profundo
        (tier A), otro con EV negativo (NO BET)."""
        base = dict(league="mlb", market="totals", selection="Over", line=8.5,
                    price_decimal=1.85, generated_at="2026-08-26T12:00:00Z")
        return pd.DataFrame([
            {**base, "event_id": "e1", "home": "Marlins", "away": "Red Sox",
             "start_time": "2026-08-26T23:05:00Z",
             "estimated_probability": 0.56, "implied_probability_novig": 0.51,
             "books_count": 39},
            {**base, "event_id": "e2", "home": "Giants", "away": "Reds",
             "start_time": "2026-08-26T23:05:00Z",
             "estimated_probability": 0.51, "implied_probability_novig": 0.52,
             "books_count": 35},
        ])

    def test_la_clave_antigua_era_ambigua(self, colision):
        """Documenta POR QUE fallaba: la tupla colisiona por construccion."""
        claves = set(zip(colision.league, colision.market,
                         colision.selection, colision.price_decimal))
        assert len(claves) == 1 and len(colision) == 2

    def test_cada_partido_conserva_su_tier(self, tmp_path, colision):
        from sqp.audit import html_report

        colision.to_csv(tmp_path / "served_mlb.csv", index=False)
        recs = html_report._todos_records(cal_dir=tmp_path)
        tier = {r["partido"]: r["tier"] for r in recs}

        assert tier["Red Sox @ Marlins"] == "A"
        assert tier["Reds @ Giants"] == "NO BET"

    def test_tipster_table_conserva_el_indice_de_entrada(self, colision):
        """La propiedad de la que depende el alineado. Si alguien vuelve a
        meter un `reset_index`, esto lo caza."""
        d = colision.set_index(pd.Index([7, 42]))
        assert sorted(tipster_table(d).index) == [7, 42]
