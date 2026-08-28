"""Calibradores aceptados que esperan en staging.

El reentreno diario NO promueve: escribe candidatos a `data/models/staging/` y
la promocion es un paso manual deliberado, para que un ajuste degenerado no se
instale solo. Correcto -- pero el aviso vivia en una linea de log entre miles.

No es cosmetica: sin entrada en el registro LIVE, `method='auto'` es un no-op y
ese mercado se sirve SIN CALIBRAR. La calibracion cierra el 72% de la brecha de
Brier contra el mercado (medicion del 2026-08-25), asi que cada clave pendiente
es rendimiento medido que no se usa. El 2026-08-28: 4 calibradores vivos y 6
mercados en crudo con candidato aceptado esperando.
"""
from __future__ import annotations

import json

import pytest

from sqp.audit.html_report import _calibration_pending_block


@pytest.fixture
def registros(tmp_path, monkeypatch):
    """Redirige los dos registros a un directorio temporal."""
    import sqp.calibration.calibrator as cal
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path)
    (tmp_path / "staging").mkdir()

    def escribir(live: dict, staged: dict) -> None:
        (tmp_path / "calibration_methods.json").write_text(
            json.dumps(live), encoding="utf-8")
        (tmp_path / "staging" / "calibration_methods.json").write_text(
            json.dumps(staged), encoding="utf-8")

    return escribir


def test_señala_los_mercados_servidos_sin_calibrar(registros):
    registros({"mlb_totals": "isotonic"},
              {"mlb_totals": "isotonic", "epl_spreads": "beta",
               "wnba_spreads": "beta"})
    html = _calibration_pending_block()
    assert "Servidos SIN calibrar" in html
    assert ">2<" in html, "epl_spreads y wnba_spreads no tienen calibrador vivo"
    assert "epl_spreads" in html and "wnba_spreads" in html
    assert "promote_calibration.py" in html


def test_señala_un_cambio_de_metodo(registros):
    """`mlb_spreads` paso de beta a isotonic en un reentreno: cambiar el mapa de
    produccion no es lo mismo que estrenar uno, y hay que verlo aparte."""
    registros({"mlb_spreads": "beta"}, {"mlb_spreads": "isotonic"})
    html = _calibration_pending_block()
    assert "Cambiarian de metodo" in html
    assert "beta" in html and "isotonic" in html


def test_sin_nada_pendiente_lo_dice(registros):
    registros({"mlb_totals": "isotonic"}, {"mlb_totals": "isotonic"})
    html = _calibration_pending_block()
    assert "Nada pendiente de promover" in html


def test_un_calibrador_vivo_sin_candidato_hoy_no_se_reporta_como_pendiente(registros):
    """Un reentreno puede rechazar a los dos candidatos de una clave; el vivo
    sigue sirviendo y eso no es nada pendiente."""
    registros({"wnba_totals": "isotonic"}, {})
    html = _calibration_pending_block()
    assert "Nada pendiente de promover" in html
