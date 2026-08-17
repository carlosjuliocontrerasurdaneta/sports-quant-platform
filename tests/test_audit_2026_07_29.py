"""Regresiones de la auditoria integral 2026-07-29.

Un test por hallazgo corregido. Cada uno falla contra el codigo anterior:
  B-01  reportes invisibles por comparacion exacta de `flags`
  B-05  cuota degenerada (<=1.0) produciendo pick de precision
  B-06  banca negativa produciendo stake negativo
  B-08  fail-open de shadow_mode ante un valor de entorno no reconocido
  B-13  cuota degenerada corrompiendo el consenso no-vig
  D-01  re-ingesta de abridores sobrescribiendo nombres buenos con nulos
  D-06  contador de creditos heredando el costo de la llamada anterior
  Q-01  modo precision sin calibrador h2h promovido (aviso, no supresion)
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pandas as pd
import pytest

from sqp.audit.report import has_flag, rank_candidates
from sqp.config import Settings, _env_flag
from sqp.domain.models import Event, EventOdds, MarketLine
from sqp.pipeline.cleanup import _actionable
from sqp.pipeline.daily import _accuracy_selected, _warn_if_uncalibrated_accuracy
from sqp.pipeline.probabilities import _consensus_lines, _novig_probs


# --- B-01: visibilidad de picks en los reportes -------------------------------

def _cands(flags: list[str]) -> pd.DataFrame:
    return pd.DataFrame({
        "selection": [f"S{i}" for i in range(len(flags))],
        "stake": [0.0] * len(flags),
        "estimated_edge": [0.01] * len(flags),
        "flags": flags,
    })


def test_b01_accuracy_mode_picks_stay_visible_in_reports():
    """`shadow_mode;accuracy_mode` es el flag real de produccion desde 2026-07-28."""
    df = _cands(["shadow_mode;accuracy_mode"])
    assert len(rank_candidates(df)) == 1


def test_b01_blocking_flags_still_hidden():
    df = _cands(["market_paused", "shadow_mode;accuracy_mode", "clv_gate"])
    visible = rank_candidates(df)
    assert list(visible["flags"]) == ["shadow_mode;accuracy_mode"]


def test_b01_has_flag_matches_tokens_not_substrings():
    s = pd.Series(["shadow_mode;accuracy_mode", "not_shadow_mode", "", None])
    assert list(has_flag(s, "shadow_mode")) == [True, False, False, False]


def test_b01_cleanup_actionable_ignores_informational_flags():
    """`accuracy_mode` no es un motivo de bloqueo: con stake real el pick sigue
    siendo liquidable, y darlo por no-accionable permitiria purgar su archivo."""
    df = pd.DataFrame({"stake": [10.0, 10.0, 10.0],
                       "flags": ["accuracy_mode", "", "market_paused"]})
    assert len(_actionable(df)) == 2


# --- B-05 / B-13: cuotas degeneradas ------------------------------------------

def test_b05_accuracy_rejects_degenerate_price():
    """price_decimal <= 1.0 no paga nada; el stake plano no pasa por Kelly, que
    era el unico filtro de cuotas degeneradas del pipeline."""
    assert _accuracy_selected("h2h", 0.9, 0.70, False, 1.0) is False
    assert _accuracy_selected("h2h", 0.9, 0.70, False, 0.5) is False
    assert _accuracy_selected("h2h", 0.9, 0.70, False, 1.05) is True


def test_b05_accuracy_still_requires_h2h_threshold_and_complete_market():
    assert _accuracy_selected("totals", 0.9, 0.70, False, 2.0) is False
    assert _accuracy_selected("h2h", 0.9, 0.70, True, 2.0) is False
    assert _accuracy_selected("h2h", 0.69, 0.70, False, 2.0) is False
    assert _accuracy_selected("h2h", 0.70, 0.70, False, 2.0) is True


def _eo(prices: list[tuple[str, float]]) -> EventOdds:
    ev = Event(event_id="e1", sport_key="baseball_mlb", league="mlb",
               home="Home", away="Away", start_time="2026-07-29T18:00:00Z")
    lines = [MarketLine(market="h2h", outcome=o, point=None, price_decimal=p,
                        bookmaker=f"bk{i}")
             for i, (o, p) in enumerate(prices)]
    return EventOdds(event=ev, lines=lines)


def test_b13_consensus_drops_degenerate_quotes():
    cons = _consensus_lines(_eo([("Home", 1.0), ("Home", 1.90), ("Away", 2.10)]))
    assert cons[("h2h", "Home", None)] == pytest.approx(1.90)


def test_b13_degenerate_quote_does_not_fabricate_certainty():
    """Con la cuota 1.0 incluida, 1/1.0 = 1.0 es una probabilidad implicita de
    CERTEZA y remove_vig_power normalizaba el mercado entero a su alrededor."""
    fair = _novig_probs(_consensus_lines(_eo([("Home", 1.0), ("Away", 2.10)])),
                        "h2h")
    assert fair == {}  # mercado incompleto tras descartar la cuota corrupta


# --- B-06: banca negativa -----------------------------------------------------

def test_b06_negative_bankroll_never_produces_negative_stake():
    """settle.py grada una perdida como pnl = -stake: un stake negativo
    convertiria una perdida en ganancia."""
    from sqp.risk.kelly import kelly_fraction_stake
    stake, pct = kelly_fraction_stake(0.9, 2.0, -500.0, 0.25, 0.02, 0.02)
    assert stake == 0.0 and pct == 0.0
    # el stake plano del modo precision se calcula fuera de Kelly
    assert round(max(0.0, -500.0) * 0.02, 2) == 0.0


# --- B-08: fail-open de shadow_mode ------------------------------------------

@pytest.mark.parametrize("raw", ["", "on", "off", "  true  ", "si", "nope"])
def test_b08_env_flag_never_silently_disables_yaml(raw):
    """Un valor no reconocido debe ser indistinguible de "no configurado" para
    que la configuracion yaml mantenga el control."""
    with patch.dict(os.environ, {"SHADOW_MODE": raw}, clear=False):
        got = _env_flag("SHADOW_MODE")
        assert got in (True, False, None)
        if raw.strip().lower() not in ("1", "true", "yes", "on", "0", "false", "no", "off"):
            assert got is None, f"{raw!r} deberia ceder el control al yaml"


def test_b08_env_flag_recognized_values():
    for raw, expected in (("1", True), ("true", True), ("YES", True), ("on", True),
                          ("0", False), ("false", False), ("no", False), ("off", False)):
        with patch.dict(os.environ, {"SHADOW_MODE": raw}, clear=False):
            assert _env_flag("SHADOW_MODE") is expected


def test_b08_unset_returns_none():
    env = {k: v for k, v in os.environ.items() if k != "SHADOW_MODE"}
    with patch.dict(os.environ, env, clear=True):
        assert _env_flag("SHADOW_MODE") is None


def test_production_yaml_never_leaves_capital_unguarded():
    """Produccion NUNCA puede quedarse sin barrera de capital.

    Antes esta comprobacion vivia dentro del test de B-08 como un
    `pytest.skip`: si default.yaml dejaba de declarar `shadow_mode: true`, la
    prueba se saltaba a si misma. Es decir, el unico control que existia contra
    la desactivacion se apagaba EXACTAMENTE en el estado que debia vigilar, y
    la suite seguia verde (auditoria 2026-08-05, F-04).

    Hasta el 2026-08-16 el candado exigia `shadow_mode: true`. El operador
    levanto el shadow ese dia por decision explicita (registrada en
    Obsidian/Decisiones y en la bitacora), y la suite se rompio exactamente como
    este test fue disenado para romperse: la desactivacion no se colo en un
    diff.

    Lo que el candado protege NO es un flag concreto -- la politica cambia y los
    flags con ella -- sino el invariante: **siempre debe quedar al menos una
    barrera activa entre un pick y el dinero**. Hoy hay tres candidatas, todas
    default-deny: shadow global, el gate de prediccion (regla rectora desde
    2026-08-16) y el de CLV (la regla anterior, ya solo evidencia). Apagarlas
    TODAS deja la banca expuesta a cada candidato que supere `min_edge`, y eso
    no puede colarse en un diff."""
    from sqp.config import CONFIG_DIR, load_yaml
    cfg = load_yaml(CONFIG_DIR / "default.yaml")
    barreras = {
        "shadow_mode": cfg.get("shadow_mode") is True,
        "prediction_gate": bool((cfg.get("prediction_gate") or {}).get("enabled")),
        "clv_gate": bool((cfg.get("clv_gate") or {}).get("enabled")),
    }
    assert any(barreras.values()), (
        "configs/default.yaml deja el capital SIN NINGUNA barrera "
        f"({barreras}). Con esa combinacion todo candidato por encima de "
        "min_edge lleva stake real sin haber demostrado nada. Si es "
        "deliberado, registralo en Obsidian/Decisiones y actualiza este test; "
        "si no, es una regresion de control de riesgo.")


def test_b08_production_yaml_shadow_survives_unrecognized_env():
    """Un SHADOW_MODE no reconocido NO puede alterar lo que declara el yaml.

    Se compara contra el valor DECLARADO en default.yaml, no contra un literal:
    lo que se vigila es que un env basura sea ignorado, sea cual sea la politica
    vigente. Antes fijaba `is True` y por tanto media dos cosas a la vez (la
    politica y la precedencia env/yaml).

    `"on"` estaba en esta lista como ejemplo de valor NO reconocido, pero si lo
    es: vive en `_TRUE` (config.py:23). El caso pasaba por coincidencia mientras
    el yaml declaraba `true` -- ambos lados daban True y nadie los distinguia.
    Al levantar el shadow el 2026-08-16 quedo a la vista. Los valores realmente
    no reconocidos son los de abajo."""
    from sqp.config import CONFIG_DIR, load_yaml
    declarado = load_yaml(CONFIG_DIR / "default.yaml").get("shadow_mode") is True
    for raw in ("", "  ", "si", "verdadero"):
        with patch.dict(os.environ, {"SHADOW_MODE": raw}, clear=False):
            assert Settings.load().shadow_mode is declarado, (
                f"SHADOW_MODE={raw!r} altero el shadow mode declarado en el yaml")


# --- Q-01: modo precision sin calibrador -------------------------------------

def test_q01_warns_when_accuracy_mode_has_no_h2h_calibrator(caplog):
    s = Settings()
    s.pick_mode, s.accuracy_threshold, s.calibration_enabled = "accuracy", 0.70, True
    with patch("sqp.calibration.calibrator._load_method_registry", return_value={}):
        with caplog.at_level("WARNING"):
            missing = _warn_if_uncalibrated_accuracy("mlb", s)
    assert missing is True
    assert "NO calibrada" in caplog.text


def test_q01_silent_when_calibrator_is_promoted(caplog):
    s = Settings()
    s.pick_mode, s.accuracy_threshold, s.calibration_enabled = "accuracy", 0.70, True
    with patch("sqp.calibration.calibrator._load_method_registry",
               return_value={"mlb_h2h": "isotonic"}):
        with caplog.at_level("WARNING"):
            missing = _warn_if_uncalibrated_accuracy("mlb", s)
    assert missing is False
    assert caplog.text == ""


# --- D-01: re-ingesta de abridores -------------------------------------------

def test_d01_null_starters_do_not_overwrite_stored_names(tmp_path):
    """`fetch_starters` emite una fila por juego programado aunque la API no
    hidrate probablePitcher; con keep="last" la re-corrida borraba el nombre."""
    from sqp.storage.starters import StartersStore
    st = StartersStore(tmp_path)
    st.save("mlb", [{"game_id": "1", "date": "2026-07-29",
                     "home_starter": "Ace A", "away_starter": "Ace B"}])
    st.save("mlb", [{"game_id": "1", "date": "2026-07-29",
                     "home_starter": None, "away_starter": None}])
    rows = [{"game_id": "1"}]
    assert st.attach("mlb", rows) == 1
    assert rows[0]["home_starter"] == "Ace A"
    assert rows[0]["away_starter"] == "Ace B"


def test_d01_partial_update_still_applies(tmp_path):
    """Una fila con al menos un abridor SI es informativa y debe entrar."""
    from sqp.storage.starters import StartersStore
    st = StartersStore(tmp_path)
    st.save("mlb", [{"game_id": "1", "date": "2026-07-29",
                     "home_starter": "Old", "away_starter": "B"}])
    st.save("mlb", [{"game_id": "1", "date": "2026-07-29",
                     "home_starter": "New", "away_starter": None}])
    rows = [{"game_id": "1"}]
    st.attach("mlb", rows)
    assert rows[0]["home_starter"] == "New"


def test_d01_all_null_batch_keeps_store_intact(tmp_path):
    from sqp.storage.starters import StartersStore
    st = StartersStore(tmp_path)
    st.save("mlb", [{"game_id": "1", "date": "2026-07-29",
                     "home_starter": "A", "away_starter": "B"}])
    assert st.save("mlb", [{"game_id": "2", "date": "2026-07-30",
                            "home_starter": None, "away_starter": None}]) == 1


# --- D-06: contador de creditos ----------------------------------------------

def test_d06_requests_last_is_reset_between_calls():
    """Sin reset, una respuesta sin headers de cuota heredaba el costo de la
    llamada anterior y closing_capture lo volvia a sumar al contador diario."""
    from sqp.providers.odds_api import OddsAPIClient

    class _Resp:
        status_code = 200

        def __init__(self, headers):
            self.headers = headers

        def raise_for_status(self):
            return None

        def json(self):
            return []

    class _Session:
        def __init__(self, seq):
            self.seq = list(seq)

        def get(self, *a, **k):
            return _Resp(self.seq.pop(0))

    c = OddsAPIClient(api_key="k")
    c.session = _Session([{"x-requests-last": "10"}, {}])
    c._get("/a")
    assert c.requests_last == 10
    c._get("/b")
    assert c.requests_last is None, "el costo de la llamada previa se heredo"


def test_q01_warns_when_calibration_disabled(caplog):
    s = Settings()
    s.pick_mode, s.accuracy_threshold, s.calibration_enabled = "accuracy", 0.70, False
    with caplog.at_level("WARNING"):
        assert _warn_if_uncalibrated_accuracy("mlb", s) is True
    assert "calibration_enabled=false" in caplog.text
