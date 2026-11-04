"""AUD-008 (registro de calibracion: lock y lectura fallida) y AUD-020
(complementariedad f(p)+f(1-p)=1 como diagnostico)."""
from __future__ import annotations

import json
import logging

import numpy as np
import pytest

import sqp.calibration.calibrator as cal


@pytest.fixture()
def registro(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path)
    path = tmp_path / "calibration_methods.json"
    original = {"mlb_h2h": "isotonic", "nba_totals": "beta"}
    path.write_text(json.dumps(original), encoding="utf-8")
    return path, original


def test_set_best_method_conserva_entradas_y_anade(registro):
    path, original = registro
    cal._set_best_method("nhl_h2h", "beta")
    assert json.loads(path.read_text(encoding="utf-8")) == {**original, "nhl_h2h": "beta"}


@pytest.mark.parametrize("contenido", [b"[]", b"\xff\xfe\x00bad", b"{not json"])
def test_lectura_fallida_no_reduce_el_registro(registro, contenido):
    path, _ = registro
    path.write_bytes(contenido)
    with pytest.raises((ValueError, UnicodeDecodeError)):
        cal._set_best_method("nhl_h2h", "beta")
    assert path.read_bytes() == contenido        # intacto, no reescrito


def test_oserror_persistente_no_reduce_el_registro(registro, monkeypatch):
    path, _ = registro
    antes = path.read_bytes()

    def falla(*a, **k):
        raise PermissionError("compartido")

    monkeypatch.setattr(cal, "read_json_retrying", falla)
    with pytest.raises(OSError):
        cal._set_best_method("nhl_h2h", "beta")
    assert path.read_bytes() == antes


def test_set_best_method_toma_el_lock(registro, monkeypatch):
    visto = []
    real = cal.locked

    from contextlib import contextmanager

    @contextmanager
    def espia(target, *a, **k):
        visto.append(target.name)
        with real(target, *a, **k):
            yield

    monkeypatch.setattr(cal, "locked", espia)
    cal._set_best_method("nhl_h2h", "beta")
    assert visto == ["calibration_methods.json"]


def test_lector_de_servicio_sigue_degradando_a_vacio(registro):
    path, _ = registro
    path.write_bytes(b"[]")
    assert cal._load_method_registry() == {}
    path.write_bytes(b"\xff\xfe\x00bad")
    assert cal._load_method_registry() == {}


def test_complementarity_gap_distingue_simetrico_de_asimetrico():
    assert cal.complementarity_gap(lambda x: np.asarray(x)) == pytest.approx(0.0)
    assert cal.complementarity_gap(lambda x: np.clip(np.asarray(x) + 0.05, 0, 1)) > 0.04


def test_calibrador_no_complementario_emite_warning_sin_cambiar_veredicto(
        tmp_path, monkeypatch, caplog):
    class Sesgado:
        def predict(self, x):
            return np.clip(np.asarray(x, dtype=float) * 0.9 + 0.08, 0, 1)

    monkeypatch.setattr(cal, "_model_path", lambda *a, **k: tmp_path / "m.pkl")
    (tmp_path / "m.pkl").write_bytes(b"x")
    monkeypatch.setattr(cal, "_load_calibrator", lambda p: Sesgado())
    with caplog.at_level(logging.WARNING):
        defecto = cal.calibrator_defect("x_spreads", "isotonic", staging=False)
    assert defecto == cal.structural_defect(Sesgado().predict)   # veredicto igual
    assert any("no complementario" in r.getMessage() for r in caplog.records)
