"""AUD-005: ventanas fallidas del proveedor de tenis no habilitan anulaciones."""
from __future__ import annotations

from sqp.settlement import runner
from sqp.settlement.runner import _settle_tennis

from .test_settle_tennis_e2e import (
    LEAGUE, _graded_rows, _results, _write_inputs, _write_served)


class _FakeFailed:
    """Proveedor con payload sano pero una ventana fallida."""
    def __init__(self, results, failed):
        self.results = results
        self.failed_windows = failed

    def fetch_results(self, league, days_back=5):
        return self.results


def test_ventana_fallida_no_anula_candidatos_por_expiracion(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _write_inputs(tmp_path, with_stale=True)
    settled = _settle_tennis(
        LEAGUE, days_from=2, provider=_FakeFailed(_results(), ["atp 20260101: 503"]))
    ids = set(settled["event_id"]) if not settled.empty else set()
    assert "e4" not in ids  # e4 (5 dias, sin resultado) NO se anula
    assert {"e1", "e2"} <= ids  # lo que si tiene resultado se liquida


def test_ventana_fallida_no_anula_filas_servidas(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _write_inputs(tmp_path)
    _write_served(tmp_path)
    _settle_tennis(
        LEAGUE, days_from=2, provider=_FakeFailed(_results(), ["atp 20260101: 503"]))
    assert _graded_rows(tmp_path).empty


def test_sin_ventanas_fallidas_las_anulaciones_siguen(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _write_inputs(tmp_path, with_stale=True)
    _write_served(tmp_path)
    settled = _settle_tennis(LEAGUE, days_from=2, provider=_FakeFailed(_results(), []))
    e4 = settled.set_index("event_id").loc["e4"]
    assert e4["result"] == "void" and "stale_void" in str(e4["flags"])
