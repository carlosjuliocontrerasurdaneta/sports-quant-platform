"""Regresiones de la auditoria integral 2026-08-31 / 09-01 (iteracion 4), lote 2.

Cada test nombra el ID del hallazgo que fija. Todos son defectos de METRICA o de
robustez verificados durante la auditoria, no preferencias.
"""
from __future__ import annotations

import math

import pandas as pd
import pytest


# --- N4-M-4: el CLV global y la regla de salida del shadow ignoran no finitos --

def _clv_row(clv_pct: float, beat: bool = True, league: str = "mlb",
             market: str = "h2h") -> dict:
    # `daily_clv` segmenta tambien por `result` (clv.py:233).
    return {"league": league, "market": market, "clv_pct": clv_pct,
            "beat_close": beat, "result": "win"}


def test_finite_clv_drops_nan_and_both_infinities():
    from sqp.audit.clv import finite_clv
    df = pd.DataFrame([_clv_row(0.01), _clv_row(float("nan")),
                       _clv_row(math.inf), _clv_row(-math.inf)])
    assert len(finite_clv(df)) == 1


def test_shadow_exit_rule_is_not_satisfied_by_an_infinite_median(tmp_path,
                                                                monkeypatch):
    """`inf > 0` es True: una sola fila con precio corrupto podia declarar
    cumplida la parte CLV de la regla de salida del shadow mode, que es una
    decision de dinero real (N4-M-4)."""
    from sqp.audit import clv as clv_mod

    # n suficiente para el minimo, pero todas las filas utiles son negativas:
    # sin el filtro, el `inf` arrastra la mediana y la regla "cumple".
    rows = [_clv_row(-0.01) for _ in range(clv_mod.SHADOW_EXIT_MIN_N)]
    rows += [_clv_row(math.inf) for _ in range(clv_mod.SHADOW_EXIT_MIN_N)]
    df = pd.DataFrame(rows)

    monkeypatch.setattr(clv_mod, "compute_clv", lambda bets_dir, root: (df, 0))
    out = clv_mod.daily_clv(bets_dir=tmp_path, root=tmp_path)

    assert out["shadow_clv_ok"] is False
    assert out["median_clv_pct"] == pytest.approx(-0.01)
    assert out["n_non_finite"] == clv_mod.SHADOW_EXIT_MIN_N
    assert out["n_finite"] == clv_mod.SHADOW_EXIT_MIN_N


def test_clv_summary_reports_finite_and_discarded_counts(tmp_path, monkeypatch):
    from sqp.audit import clv as clv_mod
    df = pd.DataFrame([_clv_row(0.02), _clv_row(0.04), _clv_row(float("nan"))])
    monkeypatch.setattr(clv_mod, "compute_clv", lambda bets_dir, root: (df, 7))
    out = clv_mod.daily_clv(bets_dir=tmp_path, root=tmp_path)
    assert out["n_matched"] == 3 and out["n_finite"] == 2
    assert out["n_non_finite"] == 1 and out["n_unmatched"] == 7
    assert out["median_clv_pct"] == pytest.approx(0.03)


# --- N4-M-3: el ROI global debe decir sobre cuantas apuestas se calcula -------

def _settled_row(stake: float, pnl: float, result: str = "win") -> dict:
    return {"league": "mlb", "market": "h2h", "selection": "A", "line": "",
            "event_id": "e", "price_decimal": 2.0, "stake": stake, "pnl": pnl,
            "result": result, "estimated_probability": 0.55,
            "calibrated_probability": 0.55, "implied_probability_novig": 0.5,
            "estimated_edge": 0.1, "generated_at": "2026-08-30T11:00:00+00:00"}


def test_global_roi_block_exposes_n_staked(tmp_path):
    """"ROI realizado" al lado de "1.090 apuestas liquidadas" se leia como si el
    ROI aplicara a las 1.090 cuando corresponde a las 150 con stake (N4-M-3).
    `_segment_audit` ya exponia `n_staked`; el bloque global no."""
    from sqp.audit.report import settlement_audit_report
    bets = tmp_path / "bets"
    bets.mkdir()
    rows = [_settled_row(10.0, 10.0), _settled_row(0.0, 0.0),
            _settled_row(0.0, 0.0, result="loss")]
    pd.DataFrame(rows).to_csv(bets / "settled_mlb.csv", index=False)

    # Devuelve la RUTA del markdown escrito, no el texto.
    from pathlib import Path
    text = Path(settlement_audit_report(bets_dir=bets)).read_text(encoding="utf-8")
    assert "con stake > 0: 1" in text
    assert "no sobre 3" in text
    # El ROI es +100% sobre la unica apuesta con stake, no +33% sobre las tres.
    assert "ROI realizado: 100.00%" in text


