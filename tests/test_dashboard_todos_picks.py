"""Pestana "Todos los Picks" del dashboard diario.

REGLA FUNDAMENTAL del operador (2026-08-26, SACROSANTA E INAMOVIBLE): "generar
picks para todos los deportes y mercados, priorizando aquellos con las mayores
probabilidades".

Motivo real de estos tests: la lista se estaba generando en ficheros .md que el
operador no abre. El reporte que SI mira es report_latest.html, y ahi no estaba
-- de modo que la regla se cumplia sobre el papel y no en la practica. Un
entregable invisible no es un entregable.
"""
from __future__ import annotations

import pandas as pd

from sqp.audit.html_report import _todos_section, html_dashboard


def _served(tmp_path, rows):
    base = {"league": "mlb", "market": "h2h", "selection": "A", "line": None,
            "price_decimal": 2.0, "estimated_probability": 0.5,
            "implied_probability_novig": 0.5, "estimated_edge": 0.0,
            "books_count": 10, "stake": 0.0, "flags": "served_stream",
            "generated_at": "2026-08-26T11:00:00+00:00"}
    df = pd.DataFrame([{**base, **r} for r in rows])
    (tmp_path / "served_mlb.csv").write_text(df.to_csv(index=False),
                                             encoding="utf-8")
    return tmp_path


class TestTodosLosPicks:
    def test_ordena_por_probabilidad_descendente(self, tmp_path):
        h = _todos_section(_served(tmp_path, [
            {"selection": "BAJA", "estimated_probability": 0.20},
            {"selection": "ALTA", "estimated_probability": 0.90},
        ]))
        assert h.index("ALTA") < h.index("BAJA")

    def test_incluye_lineas_bloqueadas_por_el_gate(self, tmp_path):
        """El nucleo: generar != apostar. Lo que el gate bloquea sigue en la
        lista; el gate quita el stake, nunca la fila."""
        h = _todos_section(_served(tmp_path, [
            {"selection": "BLOQUEADA", "flags": "prediction_gate",
             "estimated_edge": -0.3},
        ]))
        assert "BLOQUEADA" in h

    def test_muestra_breakeven_y_margen(self, tmp_path):
        h = _todos_section(_served(tmp_path, [{"price_decimal": 1.07,
                                               "estimated_probability": 0.90}]))
        assert "Breakeven" in h and "Margen" in h
        assert "0.9346" in h          # 1/1.07
        assert "-0.0346" in h         # 0.90 - 0.9346 -> margen NEGATIVO

    def test_sin_datos_no_revienta(self, tmp_path):
        assert "Sin stream servido" in _todos_section(tmp_path)


class TestEstaEnElDashboard:
    """Sin esto, la seccion podria existir y no estar cableada -- exactamente el
    fallo que motivo estos tests."""

    def test_la_pestana_esta_en_la_navegacion_y_el_panel(self, tmp_path):
        page = html_dashboard(predictions_dir=tmp_path / "pred",
                              bets_dir=tmp_path / "bets", make_latest=False)
        html_txt = (tmp_path / "pred" / __import__("os").path.basename(page)).read_text(
            encoding="utf-8")
        assert 'data-tab="todos"' in html_txt, "falta la pestana en la nav"
        assert 'id="todos"' in html_txt, "falta el panel"

    def test_no_rompe_las_pestanas_existentes(self, tmp_path):
        page = html_dashboard(predictions_dir=tmp_path / "pred",
                              bets_dir=tmp_path / "bets", make_latest=False)
        txt = (tmp_path / "pred" / __import__("os").path.basename(page)).read_text(
            encoding="utf-8")
        for tab in ("picks", "audit", "diagnostics", "patterns", "history"):
            assert f'data-tab="{tab}"' in txt
