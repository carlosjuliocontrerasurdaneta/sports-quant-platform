"""_select_live league-activity detection.

A transient /sports status-check error must NOT silently drop a league from the
daily run (this is what excluded MLB on 2026-06-23). _select_live should mirror
run_league and assume active on error, while a SUCCESSFUL check returning
False/None still excludes the league (out of season / unknown key).
"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

_RUN_ALL = Path(__file__).resolve().parents[1] / "scripts" / "run_all.py"


def _load_run_all():
    spec = importlib.util.spec_from_file_location("run_all_under_test", _RUN_ALL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


run_all = _load_run_all()
_SETTINGS = SimpleNamespace(odds_api_key="k", regions="us", odds_format="decimal")


class _FakeClient:
    """Plenty of quota; no dynamic tennis tournaments. Subclasses override
    is_sport_active to drive the scenario under test."""
    requests_remaining = 1_000_000

    def __init__(self, *args, **kwargs):
        pass

    def list_sports(self, all_sports=True):
        return []


def test_select_live_assumes_active_on_status_check_error(monkeypatch):
    class _Client(_FakeClient):
        def is_sport_active(self, sport_key):
            if sport_key == "baseball_mlb":
                raise RuntimeError("transient /sports failure")
            return True

    monkeypatch.setattr(run_all, "OddsAPIClient", _Client)
    supported = {"mlb": "baseball_mlb", "wnba": "basketball_wnba"}

    selected, active = run_all._select_live(_SETTINGS, supported, None)

    assert "mlb" in active           # error -> assumed active, not dropped
    assert "wnba" in active
    assert "mlb" in selected         # priority #1 -> selected within budget


def test_select_live_excludes_inactive_and_unknown(monkeypatch):
    class _Client(_FakeClient):
        def is_sport_active(self, sport_key):
            return {"baseball_mlb": False,      # out of season
                    "soccer_x": None,            # unknown key (typo)
                    "basketball_wnba": True}.get(sport_key)

    monkeypatch.setattr(run_all, "OddsAPIClient", _Client)
    supported = {"mlb": "baseball_mlb", "sx": "soccer_x", "wnba": "basketball_wnba"}

    _, active = run_all._select_live(_SETTINGS, supported, None)

    assert "mlb" not in active        # successful False -> excluded
    assert "sx" not in active         # successful None -> excluded
    assert "wnba" in active
