"""AUD-004 (fallos silenciosos -> rc=0) y AUD-008 (tope diario por coste previsto).

Sin red ni cuota real: clientes y modulos falsos.
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from sqp.exceptions import LockNoAdquiridoError
from sqp.pipeline import closing_capture
from sqp.pipeline.closing_capture import capture_closing

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "capture_closing_odds.py"
NOW = datetime(2026, 6, 26, 22, 0, tzinfo=timezone.utc)


def _seed(pred_dir: Path, league: str, eid: str) -> None:
    pd.DataFrame([{"event_id": eid}]).to_csv(pred_dir / f"candidates_{league}.csv", index=False)
    pd.DataFrame([{"event_id": eid, "start_time": "2026-06-26T23:00:00Z"}]).to_csv(
        pred_dir / f"predictions_{league}.csv", index=False)


class _Client:
    def __init__(self, cost=3, regions="us", raises: Exception | None = None):
        self.requests_last = cost
        self.requests_remaining = 5000
        self.regions = regions
        self.raises = raises
        self.calls: list[str] = []

    def fetch_odds(self, league_id, sport_key, markets="h2h,spreads,totals"):
        self.calls.append(league_id)
        if self.raises:
            raise self.raises
        return []


class _Store:
    def append_snapshot(self, league, events):
        return len(events)


@pytest.fixture
def two_leagues(tmp_path, monkeypatch):
    monkeypatch.setattr(closing_capture, "ROOT", tmp_path)
    _seed(tmp_path, "mlb", "e1")
    _seed(tmp_path, "wnba", "w1")
    return tmp_path


def _http401() -> Exception:
    import requests
    resp = requests.Response()
    resp.status_code = 401
    return requests.HTTPError("401 Unauthorized", response=resp)


def test_todas_las_ligas_fallan_queda_en_el_resumen(two_leagues):
    out = capture_closing(two_leagues, settings=None, now=NOW,
                          client=_Client(raises=_http401()), odds_store=_Store())
    assert sorted(out["failed_leagues"]) == ["mlb", "wnba"]
    assert closing_capture.all_leagues_failed(out)


def test_fallo_parcial_no_es_fallo_total(two_leagues):
    class _C(_Client):
        def fetch_odds(self, league_id, sport_key, markets="h2h"):
            if league_id == "mlb":
                raise RuntimeError("boom")
            return super().fetch_odds(league_id, sport_key, markets)
    out = capture_closing(two_leagues, settings=None, now=NOW, client=_C(), odds_store=_Store())
    assert list(out["failed_leagues"]) == ["mlb"]
    assert not closing_capture.all_leagues_failed(out)


def test_exito_sin_fallos(two_leagues):
    out = capture_closing(two_leagues, settings=None, now=NOW, client=_Client(), odds_store=_Store())
    assert out["failed_leagues"] == {}
    assert not closing_capture.all_leagues_failed(out)


def test_aud008_no_pide_si_gasto_mas_coste_previsto_rebasa_el_tope(two_leagues):
    odds_dir = two_leagues / "data" / "odds"
    odds_dir.mkdir(parents=True)
    (odds_dir / ".closing_credits_20260626").write_text("299")
    client = _Client(cost=3, regions="us")  # 3 mercados x 1 region = 3 -> 302 > 300
    out = capture_closing(two_leagues, settings=None, max_credits=300, now=NOW,
                          client=client, odds_store=_Store())
    assert client.calls == []
    assert sorted(out["skipped_budget"]) == ["mlb", "wnba"]
    assert out["failed_leagues"] == {}


def test_aud008_con_saldo_suficiente_si_pide(two_leagues):
    odds_dir = two_leagues / "data" / "odds"
    odds_dir.mkdir(parents=True)
    (odds_dir / ".closing_credits_20260626").write_text("297")  # 297+3 == 300 permitido
    client = _Client(cost=3, regions="us")
    out = capture_closing(two_leagues, settings=None, max_credits=300, now=NOW,
                          client=client, odds_store=_Store())
    assert client.calls == ["mlb"]            # la segunda ya no cabe (300+3 > 300)
    assert out["skipped_budget"] == ["wnba"]
    assert out["credits_spent"] == 3


# ---------------------------------------------------------------- script / rc
def _summary(**kw):
    base = {"captured": {}, "bet_events": {}, "skipped_budget": [], "credits_spent": 0,
            "leagues_considered": [], "attempted": [], "failed_leagues": {}}
    base.update(kw)
    return base


@pytest.fixture
def script(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("capture_closing_odds_under_test", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr("sys.argv", ["capture_closing_odds.py"])
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    settings = SimpleNamespace(revalidation_enabled=True, intraday_scan_enabled=True,
                               revalidation_window_min=60,
                               revalidation_price_max_age_min=30,
                               risk=SimpleNamespace(min_edge=0.03))
    monkeypatch.setattr(mod.Settings, "load", staticmethod(lambda: settings))
    monkeypatch.setattr(mod, "capture_closing", lambda *a, **k: _summary())
    calls = {"reval": 0, "intraday": 0}

    def reval(*a, **k):
        calls["reval"] += 1
        return {"evaluated": 0, "kept": 0, "revoked": 0, "skipped_no_price": 0}

    def intraday(*a, **k):
        calls["intraday"] += 1
        return {"scanned": 0, "would_generate": 0, "leagues": []}

    monkeypatch.setattr("sqp.pipeline.revalidation.revalidate_candidates", reval)
    monkeypatch.setattr("sqp.pipeline.intraday_scan.log_intraday_edges", intraday)
    return SimpleNamespace(mod=mod, calls=calls, root=tmp_path, mp=monkeypatch)


def test_script_exito_normal_rc0(script):
    assert script.mod.main() == 0
    assert script.calls == {"reval": 1, "intraday": 1}


def test_script_todas_las_ligas_fallidas_rc1(script):
    script.mp.setattr(script.mod, "capture_closing", lambda *a, **k: _summary(
        attempted=["mlb"], failed_leagues={"mlb": "HTTPError: 401"}))
    assert script.mod.main() == 1
    assert script.calls == {"reval": 1, "intraday": 1}   # los pasos siguientes corren


def test_script_fallo_parcial_de_ligas_rc1_y_siguen_los_pasos(script):
    # Seguimiento de AUD-004: la liga fallida no tiene snapshot de cierre, asi que
    # el fallo debe llegar al centinela; las demas etapas corren igual.
    script.mp.setattr(script.mod, "capture_closing", lambda *a, **k: _summary(
        attempted=["mlb", "nba"], failed_leagues={"mlb": "boom"}))
    assert script.mod.main() == 1
    assert script.calls == {"reval": 1, "intraday": 1}


@pytest.mark.parametrize("exc", [RuntimeError("boom"), LockNoAdquiridoError("lock")])
def test_script_revalidacion_lanza_rc1_y_siguen_los_pasos(script, exc):
    def boom(*a, **k):
        raise exc
    script.mp.setattr("sqp.pipeline.revalidation.revalidate_candidates", boom)
    assert script.mod.main() == 1
    assert script.calls["intraday"] == 1


def test_script_guard_de_abridores_lanza_rc1_y_sigue_intradia(script):
    pred = script.root / "data" / "predictions"
    pred.mkdir(parents=True)
    pd.DataFrame([{"event_id": "e1"}]).to_csv(pred / "candidates_mlb.csv", index=False)
    script.mp.setattr("sqp.pipeline.daily._league_meta",
                      lambda lg: {"family": "baseball", "league_params": None})
    script.mp.setattr("sqp.providers.mlb_statsapi.MLBStatsProvider", lambda: object())

    def boom(*a, **k):
        raise RuntimeError("adapter roto")
    script.mp.setattr("sqp.sports.registry.get_adapter", boom)
    assert script.mod.main() == 1
    assert script.calls["intraday"] == 1


def test_script_intradia_best_effort_no_cambia_rc(script):
    def boom(*a, **k):
        raise RuntimeError("scan roto")
    script.mp.setattr("sqp.pipeline.intraday_scan.log_intraday_edges", boom)
    assert script.mod.main() == 0