# --- N4-B-5: sin stake no hay ROI --------------------------------------------

def test_patterns_hit_rate_does_not_emit_infinite_roi():
    """Con los gates denegando los 39 mercados, stake 0 por grupo es lo normal;
    `pnl / 0` daba `inf` y se renderizaba como la cadena "inf" (N4-B-5)."""
    from sqp.audit.patterns import hit_rate
    df = pd.DataFrame([
        {**_settled_row(0.0, 5.0), "side": "home"},
        {**_settled_row(0.0, 0.0, result="loss"), "side": "home"},
        {**_settled_row(4.0, 4.0), "side": "away"},
    ])
    out = hit_rate(df, ["side"]).set_index("side")
    assert pd.isna(out.loc["home", "roi_%"]), "sin stake el ROI debe ser NaN, no inf"
    assert math.isfinite(out.loc["away", "roi_%"])


# --- N4-M-8: el modo demo falla explicitamente en familias no soportadas ------

def test_synthetic_provider_rejects_tennis_with_an_explicit_error():
    """`tennis` es una familia real del sistema y la rama demo la usaba sin
    guard: salia un `KeyError: 'tennis'` opaco (N4-M-8)."""
    from sqp.exceptions import ProviderNotConfiguredError
    from sqp.providers.synthetic import SyntheticProvider
    with pytest.raises(ProviderNotConfiguredError) as exc:
        SyntheticProvider("tennis")
    assert "tennis" in str(exc.value)


@pytest.mark.parametrize("family", ["baseball", "basketball", "football",
                                    "hockey", "soccer"])
def test_synthetic_provider_still_accepts_every_supported_family(family):
    from sqp.providers.synthetic import SyntheticProvider
    assert SyntheticProvider(family).family == family


# --- N4-M-6: OFFLINE_MODE no puede salir a la red -----------------------------

class _CountingSession:
    def __init__(self):
        self.calls = 0

    def get(self, *a, **kw):
        self.calls += 1
        raise AssertionError("OFFLINE_MODE salio a la red")


def test_offline_mode_blocks_the_uncached_paid_endpoints():
    """El guard vivia dentro de `if cache`, asi que `/scores` (de pago) y
    `/sports` salian a la red igualmente en un run declarado offline (N4-M-6)."""
    from sqp.exceptions import ProviderNotConfiguredError
    from sqp.providers.odds_api import OddsAPIClient

    sess = _CountingSession()
    c = OddsAPIClient("k", "us", session=sess, offline_mode=True)
    with pytest.raises(ProviderNotConfiguredError):
        c.fetch_scores("baseball_mlb", days_from=3)
    with pytest.raises(ProviderNotConfiguredError):
        c.list_sports()
    assert sess.calls == 0


# --- N4-M-7: los proveedores ESPN saltan la ventana, no la liga ---------------

class _BadJSONResponse:
    status_code = 200
    reason = "OK"

    def raise_for_status(self):
        return None

    def json(self):
        raise ValueError("Expecting value: line 1 column 1 (char 0)")


class _StatusResponse:
    def __init__(self, code):
        self.status_code = code
        self.reason = "Too Many Requests"

    def raise_for_status(self):
        raise AssertionError("no deberia llegar aqui para un codigo reintentable")

    def json(self):
        return {}


@pytest.mark.parametrize("response_factory", [
    _BadJSONResponse,
    lambda: _StatusResponse(429),
])
def test_espn_results_skips_the_window_instead_of_killing_the_league(
        monkeypatch, response_factory):
    """El docstring promete saltar la ventana; un cuerpo no-JSON o un 429 subian
    y mataban el backfill entero de la liga, perdiendo tambien las ventanas ya
    descargadas (N4-M-7)."""
    from sqp.providers import espn_results as mod

    monkeypatch.setattr(mod.time, "sleep", lambda s: None)

    class Sess:
        def get(self, *a, **kw):
            return response_factory()

    p = mod.ESPNResultsProvider(session=Sess())
    assert p._fetch({"path": "baseball/mlb"}, "20260801-20260807") == []


def test_espn_retry_status_includes_429_in_both_providers():
    from sqp.providers.espn_results import _RETRY_STATUS as team_status
    from sqp.providers.espn_tennis import _RETRY_STATUS as tennis_status
    assert 429 in team_status and 429 in tennis_status
