"""AUD-002 (ronda audit-2026-09-18): un registro JSON sintacticamente valido
cuya raiz NO es un objeto (`[]`, `null`, `1`, `"x"`) debe degradar a `{}`
(default-deny / sin auto-pausas), nunca lanzar.

Antes, `load_prediction_gate` y `load_degradation_registry` hacian
`json.loads(...).get("markets")` dentro de un `try` que solo capturaba
`OSError` y `JSONDecodeError`: una raiz lista levantaba `AttributeError`.
En el gate eso abortaba `run_league` de TODAS las ligas (dia sin picks); en el
monitor de degradacion el `except` de `run_all.py` volvia a llamar al lector
FUERA de cualquier proteccion y abortaba el run entero antes de la primera
liga. `clv.load_clv_gate` ya comprobaba la raiz: es el patron que se adopta.
"""
from __future__ import annotations

import json

import pytest

from sqp.risk.clv_gate import load_clv_gate
from sqp.risk.degradation import (DEGRADATION_FILENAME, load_degradation_registry,
                                  paused_from_registry)
from sqp.risk.prediction_gate import (PREDICTION_GATE_FILENAME,
                                      load_prediction_gate, market_allowed)

RAICES_NO_OBJETO = ["[]", "null", "1", '"x"', '[{"markets": {}}]', "true"]


@pytest.mark.parametrize("raw", RAICES_NO_OBJETO)
def test_prediction_gate_root_not_object_denies_without_raising(tmp_path, raw):
    (tmp_path / PREDICTION_GATE_FILENAME).write_text(raw, encoding="utf-8")
    gate = load_prediction_gate(tmp_path)
    assert gate == {}
    assert market_allowed(gate, "mlb", "h2h") is False


@pytest.mark.parametrize("raw", RAICES_NO_OBJETO)
def test_degradation_registry_root_not_object_means_no_auto_pauses(tmp_path, raw):
    (tmp_path / DEGRADATION_FILENAME).write_text(raw, encoding="utf-8")
    reg = load_degradation_registry(tmp_path)
    assert reg == {}
    assert paused_from_registry(reg) == {}


@pytest.mark.parametrize("raw", RAICES_NO_OBJETO)
def test_clv_gate_root_not_object_denies(tmp_path, raw):
    # Ya era correcto; se fija para que los tres lectores no puedan divergir.
    (tmp_path / "clv_gate.json").write_text(raw, encoding="utf-8")
    assert load_clv_gate(tmp_path) == {}


def test_markets_not_dict_denies(tmp_path):
    for name, loader in ((PREDICTION_GATE_FILENAME, load_prediction_gate),
                         (DEGRADATION_FILENAME, load_degradation_registry)):
        (tmp_path / name).write_text(json.dumps({"markets": [1, 2]}), encoding="utf-8")
        assert loader(tmp_path) == {}


def test_valid_object_registry_unchanged(tmp_path):
    payload = {"markets": {"mlb|h2h": {"allowed": True, "latched": False}}}
    (tmp_path / PREDICTION_GATE_FILENAME).write_text(json.dumps(payload), encoding="utf-8")
    assert market_allowed(load_prediction_gate(tmp_path), "mlb", "h2h") is True
    (tmp_path / DEGRADATION_FILENAME).write_text(
        json.dumps({"markets": {"mlb|totals": {"paused": True}}}), encoding="utf-8")
    assert paused_from_registry(load_degradation_registry(tmp_path)) == {"mlb": ["totals"]}


def test_run_all_degradation_fallback_survives_bad_registry(tmp_path, monkeypatch):
    """El bloque de fallback de `run_all.py` (monitor fallido -> auto-pausas
    del registro persistido) no puede volver a lanzar por un registro con
    raiz no objeto. Se ejercita el helper que run_all usa para ese fallback."""
    from sqp.risk.degradation import auto_pauses_from_persisted_registry
    (tmp_path / DEGRADATION_FILENAME).write_text("[]", encoding="utf-8")
    assert auto_pauses_from_persisted_registry(tmp_path) == {}
