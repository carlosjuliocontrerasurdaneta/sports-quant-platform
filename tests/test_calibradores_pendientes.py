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

import numpy as np

from sqp.audit.html_report import _calibration_pending_block


class _Constante:
    """Mapa colapsado. A nivel de modulo porque joblib no serializa clases
    locales de un test."""

    def predict(self, p):
        return np.full(np.shape(p), 0.49)


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


def test_señala_un_calibrador_colapsado_ya_en_produccion(registros, tmp_path):
    """El caso de `wnba_totals` el 2026-08-28: llevaba dias en produccion
    mandando toda probabilidad a 0,490. El pipeline ya lo ignora al aplicar,
    pero el tablero tiene que decir que ESTA ahi."""
    import joblib

    import sqp.calibration.calibrator as cal

    registros({"wnba_totals": "isotonic"}, {})
    joblib.dump(_Constante(), str(cal._model_path("wnba_totals", "iso")))
    cal._load_calibrator.cache_clear()
    html = _calibration_pending_block()
    assert "EN PRODUCCION pero ignorado" in html
    assert "wnba_totals" in html
    # El motivo va al lado: "ignorado" sin decir por que no es accionable.
    assert "colapsado" in html


def test_un_calibrador_vivo_sin_candidato_hoy_no_se_reporta_como_pendiente(registros):
    """Un reentreno puede rechazar a los dos candidatos de una clave; el vivo
    sigue sirviendo y eso no es nada pendiente."""
    registros({"wnba_totals": "isotonic"}, {})
    html = _calibration_pending_block()
    assert "Nada pendiente de promover" in html


# --- El tablero usa el MISMO predicado que el gate y que la promocion ---------
#
# Cuando esta vista tenia su propio umbral, divergieron: el 2026-08-29 el
# candidato de `wnba_totals` estaba RECHAZADO por el gate -- constante en toda la
# banda operativa -- y sin embargo el tablero no lo marcaba, porque solo miraba
# el recorrido ancho, que las colas le compraban.


class _Sano:
    """Encoge pero conserva resolucion: promovible."""

    def predict(self, p):
        return 0.25 + 0.5 * np.asarray(p, dtype=float)


class _PlanoEnLaBanda:
    """Recorrido ancho suficiente, pero constante donde viven los picks."""

    def predict(self, p):
        p = np.asarray(p, dtype=float)
        return np.where(p < 0.20, 0.333, np.where(p > 0.80, 0.545, 0.499))


def test_marca_un_candidato_que_la_promocion_rechazaria(registros, tmp_path):
    import joblib

    import sqp.calibration.calibrator as cal

    registros({}, {"wnba_totals": "isotonic"})
    joblib.dump(_PlanoEnLaBanda(),
                str(cal._model_path("wnba_totals", "iso", staging=True)))
    cal._load_calibrator.cache_clear()

    # Premisa: el gate lo rechaza de verdad.
    assert cal.calibrator_defect("wnba_totals", "isotonic", staging=True) is not None

    html = _calibration_pending_block()
    assert "NO promovibles" in html
    assert "wnba_totals" in html


def test_marca_los_que_esperan_muestra(registros, tmp_path):
    """La vista invitaba a promover candidatos que `promote_calibration.py`
    rechaza en silencio por `n_val_events` corto."""
    import joblib

    import sqp.calibration.calibrator as cal

    registros({}, {"epl_spreads": "isotonic"})
    joblib.dump(_Sano(), str(cal._model_path("epl_spreads", "iso", staging=True)))
    cal._write_staging_meta("epl_spreads", n_val=24, n_val_events=2)
    cal._load_calibrator.cache_clear()

    html = _calibration_pending_block()
    assert "Esperando muestra (1)" in html
    assert "2/30 eventos" in html


def test_sin_metadatos_no_se_declara_espera(registros, tmp_path):
    """Sin fichero de metadatos `promote_calibrators` NO aplica el guard: si
    promoviera, decir 'esperando' seria justo el desajuste que se corrige."""
    import joblib

    import sqp.calibration.calibrator as cal

    registros({}, {"liga_h2h": "isotonic"})
    joblib.dump(_Sano(), str(cal._model_path("liga_h2h", "iso", staging=True)))
    cal._load_calibrator.cache_clear()

    html = _calibration_pending_block()
    assert "Esperando muestra" not in html
