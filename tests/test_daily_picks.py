"""REGLA FUNDAMENTAL: generar picks, no apostarlos.

Orden del operador (2026-08-26), declarada SACROSANTA E INAMOVIBLE:

    "No quiero que realice apuestas, sino que genere picks para todos los
     deportes y mercados, priorizando aquellos con las mayores probabilidades."

Estos tests son el candado de esa regla. Fijan las cuatro propiedades que la
componen -- TODOS los deportes, TODOS los mercados, orden por probabilidad
descendente, y cero apuestas -- mas la salvaguarda que impide que el ranking
mienta: junto a cada probabilidad, lo que la CUOTA exige.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "daily_picks", ROOT / "scripts" / "daily_picks.py")
assert _spec and _spec.loader
daily_picks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(daily_picks)


def _served(rows: list[dict]) -> pd.DataFrame:
    base = {"league": "mlb", "market": "h2h", "selection": "A", "line": None,
            "price_decimal": 2.0, "estimated_probability": 0.5,
            "implied_probability_novig": 0.5, "estimated_edge": 0.0,
            "books_count": 10, "stake": 0.0, "flags": "served_stream",
            "generated_at": "2026-08-26T11:00:00+00:00"}
    return pd.DataFrame([{**base, **r} for r in rows])


class TestLaReglaFundamental:
    def test_ordena_por_probabilidad_descendente(self):
        out = daily_picks.rank_picks(_served([
            {"selection": "baja", "estimated_probability": 0.30},
            {"selection": "alta", "estimated_probability": 0.90},
            {"selection": "media", "estimated_probability": 0.60},
        ]))
        assert list(out["seleccion"]) == ["alta", "media", "baja"]
        assert list(out["#"]) == [1, 2, 3]

    def test_incluye_todos_los_mercados(self):
        out = daily_picks.rank_picks(_served([
            {"market": "h2h"}, {"market": "spreads"}, {"market": "totals"},
        ]))
        assert set(out["mercado"]) == {"h2h", "spreads", "totals"}

    def test_incluye_todos_los_deportes(self):
        out = daily_picks.rank_picks(_served([
            {"league": "mlb"}, {"league": "nhl"}, {"league": "wnba"},
            {"league": "epl"}, {"league": "tennis_atp_x"},
        ]))
        assert len(set(out["liga"])) == 5

    def test_no_filtra_por_edge_ni_por_gate(self):
        """El nucleo de la regla: generar != apostar. Una seleccion con edge
        negativo y bloqueada por el gate DEBE aparecer igual en la lista."""
        out = daily_picks.rank_picks(_served([
            {"selection": "bloqueada", "estimated_edge": -0.20,
             "flags": "prediction_gate", "estimated_probability": 0.70},
        ]))
        assert list(out["seleccion"]) == ["bloqueada"]

    def test_la_lista_no_apuesta_nada(self):
        out = daily_picks.rank_picks(_served([{"stake": 0.0}, {"stake": 0.0}]))
        assert not out["estado"].str.startswith("STAKE").any()


class TestSalvaguardaDelBreakeven:
    """Ordenar por probabilidad a secas es `pick_mode: accuracy`, revertido el
    2026-07-31 porque un favorito a cuota 1.07 acierta el 90% y aun asi pierde.
    La lista debe hacer ese hecho VISIBLE, no esconderlo."""

    def test_favorito_extremo_muestra_margen_negativo(self):
        out = daily_picks.rank_picks(_served([
            {"selection": "favoritazo", "estimated_probability": 0.90,
             "price_decimal": 1.07},
        ])).iloc[0]
        assert out["breakeven"] == pytest.approx(0.9346, abs=1e-3)
        assert out["margen"] < 0

    def test_el_primero_del_ranking_puede_tener_margen_negativo(self):
        """Comprobacion de que las dos columnas son independientes: la mas
        probable no es necesariamente la mejor apuesta, y la tabla lo dice."""
        out = daily_picks.rank_picks(_served([
            {"selection": "top", "estimated_probability": 0.88, "price_decimal": 1.05},
            {"selection": "segundo", "estimated_probability": 0.55, "price_decimal": 2.20},
        ]))
        assert out.iloc[0]["seleccion"] == "top"
        assert out.iloc[0]["margen"] < 0
        assert out.iloc[1]["margen"] > 0

    def test_precio_se_reporta_y_no_queda_vacio(self):
        out = daily_picks.rank_picks(_served([{"price_decimal": 1.91}]))
        assert out.iloc[0]["precio"] == pytest.approx(1.91)

    def test_descarta_precios_inutilizables_sin_romper(self):
        out = daily_picks.rank_picks(_served([
            {"selection": "ok", "price_decimal": 2.0},
            {"selection": "degenerada", "price_decimal": 1.0},
        ]))
        assert list(out["seleccion"]) == ["ok"]


class TestFuenteYFiltros:
    def test_la_fuente_es_el_stream_servido_no_los_candidates(self, tmp_path):
        """`candidates_*.csv` solo trae lo que supero min_edge (63 filas frente a
        533 servidas el 2026-08-26). Ranquearlo incumpliria 'todos los mercados'."""
        (tmp_path / "served_mlb.csv").write_text(
            _served([{"selection": "X"}]).to_csv(index=False), encoding="utf-8")
        (tmp_path / "candidates_mlb.csv").write_text(
            _served([{"selection": "NO_DEBE_APARECER"}]).to_csv(index=False),
            encoding="utf-8")
        got = daily_picks.load_served(tmp_path, today_only=False)
        assert list(got["selection"]) == ["X"]

    def test_min_prob_recorta_por_abajo(self):
        out = daily_picks.rank_picks(_served([
            {"estimated_probability": 0.80}, {"estimated_probability": 0.20},
        ]), min_prob=0.5)
        assert len(out) == 1

    def test_filtro_por_mercado(self):
        out = daily_picks.rank_picks(_served([
            {"market": "h2h"}, {"market": "totals"},
        ]), market="totals")
        assert set(out["mercado"]) == {"totals"}

    def test_frame_vacio_no_revienta(self):
        assert daily_picks.rank_picks(pd.DataFrame()).empty


class TestEnganchadoAlFlujoDiario:
    """La regla dice DIARIAMENTE. Un script que nadie invoca no la cumple.

    Motivo real de estos tests: el 2026-08-26 afirme haber enganchado
    `daily_picks.py` a DIARIO_COMPLETO.bat y NO era cierto -- el patron de
    reemplazo no hizo match porque el .bat usa CRLF, y sin `assert` el script
    imprimio "ok" igualmente. La lista habria dejado de generarse sola sin que
    nada lo señalara.
    """

    def _bat(self) -> str:
        return (ROOT / "DIARIO_COMPLETO.bat").read_text(encoding="utf-8",
                                                        errors="replace")

    def test_el_orquestador_diario_invoca_daily_picks(self):
        assert "daily_picks.py" in self._bat(), (
            "DIARIO_COMPLETO.bat no invoca daily_picks.py: la lista dejaria de "
            "generarse a diario y la REGLA FUNDAMENTAL quedaria incumplida")

    def test_genera_las_dos_vistas(self):
        bat = self._bat()
        assert "--top 0" in bat, "falta la vista COMPLETA"
        assert "--min-margin 0" in bat, "falta la vista de margen positivo"

    def test_es_best_effort_y_no_puede_tumbar_el_run(self):
        """Son vistas: un fallo suyo no debe abortar el flujo que ya produjo los
        picks. Se comprueba que no hay `goto :error` colgando de su errorlevel."""
        bat = self._bat()
        for linea in bat.splitlines():
            if "daily_picks.py" in linea:
                continue
            if "daily_picks" in linea and "errorlevel" in linea:
                assert "goto" not in linea.lower(), (
                    f"daily_picks no es best-effort: {linea!r}")

    def test_corre_despues_del_run_no_antes(self):
        """Lee lo que el run escribe. Invocarlo antes daria la lista de ayer."""
        bat = self._bat()
        assert bat.index("RUN_DIARIO_ALL.bat") < bat.index("daily_picks.py")
