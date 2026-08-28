"""Cobertura del run: que ligas se refrescaron hoy y cuales no.

La degradacion era silenciosa. El 2026-08-27 el guardian de presupuesto no pudo
leer la cuota de la API y aplazo **14 ligas**; el tablero no lo decia por ningun
sitio. Desde que las vistas muestran todo lo vigente
(`labels.picks_vigentes`) una liga sin refrescar ya no desaparece, pero su cuota
es vieja: hay que poder verlo de un vistazo, no fila a fila.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from sqp.audit.html_report import _coverage_note


def _dia(n: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=n)).strftime("%Y-%m-%d")


def _servido(tmp_path, liga: str, dia: str, *, partido: str | None = None) -> None:
    pd.DataFrame([{"league": liga, "generated_at": f"{dia}T11:00:00+00:00",
                   "start_time": f"{partido or _dia(1)}T18:00:00Z"}]).to_csv(
        tmp_path / f"served_{liga}.csv", index=False)


def test_avisa_de_las_ligas_sin_refrescar(tmp_path):
    _servido(tmp_path, "mlb", _dia(0))
    _servido(tmp_path, "mls", _dia(-1))
    _servido(tmp_path, "wnba", _dia(-3))
    nota = _coverage_note(tmp_path)
    assert "1 de 3 ligas" in nota
    assert "Sin refrescar (2)" in nota
    assert "mls" in nota and "wnba" in nota
    assert _dia(-3) in nota, "hay que decir de CUANDO son, no solo que son viejas"


def test_todo_al_dia_no_alarma(tmp_path):
    _servido(tmp_path, "mlb", _dia(0))
    _servido(tmp_path, "mls", _dia(0))
    nota = _coverage_note(tmp_path)
    assert "2 de 2 ligas" in nota
    assert "Sin refrescar" not in nota


def test_un_torneo_terminado_no_cuenta_como_sin_refrescar(tmp_path):
    """Un ATP de hace dos semanas no se va a refrescar nunca mas. Listarlo
    convertiria el aviso en ruido permanente, que es como muere un aviso."""
    _servido(tmp_path, "mlb", _dia(0))
    _servido(tmp_path, "tennis_atp_viejo", _dia(-15), partido=_dia(-14))
    nota = _coverage_note(tmp_path)
    assert "1 de 1 ligas" in nota
    assert "tennis_atp_viejo" not in nota


def test_sin_stream_no_inventa_nada(tmp_path):
    assert _coverage_note(tmp_path) == ""


def test_un_csv_corrupto_no_tumba_el_tablero(tmp_path):
    """El tablero debe salir aunque un fichero este roto: es la vista que el
    operador abre cuando algo va mal."""
    _servido(tmp_path, "mlb", _dia(0))
    (tmp_path / "served_roto.csv").write_text("no,es;csv\nvalido", encoding="utf-8")
    assert "1 de" in _coverage_note(tmp_path)
