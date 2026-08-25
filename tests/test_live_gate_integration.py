"""Integracion de la ruta LIVE de gates -- deuda de cobertura del 2026-08-17.

El agujero que cierra: la carga de gates vive bajo ``mode != "demo"`` y el
`and` cortocircuita en demo, asi que **un NameError en la linea que consulta el
gate paso los 1073 tests**. Lo cazo `ruff`, no la suite. Lo mismo aplicaba al
gate de CLV desde julio. Habia un test de resolucion de simbolos como mitigacion;
faltaba el de integracion real, que es este.

No toca red ni artefactos de produccion: `daily.ROOT` se redirige a tmp_path y el
cliente de odds se sustituye por uno sintetico. Si la ruta live dejara de
ejecutarse, estos tests fallarian en vez de pasar en verde por cortocircuito.
"""
from __future__ import annotations

import json

import pandas as pd
import pytest

from sqp.config import Settings
from sqp.pipeline import daily
from sqp.providers.synthetic import SyntheticProvider

LEAGUE = "nba"


class _FakeClient:
    """Sustituto de OddsAPIClient: sin red, misma superficie que usa run_league."""

    # `last_response_cached` lo consulta run_league para no contar como gasto de
    # cuota una respuesta servida desde cache. True = no se gasto credito, que es
    # lo correcto para un doble sin red.
    last_response_cached = True

    def __init__(self, events):
        self._events = events

    def is_sport_active(self, sport_key):      # noqa: ARG002
        return True

    def fetch_odds(self, *a, **k):             # noqa: ARG002
        return self._events

    def fetch_scores(self, *a, **k):           # noqa: ARG002
        return []


@pytest.fixture
def live(tmp_path, monkeypatch):
    """run_league en modo LIVE, aislado: ROOT a tmp_path y proveedor sintetico."""
    sp = SyntheticProvider("basketball")
    results = sp.fetch_results(LEAGUE)
    events = sp.fetch_odds(LEAGUE, three_way=False)

    monkeypatch.setattr(daily, "ROOT", tmp_path)
    monkeypatch.setattr(daily, "OddsAPIClient",
                        lambda *a, **k: _FakeClient(events))
    monkeypatch.setattr(daily, "_fetch_recent_scores", lambda *a, **k: [])

    class _RS:
        def __init__(self, root):
            pass

        def load(self, league):                # noqa: ARG002
            return results

    monkeypatch.setattr(daily, "ResultsStore", _RS)
    (tmp_path / "data" / "bets").mkdir(parents=True)
    return tmp_path


def _settings(**over):
    s = Settings.load()
    s.pick_mode = "edge"
    s.shadow_mode = False          # aislar los gates: shadow los tapa a todos
    s.clv_gate_enabled = False     # el rector desde 2026-08-16 es el de prediccion
    s.prediction_gate_enabled = True
    # El cap de plausibilidad (flag `suspect`) tiene PRECEDENCIA sobre shadow y
    # sobre los gates en la cadena de stake-0, asi que con datos sinteticos tapa
    # la capa que estos tests miden. Se relaja para AISLAR el gate; el cap tiene
    # sus propios tests y no es lo que se prueba aqui.
    s.risk.max_plausible_edge = 10.0
    for k, v in over.items():
        setattr(s, k, v)
    return s


def _write_gate(root, allowed: bool):
    (root / "data" / "bets" / "prediction_gate.json").write_text(json.dumps({
        "generated_at": "2026-08-25T00:00:00+00:00",
        "markets": {f"{LEAGUE}|{m}": {"allowed": allowed, "n": 400,
                                      "p_value": 0.01, "ev_flat": 0.03,
                                      "wins": 220, "reason": "ok"}
                    for m in ("h2h", "spreads", "totals")},
    }), encoding="utf-8")


def _candidates(root):
    p = root / "data" / "predictions" / f"candidates_{LEAGUE}.csv"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p)
    # Sin ninguna bandera la columna llega como float (todo NaN) y `.str` revienta.
    # Normalizar a texto es parte del contrato que se quiere afirmar.
    df["flags"] = df["flags"].fillna("").astype(str)
    return df


def test_live_branch_actually_executes(live):
    """Regresion directa del fallo de 2026-08-17: si la rama live no corriera,
    no se escribiria nada en el directorio de produccion de tmp_path."""
    daily.run_league(LEAGUE, _settings(), mode="live")
    out = live / "data" / "predictions"
    assert out.exists(), "la rama live no llego a escribir: no se ejecuto"
    # Y NO en el subdirectorio demo: live y demo no pueden confundirse.
    assert not (out / "demo").exists()


def test_missing_registry_is_default_deny_not_fail_open(live):
    """Sin registro, {} debe tratarse como deny, jamas como 'todo permitido'."""
    # registro deliberadamente ausente: no se escribe prediction_gate.json
    daily.run_league(LEAGUE, _settings(), mode="live")
    df = _candidates(live)
    assert not df.empty
    assert (df["stake"] == 0).all()
    assert df["flags"].str.contains("prediction_gate").all()


def test_denied_market_gets_zero_stake_and_the_gate_flag(live):
    _write_gate(live, allowed=False)
    daily.run_league(LEAGUE, _settings(), mode="live")
    df = _candidates(live)
    assert not df.empty
    assert (df["stake"] == 0).all()
    assert df["flags"].str.contains("prediction_gate").all()


def test_allowed_market_can_carry_stake(live):
    """Contraprueba imprescindible: si el gate negara SIEMPRE, los tres tests de
    arriba pasarian igual y no probarian nada."""
    _write_gate(live, allowed=True)
    daily.run_league(LEAGUE, _settings(), mode="live")
    df = _candidates(live)
    assert not df.empty
    assert (df["stake"] > 0).any(), "ningun candidato con stake: el gate no abre"
    assert not df["flags"].str.contains("prediction_gate").all()


def test_shadow_mode_outranks_an_open_gate(live):
    """Shadow es global y tiene precedencia sobre los gates por mercado."""
    _write_gate(live, allowed=True)
    daily.run_league(LEAGUE, _settings(shadow_mode=True), mode="live")
    df = _candidates(live)
    assert not df.empty
    assert (df["stake"] == 0).all()
    assert df["flags"].str.contains("shadow_mode").all()


def test_disabled_gate_does_not_block(live):
    """prediction_gate_enabled=False => None => la capa no opina (no deny)."""
    daily.run_league(LEAGUE, _settings(prediction_gate_enabled=False), mode="live")
    df = _candidates(live)
    assert not df.empty
    assert not df["flags"].str.contains("prediction_gate").any()
